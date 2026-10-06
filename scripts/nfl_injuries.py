"""Official NFL injury report, one page per season/week, saved as slim JSON.

Source: https://www.nfl.com/injuries/league/<season>/reg<week> (robots.txt allows /injuries/).
Only rows with a Game Status (Out / Doubtful / Questionable) are kept.
Finished weeks are never re-fetched; the latest two weeks of the current season are
refreshed each run because reports change.

    python scripts/nfl_injuries.py            # all seasons found in data/raw/seasons
    python scripts/nfl_injuries.py --force    # re-fetch everything
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
OUT = ROOT / "data" / "raw" / "nfl_injuries"
UA = "Mozilla/5.0 (compatible; qttbb-league-research; personal low-volume use)"
DELAY = 1.5

TEAM_RE = re.compile(r'd3-o-section-sub-title"><span>(.*?)</span>', re.S)
ROW_RE = re.compile(
    r'<tr><td scope="row"[^>]*>\s*(?:<a [^>]*>)?\s*(.*?)\s*(?:</a>)?\s*</td>'
    r"<td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>",
    re.S,
)


def fetch_page(season, week):
    url = f"https://www.nfl.com/injuries/league/{season}/reg{week}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def parse(page):
    """-> list of {team, name, pos, injury, practice, game} for rows with a game status."""
    rows = []
    parts = TEAM_RE.split(page)  # [pre, team1, body1, team2, body2, ...]
    for team, body in zip(parts[1::2], parts[2::2]):
        for name, pos, inj, prac, game in ROW_RE.findall(body):
            clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
            if clean(game):
                rows.append({"team": clean(team), "name": clean(name), "pos": clean(pos),
                             "injury": clean(inj), "practice": clean(prac), "game": clean(game)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    state = json.loads((ROOT / "data" / "raw" / "state.json").read_text(encoding="utf-8"))
    seasons = sorted(int(p.stem) for p in (ROOT / "data" / "raw" / "seasons").glob("*.json"))
    for season in seasons:
        season_weeks = 17 if season <= 2020 else 18  # 18-week seasons began in 2021; the site serves a fallback page for a non-existent week 18
        last_week = min(season_weeks, state["week"]) if str(season) == state["season"] else season_weeks
        for week in range(1, last_week + 1):
            f = OUT / str(season) / f"reg{week:02d}.json"
            recent = str(season) == state["season"] and week >= last_week - 1
            if f.exists() and not args.force and not recent:
                continue
            page = fetch_page(season, week)
            time.sleep(DELAY)
            if page is None:
                print(f"{season} wk{week}: 404, skipping")
                continue
            rows = parse(page)
            if not rows and week > 17:
                continue  # 17-game seasons have no week 18 report
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(rows, indent=1, sort_keys=True), encoding="utf-8")
            outs = sum(r["game"] == "Out" for r in rows)
            print(f"{season} wk{week}: {len(rows)} designations ({outs} Out)")


if __name__ == "__main__":
    main()
