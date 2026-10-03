"""One reproducible development gate, shared by local work and all CI platforms."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from premium_emoji.validation import validate_sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'validate-data'])
    parser.add_argument('--web', action='store_true', help='Also build the offline site and verify DOM and Python/JS parity (npm ci required)')
    args = parser.parse_args()
    errors = validate_sources()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Source data: valid', flush=True)
    if args.command == 'validate-data':
        return 0
    environment = os.environ.copy()
    environment['EMOJI_QA_PYTHON'] = sys.executable
    commands = [[sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-v']]
    if args.web:
        commands += [[sys.executable, '-X', 'utf8', 'generate_site.py', '--offline'],
                     ['node', 'tests/catalog_dom.cjs'], ['node', 'tests/selection_parity.cjs']]
    for command in commands:
        print('> ' + ' '.join(command), flush=True)
        try:
            subprocess.run(command, cwd=ROOT, env=environment, check=True)
        except FileNotFoundError as error:
            print(f'Missing development runtime: {error}', file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as error:
            return error.returncode
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
