#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

PROJECT = Path(__file__).resolve().parents[1]
INVENTORY_DIR = PROJECT / "public" / "data" / "inventories"
MANIFEST_PATH = PROJECT / "public" / "data" / "inventories.json"
COVER_DIR = PROJECT / "public" / "covers"
API_URL = "https://boardgamegeek.com/xmlapi2/thing"
USER_AGENT = "BeiguanBoardgameInventory/1.0"


def issue_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^###\s+(.+?)\s*$", body, re.MULTILINE))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group(1).strip()] = body[match.end():end].strip()
    return sections


def parse_games(raw: str) -> list[str]:
    games: dict[str, None] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.fullmatch(r"\d{1,9}", line)
        if not match:
            raise ValueError(f"无法识别这一行：{line}")
        games[line] = None
    if not games:
        raise ValueError("BGG ID 清单不能为空")
    if len(games) > 500:
        raise ValueError("一次最多提交 500 款桌游")
    return list(games)


def request_bytes(url: str, token: str = "", attempts: int = 5) -> bytes:
    headers = {"Accept": "application/xml,image/*", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in (202, 429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        time.sleep(min(5 * (attempt + 1), 20))
    raise RuntimeError(f"请求失败：{last_error}")


def value(item: ET.Element, tag: str) -> str:
    element = item.find(tag)
    return element.get("value", "") if element is not None else ""


def number(raw: str):
    try:
        result = float(raw)
        return int(result) if result.is_integer() else round(result, 4)
    except (TypeError, ValueError):
        return None


def is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text)) and not bool(re.search(r"[\u3040-\u30ff\uac00-\ud7af]", text))


def best_players(item: ET.Element) -> list[str]:
    poll = next((node for node in item.findall("poll") if node.get("name") == "suggested_numplayers"), None)
    if poll is None:
        return []
    ranked = []
    for results in poll.findall("results"):
        best = next((entry for entry in results.findall("result") if entry.get("value") == "Best"), None)
        votes = int(best.get("numvotes", "0")) if best is not None else 0
        if votes:
            ranked.append((results.get("numplayers", ""), votes))
    if not ranked:
        return []
    highest = max(votes for _, votes in ranked)
    return [players for players, votes in ranked if votes == highest and players]


def parse_item(item: ET.Element) -> tuple[dict, str]:
    names = item.findall("name")
    original = next((node.get("value", "") for node in names if node.get("type") == "primary"), "")
    local = next((node.get("value", "") for node in names if node.get("type") == "alternate" and is_chinese(node.get("value", ""))), original)
    minimum, maximum = number(value(item, "minplayers")), number(value(item, "maxplayers"))
    supported = [str(count) for count in range(minimum, maximum + 1)] if isinstance(minimum, int) and isinstance(maximum, int) else []
    rank_node = next((node for node in item.findall("./statistics/ratings/ranks/rank") if node.get("name") == "boardgame"), None)
    bgg_id = item.get("id", "")
    image = (item.findtext("image") or "").strip()
    game = {
        "id": f"bgg-{bgg_id}",
        "bggId": bgg_id,
        "name": local or original or f"BGG {bgg_id}",
        "originalName": original,
        "cover": f"public/covers/bgg-{bgg_id}.webp" if image else "",
        "players": str(minimum) if minimum == maximum and minimum else (f"{minimum}-{maximum}" if minimum and maximum else ""),
        "supportedPlayers": supported,
        "bestPlayers": best_players(item),
        "playingTime": number(value(item, "playingtime")),
        "weight": number(value(item, "./statistics/ratings/averageweight")),
        "types": [node.get("value", "") for node in item.findall("link") if node.get("type") == "boardgamecategory"],
        "mechanics": [node.get("value", "") for node in item.findall("link") if node.get("type") == "boardgamemechanic"],
        "rating": number(value(item, "./statistics/ratings/average")),
        "rank": number(rank_node.get("value", "")) if rank_node is not None else None,
    }
    return game, image


def fetch_games(requested: list[str], token: str) -> list[tuple[dict, str]]:
    found: dict[str, tuple[dict, str]] = {}
    ids = list(requested)
    for start in range(0, len(ids), 20):
        batch = ids[start:start + 20]
        query = f"{API_URL}?id={','.join(batch)}&stats=1"
        root = ET.fromstring(request_bytes(query, token))
        for item in root.findall("item"):
            bgg_id = item.get("id", "")
            found[bgg_id] = parse_item(item)
        if start + 20 < len(ids):
            time.sleep(2)
    missing = [bgg_id for bgg_id in ids if bgg_id not in found]
    if missing:
        raise ValueError(f"BGG 未返回这些 ID：{', '.join(missing)}")
    return [found[bgg_id] for bgg_id in ids]


def save_cover(game: dict, image_url: str) -> None:
    if not image_url:
        return
    destination = PROJECT / game["cover"]
    if destination.is_file():
        return
    source = request_bytes(image_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(source)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((900, 900), Image.Resampling.LANCZOS)
        image.save(destination, "WEBP", quality=78, method=6)


def rebuild_manifest() -> None:
    inventories = []
    for path in sorted(INVENTORY_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        games = []
        for existing in payload.get("games", []):
            if not re.fullmatch(r"\d+", str(existing.get("bggId") or "").strip()):
                continue
            game = dict(existing)
            game.pop("playStatus", None)
            games.append(game)
        if games != payload.get("games", []):
            payload["games"] = games
            payload.setdefault("meta", {})["count"] = len(games)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        meta = payload.get("meta", {})
        inventories.append({
            "id": str(meta.get("id") or path.stem),
            "name": str(meta.get("name") or path.stem),
            "file": f"public/data/inventories/{path.name}",
            "count": len(games),
        })
    manifest = {"generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), "inventories": inventories}
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    token = os.environ.get("BGG_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("缺少 BGG_API_TOKEN")
    event_path = Path(os.environ.get("ISSUE_EVENT_PATH") or os.environ.get("GITHUB_EVENT_PATH", ""))
    event = json.loads(event_path.read_text(encoding="utf-8"))
    issue = event["issue"]
    login = issue["user"]["login"]
    owner_id = "hou" if login.lower() == "turft" else login.lower()
    if not re.fullmatch(r"[a-z0-9-]{1,39}", owner_id):
        raise ValueError("GitHub 用户名无法转换为库存标识")
    sections = issue_sections(issue.get("body") or "")
    display_name = sections.get("显示名称", "").strip()
    if not display_name or len(display_name) > 40:
        raise ValueError("显示名称不能为空且不能超过 40 个字符")
    requested = parse_games(sections.get("BGG ID 清单", ""))
    games_with_images = fetch_games(requested, token)
    for game, image_url in games_with_images:
        save_cover(game, image_url)
    payload = {
        "meta": {
            "id": owner_id,
            "name": display_name,
            "github": login,
            "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "count": len(games_with_images),
        },
        "games": [game for game, _ in games_with_images],
    }
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    (INVENTORY_DIR / f"{owner_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rebuild_manifest()


if __name__ == "__main__":
    main()
