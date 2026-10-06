"""Turn raw Sleeper data into the JSON a front end can read.

Outputs (data/processed/):
  <season>/weeks.json      per-week, per-roster lineup analysis
  <season>/integrity.json  per-roster integrity score + itemised deductions
  rivalries.json           all-time head-to-head for every pair of owners
  owners.json              owner directory (id, display name, team name, avatar)

    python scripts/score.py
"""
import json
import sys
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


def snapshots_for(season, week):
    d = RAW / "snapshots" / season / f"wk{int(week):02d}"
    return [load(f) for f in sorted(d.glob("*.json"))] if d.exists() else []


def analyse_season(bundle, players, cfg):
    league = bundle["league"]
    season = league["season"]
    slots = [s for s in league["roster_positions"] if s not in ("BN", "IR", "TAXI")]
    last_scored = league["settings"].get("last_scored_leg", 0)
    w = cfg["integrity"]["weights"]
    out_set = set(cfg["integrity"]["out_statuses"])
    doubt_set = set(cfg["integrity"]["doubtful_statuses"])

    weeks, events = {}, defaultdict(list)
    prev_starters = {}
    for wk in sorted(bundle["matchups"], key=int):
        if int(wk) > last_scored:
            continue
        snaps = snapshots_for(season, wk)
        weeks[wk] = []
        for m in bundle["matchups"][wk]:
            rid = m["roster_id"]
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

            # injury flags from game-day snapshots: still in the final lineup despite being Out/Doubtful
            flags = {}
            for s in snaps:
                for r in s["rosters"]:
                    if r["roster_id"] != rid:
                        continue
                    for p, st in r["statuses"].items():
                        if p in starters and (st in out_set or st in doubt_set):
                            flags.setdefault(p, {"status": st, "first_seen": s["taken_at"]})

            stale = prev_starters.get(rid) == starters
            prev_starters[rid] = starters
            eff = round(actual / best, 4) if best else None

            row = {
                "roster_id": rid, "points": round(actual, 2), "optimal_points": round(best, 2),
                "efficiency": eff, "points_left": left, "empty_slots": empty,
                "zero_point_starters": zero, "bench_misses": bench_misses,
                "injured_starters": flags, "stale_lineup": stale, "snapshots_available": bool(snaps),
            }
            weeks[wk].append(row)

            def ev(kind, delta, detail):
                if delta:
                    events[rid].append({"week": int(wk), "kind": kind, "delta": delta, "detail": detail})

            ev("empty_slot", w["empty_slot"] * empty, f"{empty} empty starting slot(s)")
            for p, f in flags.items():
                key = "injured_starter_out" if f["status"] in out_set else "injured_starter_doubtful"
                ev(key, w[key], f'{players.get(p, {}).get("name", p)} was {f["status"]} at {f["first_seen"]} and stayed in the lineup')
            lost = max(round(left / 10 * w["points_left_per_10"], 2), w["points_left_cap_per_week"])
            ev("points_left", lost, f"{left} pts left on the bench vs. best lineup")
            if stale:
                ev("stale_lineup", w["stale_lineup"], "identical lineup to previous week")
            if eff is not None and eff >= w["efficiency_bonus_threshold"]:
                ev("efficiency_bonus", w["efficiency_bonus"], f"{eff:.0%} lineup efficiency")

    cfgi = cfg["integrity"]
    scores = []
    for r in bundle["rosters"]:
        rid = r["roster_id"]
        total = cfgi["start_score"] + sum(e["delta"] for e in events[rid])
        scores.append({
            "roster_id": rid, "owner_id": r["owner_id"],
            "score": round(max(cfgi["min_score"], min(cfgi["max_score"], total)), 1),
            "events": events[rid],
        })
    scores.sort(key=lambda s: -s["score"])
    return weeks, scores


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

    current = bundles[-1]
    weeks, scores = analyse_season(current, players, cfg)
    season = current["league"]["season"]
    dump(OUT / season / "weeks.json", weeks)
    dump(OUT / season / "integrity.json", scores)
    dump(OUT / "rivalries.json", head_to_head(bundles, owners, cfg))

    print(f"season {season}: {len(weeks)} scored week(s)")
    for s in scores:
        print(f'  {owners.get(s["owner_id"], {}).get("display_name", s["owner_id"]):<18}{s["score"]:>6}  ({len(s["events"])} events)')


if __name__ == "__main__":
    main()
