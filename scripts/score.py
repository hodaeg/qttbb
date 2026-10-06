"""Turn raw Sleeper data into the JSON a front end can read.

Outputs (data/processed/):
  <season>/weeks.json      per-week, per-roster lineup analysis
  <season>/tegridy.json    per-roster Tegridy Factor (penalty total, lower is better) + itemised penalties
  <season>/efficiency.json per-roster lineup efficiency (a skill stat, deliberately NOT part of Tegridy Factor)
  tegridy_alltime.json     Tegridy Factor summed across seasons
  rivalries.json           all-time head-to-head for every pair of owners
  owners.json              owner directory (id, display name, team name, avatar)

    python scripts/score.py
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

FLEX_ELIGIBLE = {
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")


def eligible(slot, pos):
    return pos in FLEX_ELIGIBLE[slot] if slot in FLEX_ELIGIBLE else slot == pos


def optimal_lineup(slots, pool, pts):
    """Best possible lineup. Dedicated slots first, then flex slots (fewest options first)."""
    order = sorted(range(len(slots)), key=lambda i: len(FLEX_ELIGIBLE.get(slots[i], {slots[i]})))
    used, lineup = set(), [None] * len(slots)
    for i in order:
        best = max(
            (p for p in pool if p not in used and eligible(slots[i], pool[p])),
            key=lambda p: pts.get(p, 0),
            default=None,
        )
        if best is not None:
            used.add(best)
            lineup[i] = best
    return lineup


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
POS_ALIASES = {"PK": "K", "FB": "RB", "HB": "RB"}


def norm_name(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    parts = [w for w in re.sub(r"[^a-z ]", "", s.replace("-", " ")).split() if w not in SUFFIXES]
    return " ".join(parts)


def norm_pos(pos):
    return POS_ALIASES.get(pos, pos)


def nfl_report_for(season, week):
    """Official NFL injury report for that week, indexed by normalised player name."""
    f = RAW / "nfl_injuries" / str(season) / f"reg{int(week):02d}.json"
    rows = load(f)
    if rows is None:
        return None
    index = defaultdict(list)
    for r in rows:
        index[norm_name(r["name"])].append(r)
    return index


def report_flag(index, player):
    """Out/Doubtful designation for this player on that week's report, or None."""
    for r in index.get(norm_name(player.get("name")), []):
        if r["game"] in ("Out", "Doubtful") and norm_pos(r["pos"]) == norm_pos(player.get("pos")):
            return r
    return None


class ByeDetector:
    """Was this player's NFL team off that week? Needs data/raw/nfl_schedule and data/raw/player_teams
    (scripts/nfl_context.py). Players on bye have no stats row that week, so the team is taken from the
    nearest week with a row: up to 8 weeks back, then up to 4 forward."""

    def __init__(self):
        self.schedule, self.teams = {}, {}

    def _schedule(self, season):
        if season not in self.schedule:
            self.schedule[season] = load(RAW / "nfl_schedule" / f"{season}.json")
        return self.schedule[season]

    def _teams(self, season, week):
        key = (season, week)
        if key not in self.teams:
            self.teams[key] = load(RAW / "player_teams" / str(season) / f"wk{week:02d}.json") or {}
        return self.teams[key]

    def team_at(self, season, week, pid, pos):
        if pos == "DEF":
            return pid  # team defenses are keyed by team abbreviation
        for wk in [week] + list(range(week - 1, max(week - 9, 0), -1)) + list(range(week + 1, week + 5)):
            t = self._teams(season, wk).get(pid)
            if t:
                return t
        return None

    def is_bye(self, season, week, pid, pos):
        sched = self._schedule(season)
        if not sched or str(week) not in sched:
            return None  # unknown, no schedule data
        team = self.team_at(season, int(week), pid, pos)
        if team is None:
            return None
        playing = sched[str(week)]
        if team not in {t for teams in sched.values() for t in teams}:
            return None  # abbreviation we can't reconcile with the schedule
        return team not in playing


def effective_points(m):
    """Sleeper uses custom_points (commissioner adjustment) when set, otherwise points."""
    return m["custom_points"] if m.get("custom_points") is not None else m["points"]


