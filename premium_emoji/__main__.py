"""Run the same CLI used by the portable skill: python -m premium_emoji."""
import sys
from .cli import main

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
raise SystemExit(main())
