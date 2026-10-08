#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

VAULT = Path(os.environ.get("BOARDGAME_VAULT", "/Users/hou/Documents/hou"))
NOTES_DIR = VAULT / "桌游"
PROJECT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = PROJECT / "public"
INVENTORY_ID = "hou"
DATA_PATH = PUBLIC_DIR / "data" / "inventories" / f"{INVENTORY_ID}.json"
MANIFEST_PATH = PUBLIC_DIR / "data" / "inventories.json"
COVER_DIR = PUBLIC_DIR / "covers"

PUBLIC_FIELDS = (
    "title", "aliases", "封面", "人数", "支持人数", "最佳人数", "时长", "重度",
    "类型", "机制", "BGG ID", "BGG名称", "BGG评分", "BGG排名", "BGG同步时间", "持有状态",
)


def scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else value
        except json.JSONDecodeError:
            return [part.strip().strip("\"'") for part in value[1:-1].split(",") if part.strip()]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return json.loads(value) if value.startswith('"') else value[1:-1].replace("''", "'")
        except json.JSONDecodeError:
            return value[1:-1]
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return float(value) if "." in value else int(value)
    return value


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    lines = text[3:end].strip("\n").splitlines()
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^([^\s][^:]*):(?:\s*(.*))?$", line)
        if not match:
            index += 1
            continue
        key, raw = match.group(1).strip(), (match.group(2) or "").strip()
        if raw:
            result[key] = scalar(raw)
            index += 1
            continue
        items = []
        lookahead = index + 1
        while lookahead < len(lines):
            item = re.match(r"^\s+-\s+(.*)$", lines[lookahead])
            if not item:
                break
            items.append(scalar(item.group(1)))
            lookahead += 1
        result[key] = items if items else ""
        index = lookahead
    return result


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def as_number(value: Any) -> float | int | None:
    try:
        number = float(value)
        return int(number) if number.is_integer() else round(number, 4)
    except (TypeError, ValueError):
        return None


def as_date(value: Any) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else ""


def cover_source(value: Any) -> Path | None:
    match = re.fullmatch(r"\[\[(.+?)\]\]", str(value or "").strip())
    if not match:
        return None
    path = VAULT / match.group(1)
    return path if path.is_file() else None


def stable_id(path: Path) -> str:
    return hashlib.sha1(path.stem.encode("utf-8")).hexdigest()[:12]


def make_cover(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.thumbnail((900, 900), Image.Resampling.LANCZOS)
        image.save(destination, "WEBP", quality=78, method=6)


def collect(output_root: Path) -> dict[str, Any]:
    games = []
    output_covers = output_root / "covers"
    output_covers.mkdir(parents=True, exist_ok=True)
    for note in sorted(NOTES_DIR.glob("*.md"), key=lambda item: item.name):
        frontmatter = parse_frontmatter(note.read_text(encoding="utf-8"))
        if str(frontmatter.get("持有状态", "")).strip() != "拥有":
            continue
        bgg_id = str(frontmatter.get("BGG ID") or "").strip()
        if not re.fullmatch(r"\d+", bgg_id):
            continue
        game_id = stable_id(note)
        source = cover_source(frontmatter.get("封面"))
        cover = ""
        if source:
            destination = output_covers / f"{game_id}.webp"
            cached = COVER_DIR / destination.name
            if cached.is_file() and cached.stat().st_mtime_ns >= source.stat().st_mtime_ns:
                shutil.copy2(cached, destination)
            else:
                make_cover(source, destination)
            cover = f"public/covers/{destination.name}"
        aliases = as_list(frontmatter.get("aliases"))
        original_name = str(frontmatter.get("BGG名称") or "").strip()
        if not original_name:
            original_name = next((name for name in aliases if not re.search(r"[\u3400-\u9fff]", name)), "")
        games.append({
            "id": game_id,
            "bggId": bgg_id,
            "name": str(frontmatter.get("title") or note.stem).strip(),
            "originalName": original_name,
            "cover": cover,
            "players": str(frontmatter.get("人数") or "").strip(),
            "supportedPlayers": as_list(frontmatter.get("支持人数")),
            "bestPlayers": as_list(frontmatter.get("最佳人数")),
            "playingTime": as_number(frontmatter.get("时长")),
            "weight": as_number(frontmatter.get("重度")),
            "types": as_list(frontmatter.get("类型")),
            "mechanics": as_list(frontmatter.get("机制")),
            "rating": as_number(frontmatter.get("BGG评分")),
            "rank": as_number(frontmatter.get("BGG排名")),
            "updatedAt": as_date(frontmatter.get("BGG同步时间")),
        })
    return {
        "meta": {
            "id": INVENTORY_ID,
            "name": "hou",
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "count": len(games),
        },
        "games": games,
    }


def content_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {game["id"]: game for game in payload.get("games", [])}


def comparable_game(game: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in game.items() if key not in ("id", "updatedAt")}


def reconcile_updated_at(previous: dict[str, Any], current: dict[str, Any]) -> None:
    old = content_map(previous)
    today = datetime.now().astimezone().date().isoformat()
    for game in current.get("games", []):
        prior = old.get(game["id"])
        if not prior:
            game["updatedAt"] = game.get("updatedAt") or today
        elif comparable_game(prior) != comparable_game(game):
            game["updatedAt"] = today
        else:
            game["updatedAt"] = prior.get("updatedAt") or game.get("updatedAt") or ""


def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old, new = content_map(previous), content_map(current)
    added = sorted((new[key]["name"] for key in new.keys() - old.keys()))
    removed = sorted((old[key]["name"] for key in old.keys() - new.keys()))
    changed = []
    for key in old.keys() & new.keys():
        if comparable_game(old[key]) != comparable_game(new[key]):
            changed.append(new[key]["name"])
    missing = [game["name"] for game in current["games"] if not game["cover"] or not game["supportedPlayers"]]
    return {
        "added": sorted(added),
        "changed": sorted(changed),
        "removed": sorted(removed),
        "missing": sorted(missing),
        "total": len(current["games"]),
        "hasChanges": bool(added or changed or removed) or old != new or not DATA_PATH.exists(),
    }


def load_previous() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"games": []}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"games": []}


def write_payload(payload: dict[str, Any], source_root: Path) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    desired = {Path(game["cover"]).name for game in payload["games"] if game["cover"]}
    for old_cover in COVER_DIR.glob("*.webp"):
        if old_cover.name not in desired:
            old_cover.unlink()
    for source in (source_root / "covers").glob("*.webp"):
        destination = COVER_DIR / source.name
        if not destination.exists() or hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            shutil.copy2(source, destination)
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inventories = []
    for inventory_path in sorted(DATA_PATH.parent.glob("*.json")):
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            meta = inventory.get("meta", {})
            inventories.append({
                "id": str(meta.get("id") or inventory_path.stem),
                "name": str(meta.get("name") or inventory_path.stem),
                "file": f"public/data/inventories/{inventory_path.name}",
                "count": len(inventory.get("games", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    manifest = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "inventories": inventories,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "write"), default="plan")
    args = parser.parse_args()
    previous = load_previous()
    with tempfile.TemporaryDirectory(prefix="boardgame-inventory-") as temporary:
        temporary_root = Path(temporary)
        current = collect(temporary_root)
        reconcile_updated_at(previous, current)
        report = compare(previous, current)
        if args.mode == "write":
            write_payload(current, temporary_root)
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
