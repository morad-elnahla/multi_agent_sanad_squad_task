"""Live LangChain adapter with independently budgeted transport retries."""
import json
import math
import os
import random
import time
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from .rate_limits import TokenGate, retry_after_seconds


class ProviderFailure(RuntimeError):
    """Contains only an internally generated, safe diagnostic message."""


def setting(name, default, minimum=0, integer=False, values=None):
    raw = (os.environ if values is None else values).get(name)
    value = float(default if raw is None or raw == '' else raw)
    if not math.isfinite(value) or value < minimum or (integer and not value.is_integer()):
        raise ValueError(f'Invalid setting: {name}')
    return int(value) if integer else value


class LiveProvider:
    mode = 'live'

    def __init__(self, options=None, progress=None):
        values = dict(os.environ)
        values.update(options or {})
        self._values = values
        self.progress = progress or (lambda event: None)
        get = values.get
        number = lambda name, default, minimum=0, integer=False: setting(name, default, minimum, integer, values)
        if not get('OPENAI_API_KEY'):
            raise ValueError('OPENAI_API_KEY is required for live mode; use --mode demo for offline fixtures')
        self.model = get('LLM_MODEL', 'gpt-4.1-mini')
        is_groq = urlparse(get('OPENAI_BASE_URL', '')).hostname == 'api.groq.com'
        self.output_limit = number('LLM_MAX_COMPLETION_TOKENS', 4096, 256, integer=True)
        self.retries = number('LLM_RATE_LIMIT_RETRIES', 3, integer=True)
        self.max_wait = number('LLM_MAX_RETRY_WAIT_SECONDS', 300, 1)
        self.base_wait = number('LLM_RETRY_BASE_SECONDS', 61, 1)
        self.gate = TokenGate(number('LLM_TOKENS_PER_MINUTE', 7500 if is_groq else 0, integer=True))
        kwargs = {'model': self.model, 'timeout': 60, 'max_retries': 0,
                  'max_completion_tokens': self.output_limit,
                  'api_key': get('OPENAI_API_KEY'),
                  'base_url': get('OPENAI_BASE_URL') or 'https://api.openai.com/v1'}
        effort = get('LLM_REASONING_EFFORT')
        if effort:
            kwargs['reasoning_effort'] = effort
        self.gate.notify = self.progress
        self.llm = ChatOpenAI(**kwargs)
        self.calls = []
        self.rates = [self._rate('INPUT_USD_PER_MILLION'), self._rate('OUTPUT_USD_PER_MILLION')]

    def _rate(self, name):
        if self._values.get(name) in (None, ''):
            return None
        return setting(name, 0, values=self._values)

    def settings_snapshot(self):
        return {'tokens_per_minute': self.gate.budget,
                'max_completion_tokens': self.output_limit,
                'rate_limit_retries': self.retries,
                'max_retry_wait_seconds': self.max_wait,
                'retry_base_seconds': self.base_wait}

    async def generate(self, role, prompt, payload, schema, slot):
        text = json.dumps(payload, ensure_ascii=False)
        # Approximate English/JSON input + schema overhead, then reserve the
        # configured maximum completion. Server limits remain authoritative.
        input_bytes = len((prompt + text + json.dumps(schema.model_json_schema())).encode('utf-8'))
        reservation = math.ceil(input_bytes / 3) + 256 + self.output_limit
        messages = [SystemMessage(content=prompt), HumanMessage(content=text)]
        agent = f"writer:{payload['post_type']['name']}" if role == 'writer' else role
        request_id = f'{slot}:{agent}:{len(self.calls) + 1}'
        runnable = self.llm.with_structured_output(schema, method='json_schema', include_raw=True)
        for attempt in range(1, self.retries + 2):
            record = {'slot': slot, 'role': role, 'agent': agent, 'model': self.model,
                      'request_id': request_id, 'transport_attempt': attempt,
                      'input_tokens': None, 'output_tokens': None, 'cost_usd': None}
            async with self.gate.request(reservation, f'{slot}/{agent}') as waited:
                record['budget_wait_seconds'] = round(waited, 3)
                start = time.monotonic()
                try:
                    result = await runnable.ainvoke(messages)
                    usage = result['raw'].usage_metadata or {}
                    record['input_tokens'] = usage.get('input_tokens')
                    record['output_tokens'] = usage.get('output_tokens')
                    recorded = [record['input_tokens'], record['output_tokens']]
                    self.gate.record(sum(recorded) if all(v is not None for v in recorded) else reservation)
                    if all(v is not None for v in [*self.rates, *recorded]):
                        record['cost_usd'] = (recorded[0] * self.rates[0] + recorded[1] * self.rates[1]) / 1_000_000
                    if result['parsing_error'] or result['parsed'] is None:
                        raise ValueError('Structured model response could not be parsed')
                    record['status'] = 'ok'
                    return result['parsed']
                except Exception as exc:
                    record['status'] = 'error'
                    record['error_type'] = type(exc).__name__
                    status = getattr(exc, 'status_code', None)
                    record['http_status'] = status if isinstance(status, int) else None
                    # Both SDK and LangChain-normalized rate-limit exceptions
                    # are supported without storing raw exception text or bodies.
                    limited = status == 429 or 'ratelimit' in type(exc).__name__.lower()
                    response = getattr(exc, 'response', None)
                    headers = getattr(response, 'headers', {}) or {}
                    code = getattr(exc, 'code', None)
                    permanent = code in ('insufficient_quota', 'billing_hard_limit_reached')
                    if limited and not permanent:
                        suggested = retry_after_seconds(headers)
                        delay = (suggested if suggested is not None else self.base_wait * 2 ** (attempt - 1)) + random.uniform(.1, 1)
                        record['retry_after_seconds'] = round(delay, 3)
                        if attempt <= self.retries and delay <= self.max_wait:
                            record['status'] = 'rate_limited'
                            record['will_retry'] = True
                            self.gate.cooldown(delay)
                            print(f'[{slot}/{agent}] Rate limit: retry {attempt}/{self.retries} after at least {delay:.1f}s.', flush=True)
                            self.progress({'event': 'retry', 'slot': slot, 'agent': agent,
                                           'seconds': round(delay, 1), 'attempt': attempt})
                            continue
                        record['will_retry'] = False
                        reason = 'provider reset exceeds configured wait limit' if delay > self.max_wait else 'rate-limit retries exhausted'
                    elif permanent:
                        reason = 'provider quota unavailable; check account quota'
                    else:
                        reason = type(exc).__name__
                    raise ProviderFailure(f'{role} provider failure: {reason}') from None
                finally:
                    record['latency_seconds'] = round(time.monotonic() - start, 3)
                    self.calls.append(record)
