"""Small CLI layer; all work is in the importable pipeline package."""
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from .config import Config
from .models import Plan, Slot
from .demo import DemoProvider
from .orchestrator import apply_overrides, run_week

ROOT = Path(__file__).resolve().parents[1]

def main(piece=False):
    parser = argparse.ArgumentParser(description='Grounded weekly X content pipeline')
    parser.add_argument('--config-dir', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mode', choices=['live','demo'], default='live')
    parser.add_argument('--concurrency', type=int, default=3)
    if piece:
        parser.add_argument('--type', required=True)
        parser.add_argument('--topic', required=True)
    else:
        parser.add_argument('--plan', type=Path, default=ROOT / 'plan.json')
        parser.add_argument('--set', action='append', default=[], metavar='SLOT=TOPIC')
    args = parser.parse_args()
    try:
        load_dotenv(args.config_dir / '.env', override=False)
        config = Config(args.config_dir)
        if piece:
            plan = Plan(slots=[Slot(id='piece_1', type=args.type, focus=args.topic)])
        else:
            plan = apply_overrides(Plan.model_validate_json(args.plan.read_text()), args.set)
        if args.mode == 'demo':
            provider = DemoProvider()
        else:
            from .providers import LiveProvider
            provider = LiveProvider()
        output = args.output or ROOT / 'output' / datetime.now(timezone.utc).strftime('local-%Y%m%dT%H%M%S%fZ')
        summary = asyncio.run(run_week(plan, config, provider, output, args.concurrency))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Configuration error: {exc}\n')
    print(json.dumps(summary, indent=2))
    print(f'Run folder: {output.resolve()}')
    return 1 if summary['pieces_dropped'] else 0
