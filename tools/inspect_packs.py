"""Download Telegram pack previews and make numbered sheets for manual review."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bot
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFont
from rlottie_python import LottieAnimation

ROOT = bot.REPO_DIR / '.runtime' / 'packs'
PACKS = ['RoundFlags', 'GameIcons', 'GameEmoji', 'EffectEmoji', 'CuteEmoji', 'TopicIcons', 'MovieIcons', 'AnimalIcons']


async def download_previews():
    ROOT.mkdir(parents=True, exist_ok=True)
    limit = asyncio.Semaphore(12)
    async with Bot(bot.BOT_TOKEN) as client:
        async def one(pack, index, sticker):
            directory = ROOT / pack
            directory.mkdir(exist_ok=True)
            target = directory / f'{index:03d}.webp'
            if target.exists():
                return
            thumbnail = sticker.get('thumbnail')
            file_id = thumbnail['file_id'] if thumbnail else sticker['file_id']
            async with limit:
                for attempt in range(3):
                    try:
                        await client.download(file_id, destination=target)
                        return
                    except Exception:
                        if target.exists():
                            target.unlink()
                        if attempt == 2:
                            print(f'Preview unavailable: {pack} #{index}', flush=True)
                            return
                        await asyncio.sleep(attempt + 1)

        for name in PACKS:
            metadata_file = ROOT / f'{name}.json'
            if not metadata_file.exists():
                fetched = await client.get_sticker_set(name)
                metadata_file.write_text(json.dumps(fetched.model_dump(mode='json', exclude_none=True), ensure_ascii=False, indent=2), encoding='utf-8')
            pack = json.loads(metadata_file.read_text(encoding='utf-8'))
            await asyncio.gather(*(one(name, i, sticker) for i, sticker in enumerate(pack['stickers'], 1)))
            print(f'{name}: downloaded {len(list((ROOT / name).glob("*.webp")))}/{len(pack["stickers"])} previews', flush=True)


def make_sheets(animated_frame=False):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    heading = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 22)
    for name in PACKS:
        pack = json.loads((ROOT / f'{name}.json').read_text(encoding='utf-8'))
        for start in range(0, len(pack['stickers']), 48):
            subset = pack['stickers'][start:start + 48]
            sheet = Image.new('RGB', (8 * 126, 52 + ((len(subset) + 7) // 8) * 137), '#17202e')
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 12), f'{name} — {start + 1}–{start + len(subset)}', font=heading, fill='white')
            for position, sticker in enumerate(subset):
                index = start + position + 1
                left = (position % 8) * 126
                top = 52 + (position // 8) * 137
                background = '#e2e8f0' if name in ['GameIcons', 'MovieIcons', 'TopicIcons', 'AnimalIcons'] else '#283649'
                draw.rounded_rectangle((left + 3, top + 3, left + 122, top + 132), radius=9, fill=background)
                source = ROOT / name / f'{index:03d}.webp'
                if source.exists():
                    if animated_frame and sticker['is_animated']:
                        animation = LottieAnimation.from_tgs(str(ROOT / name / f'{index:03d}.tgs'))
                        icon = animation.render_pillow_frame(animation.lottie_animation_get_totalframe() // 2, width=100, height=100)
                    else:
                        icon = Image.open(source).convert('RGBA')
                    icon.thumbnail((100, 100))
                    sheet.paste(icon, (left + (126 - icon.width) // 2, top + 7 + (100 - icon.height) // 2), icon)
                draw.text((left + 45, top + 110), str(index), font=font, fill='#111827' if name in ['GameIcons', 'MovieIcons', 'TopicIcons', 'AnimalIcons'] else 'white')
            suffix = '-mid' if animated_frame else ''
            target = ROOT / f'{name}{suffix}-{start // 48 + 1:02d}.png'
            sheet.save(target)
            print(target, flush=True)


if __name__ == '__main__':
    asyncio.run(download_previews())
    make_sheets()
