"""Legacy Rankings, computed automatically (Mike used to do these by hand).

Method: start from Mike's published list (config/legacy_baseline.json, through the 2025 season, which includes
the ESPN years before 2019) and add everything that has happened since, straight from Sleeper data. Each owner's
unexplained difference between Mike's published total and his stated formula is kept frozen as an `adjustment`
(listed for Mike to review), so the app matches his list today and moves on its own from here.

Scoring (config/legacy_baseline.json "formula"): championship +100, sacko -80, division title +15, playoff
appearance +5, playoff win +10, led league in scoring +15, last in scoring -15, perfect season +100, and +/-20 for
every .025 of all-time win% above/below .500. The all-time record counts only games played while still in
contention for the Bria Bowl or the Sacko (same rule as the Tegridy Factor playoff relevance).

Stats derived from Sleeper (2019 and later) carry an asterisk: there is no ESPN-era data for them.

  data/processed/legacy_rankings.json
  data/processed/legacy/history/<season>-wkNN.json   weekly snapshot, used for week-over-week movement

    python scripts/legacy.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sleeper  # noqa: E402
import score as S  # noqa: E402
from profiles import placements  # noqa: E402

ROOT = sleeper.ROOT
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
ASTERISK = "*"
ASTERISK_NOTE = "2019 and later only (Sleeper-era data). There is no ESPN-era data for this stat."


def load(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")


def pct(w, l, t):
    g = w + l + t
    return (w + t / 2) / g if g else 0.5


def record_bonus(w, l, t, F):
    """+/-20 per .025 of win% away from .500, truncated toward zero."""
    return int((pct(w, l, t) - 0.5) / F["record_bonus_step_win_pct"]) * F["record_bonus_per_step"]


def formula_points(c, s, d, a, pw, bonus_sum, perfect, rec, F):
    return (F["championship"] * c + F["sacko"] * s + F["division_title"] * d + F["playoff_appearance"] * a
            + F["playoff_win"] * pw + bonus_sum + F["perfect_season"] * perfect + record_bonus(*rec, F))


def season_results(bundle):
    """What each owner earned in one season under Mike's rules (events only count once they are decided)."""
    L, st = bundle["league"], bundle["league"]["settings"]
    season, start = L["season"], st["playoff_week_start"]
    complete = L["status"] == "complete"
    last = 99 if complete else st.get("last_scored_leg", 0)
    reg_done = complete or last >= start - 1
    playoffs_started = complete or last >= start
    owner_of = {r["roster_id"]: r["owner_id"] for r in bundle["rosters"]}
    rel = S.playoff_relevance(bundle)
    in_bracket = {t for m in bundle.get("winners_bracket") or [] for t in (m.get("t1"), m.get("t2")) if t}
    place = placements(bundle) if complete else {}
    final = next((m for m in bundle.get("winners_bracket") or [] if m.get("p") == 1), None) if complete else None

    counted = defaultdict(lambda: [0, 0, 0])  # all games played while still in contention
    pw = defaultdict(lambda: [0, 0, 0])       # winners-bracket games (Bria playoffs) while in contention
    reg = defaultdict(lambda: [0, 0, 0])
    for wk, ms in bundle["matchups"].items():
        wk = int(wk)
        if wk > last:
            continue
        groups = defaultdict(list)
        for m in ms:
            if m.get("matchup_id") is not None:
                groups[m["matchup_id"]].append(m)
        for pair in groups.values():
            if len(pair) != 2 or not any(S.effective_points(x) for x in pair):
                continue
            for me, op in (pair, pair[::-1]):
                rid, mine, theirs = me["roster_id"], S.effective_points(me), S.effective_points(op)
                res = 0 if mine > theirs else 1 if mine < theirs else 2
                if wk < start:
                    counted[owner_of[rid]][res] += 1
                    reg[owner_of[rid]][res] += 1
                else:
                    r = rel.get(rid)
                    if r and (r["last_week"] is None or wk <= r["last_week"]):
                        counted[owner_of[rid]][res] += 1
                        if r["bracket"] == "winners":
                            pw[owner_of[rid]][res] += 1

    pf = {r["owner_id"]: r["settings"]["fpts"] + r["settings"]["fpts_decimal"] / 100 for r in bundle["rosters"]}
    divs = defaultdict(list)
    for r in bundle["rosters"]:
        s = r["settings"]
        divs[s["division"]].append((s["wins"], pf[r["owner_id"]], r["owner_id"]))
    div_winner = {sorted(rows, reverse=True)[0][2] for rows in divs.values()} if reg_done else set()
    leader = max(pf, key=pf.get) if reg_done else None
    lastp = min(pf, key=pf.get) if reg_done else None

    out = {}
    for r in bundle["rosters"]:
        u, rid = r["owner_id"], r["roster_id"]
        champ = complete and place.get(rid) == 1
        sacko = complete and place.get(rid) == 12
        c = counted[u]
        out[u] = {
            "season": season, "complete": complete,
            "championship": champ, "sacko": sacko,
            "bria_bowl": bool(final and rid in (final.get("t1"), final.get("t2"))),
            "runner_up": complete and place.get(rid) == 2,
            "division_title": u in div_winner,
            "playoff_appearance": playoffs_started and rid in in_bracket,
            "playoff_record": list(pw[u]), "counted_record": list(c),
            "regular_season_record": list(reg[u]),
            "regular_season_points": round(pf[u], 2),
            "led_scoring": u == leader, "last_scoring": u == lastp,
            "perfect_season": bool(champ and c[1] == 0 and c[2] == 0),
            "unbeaten_regular_season": reg_done and reg[u][1] == 0 and reg[u][2] == 0 and sum(reg[u]) > 0,
        }
    return out


