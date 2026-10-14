import asyncio
from types import SimpleNamespace
import pytest
from pipeline.rate_limits import TokenGate, retry_after_seconds
from pipeline.providers import LiveProvider, ProviderFailure
from pipeline.models import TopicChoice
from test_provider import FakeModel


class Clock:
    def __init__(self):
        self.now = 0
        self.waits = []
    def time(self):
        return self.now
    async def sleep(self, delay):
        self.waits.append(delay)
        self.now += delay
        await asyncio.sleep(0)


class OpenAIRateLimitError(Exception):
    status_code = 429
    code = 'rate_limit_exceeded'
    def __init__(self, headers=None):
        self.response = SimpleNamespace(headers=headers or {})


class FlakyModel(FakeModel):
    def __init__(self, failures, headers=None):
        super().__init__()
        self.failures = failures
        self.headers = headers
        self.invocations = 0
    async def ainvoke(self, messages):
        self.invocations += 1
        if self.invocations <= self.failures:
            raise OpenAIRateLimitError(self.headers)
        return await super().ainvoke(messages)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'placeholder')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.groq.com/openai/v1')
    monkeypatch.setattr('pipeline.providers.ChatOpenAI', lambda **kw: FakeModel())
    monkeypatch.setattr('pipeline.providers.random.uniform', lambda *_: .5)
    value = LiveProvider()
    clock = Clock()
    value.gate = TokenGate(7500, clock=clock.time, sleep=clock.sleep)
    return value, clock


def invoke(provider):
    return asyncio.run(provider.generate('research', 'instructions', {}, TopicChoice, 'a'))


def test_429_retried_and_every_attempt_logged(live):
    provider, clock = live
    provider.llm = FlakyModel(1, {'retry-after': '4'})
    assert invoke(provider).kb_id == 'reentrancy'
    assert provider.llm.invocations == 2
    assert clock.waits == [4.5]
    assert [r['transport_attempt'] for r in provider.calls] == [1, 2]
    assert provider.calls[0]['status'] == 'rate_limited'
    assert provider.calls[0]['input_tokens'] is None
    assert provider.calls[1]['status'] == 'ok'


def test_missing_header_uses_backoff(live):
    provider, clock = live
    provider.llm = FlakyModel(2)
    invoke(provider)
    assert clock.waits == [61.5, 122.5]


def test_retry_budget_is_bounded(live):
    provider, clock = live
    provider.retries = 2
    provider.llm = FlakyModel(9, {'retry-after': '1'})
    with pytest.raises(ProviderFailure, match='retries exhausted'):
        invoke(provider)
    assert len(provider.calls) == 3
    assert len(clock.waits) == 2


def test_long_provider_reset_is_not_retried_early(live):
    provider, clock = live
    provider.llm = FlakyModel(1, {'retry-after': '86400'})
    with pytest.raises(ProviderFailure, match='wait limit'):
        invoke(provider)
    assert clock.waits == [] and provider.llm.invocations == 1


def test_insufficient_quota_is_not_retried(live):
    provider, clock = live
    class QuotaModel(FakeModel):
        async def ainvoke(self, messages):
            error = OpenAIRateLimitError()
            error.code = 'insufficient_quota'
            raise error
    provider.llm = QuotaModel()
    with pytest.raises(ProviderFailure, match='quota unavailable'):
        invoke(provider)
    assert clock.waits == [] and len(provider.calls) == 1


def test_shared_gate_waits_for_budget_expiry():
    clock = Clock()
    gate = TokenGate(7500, clock=clock.time, sleep=clock.sleep)
    async def work():
        async with gate.request(4000, 'writer'):
            gate.record(5000)
        async with gate.request(4000, 'reviewer'):
            assert clock.now >= 61
            gate.record(3000)
    asyncio.run(work())
    assert clock.waits == [61]


def test_budgeted_calls_cannot_race():
    gate = TokenGate(7500)
    active = 0
    peak = 0
    async def work():
        nonlocal active, peak
        async with gate.request(100, 'a'):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            gate.record(100)
            active -= 1
    async def group():
        await asyncio.gather(work(), work(), work())
    asyncio.run(group())
    assert peak == 1


@pytest.mark.parametrize('header,expected', [('2', 2), ('-1', 0), ('invalid', None), ('nan', None), ('inf', None)])
def test_retry_header_parsing(header, expected):
    assert retry_after_seconds({'retry-after': header}) == expected


def test_groq_default_budget(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'placeholder')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.groq.com/openai/v1')
    monkeypatch.delenv('LLM_TOKENS_PER_MINUTE', raising=False)
    monkeypatch.setattr('pipeline.providers.ChatOpenAI', lambda **kw: FakeModel())
    assert LiveProvider().gate.budget == 7500
