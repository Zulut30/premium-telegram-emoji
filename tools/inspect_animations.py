"""Cache TGS animations and render three frames for visual analysis."""
import asyncio
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFont
from rlottie_python import LottieAnimation

ROOT = bot.REPO_DIR / '.runtime' / 'packs'


async def download():
    limit = asyncio.Semaphore(12)
    async with Bot(bot.BOT_TOKEN) as client:
        async def one(name, index, sticker):
            target = ROOT / name / f'{index:03d}.tgs'
            if target.exists():
                return
            async with limit:
                await client.download(sticker['file_id'], destination=target)

        for source in ROOT.glob('*.json'):
            pack = json.loads(source.read_text(encoding='utf-8'))
            if 'stickers' not in pack:
                continue
            await asyncio.gather(*(one(pack['name'], index, sticker) for index, sticker in enumerate(pack['stickers'], 1) if sticker['is_animated']))
            print(pack['name'] + ': originals cached', flush=True)


def render(name, indices):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    for start in range(0, len(indices), 12):
        subset = indices[start:start + 12]
        sheet = Image.new('RGB', (940, len(subset) * 115 + 35), '#17202e')
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 8), name + ' — начало / середина / конец', font=font, fill='white')
        for row, index in enumerate(subset):
            anim = LottieAnimation.from_tgs(str(ROOT / name / f'{index:03d}.tgs'))
            total = anim.lottie_animation_get_totalframe()
            draw.text((12, 45 + row * 115), str(index), font=font, fill='white')
            for column, frame in enumerate([0, total // 2, max(0, total - 2)]):
                rendered = anim.render_pillow_frame(frame, width=100, height=100)
                left = 72 + column * 280
                top = 35 + row * 115
                draw.rectangle((left, top, left + 120, top + 108), fill='#e2e8f0')
                sheet.paste(rendered, (left + 10, top + 4), rendered)
                draw.rectangle((left + 130, top, left + 250, top + 108), fill='#283649')
                sheet.paste(rendered, (left + 140, top + 4), rendered)
        output = ROOT / f'{name}-frames-{start // 12 + 1:02d}.png'
        sheet.save(output)
        print(output, flush=True)


if __name__ == '__main__':
    asyncio.run(download())
    names = {}
    for pack in ROOT.glob('*.json'):
        if pack.name == 'animation-layer-names.json':
            continue
        name = pack.stem
        names[name] = {}
        for source in (ROOT / name).glob('*.tgs'):
            data = json.loads(gzip.decompress(source.read_bytes()))
            names[name][source.stem] = sorted(set(__import__('re').findall(r'"nm"\s*:\s*"([^"\\]+)"', json.dumps(data, ensure_ascii=False))))
    (ROOT / 'animation-layer-names.json').write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding='utf-8')
