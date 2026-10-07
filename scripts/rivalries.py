"""Protected rivalries: a rich head-to-head object for each pair listed in config/league.json.

Run after score.py and profiles.py (it reads the owner profiles for the side-by-side comparison).

  data/processed/protected_rivalries.json

    python scripts/rivalries.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"


def load(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def eff(m):
    return m["custom_points"] if m.get("custom_points") is not None else m["points"]


def tally(games):
    """Series record from A's point of view."""
    aw = sum(g["a_points"] > g["b_points"] for g in games)
    bw = sum(g["b_points"] > g["a_points"] for g in games)
    n = len(games)
    return {"games": n, "a_wins": aw, "b_wins": bw, "ties": n - aw - bw,
            "a_points": round(sum(g["a_points"] for g in games), 2), "b_points": round(sum(g["b_points"] for g in games), 2),
            "a_avg": round(sum(g["a_points"] for g in games) / n, 2) if n else None,
            "b_avg": round(sum(g["b_points"] for g in games) / n, 2) if n else None,
            "a_win_pct": round((aw + (n - aw - bw) / 2) / n, 3) if n else None}


def winner(g):
    return "a" if g["a_points"] > g["b_points"] else "b" if g["b_points"] > g["a_points"] else None


def streaks(games):
    """Current streak (most recent consecutive wins by one side) and each side's longest."""
    cur_side, cur_len, since = None, 0, None
    best = {"a": 0, "b": 0}
    run_side, run = None, 0
    for g in games:
        w = winner(g)
        if w and w == run_side:
            run += 1
        else:
            run_side, run = w, 1 if w else 0
        if w:
            best[w] = max(best[w], run)
    # current: walk back from the end
    for g in reversed(games):
        w = winner(g)
        if w is None:
            break
        if cur_side is None:
            cur_side = w
        if w != cur_side:
            break
        cur_len += 1
        since = g
    return cur_side, cur_len, since, best


def bracket_label(bun, ra, rb, rnd):
    """What kind of playoff game was this? Read from the winners / losers brackets."""
    names = {("winners", 1): "Championship", ("winners", 3): "Third-place game", ("winners", 5): "Fifth-place game",
             ("losers", 1): "Toilet bowl final (decides last place)", ("losers", 3): "Losers bracket 9th/10th place game",
             ("losers", 5): "Losers bracket 7th/8th place game"}
    for bracket in ("winners", "losers"):
        for m in bun.get(f"{bracket}_bracket") or []:
            if m.get("r") == rnd and {m.get("t1"), m.get("t2")} == {ra, rb}:
                return names.get((bracket, m.get("p"))) or f'{bracket.capitalize()} bracket, round {rnd}'
    return None


