"""Background jobs for Streamlit; no Streamlit calls run in worker threads."""
import asyncio
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from .config import Config
from .demo import DemoProvider
from .providers import LiveProvider
from .orchestrator import run_week

# One active UI job per server, so browser tabs do not multiply a free-tier load.
RUN_LOCK = threading.Lock()

@dataclass
class Job:
    output: Path
    events: deque = field(default_factory=lambda: deque(maxlen=500))
    done: bool = False
    summary: dict | None = None
    error: str | None = None

    def notify(self, event):
        self.events.append(dict(event))


def start_job(plan, root, output_root, mode, options, concurrency):
    if not RUN_LOCK.acquire(blocking=False):
        raise ValueError('Another UI run is active. Wait for it to finish.')
    try:
        config = Config(root)  # Freeze files before starting the worker.
        name = datetime.now(timezone.utc).strftime('ui-%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
        job = Job(Path(output_root) / name)
        provider = DemoProvider() if mode == 'demo' else LiveProvider(options=options, progress=job.notify)
    except Exception:
        RUN_LOCK.release()
        raise

    def work():
        try:
            job.summary = asyncio.run(run_week(plan, config, provider, job.output,
                                              concurrency, notify=job.notify))
        except Exception as exc:
            job.error = f'Run failed ({type(exc).__name__}). Check configuration and the partial run folder.'
        finally:
            job.done = True
            RUN_LOCK.release()
    threading.Thread(target=work, daemon=True, name='content-pipeline-worker').start()
    return job
