"""Pull league data (current season + every prior Sleeper season) into data/raw.

Past, completed seasons are immutable, so they are fetched once and skipped
afterwards unless --force is passed.

    python scripts/fetch.py
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
RAW = ROOT / "data" / "raw"
MAX_WEEK = 18


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")


def fetch_season(league_id, force=False):
    league = sleeper.get(f"/league/{league_id}")
    season = league["season"]
    out = RAW / "seasons" / f"{season}.json"
    if out.exists() and not force:
        prev = json.loads(out.read_text(encoding="utf-8"))
        if prev["league"]["status"] == "complete" and "winners_bracket" in prev:
            print(f"{season}: complete, skipping")
            return prev
    print(f"{season}: fetching ({league['status']})")
    bundle = {
        "league": league,
        "users": sleeper.get(f"/league/{league_id}/users"),
        "rosters": sleeper.get(f"/league/{league_id}/rosters"),
        "winners_bracket": sleeper.get(f"/league/{league_id}/winners_bracket"),
        "losers_bracket": sleeper.get(f"/league/{league_id}/losers_bracket"),
        "matchups": {},
        "transactions": {},
    }
    for week in range(1, MAX_WEEK + 1):
        m = sleeper.get(f"/league/{league_id}/matchups/{week}")
        if not m:
            break
        bundle["matchups"][str(week)] = m
        bundle["transactions"][str(week)] = sleeper.get(f"/league/{league_id}/transactions/{week}")
    write(out, bundle)
    return bundle


def update_players(bundles):
    """Slim name/position table for every player that has ever been rostered."""
    ids = set()
    for b in bundles:
        for r in b["rosters"]:
            ids.update(r.get("players") or [])
        for week in b["matchups"].values():
            for m in week:
                ids.update(m.get("players") or [])
    path = RAW / "players_slim.json"
    slim = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    db = sleeper.nfl_players()
    for pid in ids:
        if pid in db:
            slim[pid] = sleeper.slim_player(pid, db[pid])
    write(path, slim)
    print(f"players_slim: {len(slim)} players")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch completed seasons too")
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config" / "league.json").read_text(encoding="utf-8"))

    bundles, league_id = [], cfg["league_id"]
    while league_id and league_id != "0":
        b = fetch_season(league_id, args.force)
        bundles.append(b)
        league_id = b["league"].get("previous_league_id")

    write(RAW / "state.json", sleeper.get("/state/nfl"))
    update_players(bundles)


if __name__ == "__main__":
    main()
