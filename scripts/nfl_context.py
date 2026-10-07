"""NFL schedule + which team each rostered player was on, per week. Used to detect bye-week starters.

Both come from Sleeper's undocumented api.sleeper.com endpoints (the documented v1 API has neither),
so they could change. Finished weeks are fetched once and cached; the current season refreshes.

  data/raw/nfl_schedule/<season>.json      { "<week>": ["ARI", "KC", ...] }   teams that PLAYED that week
  data/raw/nfl_games/<season>.json         { "<week>": [ {home, away, date, game_id} ] }  the games themselves
  data/raw/player_teams/<season>/wkNN.json { "<player_id>": "TEAM" }          only players in players_slim.json
  data/raw/player_points/<season>/wkNN.json { "<player_id>": ["POS", pts] }    EVERY QB/RB/WR/TE/K/DEF who played, scored
                                                                              with the league's own scoring settings (used
                                                                              for FAAB replacement level)

    python scripts/nfl_context.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
RAW = ROOT / "data" / "raw"


def season_weeks(season):
    return 17 if season <= 2020 else 18


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")


def fetch_schedule(season, current):
    f, g = RAW / "nfl_schedule" / f"{season}.json", RAW / "nfl_games" / f"{season}.json"
    if f.exists() and g.exists() and not current:
        return
    games = sleeper.get_site(f"https://api.sleeper.com/schedule/nfl/regular/{season}")
    playing, by_week = defaultdict(set), defaultdict(list)
    for x in games:
        playing[str(x["week"])].update([x["home"], x["away"]])
        by_week[str(x["week"])].append({"home": x["home"], "away": x["away"], "date": x.get("date"), "game_id": x.get("game_id")})
    write(f, {w: sorted(t) for w, t in playing.items()})
    write(g, dict(by_week))
    print(f"schedule {season}: {len(playing)} weeks, {len(games)} games")


def fetch_player_teams(season, current_season, current_week, wanted):
    top = min(season_weeks(season), current_week) if str(season) == current_season else season_weeks(season)
    for week in range(1, top + 1):
        f = RAW / "player_teams" / str(season) / f"wk{week:02d}.json"
        recent = str(season) == current_season and week >= top - 1
        if f.exists() and not recent:
            continue
        rows = sleeper.get_site(f"https://api.sleeper.com/stats/nfl/{season}/{week}?season_type=regular")
        teams = {r["player_id"]: r["team"] for r in rows if r.get("team") and r["player_id"] in wanted}
        write(f, teams)
        print(f"player_teams {season} wk{week}: {len(teams)}/{len(rows)} rows kept")


FANTASY_POS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def fetch_player_points(season, current_season, current_week, scoring):
    """League-scored points for every fantasy-relevant player, from raw weekly stats (matches Sleeper's own
    recorded points for rostered players exactly)."""
    top = min(season_weeks(season), current_week) if str(season) == current_season else season_weeks(season)
    for week in range(1, top + 1):
        f = RAW / "player_points" / str(season) / f"wk{week:02d}.json"
        recent = str(season) == current_season and week >= top - 1
        if f.exists() and not recent:
            continue
        rows = sleeper.get_site(f"https://api.sleeper.com/stats/nfl/{season}/{week}?season_type=regular")
        out = {}
        for r in rows:
            pos = (r.get("player") or {}).get("position")
            st = r.get("stats") or {}
            if pos not in FANTASY_POS or not st:
                continue
            pts = round(sum(st[k] * v for k, v in scoring.items() if k in st), 2)
            if st.get("gp", 0) >= 1 or pts != 0:
                out[r["player_id"]] = [pos, pts]
        write(f, out)
        print(f"player_points {season} wk{week}: {len(out)} players")


def main():
    argparse.ArgumentParser().parse_args()
    state = json.loads((RAW / "state.json").read_text(encoding="utf-8"))
    wanted = set(json.loads((RAW / "players_slim.json").read_text(encoding="utf-8")))
    for p in sorted((RAW / "seasons").glob("*.json")):
        season = int(p.stem)
        fetch_schedule(season, str(season) == state["season"])
        fetch_player_teams(season, state["season"], state["week"], wanted)
        scoring = json.loads(p.read_text(encoding="utf-8"))["league"]["scoring_settings"]
        fetch_player_points(season, state["season"], state["week"], scoring)


if __name__ == "__main__":
    main()
