"""Import a fully reviewed batch, preserving existing catalog and pack metadata.

Requires requirements-inspection.txt and the cache created by review_pack_batch.py.
Dry run is the default; --write-catalog writes the catalog, metadata and reports.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

from PIL import Image
from import_reviewed_packs import cell, key_for

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.runtime' / 'packs'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def image_properties(path):
    """Distinguish empty images and coloured art from repaintable grayscale icons."""
    with Image.open(path).convert('RGBA') as image:
        pixels = [p for p in image.getdata() if p[3] > 32]
    if not pixels:
        return {'empty': True, 'monochrome': False}
    chromatic = sum(max(p[:3]) - min(p[:3]) > 20 for p in pixels)
    return {'empty': False, 'monochrome': chromatic / len(pixels) < .01}


def render_report(pack):
    items = pack['items']
    telegram_title = ' '.join(pack['telegram_title'].split())
    text = (f'# {pack["title_ru"]}\n\nИсточник: [{telegram_title}]({pack["url"]}). '
            f'Проверено {pack["reviewed_on"]} через Telegram Bot API, превью и исходные анимации.\n\n'
            f'Категория: **{pack["category"]}**. Стиль: {pack["style"]}.\n\n'
            f'{len(items)} эмодзи; анимированных: {sum(i["is_animated"] for i in items)}; '
            f'адаптивных в Telegram: {sum(i["needs_repainting"] for i in items)}.\n\n')
    text += ''.join(f'- {note}\n' for note in pack['notes']) + '\n'
    text += '| № | Название | Подкатегория | custom_emoji_id | key | fallback | Примечание |\n|---|---|---|---|---|---|---|\n'
    for item in items:
        note = ('Требует уточнения. ' if item['needs_review'] else '') + ' '.join(item['notes'])
        text += '| ' + ' | '.join(cell(v) for v in [item['pack_index'], item['name_ru'], item['subcategory'], item['emoji_id'], item['key'], item['fallback'], note]) + ' |\n'
    return text.rstrip() + '\n'


def render_compositions(document, by_id):
    text = '# Составные эмодзи\n\nВставляйте части подряд без пробелов, в указанном порядке. '
    text += 'Повторяющиеся ID сохранены: один элемент может быть нужен несколько раз. '
    text += 'Внешний вид и стыки проверены на статичных превью; в Telegram возможны различия из-за темы и фазы анимации.\n\n'
    text += 'HTML ниже предназначен для сообщений Telegram Bot API с `parse_mode="HTML"`; возможность отправки custom emoji зависит от прав бота.\n\n'
    for group in document['compositions']:
        text += f'## {group["name_ru"]}\n\nПак: [{group["pack_name"]}](https://t.me/addemoji/{group["pack_name"]}).\n\n'
        text += 'Позиции: ' + ' → '.join(map(str, group['pack_indices'])) + '.\n\n'
        text += 'ID по порядку: `' + ' '.join(group['emoji_ids']) + '`.\n\n'
        if group.get('needs_review'):
            text += '**Есть недоступная или неустановленная часть; полное превью сборки не подтверждено.**\n\n'
        # A valid default emoji is intentional: many source fallback values are ordinary letters.
        html = ''.join(f'<tg-emoji emoji-id="{eid}">✨</tg-emoji>' for eid in group['emoji_ids'])
        text += '```html\n' + html + '\n```\n\n'
    return text.rstrip() + '\n'


def import_batch(batch_path, write=False):
    batch = read_json(batch_path)
    review_path = batch_path.with_name(batch_path.stem + '-review.json')
    review = read_json(review_path)
    date = review['reviewed_on']
    original_path = ROOT / 'references' / 'emoji-catalog.md'
    original = original_path.read_text(encoding='utf-8')
    ids_path = ROOT / 'emoji-ids.txt'
    ids_bytes = ids_path.read_bytes()
    existing_keys = {eid: key.strip() for key, eid in re.findall(r'^\|\s*([^|]+?)\s*\|\s*(\d{15,22})\s*\|', original, re.M)}
    existing_ids = set(existing_keys)
    used_keys = set(existing_keys.values())
    next_section = max(map(int, re.findall(r'^## Section (\d+)', original, re.M)), default=0) + 1
    metadata_path = ROOT / 'data' / 'emoji-packs.json'
    document = read_json(metadata_path) if metadata_path.exists() else {'schema_version': 1, 'packs': []}
    preserved = {p['name']: p for p in document['packs']}
    seen = set()
    imported = []
    new_rows = []
    updated = original
    overrides_to_copy = {}

    for name in batch['packs']:
        source = read_json(CACHE / f'{name}.json')
        conf = review['packs'][name]
        stickers = source['stickers']
        expected_pages = list(range(1, math.ceil(len(stickers) / 64) + 1))
        if conf.get('reviewed_pages') != expected_pages:
            raise ValueError(f'{name}: all contact sheet pages must be reviewed before import')
        labels = [line.split('|', 1) for line in (ROOT / 'data' / 'labels' / f'{name}.txt').read_text(encoding='utf-8').splitlines() if line.strip()]
        if len(labels) != len(stickers) or any(len(line) != 2 for line in labels):
            raise ValueError(f'{name}: labels do not match sticker count')
        pack = {'name': name, 'telegram_title': source['title'], 'title_ru': conf['title_ru'], 'category': conf['category'],
                'style': conf['style'], 'url': f'https://t.me/addemoji/{name}', 'reviewed_on': date,
                'usage': 'Поиск и оформление сообщений, рубрик и тематических подборок по названиям и подкатегориям.',
                'notes': conf.get('notes', []), 'count': len(labels), 'items': []}
        repeated = Counter()
        for index, (sticker, (title, subcategory)) in enumerate(zip(stickers, labels), 1):
            eid = str(sticker['custom_emoji_id'])
            if eid in seen:
                raise ValueError(f'Duplicate ID within batch: {eid}')
            seen.add(eid)
            repeated[title] += 1
            if repeated[title] > 1:
                title += f' — вариант {repeated[title]}'
            extra = dict(conf.get('overrides', {}).get(str(index), {}))
            preview = CACHE / name / f'{index:03}.webp'
            frame = CACHE / name / f'{index:03}-frame.png'
            chosen = frame if frame.exists() and not image_properties(frame)['empty'] else preview
            available = chosen.exists() and chosen.stat().st_size > 0
            properties = image_properties(chosen) if available else {'empty': True, 'monochrome': False}
            notes = list(extra.pop('notes', []))
            tags = list(dict.fromkeys([conf['category'], subcategory, conf['style'], name, *extra.pop('tags', [])]))
            adaptive = bool(sticker.get('needs_repainting'))
            if adaptive:
                tags.append('адаптивный')
            if not available:
                extra.update(needs_review=True, availability='telegram_unavailable')
                if not notes:
                    notes.append('Telegram не отдаёт файл; содержание изображения не подтверждено.')
            elif properties['empty']:
                extra.update(needs_review=True, availability='transparent_placeholder')
                if not notes:
                    notes.append('Изображение полностью прозрачное; назначение элемента не установлено.')
            item = {'pack_index': index, 'emoji_id': eid, 'key': existing_keys.get(eid) or key_for(name, title, used_keys),
                    'name_ru': title, 'category': conf['category'], 'subcategory': subcategory, 'tags': tags,
                    'fallback': sticker.get('emoji') or '✨', 'original_fallback': sticker.get('emoji', ''),
                    'is_animated': bool(sticker['is_animated']), 'is_video': bool(sticker['is_video']),
                    'needs_repainting': adaptive, 'monochrome': properties['monochrome'],
                    'file_unique_id': sticker['file_unique_id'], 'identification': 'manual_visual_review',
                    'needs_review': False, 'notes': notes, 'preview_source': 'rendered_original_frame' if chosen == frame else 'telegram_thumbnail',
                    'preview_sha256': hashlib.sha256(chosen.read_bytes()).hexdigest() if available else None, **extra}
            if chosen == frame and available:
                overrides_to_copy[eid] = frame
            pack['items'].append(item)
        additions = [i for i in pack['items'] if i['emoji_id'] not in existing_ids]
        if additions:
            updated += f'\n\n## Section {next_section} — {pack["title_ru"]}\nPack: {pack["url"]}\n\nКатегория: {pack["category"]}. Стиль: {pack["style"]}.\n\n| key suggestion | emoji_id | description | fallback |\n|---|---|---|---|\n'
            for item in additions:
                updated += '| ' + ' | '.join(cell(item[k]) for k in ['key', 'emoji_id', 'name_ru', 'fallback']) + ' |\n'
                existing_ids.add(item['emoji_id'])
            new_rows.extend(additions)
            next_section += 1
        preserved[name] = pack
        imported.append(pack)

    document.update(schema_version=2, reviewed_on=date, method='Manual visual review, Telegram metadata, source animation frames; uncertain identities and unavailable images are marked.')
    document['packs'] = list(preserved.values())
    by_id = {i['emoji_id']: i for p in document['packs'] for i in p['items']}
    composition_path = ROOT / 'data' / 'emoji-compositions.json'
    composition_doc = read_json(composition_path) if composition_path.exists() else {'schema_version': 1, 'compositions': []}
    compositions = {g['key']: g for g in composition_doc['compositions']}
    spec_path = batch_path.with_name(batch_path.stem + '-compositions.json')
    for spec in read_json(spec_path)['compositions'] if spec_path.exists() else []:
        pack = preserved[spec['pack_name']]
        group = dict(spec)
        group['emoji_ids'] = [pack['items'][index - 1]['emoji_id'] for index in spec['pack_indices']]
        group['needs_review'] = any(by_id[eid].get('availability') for eid in group['emoji_ids'])
        compositions[group['key']] = group
        for eid in group['emoji_ids']:
            item = by_id[eid]
            item['role'] = 'composition_part'
            memberships = item.setdefault('composition_keys', [])
            if group['key'] not in memberships:
                memberships.append(group['key'])
    composition_doc['compositions'] = list(compositions.values())

    stats = {'packs': len(imported), 'batch_items': len(seen), 'new_catalog_items': len(new_rows),
             'metadata_packs': len(document['packs']), 'catalog_unique_ids': len(existing_ids),
             'compositions': len(compositions), 'frame_previews': len(overrides_to_copy),
             'unavailable': sum(i.get('availability') == 'telegram_unavailable' for p in imported for i in p['items']),
             'transparent': sum(i.get('availability') == 'transparent_placeholder' for p in imported for i in p['items']),
             'needs_review': sum(i['needs_review'] for p in imported for i in p['items']), 'written': write}
    if not write:
        return stats
    if original_path.read_text(encoding='utf-8') != original or ids_path.read_bytes() != ids_bytes:
        raise RuntimeError('Catalog changed during import; retry with the bot stopped.')
    original_path.write_text(updated, encoding='utf-8', newline='\n')
    existing_lines = set(re.findall(r'^(\d{15,22})\b', ids_bytes.decode('utf-8'), re.M))
    append = ''.join(f'\n{i["emoji_id"]} - {i["name_ru"]}' for i in new_rows if i['emoji_id'] not in existing_lines)
    if append:
        ids_path.write_bytes(ids_bytes + (append + '\n').encode('utf-8'))
    metadata_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    composition_path.write_text(json.dumps(composition_doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    assets = ROOT / 'assets' / 'previews'
    assets.mkdir(parents=True, exist_ok=True)
    for eid, source in overrides_to_copy.items():
        shutil.copy2(source, assets / f'{eid}.png')
    for pack in imported:
        (ROOT / 'references' / 'packs' / f'{pack["name"]}.md').write_text(render_report(pack), encoding='utf-8', newline='\n')
    report = (f'# Импорт {len(imported)} паков — {date}\n\n{len(seen):,} custom_emoji_id в партии. Для каждого сохранены русское название, категория, подкатегория, стиль, источник и поисковые теги.\n\n'
              f'Просмотрены все контактные листы. Прозрачных изображений: {stats["transparent"]}; недоступных файлов: {stats["unavailable"]}; '
              f'описаний с отметкой для уточнения: {stats["needs_review"]}. Для {stats["frame_previews"]} превью выбран видимый кадр исходной анимации.\n\n'
              'Идентичные картинки с разными ID сохранены. Названия неизвестных логотипов описывают эмблему и не приписывают ей бренд. '
              'Буквы и числа размечены по символам; составные изображения — по частям. [Примеры сборки](emoji-compositions.md).\n\n'
              '| Пак | Русское название | Категория | Эмодзи | Уточнить |\n|---|---|---|---|---|\n')
    for pack in imported:
        report += '| ' + ' | '.join([f'[{pack["name"]}]({pack["url"]})', f'[{pack["title_ru"]}](packs/{pack["name"]}.md)', pack['category'], str(pack['count']), str(sum(i['needs_review'] for i in pack['items']))]) + ' |\n'
    report += '\n## Источники и метод\n\n'
    report += ''.join(f'- {source}\n' for source in review['sources'])
    report += '\nКатегории и русские названия — редакционная разметка изображений, а не официальные названия авторов. Флаг needs_repainting берётся из Telegram; монохромное отображение сайта определяется по цветам превью.\n'
    (ROOT / 'references' / f'pack-analysis-{date}.md').write_text(report, encoding='utf-8', newline='\n')
    (ROOT / 'references' / 'emoji-compositions.md').write_text(render_compositions(composition_doc, by_id), encoding='utf-8', newline='\n')
    index_path = ROOT / 'references' / 'pack-analysis.md'
    historical_path = ROOT / 'references' / 'pack-analysis-initial-eight.md'
    if index_path.exists() and index_path.read_text(encoding='utf-8').startswith('# Анализ восьми') and not historical_path.exists():
        shutil.copy2(index_path, historical_path)
    index_text = f'# Анализ паков Telegram Emoji\n\nРазмечено {len(document["packs"])} паков и {sum(p["count"] for p in document["packs"])} эмодзи. '
    index_text += 'Русские названия и категории даны по изображениям; неизвестные эмблемы, прозрачные и недоступные элементы отмечены для уточнения.\n\n'
    index_text += '- [Первоначальные восемь паков](pack-analysis-initial-eight.md).\n'
    index_text += f'- [Партия {date}](pack-analysis-{date}.md).\n- [Составные эмодзи: порядок ID и HTML](emoji-compositions.md).\n\n'
    index_text += '| Пак | Русское название | Категория | Эмодзи |\n|---|---|---|---|\n'
    for pack in document['packs']:
        index_text += '| ' + ' | '.join([f'[{pack["name"]}]({pack["url"]})', f'[{pack["title_ru"]}](packs/{pack["name"]}.md)', pack['category'], str(pack['count'])]) + ' |\n'
    index_path.write_text(index_text, encoding='utf-8', newline='\n')
    return stats


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=Path)
    parser.add_argument('--write-catalog', action='store_true')
    args = parser.parse_args()
    print(json.dumps(import_batch(args.batch, args.write_catalog), ensure_ascii=False))
