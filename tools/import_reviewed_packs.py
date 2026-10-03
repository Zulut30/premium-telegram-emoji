"""Build catalog records from manually reviewed labels and Telegram metadata."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.runtime' / 'packs'
CONFIG = {
    'RoundFlags': ('Круглые флаги стран и территорий', 'География и флаги', 'Языковые меню, выбор региона, международные новости, путешествия.', ['флаг', 'страна', 'регион', 'география'], False),
    'GameIcons': ('Эмблемы игр и игровых вселенных', 'Игры и игровые вселенные', 'Разделы игровых сообществ, новости об играх, фракции и игровые коллекции.', ['игра', 'логотип', 'эмблема', 'game', 'gaming'], True),
    'GameEmoji': ('Пиксельный игровой сленг', 'Игровой сленг и реакции', 'Короткие игровые реакции, статусы, характеристики, торговля и общение команды.', ['игра', 'пиксель', 'надпись', 'сленг', 'gaming'], False),
    'EffectEmoji': ('Анимированные эффекты и акценты', 'Эффекты и оформление', 'Акценты в постах, эмоциональные реакции, праздник, движение, указатели.', ['эффект', 'анимация', 'акцент', 'оформление'], False),
    'CuteEmoji': ('Милые рисованные эмодзи', 'Милые эмодзи', 'Дружелюбные сообщения, личные блоги, поздравления, реакции и мягкое оформление.', ['милый', 'рисованный', 'пастельный', 'cute'], False),
    'TopicIcons': ('Иконки тем и навигации', 'Иконки тем и навигации', 'Темы форумов, меню ботов, рубрики, разделы сообщества и навигация.', ['иконка', 'тема', 'навигация', 'меню', 'topic'], True),
    'MovieIcons': ('Эмблемы кино, сериалов и франшиз', 'Кино и сериалы', 'Киноподборки, обсуждения сериалов, фанатские сообщества и тематические разделы.', ['кино', 'сериал', 'фильм', 'эмблема', 'movie'], True),
    'AnimalIcons': ('Иконки животных', 'Животные', 'Зоотематика, природа, питомцы, игровые аватары и тематические рубрики.', ['животное', 'мордочка', 'иконка', 'animal'], True),
}
LETTERS = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя', ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r','s','t','u','f','kh','ts','ch','sh','shch','','y','','e','yu','ya']))
MOVIE_ALIASES = {
    'Бэтмен': ['Batman', 'DC'], 'Супермен': ['Superman', 'DC'], 'Чудо-женщина': ['Wonder Woman', 'DC'],
    'Каратель': ['Punisher', 'Marvel'], 'Трансформеры': ['Transformers'], 'Звёздные войны': ['Star Wars'],
    'Гарри Поттер': ['Harry Potter', 'Hogwarts'], 'Игра престолов': ['Game of Thrones'], 'Властелин колец': ['Lord of the Rings', 'LOTR'],
    'Обитель зла': ['Resident Evil'], 'Охотники за привидениями': ['Ghostbusters'], 'Барби': ['Barbie'],
    'V — значит вендетта': ['V for Vendetta'], 'Секретные материалы': ['The X-Files'], 'Разделение': ['Severance', 'Lumon'],
    'Маньяк': ['Maniac', 'NPB'], 'Первому игроку приготовиться': ['Ready Player One', 'IOI'], 'Джон Уик': ['John Wick'],
    'Чужой': ['Alien', 'Weyland-Yutani'], 'Дюна': ['Dune'], 'Мир Дикого Запада': ['Westworld'],
    'Теория большого взрыва': ['The Big Bang Theory'], 'Робокоп': ['RoboCop', 'OCP'], 'Во все тяжкие': ['Breaking Bad'],
    'Драйв': ['Drive'], 'Судья Дредд': ['Dredd'], 'Цельнометаллическая оболочка': ['Full Metal Jacket'],
    'Безумный Макс': ['Mad Max'], 'Автостопом по галактике': ["The Hitchhiker's Guide to the Galaxy"],
    'Чёрное зеркало': ['Black Mirror'], 'Начало': ['Inception'], 'Интерстеллар': ['Interstellar'],
    'Мистер Робот': ['Mr. Robot', 'fsociety'], 'Твин Пикс': ['Twin Peaks'], 'Зачарованные': ['Charmed'],
    'Настоящий детектив': ['True Detective'], 'Дэдпул': ['Deadpool', 'Marvel'], 'Люди Икс': ['X-Men', 'Marvel'],
    'Локи': ['Loki', 'Marvel'], 'Звёздный путь': ['Star Trek'], 'Терминатор': ['Terminator', 'Skynet'],
    'Бегущий по лезвию': ['Blade Runner', 'Tyrell'], 'Парк Юрского периода': ['Jurassic Park'],
    'Люди в чёрном': ['Men in Black', 'MIB'], 'Хранители': ['Watchmen'], 'Лицо со шрамом': ['Scarface'],
    'Сыны анархии': ['Sons of Anarchy'], 'Леон': ['Leon', 'The Professional'], 'Матрица': ['The Matrix'],
    'Доктор Кто': ['Doctor Who', 'TARDIS'], 'Ворон': ['The Crow'], 'Заводной апельсин': ['A Clockwork Orange'],
    'Голодные игры': ['The Hunger Games'], 'Очень странные дела': ['Stranger Things', 'Dungeons & Dragons'],
    'Вилли Вонка': ['Willy Wonka', 'Wonka'], 'Пацаны': ['The Boys'], 'Крёстный отец': ['The Godfather'],
    'Острые козырьки': ['Peaky Blinders'], 'Уэнсдей': ['Wednesday', 'Nevermore'], 'Ходячие мертвецы': ['The Walking Dead'],
    'Годзилла': ['Godzilla'], 'Остаться в живых': ['Lost', 'Dharma'], 'Эквилибриум': ['Equilibrium'],
    'Джокер': ['Joker', 'DC'], 'Ведьма из Блэр': ['The Blair Witch Project'], 'Малефисента': ['Maleficent'],
    'Стражи Галактики': ['Guardians of the Galaxy', 'Marvel'], 'Хищник': ['Predator'],
    'Кремниевая долина': ['Silicon Valley', 'Pied Piper'], 'Сверхъестественное': ['Supernatural'],
    'Игра в кальмара': ['Squid Game'], 'Миротворец': ['Peacemaker', 'DC'],
}
CORRECTIONS = {
    ('RoundFlags', 64): ('🇳🇿', 'На изображении Новая Зеландия: четыре красные звезды. В Telegram ошибочно указан fallback Австралии.'),
    ('TopicIcons', 30): ('🌧️', 'На изображении дождь; исходный fallback обозначает снег.'),
    ('TopicIcons', 35): ('💥', 'Изображён взрыв, а не лицо с взрывающейся головой.'),
    ('TopicIcons', 52): ('🕒', 'Изображены часы с круговыми стрелками, а не магазин.'),
    ('TopicIcons', 83): ('🍀', 'Изображена подкова. Клевер использован как приближённый fallback удачи.'),
    ('TopicIcons', 94): ('🧴', 'Изображён флакон с дозатором, а не губка.'),
    ('TopicIcons', 104): ('🐷', 'Изображена копилка, а не урна для голосования.'),
    ('TopicIcons', 151): ('🍼', 'Изображена пустышка; бутылочка использована как приближённый fallback.'),
    ('TopicIcons', 154): ('♀️', 'Изображён женский символ, а не пожилая женщина.'),
    ('TopicIcons', 155): ('♂️', 'Изображён мужской символ, а не седой мужчина.'),
    ('AnimalIcons', 40): ('🦆', 'По широкому клюву изображена утка; исходный fallback обозначает гуся.'),
}
REVIEW = {
    ('RoundFlags', 38): 'Исходный fallback — Чад. Триколор близок к флагу Румынии; по маленькому превью оттенок синего не позволяет уверенно их различить.',
    ('GameIcons', 96): 'Авторский слой называется 92_Heroes. Эмблема отнесена к Heroes of Might and Magic; конкретная часть серии не установлена.',
}


def key_for(pack, name, used):
    stem = re.sub(r'[^a-z0-9]+', '_', ''.join(LETTERS.get(c, c) for c in name.lower())).strip('_')
    base = f'{pack.lower()}_{stem}'[:100].rstrip('_')
    candidate = base
    index = 2
    while candidate in used:
        candidate = f'{base}_{index}'
        index += 1
    used.add(candidate)
    return candidate


def cell(value):
    return str(value).replace('|', '&#124;').replace('\n', ' ')


def main(write_catalog=False):
    layers = json.loads((CACHE / 'animation-layer-names.json').read_text(encoding='utf-8'))
    catalog_path = ROOT / 'references' / 'emoji-catalog.md'
    original = catalog_path.read_text(encoding='utf-8')
    existing_ids = set(re.findall(r'\|\s*(\d{15,22})\s*\|', original))
    used_keys = set(re.findall(r'^\|\s*([^|]+?)\s*\|\s*\d{15,22}\s*\|', original, re.MULTILINE))
    existing_keys = {eid: key.strip() for key, eid in re.findall(r'^\|\s*([^|]+?)\s*\|\s*(\d{15,22})\s*\|', original, re.MULTILINE)}
    section_numbers = [int(n) for n in re.findall(r'^## Section (\d+)', original, re.MULTILINE)]
    next_section = max(section_numbers, default=0) + 1
    document = {'schema_version': 1, 'reviewed_on': '2026-10-03', 'method': 'Manual visual review of all previews, rendered TGS frames and original animation layer names; Telegram fallback checked separately.', 'packs': []}
    metadata_path = ROOT / 'data' / 'emoji-packs.json'
    previous_document = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {'packs': []}
    new_rows = []
    updated = original
    seen = set()
    for name, (title, category, usage, default_tags, monochrome) in CONFIG.items():
        metadata = json.loads((CACHE / f'{name}.json').read_text(encoding='utf-8'))
        labels = [line.split('|') for line in (ROOT / 'data' / 'labels' / f'{name}.txt').read_text(encoding='utf-8').splitlines() if line.strip()]
        assert len(labels) == len(metadata['stickers']), name
        pack = {'name': name, 'telegram_title': metadata['title'], 'title_ru': title, 'category': category, 'url': f'https://t.me/addemoji/{name}', 'usage': usage, 'count': len(labels), 'items': []}
        for index, (sticker, label) in enumerate(zip(metadata['stickers'], labels), 1):
            title_ru, subcategory = label
            eid = sticker['custom_emoji_id']
            assert eid not in seen, f'Duplicate ID: {eid}'
            seen.add(eid)
            source_names = layers.get(name, {}).get(f'{index:03d}', [])
            author = next((s for s in source_names if re.match(r'^!?\d+_[A-Za-zА-Яа-я]', s)), '')
            aliases = []
            if author:
                aliases.append(re.sub(r'^!?\d+_', '', author).replace('_', ' '))
            if name == 'MovieIcons':
                for prefix, values in MOVIE_ALIASES.items():
                    if title_ru.startswith(prefix):
                        aliases.extend(values)
            if name == 'GameEmoji':
                aliases.extend([title_ru.split(' — ', 1)[0], 'геймерский сленг'])
            fallback = sticker.get('emoji') or '✨'
            notes = []
            if (name, index) in CORRECTIONS:
                fallback, note = CORRECTIONS[name, index]
                notes.append(note)
            if (name, index) in REVIEW:
                notes.append(REVIEW[name, index])
            if name == 'RoundFlags' and index in [13, 58]:
                notes.append('Два разных custom_emoji_id имеют одинаковое превью флага Индии. Оба ID сохранены.')
            if name == 'GameEmoji' and index == 3:
                notes.append('QQ имеет несколько значений; в этой анимации присутствует приветственный жест рукой.')
            if name == 'GameEmoji' and index == 47:
                notes.append('DM может означать deathmatch или direct message; контекст выбирается при использовании.')
            if name == 'MovieIcons' and index == 39:
                notes.append('В авторском слое указан Maniac nbp, на эмблеме написано NPB; название дано без спорного раскрытия сокращения.')
            tags = list(dict.fromkeys([*default_tags, category, subcategory, *aliases]))
            item = {'pack_index': index, 'emoji_id': eid, 'key': existing_keys.get(eid) or key_for(name, title_ru, used_keys), 'name_ru': title_ru, 'category': category, 'subcategory': subcategory, 'tags': tags, 'fallback': fallback, 'original_fallback': sticker.get('emoji', ''), 'is_animated': sticker['is_animated'], 'is_video': sticker['is_video'], 'monochrome': monochrome, 'file_unique_id': sticker['file_unique_id'], 'identification': 'visual_and_author_layer' if author else 'visual_and_telegram_metadata', 'author_layer': author, 'needs_review': (name, index) in REVIEW, 'notes': notes, 'preview_sha256': hashlib.sha256((CACHE / name / f'{index:03d}.webp').read_bytes()).hexdigest()}
            pack['items'].append(item)
        new_items = [item for item in pack['items'] if item['emoji_id'] not in existing_ids]
        if new_items:
            updated += f'\n\n## Section {next_section} — {title}\nPack: {pack["url"]}\n\nКатегория: {category}. {usage}\n\n| key suggestion | emoji_id | description | fallback |\n|---|---|---|---|\n'
            for item in new_items:
                updated += f'| {item["key"]} | {item["emoji_id"]} | {cell(item["name_ru"])} | {item["fallback"]} |\n'
                new_rows.append(item)
            next_section += 1
        document['packs'].append(pack)
        path = ROOT / 'references' / 'packs' / f'{name}.md'
        path.parent.mkdir(exist_ok=True)
        text = f'# {title}\n\nИсточник: [{metadata["title"]}]({pack["url"]}). Проверено 3 октября 2026 года через Telegram Bot API и визуальный просмотр.\n\nКатегория: **{category}**.\n\nПрименение: {usage}\n\n{len(labels)} эмодзи; анимированных: {sum(item["is_animated"] for item in pack["items"])}. Подкатегорий: {len({item["subcategory"] for item in pack["items"]})}.\n\n| № | Название | Подкатегория | custom_emoji_id | key | fallback | Примечание |\n|---|---|---|---|---|---|---|\n'
        for item in pack['items']:
            note = ('Требует уточнения. ' if item['needs_review'] else '') + ' '.join(item['notes'])
            text += '| ' + ' | '.join(cell(value) for value in [item['pack_index'], item['name_ru'], item['subcategory'], item['emoji_id'], item['key'], item['fallback'], note]) + ' |\n'
        path.write_text(text, encoding='utf-8', newline='\n')
    previous_packs = {pack['name']: pack for pack in previous_document['packs']}
    previous_packs.update({pack['name']: pack for pack in document['packs']})
    merged_document = {**previous_document, 'packs': list(previous_packs.values())}
    metadata_path.write_text(json.dumps(merged_document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    assert len(seen) == 884
    if write_catalog and new_rows:
        if catalog_path.read_text(encoding='utf-8') != original:
            raise RuntimeError('Catalog changed during import; retry.')
        catalog_path.write_text(updated, encoding='utf-8', newline='\n')
        ids_path = ROOT / 'emoji-ids.txt'
        ids_bytes = ids_path.read_bytes()
        ids = ids_bytes.decode('utf-8')
        existing_lines = set(re.findall(r'^(\d{15,22})\b', ids, re.MULTILINE))
        additions = ''.join(f'\n{item["emoji_id"]} - {item["name_ru"]}' for item in new_rows if item['emoji_id'] not in existing_lines) + '\n'
        ids_path.write_bytes(ids_bytes + additions.encode('utf-8'))
    report = ROOT / 'references' / ('pack-analysis-initial-eight.md' if len(previous_packs) > len(CONFIG) else 'pack-analysis.md')
    text = '# Анализ восьми паков Telegram Emoji\n\nПроверено 3 октября 2026 года. 884 разных custom_emoji_id: 610 анимированных и 274 статичных. Для каждой записи сохранены русское название, основная категория, подкатегория, уникальный key, fallback, поисковые теги и источник.\n\nАвторские названия слоёв использованы как свидетельство замысла автора, а не как проверка официальности эмблем. Редакционные категории и рекомендации по применению предложены при анализе. Неоднозначные случаи отмечены отдельно.\n\n| Пак | Название раздела | Категория | Всего | Анимированных | Подкатегорий | Применение |\n|---|---|---|---|---|---|---|\n'
    for pack in document['packs']:
        text += '| ' + ' | '.join([f'[{pack["name"]}]({pack["url"]})', f'[{pack["title_ru"]}](packs/{pack["name"]}.md)', pack['category'], str(pack['count']), str(sum(item['is_animated'] for item in pack['items'])), str(len({item['subcategory'] for item in pack['items']})), pack['usage']]) + ' |\n'
    text += '\n## Особенности и исправления\n\n- RoundFlags: исправлен fallback Новой Зеландии; два разных ID флага Индии сохранены, хотя их превью совпадают.\n- GameIcons и MovieIcons: эмблемы сверены с именами слоёв в оригинальных TGS-анимациях. Название игры или франшизы не заменено случайной подписью «значок».\n- GameEmoji: буквенные сокращения дополнены русским смыслом; грубые реакции выделены в отдельную подкатегорию. QQ и DM имеют пояснения к контексту.\n- EffectEmoji: названы сами визуальные эффекты, а не лица из исходных fallback.\n- TopicIcons: названы реальные предметы и символы, включая подкову, копилку, дозатор, пустышку, женский и мужской символы, логотип Telegram.\n- AnimalIcons: утка и гусь разделены по изображению, насекомые и паукообразные разведены по подкатегориям.\n- Чёрные эмблемы требуют светлого отображения на тёмном фоне сайта.\n\n## Требуют уточнения\n\n'
    for pack in document['packs']:
        for item in pack['items']:
            if item['needs_review']:
                text += f'- {pack["name"]} №{item["pack_index"]}, `{item["emoji_id"]}` — {item["name_ru"]}: {" ".join(item["notes"])}\n'
    text += '\n## Данные и совместимость\n\nОсновной каталог сохраняет четыре привычные колонки. Полные сведения хранятся в `data/emoji-packs.json`, а подробные таблицы — в `references/packs/`. Дедупликация проводится по custom_emoji_id: одинаковый рисунок с другим ID остаётся отдельной доступной записью.\n'
    report.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'packs': len(document['packs']), 'items': len(seen), 'new_catalog_items': len(new_rows), 'needs_review': len(REVIEW), 'catalog_written': bool(write_catalog and new_rows)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-catalog', action='store_true')
    main(parser.parse_args().write_catalog)
