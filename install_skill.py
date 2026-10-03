"""Install Telegram Premium Emoji for a supported agent on Windows, macOS or Linux."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.skill_package import AGENTS, MANIFEST, destination, install, read_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=AGENTS, default='codex')
    parser.add_argument('--scope', choices=['user', 'project'], default='user')
    parser.add_argument('--project', type=Path, help='Application folder for a project-scoped installation')
    parser.add_argument('--dest', type=Path, help='Custom skills parent directory; appends telegram-premium-emoji')
    parser.add_argument('--update', action='store_true', help='Refresh package files while preserving unrelated local files')
    parser.add_argument('--dry-run', action='store_true', help='Show the installation destination without writing files')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or later is required')
    try:
        target = destination(args.agent, scope=args.scope, project=args.project, dest=args.dest)
        payload = read_payload()
        if not args.dry_run:
            install(payload, target, update=args.update)
        manifest = json.loads(payload[MANIFEST])
        print(json.dumps({'agent': args.agent, 'path': str(target), 'dry_run': args.dry_run,
                          'files': len(payload), 'emoji_count': manifest['emoji_count'],
                          'catalog_version': manifest['catalog_version'],
                          'next': 'Open a new agent session and request telegram-premium-emoji.'}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
