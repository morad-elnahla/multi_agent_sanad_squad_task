"""Exercise live-adapter accounting without spending tokens or requiring a key."""
import asyncio
import pytest
from langchain_core.messages import AIMessage
from pipeline.models import TopicChoice
from pipeline.providers import LiveProvider

class FakeModel:
    def __init__(self, parsed=True, fail=False):
        self.parsed, self.fail = parsed, fail
    def with_structured_output(self, schema, method, include_raw):
        assert method=='json_schema' and include_raw
        return self
    async def ainvoke(self, messages):
        assert len(messages)==2
        if self.fail:
            raise TimeoutError('secret must not appear in the ledger')
        return {'raw': AIMessage(content='', usage_metadata={
            'input_tokens':100,'output_tokens':20,'total_tokens':120}),
            'parsed': TopicChoice(kb_id='reentrancy',reason='match') if self.parsed else None,
            'parsing_error': None if self.parsed else ValueError('bad schema')}

@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-placeholder-not-a-real-key')
    monkeypatch.setenv('INPUT_USD_PER_MILLION','1')
    monkeypatch.setenv('OUTPUT_USD_PER_MILLION','2')
    monkeypatch.setattr('pipeline.providers.ChatOpenAI', lambda **kwargs: FakeModel())
    value=LiveProvider()
    value.llm=FakeModel()
    return value

def invoke(provider):
    return asyncio.run(provider.generate('research','instructions',{},TopicChoice,'a'))

def test_actual_usage_and_configured_rates(provider):
    assert invoke(provider).kb_id=='reentrancy'
    call=provider.calls[0]
    assert call['input_tokens']==100 and call['output_tokens']==20
    assert call['cost_usd']==pytest.approx(.00014)

def test_parsing_failure_still_records_usage(provider):
    provider.llm=FakeModel(parsed=False)
    with pytest.raises(RuntimeError): invoke(provider)
    assert provider.calls[0]['input_tokens']==100
    assert provider.calls[0]['status']=='error'

def test_transport_failure_is_unknown_and_redacted(provider):
    provider.llm=FakeModel(fail=True)
    with pytest.raises(RuntimeError,match='TimeoutError'): invoke(provider)
    assert provider.calls[0]['cost_usd'] is None
    assert 'secret' not in str(provider.calls)

def test_missing_key_fails_before_network(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(ValueError,match='OPENAI_API_KEY'): LiveProvider()
