"""Catalog editing independent of aiogram and Git publication."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from threading import RLock

from .io import replace_files

CATALOG_WRITE_LOCK = RLock()


def sections_from_text(text: str) -> dict[str, str]:
    return {match.group(1): match.group(0)[3:]
            for match in re.finditer(r'^## Section (\d+) — .+$', text, re.MULTILINE)}


def description_to_key(description: str) -> str:
    translit = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                       ['a','b','v','g','d','e','e','zh','z','i','j','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','sch','','y','','e','yu','ya']))
    word = description.split()[0].lower()
    key = ''.join(translit.get(char, char) for char in word)
    return re.sub(r'[^a-z0-9]', '_', key).strip('_') or 'emoji'


def markdown_cell(value: str) -> str:
    return ' '.join(value.split()).replace('|', '&#124;')


def append_rows(text: str, entries: list[dict], section_num: str) -> str:
    sections = sections_from_text(text)
    if section_num not in sections:
        raise ValueError('Catalog section no longer exists')
    header = f'## {sections[section_num]}'
    section_pos = text.find(header)
    next_section = text.find('\n## ', section_pos + len(header))
    section_end = next_section if next_section != -1 else len(text)
    rows = list(re.finditer(r'^\|.*\|[ \t]*$', text[section_pos:section_end], re.MULTILINE))
    insert_at = section_pos + rows[-1].end() if rows else section_end
    additions = ''.join(f'| {description_to_key(item["description"])} | {item["emoji_id"]} | '
                        f'{markdown_cell(item["description"])} | {markdown_cell(item["fallback"])} |\n'
                        for item in entries)
    updated = text[:insert_at].rstrip() + '\n' + additions.rstrip('\n') + text[insert_at:]
    return updated.rstrip('\n') + '\n'


@dataclass(frozen=True)
class CatalogStore:
    catalog_file: Path
    ids_file: Path

    def sections(self) -> dict[str, str]:
        return sections_from_text(self.catalog_file.read_text(encoding='utf-8'))

    def append_catalog(self, entries: list[dict], section_num: str) -> None:
        with CATALOG_WRITE_LOCK:
            original = self.catalog_file.read_bytes()
            text = original.decode('utf-8').replace('\r\n', '\n')
            replace_files({self.catalog_file: append_rows(text, entries, section_num).encode('utf-8')},
                          expected={self.catalog_file: original})

    def append_ids(self, entries: list[dict]) -> None:
        with CATALOG_WRITE_LOCK:
            original = self.ids_file.read_bytes()
            additions = ''.join(f'\n{item["emoji_id"]} - {" ".join(item["description"].split())}' for item in entries)
            replace_files({self.ids_file: original + additions.encode('utf-8')}, expected={self.ids_file: original})

    def save(self, entries: list[dict], section_num: str | None, *, section_name: str = '') -> str:
        if not entries or any(not isinstance(item.get('emoji_id'), str) or not item['emoji_id'].isdigit()
                              or not isinstance(item.get('description'), str) or not item['description'].strip()
                              or not isinstance(item.get('fallback'), str) for item in entries):
            raise ValueError('Catalog entries require string IDs, descriptions and fallbacks')
        with CATALOG_WRITE_LOCK:
            original = {path: path.read_bytes() for path in [self.ids_file, self.catalog_file]}
            text = original[self.catalog_file].decode('utf-8').replace('\r\n', '\n')
            if section_name:
                name = ' '.join(section_name.split())
                if not 1 <= len(name) <= 80:
                    raise ValueError('Section name must contain 1 to 80 characters')
                section_num = str(max(map(int, sections_from_text(text)), default=0) + 1)
                text += f'\n\n## Section {section_num} — {name}\n\n'
                text += '| key suggestion | emoji_id | description | fallback |\n|---|---|---|---|\n'
            updated = append_rows(text, entries, section_num)
            additions = ''.join(f'\n{item["emoji_id"]} - {" ".join(item["description"].split())}' for item in entries)
            replace_files({self.ids_file: original[self.ids_file] + additions.encode('utf-8'),
                           self.catalog_file: updated.encode('utf-8')}, expected=original)
            return section_num