def add(totals, ev):
    totals["championships"] += ev["championship"]
    totals["sackos"] += ev["sacko"]
    totals["division_titles"] += ev["division_title"]
    totals["playoff_appearances"] += ev["playoff_appearance"]
    for i, k in enumerate(("wins", "losses", "ties")):
        totals["playoff_record"][k] += ev["playoff_record"][i]
        totals["record"][k] += ev["counted_record"][i]
    totals["perfect_seasons"] += ev["perfect_season"]
    totals["bria_bowl"]["appearances"] += ev["bria_bowl"]
    totals["bria_bowl"]["wins"] += ev["championship"]
    totals["bria_bowl"]["losses"] += ev["runner_up"]
    if ev["led_scoring"]:
        totals["scoring_bonuses"].append(15)
    if ev["last_scoring"]:
        totals["scoring_bonuses"].append(-15)


def blank():
    return {"championships": 0, "sackos": 0, "division_titles": 0, "playoff_appearances": 0, "perfect_seasons": 0,
            "playoff_record": {"wins": 0, "losses": 0, "ties": 0}, "record": {"wins": 0, "losses": 0, "ties": 0},
            "scoring_bonuses": [], "bria_bowl": {"appearances": 0, "wins": 0, "losses": 0}}


def season_points(ev, F):
    """Points a season's decided events are worth (the record bonus is handled on the all-time record)."""
    return (F["championship"] * ev["championship"] + F["sacko"] * ev["sacko"] + F["division_title"] * ev["division_title"]
            + F["playoff_appearance"] * ev["playoff_appearance"] + F["playoff_win"] * ev["playoff_record"][0]
            + (F["led_league_in_scoring"] if ev["led_scoring"] else 0) + (F["last_in_league_in_scoring"] if ev["last_scoring"] else 0)
            + F["perfect_season"] * ev["perfect_season"])


