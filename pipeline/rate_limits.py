"""One shared budget for all agents using a free-tier provider in this process."""
import asyncio
import math
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def retry_after_seconds(headers):
    """HTTP Retry-After supports either seconds or an HTTP date."""
    value = headers.get('retry-after') or headers.get('Retry-After')
    if value is None:
        return None
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            seconds = (target - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


class TokenGate:
    """Serialize budgeted API calls and reuse measured token usage after each call.

    Reservations are estimates, not a guarantee of a provider's token counting.
    Counting from completion time and keeping a 61-second window is conservative.
    Unbudgeted providers retain concurrency. A server cooldown is shared by all
    agents, including when local token budgeting is disabled.
    """
    def __init__(self, budget=0, window=61.0, clock=time.monotonic, sleep=asyncio.sleep):
        self.budget = budget
        self.window = window
        self.clock = clock
        self.sleep = sleep
        self.history = deque()
        self.lock = asyncio.Lock()
        self.blocked_until = 0.0
        self.notify = lambda event: None

    def cooldown(self, seconds):
        self.blocked_until = max(self.blocked_until, self.clock() + seconds)

    def record(self, tokens):
        if self.budget:
            self.history.append((self.clock(), tokens))

    async def wait(self, reservation, label):
        total_wait = 0.0
        while True:
            now = self.clock()
            while self.history and now - self.history[0][0] >= self.window:
                self.history.popleft()
            delay = max(0.0, self.blocked_until - now)
            if self.budget and self.history:
                needed = min(reservation, self.budget)
                if sum(tokens for _, tokens in self.history) + needed > self.budget:
                    delay = max(delay, self.history[0][0] + self.window - now)
            if delay <= 0:
                return total_wait
            print(f'[{label}] Provider budget: waiting {delay:.1f}s...', flush=True)
            self.notify({'event': 'waiting', 'agent': label, 'seconds': round(delay, 1)})
            await self.sleep(delay)
            total_wait += delay

    @asynccontextmanager
    async def request(self, reservation, label):
        if self.budget:
            async with self.lock:
                waited = await self.wait(reservation, label)
                yield waited
        else:
            waited = await self.wait(reservation, label)
            yield waited
