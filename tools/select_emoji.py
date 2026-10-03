"""JSON shortlists and stable application profiles for Codex and other AI editors."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from emoji_selection import POLICY, palette, search, search_compositions, validate_profile
from generate_site import catalog_data, parse_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('styles', help='List style families, packs, and supported role keys')
    query = commands.add_parser('search', help='Get verified candidates for a meaning or name')
    query.add_argument('query')
    query.add_argument('--style', default='')
    query.add_argument('--pack', default='')
    query.add_argument('--limit', type=int, default=12)
    query.add_argument('--include-special', action='store_true', help='Include uncertain entries, letters, digits and fragments for inspection')
    composition = commands.add_parser('compositions', help='Get complete assemblies with original order and repetitions')
    composition.add_argument('query', nargs='?', default='')
    composition.add_argument('--pack', default='')
    composition.add_argument('--limit', type=int, default=12)
    group = commands.add_parser('palette', help='Select one coherent pack and reuse saved role IDs')
    group.add_argument('--roles', nargs='+', required=True)
    group.add_argument('--style', default='')
    group.add_argument('--pack', default='')
    group.add_argument('--profile', type=Path, help='Application profile JSON: reuse if it exists')
    group.add_argument('--save', action='store_true', help='Write/update the supplied profile path')
    check = commands.add_parser('validate', help='Check that an application profile uses verified compatible IDs')
    check.add_argument('profile', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'styles':
            result = {'styles': POLICY['styles'], 'roles': {key: rule['label'] for key, rule in POLICY['intents'].items()}}
        else:
            data = catalog_data(parse_catalog(), {})
            if args.command in {'search', 'compositions'}:
                if not 1 <= args.limit <= 100:
                    raise ValueError('Limit must be between 1 and 100')
                if args.command == 'compositions':
                    result = search_compositions(data, args.query, pack=args.pack, limit=args.limit)
                else:
                    result = search(data, args.query, style=args.style, pack=args.pack, limit=args.limit,
                                    include_special=args.include_special)
            elif args.command == 'validate':
                errors = validate_profile(data, json.loads(args.profile.read_text(encoding='utf-8')))
                result = {'valid': not errors, 'errors': errors}
                if errors:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 1
            else:
                if args.save and not args.profile:
                    raise ValueError('--save requires --profile')
                existing = json.loads(args.profile.read_text(encoding='utf-8')) if args.profile and args.profile.exists() else None
                result = palette(data, args.roles, style=args.style, pack=args.pack, profile=existing)
                if args.save:
                    args.profile.parent.mkdir(parents=True, exist_ok=True)
                    temporary = args.profile.with_name(args.profile.name + '.tmp')
                    temporary.write_text(json.dumps(result['profile'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    temporary.replace(args.profile)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
