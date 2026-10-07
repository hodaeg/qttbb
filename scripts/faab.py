"""FAAB efficiency ("Bang for Buck"): how many starting-lineup points does each FAAB dollar buy?

For every winning waiver claim, follow the player on that owner's roster from the week he arrives
until he leaves, and add up the points he scored while in the STARTING lineup. Points on the bench
don't count, because they didn't help the owner. Efficiency = those points / dollars bid.

  - Only claims with a bid of $1 or more are "paid"; $0 claims are tracked separately so free
    pickups don't inflate the ratio.
  - Claims the commissioner later undid (and Sleeper refunded) are ignored.
  - All weeks count: regular season and playoffs.

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


def trace(bundle, rid, pid, leg, last):
    """Follow a claimed player on one roster: -> (weeks rostered, weeks started, starter points, bench-only weeks)."""
    rostered = started = 0
    pts = 0.0
    first = None
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
            pts += dict(zip(row["starters"], row["starters_points"])).get(pid, 0) or 0
    return {"first_week": first, "weeks_rostered": rostered, "weeks_started": started, "points_started": round(pts, 2)}


def summarise(claims):
    paid = [c for c in claims if c["bid"] >= 1]
    free = [c for c in claims if c["bid"] < 1]
    dollars = sum(c["bid"] for c in paid)
    pts = round(sum(c["points_started"] for c in paid), 2)
    brief = lambda c: {k: c[k] for k in ("season", "week", "player", "pos", "bid", "weeks_started", "points_started", "points_per_dollar")}
    big = [c for c in paid if c["bid"] >= 5]
    return {
        "paid_claims": len(paid), "dollars_spent": dollars, "points_from_paid_claims": pts,
        "points_per_dollar": round(pts / dollars, 2) if dollars else None,
        "hit_rate": round(sum(1 for c in paid if c["weeks_started"] > 0) / len(paid), 3) if paid else None,
        "claims_dropped_before_playing": sum(1 for c in paid if c["outcome"] == "dropped_before_playing"),
        "claims_benched_only": sum(1 for c in paid if c["outcome"] == "never_started"),
        "free_claims": len(free), "points_from_free_claims": round(sum(c["points_started"] for c in free), 2),
        "best_value": brief(max(big, key=lambda c: c["points_per_dollar"])) if big else None,
        "most_points": brief(max(paid, key=lambda c: c["points_started"])) if paid else None,
        "biggest_bust": brief(max((c for c in paid if c["weeks_started"] == 0), key=lambda c: c["bid"])) if any(c["weeks_started"] == 0 for c in paid) else None,
    }


def main():
    players = load(RAW / "players_slim.json", {})
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    claims = []
    for b in bundles:
        L = b["league"]
        season = L["season"]
        last = 99 if L["status"] == "complete" else L["settings"].get("last_scored_leg", 0)
        owner_of = {r["roster_id"]: r["owner_id"] for r in b["rosters"]}
        undone = reversed_claims(b)
        for wk, txs in b["transactions"].items():
            for t in txs:
                if t["type"] != "waiver" or t["status"] != "complete" or t["transaction_id"] in undone:
                    continue
                rid = t["roster_ids"][0]
                pid = next(iter(t["adds"]))
                bid = (t.get("settings") or {}).get("waiver_bid") or 0
                tr = trace(b, rid, pid, int(wk), last)
                claims.append({
                    "season": season, "week": int(wk), "owner_id": owner_of[rid], "roster_id": rid,
                    "player_id": pid, "player": players.get(pid, {}).get("name", pid), "pos": players.get(pid, {}).get("pos"),
                    "bid": bid, "dropped": [players.get(d, {}).get("name", d) for d in (t.get("drops") or {})], **tr,
                    "points_per_dollar": round(tr["points_started"] / bid, 2) if bid else None,
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
    out = {
        "name": "Bang for Buck",
        "definition": "Starting-lineup points a FAAB-acquired player scored for the owner, divided by the dollars bid. Only claims of $1+ count as paid; $0 claims are tracked separately. Bench points don't count. Claims the commissioner undid are ignored. Claims dropped before the player ever shows on a roster for a game week count as dollars spent with no return (outcome 'dropped_before_playing'). Does not account for what the owner would have had without the claim, or for bench stashes bought on purpose (handcuffs, injury stashes).",
        "league": summarise(claims), "owners": owners, "claims": sorted(claims, key=lambda c: (c["season"], c["week"], c["roster_id"])),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "faab_efficiency.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")

    names = load(OUT / "owners.json", {})
    lg = out["league"]
    print(f"league: {lg['paid_claims']} paid claims, ${lg['dollars_spent']} -> {lg['points_from_paid_claims']} pts = {lg['points_per_dollar']} pts per $1, hit rate {lg['hit_rate']}")
    print(f"{'#':<3}{'owner':<16}{'paid':>5}{'$':>6}{'pts':>9}{'pts/$':>7}{'hit%':>6}")
    for u in ranked:
        o = owners[u]
        print(f"{o['rank']:<3}{names[u]['display_name']:<16}{o['paid_claims']:>5}{o['dollars_spent']:>6}{o['points_from_paid_claims']:>9.1f}{o['points_per_dollar']:>7.2f}{o['hit_rate']*100:>6.0f}")


if __name__ == "__main__":
    main()
