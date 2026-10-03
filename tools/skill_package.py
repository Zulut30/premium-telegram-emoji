"""Build and install a self-contained Agent Skill using only the standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'telegram-premium-emoji'
MANIFEST = 'skill-manifest.json'
FILES = (
    'SKILL.md', 'emoji_catalog.py', 'emoji_selection.py', 'install_skill.py',
    'scripts/select_emoji.py', 'tools/select_emoji.py', 'tools/skill_package.py',
    'agents/openai.yaml', 'data/emoji-packs.json', 'data/emoji-compositions.json',
    'data/selection-policy.json', 'references/emoji-catalog.md',
    'references/emoji-selection.md', 'references/emoji-compositions.md',
    'references/pack-analysis.md', 'references/pack-analysis-initial-eight.md',
    'references/pack-analysis-2026-10-03.md', 'references/platforms.md',
    'premium_emoji/__init__.py', 'premium_emoji/__main__.py',
    'premium_emoji/paths.py', 'premium_emoji/policy.py', 'premium_emoji/catalog.py',
    'premium_emoji/query.py', 'premium_emoji/rendering.py', 'premium_emoji/ranking.py',
    'premium_emoji/selection.py', 'premium_emoji/profile_validation.py',
    'premium_emoji/profiles.py', 'premium_emoji/cli.py', 'premium_emoji/io.py',
)
AGENTS = {
    'codex': ('.agents/skills', '.agents/skills'),
    'claude': ('.claude/skills', '.claude/skills'),
    'cursor': ('.cursor/skills', '.cursor/skills'),
    'copilot': ('.copilot/skills', '.github/skills'),
    'opencode': ('.config/opencode/skills', '.opencode/skills'),
    'universal': ('.agents/skills', '.agents/skills'),
    'codex-legacy': ('.codex/skills', '.codex/skills'),
}


def safe_relative(value: str) -> Path:
    path = PurePosixPath(value)
    if not path.parts or '\\' in value or ':' in value or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError(f'Invalid package path: {value}')
    return Path(*path.parts)


def read_payload(root: Path = ROOT) -> dict[str, bytes]:
    """An explicit allowlist excludes bot configuration, Git, logs and credentials."""
    root = root.resolve()
    packs = json.loads((root / 'data/emoji-packs.json').read_text(encoding='utf-8'))['packs']
    allowed = {*FILES, *[f'references/packs/{pack["name"]}.md' for pack in packs]}
    manifest_path = root / MANIFEST
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('name') != NAME or manifest.get('schema_version') != 1:
            raise ValueError('Not a supported Telegram Premium Emoji package')
        files = manifest['files']
        if set(files) != allowed:
            raise ValueError('Package file list does not match the skill resource allowlist')
    else:
        files = dict.fromkeys(allowed)
    payload = {}
    for relative, digest in sorted(files.items()):
        path = root / safe_relative(relative)
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError(f'Package file must stay within the source folder: {relative}')
        content = path.read_bytes()
        if digest is not None and hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Package integrity check failed: {relative}')
        if digest is None:
            content = content.replace(b'\r\n', b'\n')
        payload[relative] = content
    if manifest_path.exists():
        payload[MANIFEST] = manifest_path.read_bytes()
    else:
        sys.path.insert(0, str(ROOT))
        from emoji_catalog import catalog_data, parse_catalog
        data = catalog_data(parse_catalog(root / 'references/emoji-catalog.md', root / 'data/emoji-packs.json'),
                            {}, root / 'data/emoji-compositions.json')
        manifest = {'schema_version': 1, 'name': NAME, 'catalog_version': data['catalog_version'],
                    'emoji_count': len(data['items']),
                    'files': {key: hashlib.sha256(value).hexdigest() for key, value in payload.items()}}
        payload[MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return payload


def destination(agent: str, *, scope: str = 'user', project: Path | None = None,
                dest: Path | None = None, home: Path | None = None, environ: dict | None = None) -> Path:
    home = home or Path.home()
    environ = os.environ if environ is None else environ
    if dest is not None:
        return dest.expanduser().resolve() / NAME
    if scope == 'project':
        if project is None or not project.is_dir():
            raise ValueError('--scope project requires --project pointing to an existing application folder')
        return project.resolve() / AGENTS[agent][1] / NAME
    if project is not None:
        raise ValueError('--project is only used with --scope project')
    if agent == 'opencode':
        base = Path(environ['XDG_CONFIG_HOME']).expanduser() if environ.get('XDG_CONFIG_HOME') else home / '.config'
        return base.resolve() / 'opencode/skills' / NAME
    if agent == 'codex-legacy' and environ.get('CODEX_HOME'):
        return Path(environ['CODEX_HOME']).expanduser().resolve() / 'skills' / NAME
    return (home / AGENTS[agent][0]).resolve() / NAME


def install(payload: dict[str, bytes], target: Path, *, update: bool = False) -> None:
    """Update only package-owned files; preserve application profiles and local files."""
    if target.is_symlink():
        raise ValueError('Choose a real skill directory rather than a symlink')
    target = target.resolve()
    if target.exists():
        if not update:
            raise ValueError(f'Skill already exists at {target}; use --update to refresh its packaged files')
        entry = target / 'SKILL.md'
        if not entry.is_file() or not re.search(r"(?m)^name:\s*['\"]?telegram-premium-emoji['\"]?\s*$", entry.read_text(encoding='utf-8-sig')):
            raise ValueError('Refusing to update a folder without this skill name in SKILL.md')
    # Complete path checks before writing any file, including during updates.
    for relative in payload:
        path = target / safe_relative(relative)
        if not path.resolve().is_relative_to(target) or path.is_symlink() or path.is_dir():
            raise ValueError(f'Unsafe installation target: {relative}')
        for parent in path.parents:
            if parent == target.parent:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f'Unsafe installation parent for: {relative}')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.emoji-skill-', dir=target.parent) as directory:
        stage = Path(directory).resolve()
        if not stage.is_relative_to(target.parent):
            raise ValueError('Staging directory escaped the installation parent')
        for relative, content in payload.items():
            path = stage / safe_relative(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for relative in payload:
            path = target / safe_relative(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            (stage / relative).replace(path)


def archive(payload: dict[str, bytes], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative, content in sorted(payload.items()):
            safe_relative(relative)
            info = zipfile.ZipInfo(f'{NAME}/{relative}', date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist', help='Directory for ZIP, .skill and SHA256SUMS')
    args = parser.parse_args()
    try:
        payload = read_payload()
        args.output.mkdir(parents=True, exist_ok=True)
        zipped = args.output / f'{NAME}.zip'
        archive(payload, zipped)
        skill = args.output / f'{NAME}.skill'
        skill.write_bytes(zipped.read_bytes())
        checksums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in [zipped, skill])
        (args.output / 'SHA256SUMS').write_text(checksums, encoding='utf-8')
        manifest = json.loads(payload[MANIFEST])
        print(json.dumps({'output': str(args.output.resolve()), 'files': len(payload),
                          'emoji_count': manifest['emoji_count'], 'catalog_version': manifest['catalog_version']}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
