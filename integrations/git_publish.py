"""Publish catalog files without committing unrelated staged application changes."""
import base64
import os
from pathlib import Path
import subprocess


def publish_catalog(repo: Path, files: list[Path], descriptions: list[str]) -> str:
    committed = False
    try:
        paths = [str(path.relative_to(repo)) for path in files]
        subprocess.run(['git', 'add', '--', *paths], cwd=repo, check=True, capture_output=True, timeout=30)
        subprocess.run(['git', 'commit', '--only', '-m', 'Add emoji: ' + ', '.join(descriptions), '--', *paths],
                       cwd=repo, check=True, capture_output=True, timeout=30)
        committed = True
        environment = os.environ.copy()
        environment['GIT_TERMINAL_PROMPT'] = '0'
        token = environment.get('GITHUB_TOKEN', '')
        if token:
            credential = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
            index = int(environment.get('GIT_CONFIG_COUNT', '0'))
            environment['GIT_CONFIG_COUNT'] = str(index + 1)
            environment[f'GIT_CONFIG_KEY_{index}'] = 'http.https://github.com/.extraheader'
            environment[f'GIT_CONFIG_VALUE_{index}'] = f'AUTHORIZATION: basic {credential}'
        result = subprocess.run(['git', 'push'], cwd=repo, capture_output=True, text=True, env=environment, timeout=60)
        return ('✅ Запушено в GitHub' if result.returncode == 0 else
                '⚠️ Файлы сохранены локально, но push не удался. Проверь доступ к GitHub.')
    except (subprocess.SubprocessError, OSError, ValueError):
        if committed:
            return '⚠️ Файлы и коммит сохранены локально, но push не завершился. Проверь доступ к GitHub.'
        return '⚠️ Файлы сохранены локально, но Git не смог создать коммит. Проверь настройки Git.'