def playoff_relevance(bundle):
    """Which playoff games still mattered to each roster?

    League rule: only the title (winners bracket) and last place (losers bracket) matter.
      - Winners bracket: a game counts up to and including the first one you LOSE; later games
        (third-place, consolation) don't matter.
      - Losers bracket (toilet bowl): a game counts up to and including the first one you WIN,
        since that saves you from last place.
    Results come from actual points, not the bracket's w/l labels: in Sleeper's losers bracket
    `w` is the LOWER scorer (the one who keeps advancing). Verified against every past playoff game.

    -> { roster_id: { "bracket": "winners"|"losers", "last_week": int|None, "reason": str } }
    last_week None means every playoff week counts (a champion, or a team still alive).
    """
    start = bundle["league"]["settings"]["playoff_week_start"]
    last_scored = bundle["league"]["settings"].get("last_scored_leg", 0)
    brackets = {
        "winners": {t for m in bundle.get("winners_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t},
        "losers": {t for m in bundle.get("losers_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t},
    }
    out = {}
    for name, rosters in brackets.items():
        for rid in rosters:
            done = bundle["league"]["status"] == "complete"
            info = {"bracket": name, "last_week": None, "reason": (
                "still in contention" if not done else
                "won the title (never lost in the winners bracket)" if name == "winners" else
                "lost every losers-bracket game (finished last)")}
            for wk in range(start, last_scored + 1):
                rows = {m["roster_id"]: m for m in bundle["matchups"].get(str(wk), [])}
                me = rows.get(rid)
                if not me or me.get("matchup_id") is None:
                    continue  # bye
                opp = next((m for m in rows.values() if m["roster_id"] != rid and m["matchup_id"] == me["matchup_id"]), None)
                if opp is None:
                    continue
                mine, theirs = effective_points(me), effective_points(opp)
                if name == "winners" and mine < theirs:
                    info = {"bracket": name, "last_week": wk, "reason": "eliminated from the title race (lost in the winners bracket)"}
                    break
                if name == "losers" and mine > theirs:
                    info = {"bracket": name, "last_week": wk, "reason": "safe from last place (won in the losers bracket)"}
                    break
            out[rid] = info
    return out


def snapshots_for(season, week):
    d = RAW / "snapshots" / season / f"wk{int(week):02d}"
    return [load(f) for f in sorted(d.glob("*.json"))] if d.exists() else []


def analyse_season(bundle, players, cfg):
    league = bundle["league"]
    season = league["season"]
    slots = [s for s in league["roster_positions"] if s not in ("BN", "IR", "TAXI")]
    last_scored = league["settings"].get("last_scored_leg", 0)
    w = cfg["tegridy"]["weights"]
    bye = ByeDetector()
    relevance = playoff_relevance(bundle)
    playoff_start = league["settings"].get("playoff_week_start") or 99
    out_set = set(cfg["tegridy"]["out_statuses"])
    doubt_set = set(cfg["tegridy"]["doubtful_statuses"])

    weeks, events = {}, defaultdict(list)
    prev_starters = {}
    for wk in sorted(bundle["matchups"], key=int):
        if int(wk) > last_scored:
            continue
        snaps = snapshots_for(season, wk)
        weeks[wk] = []
        for m in bundle["matchups"][wk]:
            # No matchup = bye or eliminated. Sleeper still returns a stale carried-over `starters`
            # list for these, but no game was played, so it has no bearing on integrity.
            if m.get("matchup_id") is None:
                continue
            rid = m["roster_id"]
            rel = relevance.get(rid)
            counts = not (int(wk) >= playoff_start and (rel is None or (rel["last_week"] is not None and int(wk) > rel["last_week"])))
            reason = None if counts else (rel["reason"] if rel else "not in either playoff bracket")
            pts = m.get("players_points") or {}
            starters = m.get("starters") or []
            pool = {p: (players.get(p, {}).get("pos") or "?") for p in (m.get("players") or [])}
            actual = sum(pts.get(p, 0) for p in starters if p and p != "0")
            best_lineup = optimal_lineup(slots, pool, pts)
            best = sum(pts.get(p, 0) for p in best_lineup if p)
            left = round(max(best - actual, 0), 2)

            empty = sum(1 for p in starters if not p or p == "0")
            zero = [p for p in starters if p and p != "0" and pts.get(p, 0) == 0]
            bench_misses = []
            for i, p in enumerate(starters):
                if not p or p == "0" or i >= len(slots):
                    continue
                better = [b for b in pool if b not in starters and eligible(slots[i], pool[b]) and pts.get(b, 0) > pts.get(p, 0)]
                if better:
                    b = max(better, key=lambda x: pts.get(x, 0))
                    bench_misses.append({"slot": slots[i], "started": p, "started_pts": pts.get(p, 0), "bench": b, "bench_pts": pts.get(b, 0)})

            # Injury flags, two sources:
            #  1. official NFL injury report: game status Out/Doubtful AND scored 0 as a starter (retroactive rule)
            #  2. game-day snapshots: Out/Doubtful at snapshot time and still in the final lineup
            flags = {}
            report = nfl_report_for(season, wk)
            if report is not None:
                for p in starters:
                    if p and p != "0" and pts.get(p, 0) == 0 and p in players:
                        hit = report_flag(report, players[p])
                        if hit:
                            flags[p] = {"status": hit["game"], "source": "nfl_report", "injury": hit["injury"], "practice": hit["practice"]}
            for s in snaps:
                for r in s["rosters"]:
                    if r["roster_id"] != rid:
                        continue
                    for p, st in r["statuses"].items():
                        if p in starters and (st in out_set or st in doubt_set):
                            flags.setdefault(p, {"status": st, "source": "snapshot", "first_seen": s["taken_at"]})

            bye_starters = [p for p in zero if bye.is_bye(season, int(wk), p, players.get(p, {}).get("pos")) is True]

            stale = prev_starters.get(rid) == starters
            prev_starters[rid] = starters
            eff = round(actual / best, 4) if best else None

            row = {
                "roster_id": rid, "points": round(actual, 2), "optimal_points": round(best, 2),
                "efficiency": eff, "points_left": left, "empty_slots": empty,
                "zero_point_starters": zero, "bye_starters": bye_starters, "bench_misses": bench_misses,
                "injured_starters": flags, "stale_lineup": stale, "counts_toward_tegridy": counts, "excluded_reason": reason, "snapshots_available": bool(snaps),
            }
            weeks[wk].append(row)

            def ev(kind, penalty, detail):
                if penalty and counts:
                    events[rid].append({"week": int(wk), "kind": kind, "penalty": penalty, "detail": detail})

            ev("empty_slot", w["empty_slot"] * empty, f"{empty} empty starting slot(s)")
            for p, f in flags.items():
                key = "injured_starter_out" if f["status"] in out_set else "injured_starter_doubtful"
                pname = players.get(p, {}).get("name", p)
                if f["source"] == "nfl_report":
                    detail = f'{pname} was listed {f["status"]} ({f["injury"] or "no injury listed"}) on the official NFL injury report and scored 0 in the starting lineup'
                else:
                    detail = f'{pname} was {f["status"]} at {f["first_seen"]} and stayed in the lineup'
                ev(key, w[key], detail)
            if bye_starters:
                names = ", ".join(players.get(p, {}).get("name", p) for p in bye_starters)
                ev("bye_week_starter", w.get("bye_week_starter", 0) * len(bye_starters), f"started {names} on their NFL team's bye week")
            if stale:
                ev("stale_lineup", w["stale_lineup"], "identical lineup to previous week")

    scores, efficiency = [], []
    for r in bundle["rosters"]:
        rid = r["roster_id"]
        rows = [row for wk in weeks.values() for row in wk if row["roster_id"] == rid]
        scores.append({
            "roster_id": rid, "owner_id": r["owner_id"],
            "tegridy_factor": round(sum(e["penalty"] for e in events[rid]), 2),
            "events": events[rid],
        })
        pts, best = sum(x["points"] for x in rows), sum(x["optimal_points"] for x in rows)
        efficiency.append({
            "roster_id": rid, "owner_id": r["owner_id"], "weeks": len(rows),
            "points": round(pts, 2), "optimal_points": round(best, 2),
            "efficiency": round(pts / best, 4) if best else None,
        })
    scores.sort(key=lambda s: s["tegridy_factor"])  # lower = better
    efficiency.sort(key=lambda e: -(e["efficiency"] or 0))
    return weeks, scores, efficiency, relevance


def owners_directory(bundles):
    owners = {}
    for b in bundles:  # oldest first, so the newest display name wins
        for u in b["users"]:
            owners[u["user_id"]] = {
                "user_id": u["user_id"], "display_name": u["display_name"],
                "team_name": (u.get("metadata") or {}).get("team_name"), "avatar": u.get("avatar"),
            }
    return owners


def head_to_head(bundles, owners, cfg):
    """Pair rosters by matchup_id each week, keyed by owner (roster ids can change across seasons)."""
    pairs = defaultdict(lambda: {"games": []})
    for b in bundles:
        league = b["league"]
        owner_of = {r["roster_id"]: r["owner_id"] for r in b["rosters"]}
        playoff_start = league["settings"].get("playoff_week_start") or 99
        last = league["settings"].get("last_scored_leg", 0) if league["status"] != "complete" else 99
        for wk, ms in b["matchups"].items():
            if int(wk) > last:
                continue
            by_id = defaultdict(list)
            for m in ms:
                if m.get("matchup_id") is not None:
                    by_id[m["matchup_id"]].append(m)
            for pair in by_id.values():
                if len(pair) != 2 or any(not owner_of.get(m["roster_id"]) for m in pair):
                    continue
                a, c = sorted(pair, key=lambda m: owner_of[m["roster_id"]])
                key = f"{owner_of[a['roster_id']]}|{owner_of[c['roster_id']]}"
                pairs[key]["games"].append({
                    "season": league["season"], "week": int(wk), "playoff": int(wk) >= playoff_start,
                    "a_points": a["points"], "b_points": c["points"],
                })

    by_name = {o["display_name"].lower(): uid for uid, o in owners.items()}
    protected = {}
    for r in cfg.get("protected_rivalries", []):
        if r.get("active", True) and r["a"].lower() in by_name and r["b"].lower() in by_name:
            protected["|".join(sorted([by_name[r["a"].lower()], by_name[r["b"].lower()]]))] = r["name"]

    result = []
    for key, p in pairs.items():
        a_id, b_id = key.split("|")
        games = [g for g in p["games"] if g["a_points"] or g["b_points"]]
        if not games:
            continue
        aw = sum(g["a_points"] > g["b_points"] for g in games)
        bw = sum(g["b_points"] > g["a_points"] for g in games)
        margin = [g["a_points"] - g["b_points"] for g in games]
        result.append({
            "a": a_id, "b": b_id, "protected_rivalry": protected.get(key),
            "a_wins": aw, "b_wins": bw, "ties": len(games) - aw - bw, "games_played": len(games),
            "a_points": round(sum(g["a_points"] for g in games), 2), "b_points": round(sum(g["b_points"] for g in games), 2),
            "biggest_a_win": round(max(margin), 2), "biggest_b_win": round(-min(margin), 2),
            "games": games,
        })
    result.sort(key=lambda r: -r["games_played"])
    return result


def main():
    cfg = load(ROOT / "config" / "league.json")
    players = load(RAW / "players_slim.json", {})
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    owners = owners_directory(bundles)
    dump(OUT / "owners.json", owners)

    injury_starts, bye_starts, season_totals = [], [], {}
    injury_excluded, bye_excluded = [], []
    for b in bundles:
        season = b["league"]["season"]
        weeks, scores, efficiency, relevance = analyse_season(b, players, cfg)
        dump(OUT / season / "playoff_relevance.json", relevance)
        dump(OUT / season / "weeks.json", weeks)
        dump(OUT / season / "tegridy.json", scores)
        dump(OUT / season / "efficiency.json", efficiency)
        season_totals[season] = {x["owner_id"]: x["tegridy_factor"] for x in scores}
        owner_of = {r["roster_id"]: r["owner_id"] for r in b["rosters"]}
        for wk, rows in weeks.items():
            for row in rows:
                for pid in row["bye_starters"]:
                    rec = {
                        "season": season, "week": int(wk), "roster_id": row["roster_id"],
                        "owner_id": owner_of.get(row["roster_id"]), "player_id": pid,
                        "player": players.get(pid, {}).get("name", pid), "pos": players.get(pid, {}).get("pos"),
                    }
                    if row["counts_toward_tegridy"]:
                        bye_starts.append(rec)
                    else:
                        bye_excluded.append({**rec, "excluded_reason": row["excluded_reason"]})
                for pid, f in row["injured_starters"].items():
                    rec = {
                        "season": season, "week": int(wk), "roster_id": row["roster_id"],
                        "owner_id": owner_of.get(row["roster_id"]), "player_id": pid,
                        "player": players.get(pid, {}).get("name", pid), "pos": players.get(pid, {}).get("pos"),
                        "status": f["status"], "source": f["source"], "injury": f.get("injury"),
                    }
                    if row["counts_toward_tegridy"]:
                        injury_starts.append(rec)
                    else:
                        injury_excluded.append({**rec, "excluded_reason": row["excluded_reason"]})
        print(f"season {season}: {len(weeks)} scored week(s), best Tegridy Factor "
              f'{owners.get(scores[0]["owner_id"], {}).get("display_name", "?")} {scores[0]["tegridy_factor"]}')

    injury_starts.sort(key=lambda r: (r["season"], r["week"]))
    by_owner = defaultdict(lambda: {"out": 0, "doubtful": 0})
    for r in injury_starts:
        by_owner[r["owner_id"]]["out" if r["status"] in cfg["tegridy"]["out_statuses"] else "doubtful"] += 1
    dump(OUT / "injury_starts.json", {
        "rule": "Official NFL injury report game status Out/Doubtful AND 0 points as a starter (plus game-day snapshot flags)",
        "by_owner": by_owner, "instances": injury_starts, "excluded": injury_excluded,
    })
    bye_starts.sort(key=lambda r: (r["season"], r["week"]))
    bye_by_owner = defaultdict(int)
    for r in bye_starts:
        bye_by_owner[r["owner_id"]] += 1
    dump(OUT / "bye_starts.json", {
        "rule": "Starter scored 0 and their NFL team had no game that week (rosters with no matchup are excluded)",
        "by_owner": bye_by_owner, "instances": bye_starts, "excluded": bye_excluded,
    })
    alltime = defaultdict(lambda: {"total": 0, "by_season": {}})
    for season, totals in season_totals.items():
        for uid, t in totals.items():
            alltime[uid]["total"] = round(alltime[uid]["total"] + t, 2)
            alltime[uid]["by_season"][season] = t
    dump(OUT / "tegridy_alltime.json", dict(sorted(alltime.items(), key=lambda kv: kv[1]["total"])))
    dump(OUT / "rivalries.json", head_to_head(bundles, owners, cfg))

    print("\nTegridy Factor, all-time (lower is better):")
    for uid, a in sorted(alltime.items(), key=lambda kv: kv[1]["total"]):
        print(f'  {owners.get(uid, {}).get("display_name", uid):<18}{a["total"]:>6}   {a["by_season"]}')

    print("\nStarted a bye-week player (all seasons):")
    for uid, n in sorted(bye_by_owner.items(), key=lambda kv: -kv[1]):
        print(f'  {owners.get(uid, {}).get("display_name", uid):<18} {n}')
    print("\nStarted an Out/Doubtful player (all seasons):")
    for uid, c in sorted(by_owner.items(), key=lambda kv: -(kv[1]["out"] + kv[1]["doubtful"])):
        print(f'  {owners.get(uid, {}).get("display_name", uid):<18} out={c["out"]:<3} doubtful={c["doubtful"]}')


if __name__ == "__main__":
    main()
