"""Telegram thumbnail adapter. Credentials are supplied only at construction."""
from __future__ import annotations

import json
import shutil
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


class TelegramPreviewClient:
    def __init__(self, token: str, site_dir: Path, preview_dir: Path):
        if not token:
            raise ValueError('BOT_TOKEN not set')
        self.token = token
        self.api = f'https://api.telegram.org/bot{token}'
        self.site_dir = site_dir
        self.image_dir = site_dir / 'images'
        self.preview_dir = preview_dir

    def get(self, method: str, **params) -> dict:
        url = f"{self.api}/{method}?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())

    def post_json(self, method: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req  = urllib.request.Request(
            f"{self.api}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    def _download_one(self, sticker: dict) -> tuple[str, str] | None:
        """Download thumbnail for one sticker. Returns (emoji_id, relative_path) or None."""
        eid   = sticker.get("custom_emoji_id")
        thumb = sticker.get("thumbnail") or sticker.get("thumb")
        if not eid or not thumb:
            return None
        dest = self.image_dir / f"{eid}.png"
        if dest.exists() and dest.stat().st_size:
            return eid, dest.relative_to(self.site_dir).as_posix()
        for attempt in range(3):
            try:
                fdata = self.get("getFile", file_id=thumb["file_id"])
                file_path = fdata["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                partial = dest.with_suffix('.part')
                with urllib.request.urlopen(file_url, timeout=30) as response, partial.open('wb') as output:
                    shutil.copyfileobj(response, output)
                partial.replace(dest)
                return eid, dest.relative_to(self.site_dir).as_posix()
            except Exception as error:
                if attempt == 2:
                    print(f"    ✗ {eid}: {str(error).replace(self.token, '[redacted]')}")
        return None

    def fetch(self, emoji_ids: list[str], workers: int = 20) -> dict[str, str]:
        """Returns {emoji_id: local_image_path} — downloads missing in parallel."""
        self.image_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, str] = {}
        to_fetch: list[str] = []

        for eid in emoji_ids:
            cached = self.image_dir / f"{eid}.png"
            override = self.preview_dir / f"{eid}.png"
            if override.exists():
                shutil.copy2(override, cached)
                result[eid] = cached.relative_to(self.site_dir).as_posix()
            elif cached.exists() and cached.stat().st_size:
                result[eid] = cached.relative_to(self.site_dir).as_posix()
            else:
                to_fetch.append(eid)

        if not to_fetch:
            return result

        print(f"  Fetching thumbnails for {len(to_fetch)} emoji (×{workers} parallel)…")

        # Resolve sticker metadata in batches of 200
        stickers: list[dict] = []
        for i in range(0, len(to_fetch), 200):
            batch = to_fetch[i : i + 200]
            try:
                data = self.post_json("getCustomEmojiStickers", {"custom_emoji_ids": batch})
            except Exception as e:
                print(f"  Warning: getCustomEmojiStickers failed: {str(e).replace(self.token, '[redacted]')}")
                continue
            if not data.get("ok"):
                print(f"  Warning: self.api error: {data.get('description')}")
                continue
            stickers.extend(data.get("result", []))

        # Download in parallel
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._download_one, s): s for s in stickers}
            done = 0
            for future in as_completed(futures):
                res = future.result()
                if res:
                    eid, path = res
                    result[eid] = path
                    done += 1
                    if done % 20 == 0 or done == len(stickers):
                        print(f"    {done}/{len(stickers)} downloaded")

        return result
