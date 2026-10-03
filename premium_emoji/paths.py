"""Explicit repository or installed-skill paths; independent of the working directory."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    def __post_init__(self):
        object.__setattr__(self, 'root', Path(self.root).resolve())

    @property
    def catalog(self) -> Path:
        return self.root / 'references/emoji-catalog.md'

    @property
    def metadata(self) -> Path:
        return self.root / 'data/emoji-packs.json'

    @property
    def compositions(self) -> Path:
        return self.root / 'data/emoji-compositions.json'

    @property
    def policy(self) -> Path:
        return self.root / 'data/selection-policy.json'

    @property
    def ids(self) -> Path:
        return self.root / 'emoji-ids.txt'

    @property
    def web(self) -> Path:
        return self.root / 'web'

    @property
    def site(self) -> Path:
        return self.root / 'site'

    @property
    def previews(self) -> Path:
        return self.root / 'assets/previews'


DEFAULT_PATHS = ProjectPaths(Path(__file__).resolve().parents[1])
