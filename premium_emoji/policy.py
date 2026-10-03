"""Single policy source used by query parsing, ranking, profiles and browser export."""
import json
from .paths import DEFAULT_PATHS

POLICY = json.loads(DEFAULT_PATHS.policy.read_text(encoding='utf-8'))
SITE_URL = 'https://zulut30.github.io/premium-telegram-emoji/'
