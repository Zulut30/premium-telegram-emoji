"""Portable Agent Skills entrypoint; compatible with an arbitrary working directory."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools' / 'select_emoji.py'), run_name='__main__')
