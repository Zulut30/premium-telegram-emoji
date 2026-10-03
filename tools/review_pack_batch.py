"""Cache a submitted pack batch and make numbered visual review sheets."""
import argparse
import asyncio
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from config import load_environment
from premium_emoji.paths import DEFAULT_PATHS
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = DEFAULT_PATHS.root
CACHE = ROOT / '.runtime' / 'packs'


async def fetch(names, originals=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(16)
    load_environment(DEFAULT_PATHS.root)
    async with Bot(os.environ.get("BOT_TOKEN", "")) as client:
        async def metadata(name):
            path = CACHE / f'{name}.json'
            if not path.exists():
                async with semaphore:
                    try:
                        pack = await client.get_sticker_set(name)
                    except Exception as error:
                        print(f'{name}: metadata unavailable ({type(error).__name__})', flush=True)
                        return None
                path.write_text(json.dumps(pack.model_dump(mode='json', exclude_none=True), ensure_ascii=False, indent=2), encoding='utf-8')
            return json.loads(path.read_text(encoding='utf-8'))

        packs = await asyncio.gather(*(metadata(name) for name in names))
        print(json.dumps({'packs_available': sum(p is not None for p in packs), 'items': sum(len(p['stickers']) for p in packs if p)}, ensure_ascii=False), flush=True)
        async def download(name, index, sticker, original):
            directory = CACHE / name
            directory.mkdir(exist_ok=True)
            suffix = '.tgs' if original else '.webp'
            path = directory / f'{index:03d}{suffix}'
            if path.exists() and path.stat().st_size:
                return True
            thumb = sticker.get('thumbnail')
            file_id = sticker['file_id'] if original or not thumb else thumb['file_id']
            async with semaphore:
                for attempt in range(3):
                    try:
                        await client.download(file_id, destination=path)
                        return True
                    except Exception:
                        if attempt == 2:
                            print(f'{name} #{index}: {suffix} unavailable', flush=True)
                            return False
                        await asyncio.sleep(attempt + 1)
            return False

        for pack in filter(None, packs):
            name = pack['name']
            tasks = [download(name, i, s, False) for i, s in enumerate(pack['stickers'], 1)]
            if originals:
                tasks += [download(name, i, s, True) for i, s in enumerate(pack['stickers'], 1) if s['is_animated']]
            results = await asyncio.gather(*tasks)
            print(f'{name}: {len(pack["stickers"])} entries; {sum(results)}/{len(results)} files cached', flush=True)
    return [p for p in packs if p]


def make_sheets(names, size=64):
    heading = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 21)
    number_font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for name in names:
        path = CACHE / f'{name}.json'
        if not path.exists():
            continue
        pack = json.loads(path.read_text(encoding='utf-8'))
        for start in range(0, len(pack['stickers']), size):
            subset = pack['stickers'][start:start + size]
            canvas = Image.new('RGB', (8 * 136, 46 + ((len(subset) + 7) // 8) * 134), '#182333')
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 10), f'{name}  {start + 1}-{start + len(subset)}', fill='white', font=heading)
            for offset, sticker in enumerate(subset):
                index = start + offset + 1
                source = CACHE / name / f'{index:03d}-frame.png'
                if not source.exists():
                    source = CACHE / name / f'{index:03d}.webp'
                if not source.exists():
                    continue
                icon = Image.open(source).convert('RGBA')
                icon.thumbnail((108, 108))
                stat = ImageStat.Stat(icon.convert('RGB'), mask=icon.getchannel('A'))
                light = sum(stat.mean) / 3 < 120
                x, y = (offset % 8) * 136, 46 + (offset // 8) * 134
                background = '#e5e7eb' if light else '#2b394c'
                draw.rounded_rectangle((x + 3, y + 3, x + 133, y + 131), radius=7, fill=background)
                canvas.paste(icon, (x + (136 - icon.width) // 2, y + 5 + (108 - icon.height) // 2), icon)
                draw.text((x + 52, y + 111), str(index), fill='#111827' if light else 'white', font=number_font)
            canvas.save(CACHE / f'{name}-review-{start // size + 1:02d}.png')


def layer_names(names):
    result = {}
    for name in names:
        result[name] = {}
        for path in (CACHE / name).glob('*.tgs'):
            data = json.loads(gzip.decompress(path.read_bytes()))
            result[name][path.stem] = sorted(set(re.findall(r'"nm"\s*:\s*"([^"\\]+)"', json.dumps(data, ensure_ascii=False))))
    path = CACHE / 'animation-layer-names.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    previous.update(result)
    path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=Path)
    parser.add_argument('--originals', action='store_true')
    parser.add_argument('--sheets-only', action='store_true')
    args = parser.parse_args()
    names = json.loads(args.batch.read_text(encoding='utf-8'))['packs']
    if not args.sheets_only:
        asyncio.run(fetch(names, args.originals))
    make_sheets(names)
    if args.originals:
        layer_names(names)
