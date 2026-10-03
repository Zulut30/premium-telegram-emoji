"""Compatibility imports; implementation lives in premium_emoji."""
from premium_emoji.paths import DEFAULT_PATHS
from premium_emoji.policy import POLICY, SITE_URL
from premium_emoji.catalog import enrich_catalog
from premium_emoji.query import normalized, spans, matches, concepts, query_plan, plan_in_style
from premium_emoji.rendering import safe_fallback, emoji_html
from premium_emoji.ranking import fits_constraints, rank, candidate
from premium_emoji.profile_validation import merged_constraints, validate_profile
from premium_emoji.selection import search, search_compositions
from premium_emoji.profiles import palette
ROOT = DEFAULT_PATHS.root

__all__ = ['POLICY', 'SITE_URL', 'enrich_catalog', 'normalized', 'spans', 'matches', 'concepts', 'query_plan', 'plan_in_style', 'safe_fallback', 'emoji_html', 'fits_constraints', 'rank', 'candidate', 'merged_constraints', 'validate_profile', 'search', 'search_compositions', 'palette']