def main():
    base = load(ROOT / "config" / "legacy_baseline.json")
    F, snap_season = base["formula"], base["snapshot"]["season"]
    owners = load(OUT / "owners.json")
    uid_of = {o["display_name"]: u for u, o in owners.items()}
    bundles = sorted((load(f) for f in (RAW / "seasons").glob("*.json")), key=lambda b: b["league"]["season"])
    results = {b["league"]["season"]: season_results(b) for b in bundles}
    current = bundles[-1]["league"]
    cur_season, cur_week = current["season"], current["settings"].get("last_scored_leg", 0)

    sleeper_era, since = {}, {}
    for display, pub in base["owners"].items():
        u = uid_of[display]
        sleeper_era[u], since[u] = blank(), blank()
        for season, res in sorted(results.items()):
            if u not in res:
                continue
            add(sleeper_era[u] if season <= snap_season else since[u], res[u])

    rows = []
    for display, pub in base["owners"].items():
        u = uid_of[display]
        pr, rec = pub["playoff_record"], pub["record"]
        pub_bonus = sum(pub["scoring_bonuses"])
        pub_formula = formula_points(pub["championships"], pub["sackos"], pub["division_titles"], pub["playoff_appearances"], pr["wins"],
                                     pub_bonus, 0, (rec["wins"], rec["losses"], rec["ties"]), F)
        adjustment = pub["published_points"] - pub_formula

        s = since[u]
        live = {
            "championships": pub["championships"] + s["championships"], "sackos": pub["sackos"] + s["sackos"],
            "division_titles": pub["division_titles"] + s["division_titles"],
            "playoff_appearances": pub["playoff_appearances"] + s["playoff_appearances"],
            "playoff_record": {k: pr[k] + s["playoff_record"][k] for k in ("wins", "losses", "ties")},
            "record": {k: rec[k] + s["record"][k] for k in ("wins", "losses", "ties")},
            "scoring_bonuses": pub["scoring_bonuses"] + s["scoring_bonuses"], "perfect_seasons": s["perfect_seasons"],
        }
        lr = (live["record"]["wins"], live["record"]["losses"], live["record"]["ties"])
        points = formula_points(live["championships"], live["sackos"], live["division_titles"], live["playoff_appearances"],
                                live["playoff_record"]["wins"], sum(live["scoring_bonuses"]), live["perfect_seasons"], lr, F) + adjustment
        bb = pub["bria_bowl"]
        bria = ({"appearances": bb["appearances"] + s["bria_bowl"]["appearances"], "wins": bb["wins"] + s["bria_bowl"]["wins"],
                 "losses": bb["losses"] + s["bria_bowl"]["losses"], "known": True} if bb else
                {"appearances": None, "wins": live["championships"], "losses": None, "known": False,
                 "note": "Finals losses before 2019 aren't in the post, so total appearances aren't known."})

        se = sleeper_era[u]
        pre = {  # derived: published minus Sleeper era 2019-2025 (approximate; relies on the published numbers)
            "championships": pub["championships"] - se["championships"], "sackos": pub["sackos"] - se["sackos"],
            "division_titles": pub["division_titles"] - se["division_titles"],
            "playoff_appearances": pub["playoff_appearances"] - se["playoff_appearances"],
            "record": {k: rec[k] - se["record"][k] for k in ("wins", "losses", "ties")},
            "playoff_record": {k: pr[k] - se["playoff_record"][k] for k in ("wins", "losses", "ties")},
        }
        by_season = {}
        for season, res in sorted(results.items()):
            if u in res:
                ev = res[u]
                by_season[season] = {
                    "legacy_points_from_events": season_points(ev, F), "championship": ev["championship"], "sacko": ev["sacko"],
                    "division_title": ev["division_title"], "playoff_appearance": ev["playoff_appearance"],
                    "playoff_wins": ev["playoff_record"][0], "led_league_in_scoring": ev["led_scoring"],
                    "last_in_league_in_scoring": ev["last_scoring"], "bria_bowl_appearance": ev["bria_bowl"],
                    "counted_record": f'{ev["counted_record"][0]}-{ev["counted_record"][1]}' + (f'-{ev["counted_record"][2]}' if ev["counted_record"][2] else ""),
                    "season_complete": ev["complete"], "after_published_snapshot": season > snap_season,
                }
        rows.append({
            "owner_id": u, "display_name": display, "first_name": pub["first_name"],
            "points": points, "published_points": pub["published_points"], "points_since_snapshot": points - pub["published_points"],
            "adjustment": adjustment,
            "adjustment_note": "Mike's published total minus what his stated formula gives for his published numbers. Frozen; shown so Mike can check it." if adjustment else None,
            "snapshot_rank": pub["published_rank"], "published_rank_change": pub["published_rank_change"],
            "all_time": {**live, "win_pct": round(pct(*lr), 4), "bria_bowl": bria,
                         "scope": "ESPN era + Sleeper era (published through 2025, plus Sleeper since)"},
            "point_breakdown": {
                "championships": F["championship"] * live["championships"], "sackos": F["sacko"] * live["sackos"],
                "division_titles": F["division_title"] * live["division_titles"],
                "playoff_appearances": F["playoff_appearance"] * live["playoff_appearances"],
                "playoff_wins": F["playoff_win"] * live["playoff_record"]["wins"], "scoring_bonuses": sum(live["scoring_bonuses"]),
                "perfect_seasons": F["perfect_season"] * live["perfect_seasons"],
                "record_bonus": record_bonus(*lr, F), "adjustment": adjustment},
            "era_split": {
                "pre_2019_derived": {**pre, "note": "Derived: Mike's published numbers minus the Sleeper-era numbers. Approximate."},
                "sleeper_2019_to_2025": {**se, "asterisk": ASTERISK, "asterisk_note": ASTERISK_NOTE},
                "since_published_snapshot": {**s, "asterisk": ASTERISK, "asterisk_note": ASTERISK_NOTE}},
            "sleeper_era_by_season": {"asterisk": ASTERISK, "asterisk_note": ASTERISK_NOTE, "seasons": by_season},
        })

    rows.sort(key=lambda r: (-r["points"], -r["all_time"]["championships"], -r["all_time"]["win_pct"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["rank_change_since_snapshot"] = r["snapshot_rank"] - i

    # week-over-week movement from the last saved snapshot
    hist_dir = OUT / "legacy" / "history"
    prev = {}
    if cur_week:
        earlier = sorted(p for p in hist_dir.glob("*.json") if (p.stem.split("-wk")[0], int(p.stem.split("-wk")[1])) < (cur_season, cur_week))
        prev = (load(earlier[-1]) or {}).get("ranks", {}) if earlier else {r["owner_id"]: r["snapshot_rank"] for r in rows}
    for r in rows:
        r["rank_change_week"] = (prev[r["owner_id"]] - r["rank"]) if r["owner_id"] in prev else None
    for i, r in enumerate(rows):
        r["points_to_next_rank_up"] = {"owner_id": rows[i - 1]["owner_id"], "first_name": rows[i - 1]["first_name"], "points": rows[i - 1]["points"] - r["points"]} if i else None
        r["points_ahead_of_next_rank_down"] = {"owner_id": rows[i + 1]["owner_id"], "first_name": rows[i + 1]["first_name"], "points": r["points"] - rows[i + 1]["points"]} if i + 1 < len(rows) else None

    # notes for Mike: where the published list and his stated rules disagree
    notes = []
    for r in rows:
        if r["adjustment"]:
            notes.append(f'{r["first_name"]}: published {r["published_points"]} but his stated formula gives {r["published_points"] - r["adjustment"]} for his own numbers ({r["adjustment"]:+d}). Kept as a frozen adjustment.')
    for season, res in sorted(results.items()):
        if season > snap_season:
            continue
        for u, ev in res.items():
            pub = base["owners"][owners[u]["display_name"]]
            bonus = list(pub["scoring_bonuses"])
            for flag, val, label in ((ev["led_scoring"], 15, "led the league in scoring (+15)"), (ev["last_scoring"], -15, "was last in scoring (-15)")):
                if flag:
                    if val in bonus:
                        bonus.remove(val)
                    else:
                        notes.append(f'{owners[u]["first_name"]} {label} in {season} per Sleeper standings, but the published bonus list has no matching entry.')
            if ev["unbeaten_regular_season"] and not ev["perfect_season"]:
                notes.append(f'{owners[u]["first_name"]} went unbeaten in the {season} regular season but is not a "perfect season" here (treated as unbeaten through the title).')
    notes.append("Jon's published all-time win% is .493 but 81-94 is .463.")
    notes.append(base["formula"]["record_bonus_note"])

    result = {
        "name": "Legacy Rankings", "as_of": {"season": cur_season, "last_scored_week": cur_week},
        "snapshot": base["snapshot"], "formula": F, "asterisk_legend": {ASTERISK: ASTERISK_NOTE},
        "assumptions": [
            "Starts from Mike's published list (through the 2025 playoffs); everything since comes from Sleeper.",
            "All-time record counts only games played while still in contention for the Bria Bowl or the Sacko (same rule as the Tegridy Factor).",
            "Playoff record and playoff wins are winners-bracket games only; losers-bracket (toilet bowl) games count toward the all-time record only.",
            "Division title = best regular-season record in the division, ties broken by points scored.",
            "Led/last in scoring uses Sleeper's regular-season points-for standings.",
            "Perfect season = champion with no losses (and no ties) in counted games.",
            "Titles, sackos and scoring bonuses count once the season/regular season is decided; playoff appearances once the playoffs begin; the record bonus updates every week.",
        ],
        "review_notes_for_mike": notes, "rankings": rows,
    }
    dump(OUT / "legacy_rankings.json", result)
    dump(OUT / "asterisks.json", {
        "symbol": ASTERISK, "meaning": ASTERISK_NOTE,
        "about": "The league was on ESPN before 2019 and that data can't be pulled. Anything derived from Sleeper data starts in 2019, so the UI should show an asterisk next to it. Stats that include the ESPN years come only from Mike's published Legacy Rankings baseline.",
        "legacy_inclusive": {
            "where": "owner_profiles/<id>.json -> all_time and legacy; legacy_rankings.json; owner_profiles/index.json -> all_time, legacy_*",
            "stats": ["legacy points and rank", "all-time record and win%", "championships", "sackos", "division titles", "playoff appearances", "playoff record",
                      "Bria Bowl appearances/record (where Mike's post gives them)"]},
        "asterisk_2019_plus": {
            "owner_profile_sections": ["tegridy_factor", "record", "trophies", "scoring", "luck", "efficiency", "faab_and_transactions",
                                       "faab_efficiency", "head_to_head", "seasons"],
            "index_fields": ["since_2019", "faab_spent", "trades", "luck", "efficiency", "tegridy_factor", "tegridy_rank",
                             "faab_points_per_dollar", "faab_efficiency_rank", "faab_par_per_dollar", "faab_par_rank", "points_for", "points_against"],
            "files": ["tegridy_alltime.json", "<season>/tegridy.json", "penalties.json", "injury_starts.json", "bye_starts.json", "faab_efficiency.json",
                      "rivalries.json", "protected_rivalries.json", "<season>/weeks.json", "<season>/efficiency.json"],
            "note": "Points for/against, runner-ups, luck, efficiency, FAAB, trades, head-to-head and the Tegridy Factor have no ESPN-era data at all. The 2019+ versions of record, titles, sackos, playoff stats are also kept (as `since_2019`) next to the legacy-inclusive all-time numbers."},
    })
    if cur_week:
        dump(hist_dir / f"{cur_season}-wk{cur_week:02d}.json", {"season": cur_season, "week": cur_week, "ranks": {r["owner_id"]: r["rank"] for r in rows},
                                                                 "points": {r["owner_id"]: r["points"] for r in rows}})

    print(f"Legacy Rankings as of {cur_season} week {cur_week}")
    print(f"{'#':<3}{'owner':<8}{'pts':>6}{'pub':>6}{'since':>6}{'vs snap':>8}{'wk':>4}   C  S  Div  Apps  record")
    for r in rows:
        a = r["all_time"]
        print(f"{r['rank']:<3}{r['first_name']:<8}{r['points']:>6}{r['published_points']:>6}{r['points_since_snapshot']:>+6}{r['rank_change_since_snapshot']:>+8}{(r['rank_change_week'] if r['rank_change_week'] is not None else 0):>+4}"
              f"   {a['championships']}  {a['sackos']}  {a['division_titles']:>3}  {a['playoff_appearances']:>4}  {a['record']['wins']}-{a['record']['losses']}" + (f"-{a['record']['ties']}" if a['record']['ties'] else "") + f" ({a['win_pct']:.3f})")


if __name__ == "__main__":
    main()
