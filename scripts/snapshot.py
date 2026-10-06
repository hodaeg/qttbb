"""Game-day snapshot: who is in each lineup, and what is each starter's injury status?

Sleeper keeps no injury history, so this is the only way to know a player was
Out when a manager left them in. Run it shortly before kickoff windows.

    python scripts/snapshot.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT


def main():
    cfg = json.loads((ROOT / "config" / "league.json").read_text(encoding="utf-8"))
    league_id = cfg["league_id"]
    state = sleeper.get("/state/nfl")
    if state.get("season_type") != "regular" and state.get("season_type") != "post":
        print("Not in season, nothing to snapshot")
        return

    rosters = sleeper.get(f"/league/{league_id}/rosters")
    db = sleeper.nfl_players()  # cached for 24h, so this is not a fresh big call each run

    now = datetime.now(timezone.utc)
    snap = {"taken_at": now.isoformat(timespec="seconds"), "season": state["season"], "week": state["week"], "rosters": []}
    for r in rosters:
        starters = [p for p in (r.get("starters") or []) if p and p != "0"]
        snap["rosters"].append({
            "roster_id": r["roster_id"],
            "owner_id": r["owner_id"],
            "starters": r.get("starters") or [],
            "statuses": {p: (db.get(p, {}).get("injury_status")) for p in starters},
        })

    out = ROOT / "data" / "raw" / "snapshots" / f'{state["season"]}' / f'wk{state["week"]:02d}' / f'{now.strftime("%Y%m%dT%H%M%SZ")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
