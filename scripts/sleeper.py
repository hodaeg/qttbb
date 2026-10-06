"""Thin client for the public Sleeper API (read-only, no auth)."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.sleeper.app/v1"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
PLAYERS_TTL = 24 * 3600  # Sleeper asks for /players/nfl at most ~once a day


def get(path, retries=3):
    url = f"{BASE}{path}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                time.sleep(0.1)  # stay far below the ~1000 calls/min limit
                return json.load(r)
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def nfl_players():
    """Full NFL player DB, cached locally for 24h (it is several MB)."""
    CACHE.mkdir(exist_ok=True)
    f, meta = CACHE / "players.json", CACHE / "players.fetched_at"
    # Age comes from a sidecar timestamp, not file mtime, so it survives a CI cache restore.
    if f.exists() and meta.exists():
        try:
            if time.time() - float(meta.read_text()) < PLAYERS_TTL:
                return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    data = get("/players/nfl")
    f.write_text(json.dumps(data), encoding="utf-8")
    meta.write_text(str(time.time()))
    return data


def slim_player(pid, p):
    """Only the fields we need, so what gets committed stays small."""
    return {
        "name": p.get("full_name") or f'{p.get("first_name", "")} {p.get("last_name", "")}'.strip() or pid,
        "pos": p.get("position"),
        "team": p.get("team"),
        "injury_status": p.get("injury_status"),
    }
