"""JSON shortlists and stable application profiles for Agent Skills-compatible agents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .policy import POLICY
from .profiles import palette
from .selection import search, search_compositions
from .profile_validation import validate_profile
from .catalog import catalog_data, parse_catalog
from .io import atomic_write_json, read_json


def assignments(values: list[str], label: str) -> dict:
    result = {}
    for entry in values:
        key, separator, value = entry.partition('=')
        if not separator or not key.strip() or not value.strip() or key.strip() in result:
            raise ValueError(f'{label} requires unique ROLE=VALUE entries')
        result[key.strip()] = value.strip()
    return result


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
    query.add_argument('--profile', type=Path, help='Inherit saved style/packs/constraints and prefer compatible saved IDs')
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
    group.add_argument('--role-query', action='append', default=[], metavar='ROLE=QUERY', help='Meaning/state of a named application role; repeat for several roles')
    group.add_argument('--bind', action='append', default=[], metavar='ROLE=ID', help='Save a visually reviewed exact ID for a role; repeat for several roles')
    check = commands.add_parser('validate', help='Check that an application profile uses verified compatible IDs')
    check.add_argument('profile', type=Path)
    for command in [query, group]:
        command.add_argument('--animation', choices=['any', 'static', 'animated'], default='')
        command.add_argument('--color', choices=['any', 'monochrome', 'color'], default='')
        command.add_argument('--repainting', choices=['any', 'required', 'fixed'], default='')
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
                    constraints = {field: getattr(args, field) for field in ['animation', 'color', 'repainting'] if getattr(args, field)}
                    profile = read_json(args.profile) if args.profile else None
                    result = search(data, args.query, style=args.style, pack=args.pack, limit=args.limit, constraints=constraints,
                                    include_special=args.include_special, profile=profile)
            elif args.command == 'validate':
                errors = validate_profile(data, read_json(args.profile))
                result = {'valid': not errors, 'errors': errors}
                if errors:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 1
            else:
                if args.save and not args.profile:
                    raise ValueError('--save requires --profile')
                existing = read_json(args.profile) if args.profile and args.profile.exists() else None
                constraints = {field: getattr(args, field) for field in ['animation', 'color', 'repainting'] if getattr(args, field)}
                result = palette(data, args.roles, style=args.style, pack=args.pack, profile=existing, constraints=constraints,
                                 role_queries=assignments(args.role_query, '--role-query'), bindings=assignments(args.bind, '--bind'))
                if args.save:
                    atomic_write_json(args.profile, result['profile'])
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
