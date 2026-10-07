"""FAAB efficiency ("Bang for Buck"): how many starting-lineup points does each FAAB dollar buy?

For every winning waiver claim, follow the player on that owner's roster from the week he arrives
until he leaves, and add up the points he scored while in the STARTING lineup. Points on the bench
don't count, because they didn't help the owner. Efficiency = those points / dollars bid.

  - Only claims with a bid of $1 or more are "paid"; $0 claims are tracked separately so free
    pickups don't inflate the ratio.
  - Claims the commissioner later undid (and Sleeper refunded) are ignored.
  - All weeks count: regular season and playoffs.

Also measures points above replacement (PAR): his points minus the position's replacement level for each week he started.

Writes data/processed/faab_efficiency.json. Run after score.py, before profiles.py.

    python scripts/faab.py
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


def reversed_claims(bundle):
    """Transaction ids of waiver claims the commissioner later undid (dropped the player; Sleeper refunds the bid)."""
    all_tx = sorted((t for txs in bundle["transactions"].values() for t in txs), key=lambda t: t["created"])
    out = {}
    for ct in (t for t in all_tx if t["type"] == "commissioner" and t.get("drops")):
        for pid in ct["drops"]:
            cands = [t for t in all_tx if t["type"] == "waiver" and t["status"] == "complete" and t["roster_ids"] == ct["roster_ids"]
                     and pid in (t.get("adds") or {}) and t["created"] < ct["created"] and t["transaction_id"] not in out]
            if cands:
                out[max(cands, key=lambda t: t["created"])["transaction_id"]] = ct
    return out


def replacement_levels(bundle, players, last):
    """Position replacement level for one season: { pos: points per game }.

    Standard definition: rank every NFL player at the position by his season-long points per game (league
    scoring, from data/raw/player_points; minimum half the scored weeks played), then take the (N+1)th, where
    N is the average number of players at that position started across the league per week. That is the best
    player not needed to fill a lineup, a level an owner could actually have reached for. Same for every owner.
    (A week-by-week version would be an oracle that picks each week's best non-starters after the fact.)"""
    season = bundle["league"]["season"]
    weeks = [int(w) for w in bundle["matchups"] if int(w) <= last]
    started = defaultdict(list)
    for wk in weeks:
        cnt = defaultdict(int)
        for m in bundle["matchups"][str(wk)]:
            if m.get("matchup_id") is None:
                continue
            st = set(m.get("starters") or [])
            for pid in m.get("players") or []:
                pos = players.get(pid, {}).get("pos")
                if pos and pid in st:
                    cnt[pos] += 1
        for pos, n in cnt.items():
            started[pos].append(n)

    totals, games = defaultdict(float), defaultdict(int)
    pos_of = {}
    for wk in weeks:
        for pid, (pos, pts) in (load(RAW / "player_points" / season / f"wk{wk:02d}.json") or {}).items():
            totals[pid] += pts
            games[pid] += 1
            pos_of[pid] = pos
    min_games = max(2, (len(weeks) + 1) // 2)
    by_pos = defaultdict(list)
    for pid, g in games.items():
        if g >= min_games:
            by_pos[pos_of[pid]].append(totals[pid] / g)
    out = {}
    for pos, ppgs in by_pos.items():
        ppgs.sort(reverse=True)
        n = round(sum(started[pos]) / len(started[pos])) if started[pos] else 0
        out[pos] = round(ppgs[n] if len(ppgs) > n else ppgs[-1], 2)
    return out


def trace(bundle, rid, pid, leg, last, level, players):
    """Follow a claimed player on one roster from the week he arrives until he leaves.

    Points = what he scored in the starting lineup. Points above replacement (PAR) = for each week he
    started, his points minus the position's replacement level for that season."""
    rostered = started = 0
    pts = par = 0.0
    first = None
    weekly = []
    repl = level.get(players.get(pid, {}).get("pos"), 0)
    for w in range(leg, max(int(k) for k in bundle["matchups"]) + 1):
        row = next((m for m in bundle["matchups"].get(str(w), []) if m["roster_id"] == rid), None)
        present = bool(row) and pid in (row.get("players") or [])
        if first is None:
            if present:
                first = w
            elif w > leg + 1:
                break  # never showed up on the roster
            else:
                continue
        elif not present:
            break
        rostered += 1
        if w <= last and row.get("matchup_id") is not None and pid in (row.get("starters") or []):
            started += 1
            mine = dict(zip(row["starters"], row["starters_points"])).get(pid, 0) or 0
            pts += mine
            par += mine - repl
            weekly.append({"week": w, "points": round(mine, 2), "replacement_level": repl, "above_replacement": round(mine - repl, 2)})
    return {"first_week": first, "weeks_rostered": rostered, "weeks_started": started, "points_started": round(pts, 2),
            "points_above_replacement": round(par, 2), "weekly": weekly}


def summarise(claims):
    paid = [c for c in claims if c["bid"] >= 1]
    free = [c for c in claims if c["bid"] < 1]
    dollars = sum(c["bid"] for c in paid)
    pts = round(sum(c["points_started"] for c in paid), 2)
    par = round(sum(c["points_above_replacement"] for c in paid), 2)
    brief = lambda c: {k: c[k] for k in ("season", "week", "player", "pos", "bid", "weeks_started", "points_started", "points_per_dollar",
                                         "points_above_replacement", "par_per_dollar")}
    big = [c for c in paid if c["bid"] >= 5]
    return {
        "paid_claims": len(paid), "dollars_spent": dollars, "points_from_paid_claims": pts,
        "points_per_dollar": round(pts / dollars, 2) if dollars else None,
        "points_above_replacement": par, "par_per_dollar": round(par / dollars, 2) if dollars else None,
        "hit_rate": round(sum(1 for c in paid if c["weeks_started"] > 0) / len(paid), 3) if paid else None,
        "claims_dropped_before_playing": sum(1 for c in paid if c["outcome"] == "dropped_before_playing"),
        "claims_benched_only": sum(1 for c in paid if c["outcome"] == "never_started"),
        "free_claims": len(free), "points_from_free_claims": round(sum(c["points_started"] for c in free), 2),
        "best_value": brief(max(big, key=lambda c: c["points_per_dollar"])) if big else None,
        "most_points": brief(max(paid, key=lambda c: c["points_started"])) if paid else None,
        "best_par_claim": brief(max(paid, key=lambda c: c["points_above_replacement"])) if paid else None,
        "worst_par_claim": brief(min(paid, key=lambda c: c["points_above_replacement"])) if paid else None,
        "biggest_bust": brief(max((c for c in paid if c["weeks_started"] == 0), key=lambda c: c["bid"])) if any(c["weeks_started"] == 0 for c in paid) else None,
    }


def main():
    players = load(RAW / "players_slim.json", {})
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    claims, levels = [], {}
    for b in bundles:
        L = b["league"]
        season = L["season"]
        last = 99 if L["status"] == "complete" else L["settings"].get("last_scored_leg", 0)
        owner_of = {r["roster_id"]: r["owner_id"] for r in b["rosters"]}
        level = replacement_levels(b, players, last)
        levels[season] = level
        undone = reversed_claims(b)
        for wk, txs in b["transactions"].items():
            for t in txs:
                if t["type"] != "waiver" or t["status"] != "complete" or t["transaction_id"] in undone:
                    continue
                rid = t["roster_ids"][0]
                pid = next(iter(t["adds"]))
                bid = (t.get("settings") or {}).get("waiver_bid") or 0
                tr = trace(b, rid, pid, int(wk), last, level, players)
                claims.append({
                    "season": season, "week": int(wk), "owner_id": owner_of[rid], "roster_id": rid,
                    "player_id": pid, "player": players.get(pid, {}).get("name", pid), "pos": players.get(pid, {}).get("pos"),
                    "bid": bid, "dropped": [players.get(d, {}).get("name", d) for d in (t.get("drops") or {})], **tr,
                    "points_per_dollar": round(tr["points_started"] / bid, 2) if bid else None,
                    "par_per_dollar": round(tr["points_above_replacement"] / bid, 2) if bid else None,
                    "outcome": ("dropped_before_playing" if tr["weeks_rostered"] == 0 else
                                "never_started" if tr["weeks_started"] == 0 else "started"),
                })

    by_owner, by_owner_season = defaultdict(list), defaultdict(list)
    for c in claims:
        by_owner[c["owner_id"]].append(c)
        by_owner_season[(c["owner_id"], c["season"])].append(c)
    owners = {uid: {**summarise(cs), "by_season": {s: summarise(v) for (u, s), v in sorted(by_owner_season.items()) if u == uid}}
              for uid, cs in by_owner.items()}
    ranked = sorted((u for u in owners if owners[u]["points_per_dollar"] is not None), key=lambda u: -owners[u]["points_per_dollar"])
    for i, u in enumerate(ranked, 1):
        owners[u]["rank"] = i
    par_ranked = sorted((u for u in owners if owners[u]["par_per_dollar"] is not None), key=lambda u: -owners[u]["par_per_dollar"])
    for i, u in enumerate(par_ranked, 1):
        owners[u]["par_rank"] = i
    out = {
        "name": "Bang for Buck",
        "definition": "Starting-lineup points a FAAB-acquired player scored for the owner, divided by the dollars bid. Only claims of $1+ count as paid; $0 claims are tracked separately. Bench points don't count. Claims the commissioner undid are ignored. Claims dropped before the player ever shows on a roster for a game week count as dollars spent with no return (outcome 'dropped_before_playing'). points_above_replacement (PAR) subtracts the position's replacement level for each week he started: the points per game of the (N+1)th best player at that position over the season, where N is the average number started league-wide per week (see replacement_levels). Bench stashes bought on purpose (handcuffs, injury stashes) still look like busts.",
        "replacement_levels": levels, "league": summarise(claims), "owners": owners, "claims": sorted(claims, key=lambda c: (c["season"], c["week"], c["roster_id"])),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "faab_efficiency.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")

    names = load(OUT / "owners.json", {})
    lg = out["league"]
    print(f"league: {lg['paid_claims']} paid claims, ${lg['dollars_spent']} -> {lg['points_from_paid_claims']} pts = {lg['points_per_dollar']} pts per $1, hit rate {lg['hit_rate']}")
    print(f"league PAR: {lg['points_above_replacement']} pts above replacement = {lg['par_per_dollar']} per $1")
    print(f"{'#':<3}{'owner':<16}{'paid':>5}{'$':>6}{'pts':>9}{'pts/$':>7}{'PAR':>9}{'PAR/$':>7}{'PARrk':>6}")
    for u in ranked:
        o = owners[u]
        print(f"{o['rank']:<3}{names[u]['display_name']:<16}{o['paid_claims']:>5}{o['dollars_spent']:>6}{o['points_from_paid_claims']:>9.1f}{o['points_per_dollar']:>7.2f}{o['points_above_replacement']:>9.1f}{o['par_per_dollar']:>7.2f}{o['par_rank']:>6}")


if __name__ == "__main__":
    main()
