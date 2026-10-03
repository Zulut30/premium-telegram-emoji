"""UTF-8 data IO with staged writes and rollback for coordinated catalog files."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _stage(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def replace_files(updates: dict[Path, bytes], *, expected: dict[Path, bytes] | None = None) -> None:
    """Stage every file before mutation; restore replaced files on a write failure."""
    originals = {path: path.read_bytes() if path.exists() else None for path in updates}
    staged, backups, replaced = {}, {}, []
    retained = set()
    try:
        for path, content in updates.items():
            staged[path] = _stage(path, content)
            if originals[path] is not None:
                backups[path] = _stage(path, originals[path])
        if expected and any(not path.exists() or path.read_bytes() != content for path, content in expected.items()):
            raise ValueError('Source files changed during the operation; retry against the current catalog')
        for path, temporary in staged.items():
            os.replace(temporary, path)
            replaced.append(path)
    except BaseException as error:
        failures = []
        for path in reversed(replaced):
            try:
                if path in backups:
                    os.replace(backups[path], path)
                else:
                    path.unlink(missing_ok=True)
            except OSError as rollback_error:
                if path in backups:
                    retained.add(backups[path])
                failures.append(f'{path}: {rollback_error}')
        if failures:
            raise OSError('Write failed; rollback needs manual recovery. Backups: '
                          + ', '.join(map(str, retained)) + '. ' + '; '.join(failures)) from error
        raise
    finally:
        for temporary in [*staged.values(), *backups.values()]:
            if temporary not in retained:
                temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value) -> None:
    content = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    replace_files({path: content})
