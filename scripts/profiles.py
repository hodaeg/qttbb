"""Per-owner profile objects: record, scoring, trophies, FAAB/transactions, head-to-head, and Tegridy Factor.

Run after score.py (it reads data/processed/ for Tegridy, penalties, efficiency and rivalries).

  data/processed/owner_profiles/<owner_id>.json   one rich object per owner
  data/processed/owner_profiles/index.json        one summary row per owner (for league tables)

    python scripts/profiles.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402

ROOT = sleeper.ROOT
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
PROFILES = OUT / "owner_profiles"


def load(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")


def eff(m):
    """Sleeper uses custom_points (commissioner adjustment) when set."""
    return m["custom_points"] if m.get("custom_points") is not None else m["points"]


def blank_record():
    return {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0, "games": 0}


def add_game(rec, pf, pa):
    rec["games"] += 1
    rec["points_for"] += pf
    rec["points_against"] += pa
    if pf > pa:
        rec["wins"] += 1
    elif pf < pa:
        rec["losses"] += 1
    else:
        rec["ties"] += 1


def finish_record(rec):
    g = rec["games"]
    rec["points_for"], rec["points_against"] = round(rec["points_for"], 2), round(rec["points_against"], 2)
    rec["win_pct"] = round((rec["wins"] + rec["ties"] / 2) / g, 4) if g else None
    rec["avg_points_for"] = round(rec["points_for"] / g, 2) if g else None
    rec["avg_points_against"] = round(rec["points_against"] / g, 2) if g else None
    return rec


def placements(bundle):
    """Final place (1-12) for each roster in a completed season, from the brackets.

    Winners bracket p-games give places 1-6 directly (w = higher scorer). In the losers bracket `w`
    is the LOWER scorer, so within each pair the higher scorer (`l`) finishes better:
    p5 -> 7th/8th, p3 -> 9th/10th, p1 -> 11th/12th (12th = last place, the "sacko")."""
    place = {}
    for m in bundle.get("winners_bracket") or []:
        if m.get("p") and m.get("w") and m.get("l"):
            place[m["w"]], place[m["l"]] = m["p"], m["p"] + 1
    for m in bundle.get("losers_bracket") or []:
        if m.get("p") and m.get("w") and m.get("l"):
            worse = {1: 12, 3: 10, 5: 8}[m["p"]]
            place[m["w"]], place[m["l"]] = worse, worse - 1
    return place


def playoff_label(bundle, rid, place):
    """Plain-English playoff outcome for the season."""
    win_ids = {t for m in bundle.get("winners_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t}
    lose_ids = {t for m in bundle.get("losers_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t}
    p = place.get(rid)
    if p is None:
        return None
    names = {1: "Champion", 2: "Runner-up", 3: "Third place", 4: "Fourth place", 5: "Fifth place", 6: "Sixth place", 12: "Last place (Sacko)"}
    if rid in win_ids:
        return names.get(p, f"{p}th place")
    return names.get(p, f"{p}th place") + (" (losers bracket)" if p != 12 else "")


def main():
    cfg = load(ROOT / "config" / "league.json")
    owners = load(OUT / "owners.json")
    players = load(RAW / "players_slim.json", {})
    tegridy_all = load(OUT / "tegridy_alltime.json", {})
    penalties = (load(OUT / "penalties.json", {}) or {}).get("penalties", [])
    rivalries = load(OUT / "rivalries.json", [])
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    current = bundles[-1]["league"]["season"]
    ledger = [e for e in (load(ROOT / "config" / "commissioner_penalties.json", {}) or {}).get("entries", []) if e["status"] == "confirmed"]
    taken = Counter()
    for e in ledger:
        taken[(e["owner"], e["season"])] += e["faab_taken"] * e["instances"]

    P = {uid: {
        "owner_id": uid, "display_name": o["display_name"], "first_name": o.get("first_name"), "avatar": o.get("avatar"),
        "team_names": {}, "divisions": {}, "seasons_played": [],
        "seasons": {}, "_all_reg": blank_record(), "_all_post": blank_record(),
        "_games": [], "_weekly": [],
        "_trophies": defaultdict(list), "_tx": defaultdict(Counter), "_bids": [], "_trade_partners": Counter(),
    } for uid, o in owners.items()}

    # ---------- per season ----------
    for b in bundles:
        L, season = b["league"], b["league"]["season"]
        st = L["settings"]
        start, last = st["playoff_week_start"], (st.get("last_scored_leg", 0) if L["status"] != "complete" else 99)
        complete = L["status"] == "complete"
        owner_of = {r["roster_id"]: r["owner_id"] for r in b["rosters"]}
        users = {u["user_id"]: u for u in b["users"]}
        divisions = {i: L["metadata"].get(f"division_{i}") for i in (1, 2)}
        place = placements(b) if complete else {}
        champion = next((m["w"] for m in b.get("winners_bracket") or [] if m.get("p") == 1), None) if complete else None

        # games + weekly points (for all-play / luck)
        by_week_pts = defaultdict(dict)  # week -> {owner: points}
        per = defaultdict(lambda: {"reg": blank_record(), "post": blank_record()})
        for wk, ms in b["matchups"].items():
            if int(wk) > last:
                continue
            groups = defaultdict(list)
            for m in ms:
                if m.get("matchup_id") is not None:
                    groups[m["matchup_id"]].append(m)
            for pair in groups.values():
                if len(pair) != 2 or not any(eff(x) for x in pair):
                    continue
                for me, opp in (pair, pair[::-1]):
                    uid, ouid = owner_of[me["roster_id"]], owner_of[opp["roster_id"]]
                    pf, pa = eff(me), eff(opp)
                    post = int(wk) >= start
                    add_game(per[uid]["post" if post else "reg"], pf, pa)
                    P[uid]["_games"].append({"season": season, "week": int(wk), "playoff": post, "opp": ouid, "pf": pf, "pa": pa})
                    if not post:
                        by_week_pts[int(wk)][uid] = pf

        # all-play luck (regular season): wins vs. wins you'd expect from your scores against everyone
        luck = defaultdict(lambda: {"all_play_wins": 0, "all_play_games": 0, "expected_wins": 0.0})
        for wk, pts in by_week_pts.items():
            for uid, pf in pts.items():
                others = [v for k, v in pts.items() if k != uid]
                w = sum(pf > v for v in others) + 0.5 * sum(pf == v for v in others)
                luck[uid]["all_play_wins"] += w
                luck[uid]["all_play_games"] += len(others)
                luck[uid]["expected_wins"] += w / len(others) if others else 0

        # standings (regular season, wins then points, like Sleeper)
        standing = sorted(per, key=lambda u: (-per[u]["reg"]["wins"], -per[u]["reg"]["points_for"]))
        rank = {u: i + 1 for i, u in enumerate(standing)}

        # Waiver claims the commissioner later undid: if the commissioner drops a player a roster won by waiver
        # (most recent such claim before the drop), Sleeper refunds that bid.
        all_tx = sorted((t | {"_wk": wk} for wk, txs in b["transactions"].items() for t in txs), key=lambda t: t["created"])
        reversed_ids = {}
        for ct in (t for t in all_tx if t["type"] == "commissioner" and t.get("drops")):
            for pid in ct["drops"]:
                cands = [t for t in all_tx if t["type"] == "waiver" and t["status"] == "complete" and t["roster_ids"] == ct["roster_ids"]
                         and pid in (t.get("adds") or {}) and t["created"] < ct["created"] and t["transaction_id"] not in reversed_ids]
                if cands:
                    reversed_ids[max(cands, key=lambda t: t["created"])["transaction_id"]] = ct

        # transactions
        for wk, txs in b["transactions"].items():
            for t in txs:
                rids = t.get("roster_ids") or []
                if t["transaction_id"] in reversed_ids:
                    P[owner_of[rids[0]]]["_tx"][season]["faab_refunded"] += (t.get("settings") or {}).get("waiver_bid") or 0
                    continue
                if t["type"] == "trade" and t["status"] == "complete":
                    for x in t.get("waiver_budget") or []:
                        P[owner_of[x["sender"]]]["_tx"][season]["faab_traded_out"] += x["amount"]
                        P[owner_of[x["receiver"]]]["_tx"][season]["faab_traded_in"] += x["amount"]
                    for r in rids:
                        P[owner_of[r]]["_tx"][season]["trades"] += 1
                        for r2 in rids:
                            if r2 != r:
                                P[owner_of[r]]["_trade_partners"][owner_of[r2]] += 1
                    continue
                for r in rids:
                    u = P[owner_of[r]]["_tx"][season]
                    if t["type"] == "waiver" and t["status"] == "complete":
                        bid = (t.get("settings") or {}).get("waiver_bid") or 0
                        u["waiver_claims_won"] += 1
                        u["faab_spent"] += bid
                        pid = next(iter(t.get("adds") or {}), None)
                        P[owner_of[r]]["_bids"].append({"amount": bid, "player": players.get(pid, {}).get("name", pid), "season": season, "week": int(wk)})
                    elif t["type"] == "waiver" and t["status"] == "failed":
                        u["waiver_claims_lost"] += 1
                    elif t["type"] == "free_agent" and t["status"] == "complete":
                        u["free_agent_adds"] += len(t.get("adds") or {})
                    if t["status"] == "complete" and t["type"] in ("waiver", "free_agent"):
                        u["adds"] += len(t.get("adds") or {})
                        u["drops"] += len(t.get("drops") or {})

        for r in b["rosters"]:
            uid, rid = r["owner_id"], r["roster_id"]
            if uid not in P:
                continue
            p = P[uid]
            p["seasons_played"].append(season)
            p["team_names"][season] = (users.get(uid, {}).get("metadata") or {}).get("team_name")
            p["divisions"][season] = divisions.get(r["settings"].get("division"))
            reg, post = finish_record(per[uid]["reg"]), finish_record(per[uid]["post"])
            for key, rec in (("_all_reg", reg), ("_all_post", post)):
                for k in ("wins", "losses", "ties", "games", "points_for", "points_against"):
                    p[key][k] += rec[k]
            tx = p["_tx"][season]
            used = r["settings"].get("waiver_budget_used", 0)
            lk = luck[uid]
            season_obj = {
                "season": season, "team_name": p["team_names"][season], "division": p["divisions"][season], "complete": complete,
                "regular_season": reg, "regular_season_rank": rank.get(uid), "postseason": post,
                "final_place": place.get(rid), "playoff_result": playoff_label(b, rid, place) if complete else None,
                "made_playoffs": rid in {t for m in b.get("winners_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t},
                "luck": {"expected_wins": round(lk["expected_wins"], 2), "wins": reg["wins"],
                         "luck": round(reg["wins"] - lk["expected_wins"], 2),
                         "all_play_record": f'{lk["all_play_wins"]:g}-{lk["all_play_games"] - lk["all_play_wins"]:g}'},
                "faab": {"budget": st.get("waiver_budget"), "spent": tx["faab_spent"], "refunded": tx["faab_refunded"],
                         "traded_in": tx["faab_traded_in"], "traded_out": tx["faab_traded_out"],
                         "sleeper_reported_used": used,
                         "unexplained_difference": used - (tx["faab_spent"] + tx["faab_traded_out"] - tx["faab_traded_in"]),
                         "faab_taken_as_penalty": taken[(p["display_name"], season)],
                         "remaining_unexplained": used - (tx["faab_spent"] + tx["faab_traded_out"] - tx["faab_traded_in"]) - taken[(p["display_name"], season)],
                         "waiver_claims_won": tx["waiver_claims_won"], "waiver_claims_lost": tx["waiver_claims_lost"],
                         "free_agent_adds": tx["free_agent_adds"], "adds": tx["adds"], "drops": tx["drops"], "trades": tx["trades"]},
                "sleeper_standings_reported": {"points_for": round(r["settings"]["fpts"] + r["settings"]["fpts_decimal"] / 100, 2),
                                               "points_against": round(r["settings"]["fpts_against"] + r["settings"]["fpts_against_decimal"] / 100, 2)},
            }
            p["seasons"][season] = season_obj
            if complete:
                pl = place.get(rid)
                if rid == champion:
                    p["_trophies"]["championships"].append(season)
                if pl == 2:
                    p["_trophies"]["runner_up"].append(season)
                if pl == 3:
                    p["_trophies"]["third_place"].append(season)
                if pl == 12:
                    p["_trophies"]["sackos"].append(season)
                if season_obj["made_playoffs"]:
                    p["_trophies"]["playoff_appearances"].append(season)
                    if not any(m.get("r") == 1 and rid in (m.get("t1"), m.get("t2")) for m in b["winners_bracket"]):
                        p["_trophies"]["first_round_byes"].append(season)
                if rank.get(uid) == 1:
                    p["_trophies"]["regular_season_titles"].append(season)

    # ---------- efficiency (skill stat) ----------
    eff_by = defaultdict(lambda: {"points": 0.0, "optimal_points": 0.0, "weeks": 0})
    for b in bundles:
        for e in load(OUT / b["league"]["season"] / "efficiency.json", []) or []:
            x = eff_by[e["owner_id"]]
            x["points"] += e["points"]; x["optimal_points"] += e["optimal_points"]; x["weeks"] += e["weeks"]
            if e["owner_id"] in P and b["league"]["season"] in P[e["owner_id"]]["seasons"]:
                P[e["owner_id"]]["seasons"][b["league"]["season"]]["efficiency"] = e["efficiency"]

    # ---------- tegridy ----------
    by_owner_pen = defaultdict(list)
    for pen in penalties:
        by_owner_pen[pen["manager"]["owner_id"]].append(pen)
    ranked = sorted(tegridy_all.items(), key=lambda kv: kv[1]["total"])
    t_rank = {uid: sum(1 for _, v in ranked if v["total"] < a["total"]) + 1 for uid, a in ranked}

    # ---------- head to head ----------
    h2h = defaultdict(dict)
    for r in rivalries:
        a, bb = r["a"], r["b"]
        h2h[a][bb] = {"wins": r["a_wins"], "losses": r["b_wins"], "ties": r["ties"], "games": r["games_played"],
                      "points_for": r["a_points"], "points_against": r["b_points"], "protected_rivalry": r["protected_rivalry"]}
        h2h[bb][a] = {"wins": r["b_wins"], "losses": r["a_wins"], "ties": r["ties"], "games": r["games_played"],
                      "points_for": r["b_points"], "points_against": r["a_points"], "protected_rivalry": r["protected_rivalry"]}

    # ---------- assemble ----------
    index = []
    for uid, p in P.items():
        if not p["seasons_played"]:
            continue
        games = sorted(p["_games"], key=lambda g: (g["season"], g["week"]))
        reg, post = finish_record(p["_all_reg"]), finish_record(p["_all_post"])
        total = finish_record({k: reg[k] + post[k] for k in ("wins", "losses", "ties", "games", "points_for", "points_against")})

        # streaks and extremes
        best_w = best_l = cur_w = cur_l = 0
        for g in games:
            if g["pf"] > g["pa"]:
                cur_w, cur_l = cur_w + 1, 0
            elif g["pf"] < g["pa"]:
                cur_l, cur_w = cur_l + 1, 0
            else:
                cur_w = cur_l = 0
            best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
        nz = [g for g in games if g["pf"] > 0]
        hi, lo = max(nz, key=lambda g: g["pf"]), min(nz, key=lambda g: g["pf"])
        blow = max(games, key=lambda g: g["pf"] - g["pa"]); worst = min(games, key=lambda g: g["pf"] - g["pa"])
        close = [g for g in games if abs(g["pf"] - g["pa"]) < 5]
        tag = lambda g: {"season": g["season"], "week": g["week"], "opponent_owner_id": g["opp"], "points_for": round(g["pf"], 2), "points_against": round(g["pa"], 2)}

        txs = p["_tx"]
        faab = {"spent": sum(t["faab_spent"] for t in txs.values()),
                "refunded": sum(t["faab_refunded"] for t in txs.values()),
                "traded_in": sum(t["faab_traded_in"] for t in txs.values()),
                "traded_out": sum(t["faab_traded_out"] for t in txs.values()),
                "sleeper_reported_used": sum(v["faab"]["sleeper_reported_used"] for v in p["seasons"].values()),
                "unexplained_difference": sum(v["faab"]["unexplained_difference"] for v in p["seasons"].values()),
                "faab_taken_as_penalty": sum(v["faab"]["faab_taken_as_penalty"] for v in p["seasons"].values()),
                "remaining_unexplained": sum(v["faab"]["remaining_unexplained"] for v in p["seasons"].values()),
                "note": "spent = winning bids in the transaction log, net of claims the commissioner later undid (refunded; e.g. the Sep 2021 week-1 corrections). Sleeper's own 'used' figure also reflects FAAB traded between owners and any budget edits that aren't in the log; unexplained_difference is what's left (positive = Sleeper shows more used than the log explains). faab_taken_as_penalty is FAAB the commissioner took for missed league notes (config/commissioner_penalties.json); remaining_unexplained is what's still unexplained after that (small corrections and refunds, mostly 2019 and 2021).",
                "budget_per_season": 100,
                "waiver_claims_won": sum(t["waiver_claims_won"] for t in txs.values()),
                "waiver_claims_lost": sum(t["waiver_claims_lost"] for t in txs.values()),
                "free_agent_adds": sum(t["free_agent_adds"] for t in txs.values()),
                "adds": sum(t["adds"] for t in txs.values()), "drops": sum(t["drops"] for t in txs.values()),
                "trades": sum(t["trades"] for t in txs.values()),
                "biggest_bid": max(p["_bids"], key=lambda x: x["amount"]) if p["_bids"] else None,
                "most_frequent_trade_partner": ({"owner_id": p["_trade_partners"].most_common(1)[0][0], "trades": p["_trade_partners"].most_common(1)[0][1]} if p["_trade_partners"] else None)}
        faab["spent_per_season"] = {s: txs[s]["faab_spent"] for s in sorted(txs)}

        ex = eff_by[uid]
        opp_rows = {k: v for k, v in h2h[uid].items() if v["games"]}
        pct = lambda v: (v["wins"] + v["ties"] / 2) / v["games"]
        nem = min(opp_rows, key=lambda k: (pct(opp_rows[k]), -opp_rows[k]["games"])) if opp_rows else None
        vic = max(opp_rows, key=lambda k: (pct(opp_rows[k]), opp_rows[k]["games"])) if opp_rows else None

        pens = by_owner_pen[uid]
        counted = [x for x in pens if x["counts"]]
        tg = tegridy_all.get(uid, {"total": 0, "by_season": {}})
        tegridy = {
            "total": tg["total"], "rank": t_rank.get(uid), "rank_note": "1 = best (lowest). Ties share a rank.",
            "by_season": tg["by_season"], "penalty_count": len(counted),
            "by_kind": dict(Counter(x["kind"] for x in counted)),
            "points_by_kind": {k: round(sum(x["penalty"]["total"] for x in counted if x["kind"] == k), 2) for k in sorted({x["kind"] for x in counted})},
            "clean_seasons": [s for s, v in tg["by_season"].items() if v == 0 and s != current],
            "worst_penalty_id": max(counted, key=lambda x: x["penalty"]["total"])["id"] if counted else None,
            "penalty_ids": [x["id"] for x in sorted(counted, key=lambda x: (x["season"], x["week"] or 99, x["id"]))],
            "excluded_penalty_ids": [x["id"] for x in pens if not x["counts"]],
        }

        T = p["_trophies"]
        trophies = {k: {"count": len(T[k]), "seasons": T[k]} for k in
                    ("championships", "runner_up", "third_place", "sackos", "playoff_appearances", "first_round_byes", "regular_season_titles")}

        profile = {
            "owner_id": uid, "display_name": p["display_name"], "first_name": p["first_name"], "avatar": p["avatar"],
            "current_team_name": p["team_names"].get(max(p["seasons_played"])),
            "current_division": p["divisions"].get(max(p["seasons_played"])),
            "in_current_league": current in p["seasons_played"], "seasons_played": p["seasons_played"],
            "first_season": min(p["seasons_played"]),
            "tegridy_factor": tegridy,
            "record": {"regular_season": reg, "postseason": post, "total": total,
                       "note": "Postseason includes every playoff-week game (consolation and third-place included). Points come from the weekly matchups (commissioner-adjusted where set). Sleeper's own season standings totals differ slightly in a few seasons; each season object carries sleeper_standings_reported for comparison. Win-loss records match Sleeper exactly."},
            "trophies": trophies,
            "scoring": {"highest_score": tag(hi), "lowest_score": tag(lo), "biggest_win": tag(blow), "worst_loss": tag(worst),
                        "close_games": {"definition": "decided by less than 5 points", "wins": sum(g["pf"] > g["pa"] for g in close), "losses": sum(g["pf"] < g["pa"] for g in close)},
                        "longest_win_streak": best_w, "longest_losing_streak": best_l},
            "luck": {"note": "Regular season. luck = actual wins minus wins expected from your scores vs. everyone each week.",
                     "wins": reg["wins"], "expected_wins": round(sum(s["luck"]["expected_wins"] for s in p["seasons"].values()), 2),
                     "luck": round(sum(s["luck"]["luck"] for s in p["seasons"].values()), 2)},
            "efficiency": {"note": "A skill stat. Deliberately NOT part of Tegridy Factor.", "weeks": ex["weeks"], "points": round(ex["points"], 2),
                           "optimal_points": round(ex["optimal_points"], 2), "efficiency": round(ex["points"] / ex["optimal_points"], 4) if ex["optimal_points"] else None,
                           "points_left_on_bench": round(ex["optimal_points"] - ex["points"], 2)},
            "faab_and_transactions": faab,
            "head_to_head": {"by_opponent": h2h[uid], "nemesis_owner_id": nem, "favorite_victim_owner_id": vic},
            "seasons": p["seasons"],
        }
        dump(PROFILES / f"{uid}.json", profile)
        index.append({
            "owner_id": uid, "display_name": p["display_name"], "first_name": p["first_name"], "avatar": p["avatar"], "in_current_league": profile["in_current_league"],
            "seasons": len(p["seasons_played"]), "wins": total["wins"], "losses": total["losses"], "ties": total["ties"],
            "win_pct": total["win_pct"], "points_for": total["points_for"], "points_against": total["points_against"],
            "championships": trophies["championships"]["count"], "runner_ups": trophies["runner_up"]["count"], "sackos": trophies["sackos"]["count"],
            "playoff_appearances": trophies["playoff_appearances"]["count"], "faab_spent": faab["spent"], "trades": faab["trades"],
            "luck": profile["luck"]["luck"], "efficiency": profile["efficiency"]["efficiency"],
            "tegridy_factor": tegridy["total"], "tegridy_rank": tegridy["rank"],
        })
    index.sort(key=lambda r: (r["tegridy_factor"], r["display_name"].lower()))
    dump(PROFILES / "index.json", {"as_of_season": current, "owners": index})

    print(f"{'owner':<16}{'W-L-T':<10}{'PF':>9}  {'titles':>6} {'sacko':>5} {'FAAB$':>6} {'trades':>6} {'tegridy':>8}")
    for r in sorted(index, key=lambda r: -r["points_for"]):
        print(f"{r['display_name']:<16}{r['wins']}-{r['losses']}-{r['ties']:<5}{r['points_for']:>9.1f}  {r['championships']:>6} {r['sackos']:>5} {r['faab_spent']:>6} {r['trades']:>6} {r['tegridy_factor']:>8}")


if __name__ == "__main__":
    main()