def main():
    cfg = load(ROOT / "config" / "league.json")
    owners = load(OUT / "owners.json")
    by_name = {o["display_name"].lower(): uid for uid, o in owners.items()}
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    players = load(RAW / "players_slim.json", {})
    profiles = {uid: load(OUT / "owner_profiles" / f"{uid}.json") for uid in owners}
    out = []

    for r in cfg.get("protected_rivalries", []):
        if not r.get("active", True):
            continue
        a, b = by_name[r["a"].lower()], by_name[r["b"].lower()]
        games, upcoming, trades = [], [], []
        for bun in bundles:
            L = bun["league"]
            season, st = L["season"], L["settings"]
            last = 99 if L["status"] == "complete" else st.get("last_scored_leg", 0)
            start = st["playoff_week_start"]
            final_week = start + max((m["r"] for m in bun.get("winners_bracket") or []), default=3) - 1  # last playoff week
            ra = next((x["roster_id"] for x in bun["rosters"] if x["owner_id"] == a), None)
            rb = next((x["roster_id"] for x in bun["rosters"] if x["owner_id"] == b), None)
            if ra is None or rb is None:
                continue
            for wk, ms in bun["matchups"].items():
                ma = next((m for m in ms if m["roster_id"] == ra), None)
                mb = next((m for m in ms if m["roster_id"] == rb), None)
                if not ma or not mb or ma.get("matchup_id") is None or ma["matchup_id"] != mb["matchup_id"]:
                    continue
                if int(wk) > final_week:
                    continue  # Sleeper lists a phantom week after the playoffs end
                if int(wk) > last:
                    # Playoff-week pairings shown before the playoffs are placeholders; only regular-season weeks are real.
                    if int(wk) < start:
                        upcoming.append({"season": season, "week": int(wk), "playoff": False})
                elif eff(ma) or eff(mb):
                    games.append({"season": season, "week": int(wk), "playoff": int(wk) >= start,
                                  "playoff_round": int(wk) - start + 1 if int(wk) >= start else None,
                                  "bracket_game": bracket_label(bun, ra, rb, int(wk) - start + 1) if int(wk) >= start else None,
                                  "a_points": round(eff(ma), 2), "b_points": round(eff(mb), 2)})
            for wk, txs in bun["transactions"].items():
                for t in txs:
                    if t["type"] == "trade" and t["status"] == "complete" and set(t["roster_ids"]) == {ra, rb}:
                        nm = lambda ids: [players.get(p, {}).get("name", p) for p in ids]
                        trades.append({"season": season, "week": int(wk),
                                       "a_received": nm([p for p, rid in (t.get("adds") or {}).items() if rid == ra]),
                                       "b_received": nm([p for p, rid in (t.get("adds") or {}).items() if rid == rb]),
                                       "draft_picks": len(t.get("draft_picks") or []),
                                       "faab": [{"from": "a" if x["sender"] == ra else "b", "amount": x["amount"]} for x in t.get("waiver_budget") or []]})
        games.sort(key=lambda g: (g["season"], g["week"]))
        upcoming.sort(key=lambda u: (u["season"], u["week"]))
        for g in games:
            w = winner(g)
            g["winner"] = {"a": a, "b": b}.get(w)
            g["margin"] = round(abs(g["a_points"] - g["b_points"]), 2)

        side_owner = {"a": a, "b": b}
        who = lambda side: ({"owner_id": side_owner[side], "display_name": owners[side_owner[side]]["display_name"], "first_name": owners[side_owner[side]].get("first_name")} if side else None)
        cur_side, cur_len, since, best = streaks(games)
        reg, post = [g for g in games if not g["playoff"]], [g for g in games if g["playoff"]]

        seasons = {}
        for s in sorted({g["season"] for g in games}):
            t = tally([g for g in games if g["season"] == s])
            seasons[s] = {**t, "series_winner": a if t["a_wins"] > t["b_wins"] else b if t["b_wins"] > t["a_wins"] else None}
        sw = [v["series_winner"] for v in seasons.values()]

        gdet = lambda g: {"season": g["season"], "week": g["week"], "playoff": g["playoff"], "bracket_game": g.get("bracket_game"), "a_points": g["a_points"], "b_points": g["b_points"], "winner": g["winner"], "margin": g["margin"]}
        a_wins_g = [g for g in games if g["winner"] == a]
        b_wins_g = [g for g in games if g["winner"] == b]
        series = tally(games)
        lead = a if series["a_wins"] > series["b_wins"] else b if series["b_wins"] > series["a_wins"] else None
        nm = lambda uid: owners[uid].get("first_name") or owners[uid]["display_name"]

        def comp(uid):
            p = profiles[uid]
            return {"owner_id": uid, "display_name": p["display_name"], "first_name": p["first_name"], "team_name": p["current_team_name"],
                    "all_time_record": f'{p["record"]["total"]["wins"]}-{p["record"]["total"]["losses"]}', "win_pct": p["record"]["total"]["win_pct"],
                    "points_for": p["record"]["total"]["points_for"], "championships": p["trophies"]["championships"]["count"],
                    "sackos": p["trophies"]["sackos"]["count"], "tegridy_factor": p["tegridy_factor"]["total"], "tegridy_rank": p["tegridy_factor"]["rank"],
                    "faab_par_per_dollar": p["faab_efficiency"].get("par_per_dollar"), "luck": p["luck"]["luck"]}

        out.append({
            "name": r["name"], "a": who("a"), "b": who("b"),
            "headline": (f'{nm(lead)} leads the series {max(series["a_wins"], series["b_wins"])}-{min(series["a_wins"], series["b_wins"])}'
                         + (f'-{series["ties"]}' if series["ties"] else "") if lead else f'Series tied {series["a_wins"]}-{series["b_wins"]}'),
            "series": {"all_time": series, "regular_season": tally(reg), "playoffs": tally(post), "leader_owner_id": lead},
            "current_streak": {**(who(cur_side) or {}), "length": cur_len, "since": ({"season": since["season"], "week": since["week"]} if since else None)} if cur_side else None,
            "longest_streaks": {"a": best["a"], "b": best["b"]},
            "last_meeting": gdet(games[-1]) if games else None,
            "last_5": [("W" if winner(g) == "a" else "L" if winner(g) == "b" else "T") for g in games[-5:]],
            "last_5_note": "From the first-listed owner's point of view (oldest to newest).",
            "upcoming_meetings": upcoming,
            "upcoming_note": "Regular-season weeks only. Playoff pairings are not set until the bracket is.",
            "by_season": seasons,
            "seasons_won": {"a": sw.count(a), "b": sw.count(b), "split": sw.count(None)},
            "biggest_wins": {"a": gdet(max(a_wins_g, key=lambda g: g["margin"])) if a_wins_g else None,
                             "b": gdet(max(b_wins_g, key=lambda g: g["margin"])) if b_wins_g else None},
            "closest_game": gdet(min(games, key=lambda g: g["margin"])) if games else None,
            "highest_scoring_game": gdet(max(games, key=lambda g: g["a_points"] + g["b_points"])) if games else None,
            "playoff_meetings": [gdet(g) | {"playoff_round": g["playoff_round"]} for g in post],
            "trades": trades,
            "side_by_side": {"a": comp(a), "b": comp(b)},
            "games": [gdet(g) for g in games],
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "protected_rivalries.json").write_text(json.dumps({
        "asterisk": "*", "scope": "2019 and later only (Sleeper-era data). There is no ESPN-era head-to-head data.",
        "note": "a is the first-listed owner in config/league.json. Records are from a's point of view unless marked. Playoff games include every playoff-week meeting.",
        "rivalries": out}, indent=1, sort_keys=True), encoding="utf-8")

    for v in out:
        s = v["series"]["all_time"]
        cs = v["current_streak"]
        print(f"{v['name']:<18} {s['a_wins']}-{s['b_wins']}{'-' + str(s['ties']) if s['ties'] else ''} in {s['games']} | streak: "
              f"{(cs['first_name'] + ' ' + str(cs['length'])) if cs else '-'} | last 5 (a): {' '.join(v['last_5'])} | next: "
              f"{[(u['season'], u['week']) for u in v['upcoming_meetings'][:2]]} | trades {len(v['trades'])}")


if __name__ == "__main__":
    main()
