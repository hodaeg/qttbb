# Decision log

Running record of what we decided, why, and what's still open. Newest entries at the bottom of each section.
Status: **Accepted** (agreed with the league owner), **Proposed** (suggested, not yet confirmed), **Superseded**.

App working name: *Tegrity Factor and Rivalry Hub* (from the repo's initial README). League: **Quest to the Bria Bowl** (Sleeper league `1387848854157664256`).

---

## Scope and platform

### D1 — Sleeper, not ESPN — Accepted
The old ESPN league (ID 846108, pre-2018) was probed through ESPN's API, the old `games.espn.com` URLs, and the Wayback Machine. ESPN support confirmed the data is permanently deleted. Not worth revisiting.
The league now lives on Sleeper, which has a free, public, read-only API with no key or billing. History goes back to **2019** via `previous_league_id`.

### D2 — This repo is the data layer only — Accepted
The owner is a UX designer and builds the front end from Figma designs. This repo produces versioned JSON (shapes documented in the README) and does not contain UI code.

### D3 — Python, stdlib only — Accepted
No dependencies to install, nothing to break in CI. Scripts live in `scripts/`.

### D4 — Private GitHub repo `hodaeg/qttbb` — Accepted
The repo holds friends' usernames, lineups and integrity scores, so it is private. It was created public by default and switched to private before anything was pushed.
Scheduled GitHub Actions commit refreshed data back to the repo (`refresh.yml` daily, `snapshot.yml` around kickoffs).

### D5 — Join on `owner_id`, never `roster_id` — Accepted
Roster IDs can change between seasons; owner (user) IDs are stable. All cross-season data (rivalries, all-time stats) is keyed by owner.

---

## Rivalries

### D6 — Head-to-head is computed across every Sleeper season — Accepted
Pairs are built from `matchup_id` per week. Playoff games are included and tagged `playoff: true`.

### D7 — Protected rivalries are configured, not computed — Accepted (pairs still open)
New "protected" rivalries for this year go in `config/league.json` (`protected_rivalries`, matched on Sleeper display name). A pair listed there gets its rivalry name in `rivalries.json`. The placeholder entry is inactive.
**Open:** which pairs, and what "protected" means in practice (any special scoring/stakes?).

---

## Integrity score

### D8 — Integrity score as a 100-point scale with deductions — Superseded by D16
First proposal: start at 100 and subtract weighted penalties, with a bench-points deduction and an efficiency bonus. Replaced because the 100-point baseline is arbitrary and full seasons drifted into the 60s from bench-points deductions alone.

### D9 — Keep the objective score separate from "drama" — Proposed
The score is computed automatically from data only. Subjective things (drama, conduct) should not be folded into it, or arguments about the score become arguments about people.
**Open:** whether the score has consequences (draft position, playoff penalty) or is bragging-rights only. Get the league's buy-in on the rules first.

### D16 — Tegridy Factor: a penalty count, not a score to erode — Accepted
Named by the owner (a South Park reference). **Starts at 0, only goes up; higher = less tegridy.**
- Only **fair-play** violations count. Lineup *skill* does not: bench points left and lineup efficiency are excluded, since they measure how good an owner is, not whether they play fairly. They are published separately (`efficiency.json`) as a stat, not a penalty or bonus.
- No 100-point baseline: "erode from 100" was arbitrary.
- Penalties stay weighted (not a plain count), because the owner ranked bye starts above injury flags (D15). Current weights: bye 10, Out 8, empty slot 5, Doubtful 3, stale lineup 0. They live in `config/league.json` (`tegridy.weights`).
- Output renamed: `<season>/tegridy.json` (lowest first), plus `tegridy_alltime.json`.
- Replaced `integrity.json`; removed the `points_left` penalty and `efficiency_bonus` entirely.
**Observation:** results are heavily skewed toward few penalties: all-time, 2 of 12 managers have 0, and the max is 45 (TheBoarHouse). Of 195 total penalty points: Out 96, empty slot 50, bye 40, Doubtful 9.
**Resolved by D22:** empty slots do not count.

### D10 — Optimal-lineup math validated against Sleeper — Accepted
Our "best possible lineup" matches Sleeper's own `ppts` field exactly for all 12 rosters (2026, weeks 1–4). Dedicated slots are filled first, then flex slots.

### D11 — Retroactive "started an out player" rule — Accepted
For past seasons there is no injury history in Sleeper, so the owner defined a rule using the **official NFL injury report** (`nfl.com/injuries/league/<season>/reg<week>`):

> A starter counts as an out player if the report lists their **Game Status as Out or Doubtful** AND they **scored 0** in the starting lineup.

- Matching is by normalised player name + position (suffixes like Jr./III and accents ignored). Team is deliberately not used, because Sleeper only stores a player's *current* team.
- Team defenses (DEF) can't match, as the report lists individual players.
- Only rows with a game status are stored (`data/raw/nfl_injuries/`), to keep the repo small.
- Source scraped at ~1 request per 1.5s; `robots.txt` does not disallow `/injuries/`. Finished weeks are never re-fetched.

**Known limits (undercounts, never overcounts):**
- The report is the Friday/Saturday version. A player listed *Questionable* who is then ruled out Sunday morning appears as Questionable, so he is **not** flagged. The Sunday inactive list would catch these but isn't on this page.
- Players on IR or otherwise absent from the report aren't flagged.
- A *Doubtful* player who plays and scores 0 is flagged, which is a rare false positive but follows the rule as given.

### D12 — Game-day snapshots for current/future weeks — Accepted
Sleeper keeps no injury history, so `snapshot.py` records every starting lineup and each starter's injury status at set times (Thu night, Sunday windows, Monday night). Flag = "Out/Doubtful at snapshot time and still in the final lineup". This cannot be backfilled, so it needs to run from the start of a season.
**Caveat:** GitHub cron can run 5–30 minutes late, so snapshots are scheduled well before kickoff and aren't exact-to-kickoff.

### D14 — Ignore rosters with no matchup that week — Accepted
Found when the owner checked BigDogsRevenge, 2022 Week 15: a playoff bye. Sleeper returns `matchup_id: null` for byes and eliminated teams, but still includes a `starters` list that is a stale carry-over of the last real lineup (here, identical to Week 14). Scoring it produced false flags (Pierce and Deebo Samuel "started" when the real roster had them on the bench).
Rule: if `matchup_id` is null, the roster is skipped entirely for that week (no flags, no deductions, no bonus, no row in `weeks.json`). No game means no lineup consequences.
Effect: 19 → 15 instances; removed 2020 wk16 Duke Johnson, 2022 wk15 Pierce + Samuel, 2023 wk17 Courtland Sutton.
**Lesson:** validate flags against what the manager actually saw in the app before treating them as findings. Spot-check any instance that will be shown to the league.

### D15 — Bye-week starters are tracked and penalised more heavily than injured starters — Accepted
A starter counts as a bye-week start if they scored 0 **and** their NFL team had no game that week. Rosters with no matchup are excluded first (D14).
Sources, both Sleeper's *undocumented* `api.sleeper.com` endpoints, so they could change: the NFL schedule (a bye = a team absent from that week's games) and weekly stats (the player's team **that week**, since Sleeper only stores a player's current team).
Players on bye have no stats row that week, so their team is taken from the nearest week with a row (8 back, then 4 forward). Team defenses are keyed by team abbreviation, so they resolve directly.
Result: 4 instances across 2019-2026 (TheBoarHouse 3, BigDogsRevenge 1). All 249 zero-point starter slots could be classified, none unknown. Spot-checked against known bye weeks, and none was a stale lineup.
**Weight: -10 per bye starter** (owner's call: heavier than an injury flag). An Out starter is -8 and a Doubtful starter -3. Reasoning: a bye is known weeks in advance with no ambiguity, so unlike late injury news it can't be blamed on information arriving late.

### D17 — Only games that decide the title or last place count in the playoffs — Accepted
Owner's rule: the league only cares about first place and last place. So after a manager's fate is decided, their remaining playoff games (third-place, consolation) are ignored for Tegridy Factor.
- **Winners bracket:** games count up to and including the first one you **lose**.
- **Losers bracket** (toilet bowl): games count up to and including the first one you **win** (that saves you from last place).
- **Regular season:** always counts. Byes already produce no penalties (D14).
- Computed from `winners_bracket` / `losers_bracket` (now fetched per season) and the actual matchups. Output: `<season>/playoff_relevance.json`; each `weeks.json` row carries `counts_toward_tegridy` and `excluded_reason`.
- Excluded penalties are removed from the totals and from `instances`, but listed under `excluded` in `injury_starts.json` / `bye_starts.json` so they can be reviewed.

**Two things found while building this:**
1. In Sleeper's losers bracket, `w` is the **lower** scorer (the team that keeps advancing toward last place), the opposite of the winners bracket. Verified: winners bracket `w` = higher scorer in 49/49 past games; losers bracket `w` = lower scorer in 49/49 once adjusted points are used. Because of this, results are decided from actual points, never from `w`/`l` labels.
2. Sleeper's `custom_points` (a commissioner adjustment) overrides `points` when set. It appears on exactly one matchup in 8 seasons: TheBoarHouse, 2025 week 17 (138.5 pts adjusted to 121.9, a -16.6 deduction), which flipped the bracket result. Results use the adjusted figure (`effective_points`).

**Effect:** exactly one penalty changed: Hodaeg's 2023 week 17 (Trevor Lawrence, Out), a third-place game after losing the semifinal. Hodaeg's all-time total 16 → 8. Injury starts 15 → 14.
Assumptions: one game per bracket round (true in all 8 seasons); a tied game doesn't end relevance (none exist).

### D18 — "Questionable, then didn't play" counts, at 6 points — Accepted
Motivating case: TheBoarHouse started Terry McLaurin in 2026 week 4. The Friday NFL report listed him Questionable, he was ruled out Sunday, and he scored 0. D11's Out/Doubtful-only rule missed it (the known Questionable gap).
Rule: a starter who is listed **Questionable** on the official report, **has no Sleeper stats row that week** (did not play), and **scored 0** counts as a penalty of **6** (`questionable_did_not_play`; lighter than Out = 8 because the status was less certain at the time of the report).
Retroactive result: **6 instances** across 2019-2026, all confirmed valid by the owner: Hodaeg 2022 wk4 (Kamara), ChinaKing 2023 wk16 (Reed), Gingivitis 2024 wk6 (Cook), JSusee 2024 wk9 (Cooper), TheBoarHouse 2025 wk5 (Bowers) and 2026 wk4 (McLaurin).
Not counted: 23 Questionable starters who played and scored 0.
**Known limit:** "didn't play" also covers a player who was active but never got in the game, which can't be told apart from a true inactive with this data. Going forward, game-day snapshots (D12) record the actual status live. First scheduled run: Thursday 2026-10-08.
Playoff relevance (D17) still applies; excluded games don't count.

### D19 — Departed members stay as they are for now — Accepted
Sleeper only removes members in the offseason, and TheBoarHouse (who left in 2026) still appears as a member with a roster. Their history stays in all leaderboards and rivalries unchanged. Revisit after the season: options are a "former member" flag or hiding them.

### D20 — Sleeper's app can show wrong bye information for old weeks — Noted
The owner saw JSusee's 2024 week 9 Michael Pittman marked as on a bye. He wasn't: he scored 1.9, and weekly stats put him on IND (the 2024 week 9 byes were PIT and SF). Sleeper's player record now lists him on PIT, so the app appears to show his *current* team's bye on an old week. The pipeline uses the team **as of that week**. Treat Sleeper's app as unreliable for historical bye/team labels when spot-checking; check `data/raw/player_teams/` and the schedule instead.

### D21 — Penalties weigh more the closer to the playoffs — Accepted
Owner's rule: a violation matters more when more is at stake. The multiplier depends on how many weeks before **that season's** playoff start the game is:

| When | Multiplier |
|---|---|
| In the playoffs (a game that still counts, per D17) | **2.0x** |
| 1-2 weeks before the playoffs | **1.75x** |
| 3-4 weeks before the playoffs | **1.5x** |
| 5+ weeks before | 1.0x |

Applied to each penalty: `penalty = base_penalty x multiplier`. Events record `base_penalty`, `multiplier` and `penalty`; `weeks.json` rows and the injury/bye instance lists carry `multiplier`. Tiers live in `config/league.json` (`tegridy.multipliers`).
**Schedule change is handled per season.** The playoff start comes from each season's own Sleeper settings: week **14** in 2019-2020, week **15** from 2021 onward (the regular season gained a week in **2021**, not two years ago as remembered; 2019-2020 had 13 regular-season weeks, 2021+ have 14). Nothing is hard-coded.
Effect on all-time totals (before -> after): TheBoarHouse 57 -> 82, BigDogsRevenge 36 -> 53.5, therealGandB 27 -> 34.75, ChinaKing 22 -> 28, gabroni 10 -> 17.5, Hodaeg 14 (unchanged), others small.
Interpretation note: "2 or less" was read as 1-2 weeks out and "4-3" as 3-4 weeks out, so the last regular-season week counts as 1 week out.

### D22 — Empty starting slots no longer count — Accepted
Owner's ruling: leaving a slot empty is a **tactic**, not a fair-play violation. Example: a manager who has already clinched the win (BigDogsRevenge 2023 playoffs, TheBoarHouse 2022 playoffs) leaves slots empty so a bad game can't cost them points. That is also why it shows up mostly in the playoffs.
`empty_slot` weight is now **0**. It is still recorded (`empty_slots` in `weeks.json`) but produces no penalty. Resolves the open question from D16.
Effect: removed 8 penalties (all-time before -> after, with timing multipliers): TheBoarHouse 82 -> 57, BigDogsRevenge 53.5 -> 33.5, gabroni 17.5 -> 0, ToadLicker 7.5 -> 0, MrSeeYou 21 -> 16, therealGandB 34.75 -> 29.75.
Note: this makes the score cleaner: every remaining penalty is "played someone who wasn't playing" (injured, inactive, or on bye).

### D23 — Every penalty carries its own evidence — Accepted
The front end must show not just *what* a penalty cost but *why*. New file `data/processed/penalties.json` holds one rich record per penalty (counting ones, plus excluded ones listed with `counts: false` and an `excluded_reason`, so the UI can explain "this didn't count because...").
Each record contains: stable `id`; `headline` (one display-ready sentence); `label`; `penalty` {base, multiplier, total}; `manager`; `player` (name, position, NFL team *as of that week*, lineup slot); `nfl_game` (opponent, home/away, date; null on a bye); `evidence` (report status, injury, practice status, "did not play", rule text, or bye details); `bench_option` (the best bench player who could have filled the slot, with his points); `matchup` (opponent, score, result, margin, and whether the bench option would have changed the result); `timing` (phase, weeks before playoffs, playoff round and bracket, multiplier reason); `sources` (link to the official NFL injury report page).
Per-season `tegridy.json` events link to these via `penalty_id`. Bye starters are now one penalty per player (previously grouped); totals unchanged.
Needed one new data set: `data/raw/nfl_games/<season>.json` (full schedule with opponent and date).
Neutral by design: `bench_option_would_have_changed_result` is information for the UI. It does not affect points.
Totals verified unchanged after the change (sum 210.75 across all managers).

### D24 — Per-owner profile objects — Accepted
`scripts/profiles.py` (runs after `score.py`) writes `data/processed/owner_profiles/<owner_id>.json` plus `index.json` (one summary row per owner for league tables). Each profile has: Tegridy Factor (total, rank, by season, by penalty kind, links to every penalty), record (regular season / postseason / total, PF, PA, averages), trophies, scoring highs/lows and streaks, luck, efficiency, FAAB and transactions, head-to-head with nemesis and favorite victim, and a per-season breakdown.
**Definitions:**
- *Championship* = winner of the winners-bracket final. *Sacko* = last place (12th), the loser of the losers-bracket final. In Sleeper's losers bracket the `w` team is the *lower* scorer (see D17), so within each losers-bracket pair the higher scorer places better.
- *Postseason* record includes every playoff-week game (third-place and consolation too). Regular season is separate.
- *Luck* = regular-season wins minus the wins expected from your weekly scores against everyone (all-play).
- *Efficiency* is a skill stat and not part of Tegridy Factor (D16).
- Points come from weekly matchups, commissioner-adjusted where set (D17).
**Validated against Sleeper:** win-loss-tie records match exactly for all 96 roster-seasons; champions match Sleeper's own `latest_league_winner_roster_id` in every season it exists (2022-2025); sackos match the independent last-place logic in every season; 7 completed seasons produce 7 champions and 7 sackos.
**Known differences (shown, not hidden):**
1. *Season points*: weekly matchup totals differ slightly from Sleeper's season standings in some seasons (up to 14 points, mostly 2019; small in later years), which is probably stat corrections after the fact. Each season carries `sleeper_standings_reported` for comparison. The all-time PF uses the weekly matchup numbers.
2. *FAAB*: the transaction log's winning bids are reported as `spent`. Sleeper's own `waiver_budget_used` equals `spent + traded out - traded in` for 81 of 96 roster-seasons; the other 15 are reported as `unexplained_difference`. Largest by owner (all-time): therealGandB +145, BigDogsRevenge +62, TheBoarHouse +50. Likely commissioner FAAB edits or refunds that aren't in the log; cause not confirmed.
**Resolved by D25:** the FAAB differences are commissioner penalties for missed league notes.

### D25 — Missed league note: FAAB the commissioner takes counts as a penalty, 5 each — Accepted
League rule: every member must post a league note once a year. If they don't, the commissioner takes FAAB. Each instance is one Tegridy penalty of **5 points** (kind `missed_league_note`, weight `tegridy.weights.missed_league_note`), lighter than starting an Out player (8) or a bye player (10).
Sleeper doesn't log these deductions. They were discovered as FAAB that Sleeper counts as used but the transaction log doesn't explain (D24), always in **$25 units**. They now live in a ledger the commissioner owns: `config/commissioner_penalties.json` (owner, season, `faab_taken` per instance, `instances`, `status`). Only `confirmed` entries count.
**Ledger as of the commissioner's confirmation (10 instances, $270):** therealGandB 2020 x1 ($25), 2022 x1 ($20), 2023 x1 ($25), 2024 x3 ($25 each); BigDogsRevenge 2025 x1 ($50); TheBoarHouse 2021 x1, 2025 x1 ($25 each); WhiskeyDicknCo 2025 x1 ($25).
**Amendments after review:**
- WhiskeyDicknCo 2025 and therealGandB 2022 (the $20 one) were confirmed as real penalties.
- BigDogsRevenge 2025 is **one** penalty with $50 taken (the amount was increased), not two separate $25 penalties.
- Repeat offender: every penalty record now has `evidence.lifetime_instance`, `lifetime_total` and `repeat_offender`, and the ledger supports an optional `description` shown with the penalty. The three 2024 penalties for therealGandB ("Green and Bowled") carry a repeat-offender description.
Effect on all-time Tegridy Factor: therealGandB 59.75 (6 instances), TheBoarHouse 67 (2), BigDogsRevenge 38.5 (1), WhiskeyDicknCo 9.5 (1).
Later the commissioner confirmed two more (both treated as missed league notes): BigDogsRevenge 2019 ($12) and gabroni 2022 ($11). BigDogsRevenge is now a repeat offender (2019, 2025). Ledger total: 12 instances, $293. Tegridy Factor: BigDogsRevenge 43.5, gabroni 5.
Then ToadLicker 2019 ($22) and 2024 ($13), and MrSeeYou 2019 ($6), were added (the commissioner said ToadLicker has two more penalties, matching those two gaps exactly). Ledger total: 15 instances, $334.
**FAAB now reconciles for every owner and season** (D26 explains the refunds). **Resolved:** the commissioner confirmed MrSeeYou has just the one ($6, 2019); there is no second penalty.
**No timing multiplier** (D21): these aren't tied to a game week, so they carry `week: null`, `multiplier: 1.0` and `timing.phase: "season_long"`. The playoff relevance rule (D17) doesn't apply either.
**Reconciliation:** after the ledger, TheBoarHouse's FAAB gap is exactly $0. What remains is small and old (e.g. 2019 +6 to +22, 2021 refunds of -18 and -28 from the week-1 commissioner corrections, plus a few others), left as `remaining_unexplained`.
Penalty records for these have `player`, `nfl_game`, `matchup` and `bench_option` as null; the evidence is the rule, the FAAB taken, and the instance number.

### D26 — Commissioner-undone waiver claims are refunds; first names added — Accepted
**Refunds.** On 2021-09-06 the first batch of week-1 waiver claims processed; on 2021-09-07 at 11:44am the commissioner dropped those players and Sleeper refunded the bids. The transaction log still shows the original claims as complete, so logged bids exceeded the $100 budget (ToadLicker $124, MrSeeYou $117). Rule now in `profiles.py`: if the commissioner drops a player a roster won by waiver, the most recent earlier claim for that player is treated as reversed: it doesn't count toward `spent`, and is reported as `refunded`. Result: ToadLicker refunded $28 (Ty'Son Williams $15, Sony Michel $10, Jakobi Meyers $3) and MrSeeYou $18 (Rhamondre Stevenson $6, Marquez Callaway $12), matching Sleeper's numbers exactly. `faab.spent` is now net of refunds.
**Result: every owner's FAAB reconciles to the dollar** (logged bids - refunds + traded out - traded in + ledger penalties = Sleeper's `waiver_budget_used`).
**First names.** `config/members.json` maps Sleeper display name to first name (commissioner's request, for display in the app). `first_name` is now on `owners.json`, each owner profile and the index, and each penalty's `manager`. Penalty headlines still use the Sleeper display name; the UI can choose.

### D27 — FAAB efficiency ("Bang for Buck"): starting-lineup points per FAAB dollar — Accepted
Derived from the data: every winning waiver claim names the player and the bid; weekly matchups show when he was on the owner's roster and whether he started.
**Definition:** for each claim, follow the player on that roster from the first week he appears until he leaves; add up the points he scored **while in the starting lineup** (bench points don't help the owner). Owner efficiency = those points / dollars bid. All weeks count (regular season and playoffs).
- Only claims of **$1 or more** are "paid"; $0 claims are tracked separately so free pickups don't inflate the ratio.
- Claims the commissioner later undid (and Sleeper refunded) are ignored (D26). Dollars tie to the FAAB `spent` figures exactly.
- Each claim has an outcome: `started`, `never_started` (benched), or `dropped_before_playing` (gone before he showed on a roster for a game week: 46 paid claims, $252, 3.8% of dollars, counted as spent with no return; 194 more were benched the whole time).
- Output: `data/processed/faab_efficiency.json` (league, per-owner with per-season, and every claim), and a `faab_efficiency` block on each owner profile plus `faab_points_per_dollar` and rank in the index.
**League result:** 797 paid claims, $6,686 -> 15,996 points = **2.39 points per $1**; 70% of paid claims got a start. Best: DangerDave678 3.61, Gingivitis 3.31, gabroni 3.15. Worst: TheBoarHouse 1.20, therealGandB 1.24, Hodaeg 1.30.
**Limits:** raw points ignore what the owner would have started without the claim (D28 adds points above replacement), and bench stashes bought on purpose (handcuffs, injury stashes) look like busts. Treat it as a spending-value stat, not a skill verdict. It is not part of Tegridy Factor.
### D28 — Points above replacement (PAR) for FAAB claims — Accepted
Added to D27 at the commissioner's request: a claim's value is how far above a replacement-level player he scored, not raw points.
**Definition:** for each week a claimed player started, PAR = his points minus the **position replacement level for that season**. Replacement level = the season points per game of the **(N+1)th best player at the position** among ALL NFL players (league scoring, minimum half the scored weeks played), where N = the average number started at that position across the league per week. Same for every owner. `par_per_dollar` = PAR / bid; owners are ranked on it (`par_rank`) alongside the raw "Bang for Buck" rank. Each claim carries a week-by-week breakdown.
**Data:** `data/raw/player_points/<season>/wkNN.json`, league-scored points for every QB/RB/WR/TE/K/DEF who played, computed from Sleeper's raw weekly stats and the league's own `scoring_settings`. Validated: it reproduces Sleeper's recorded points for 151 of 151 rostered players in a test week.
**Typical replacement levels (points per game):** QB 16-18, RB ~10, WR ~10, TE 7-9, K ~7.5, DEF 6-8.
**Method history (two approaches rejected, kept here so we don't repeat them):**
1. *Best eligible bench player that week.* Rejected: 42% of started weeks had no bench alternative (91% for kickers, 66% for defenses), counted as 0 points, which inflated K/DEF/QB claims; it also blamed claims for the owner's lineup mistakes (a week-8 Walker start was scored -21.5 because the owner benched a 33-point player).
2. *Weekly (N+1)th best of all players.* Rejected: an oracle that picks each week's best non-starters after the fact; produced a negative league PAR (-734), i.e. the average claim looked worse than replacement.
3. *Season points-per-game ranking, (N+1)th* (final): an achievable level. League result: 797 paid claims, $6,686, **+848 points above replacement = $0.13 per $1**.
**Results (PAR per $1):** gabroni 0.49, JSusee (Suze) 0.31, DangerDave678 0.29, TheBoarHouse 0.20, ToadLicker 0.19, BigDogsRevenge 0.19, Gingivitis 0.16, WhiskeyDicknCo 0.08, ChinaKing -0.01, Hodaeg -0.08, therealGandB -0.14, MrSeeYou -0.18. Compared with raw points per dollar, MrSeeYou drops from 5th to last, and TheBoarHouse rises from last to 4th.
**What it shows:** only 248 of 797 paid claims (31%) beat replacement. By position of the claimed player: defenses are the best buy (+$0.84 per $1 over 199 claims), QBs +0.28, TEs +0.11, RBs ~0 (211 claims, $2,978, 45% of all dollars), WRs negative (-0.18), kickers negative (-0.51).
**Limits:** it still can't tell a deliberate bench stash (handcuff, injury stash) from a bust; replacement level is season-wide, not tied to what was actually available that week; a thin bye-week roster can force a below-replacement start through no fault of the claim.
**Open:** none.

### D29 — Protected rivalries set up for 2026 — Accepted
Six rivalries, configured in `config/league.json` (`protected_rivalries`, matched on Sleeper display name): **Levi vs Gabe** (Hodaeg / gabroni), **Max vs Jon** (MrSeeYou / BigDogsRevenge), **Suze vs Zaid** (JSusee / TheBoarHouse), **Ging vs Adam** (Gingivitis / ChinaKing), **Mike vs Kyle** (WhiskeyDicknCo / ToadLicker), **Dave vs Jordan** (DangerDave678 / therealGandB). The first-listed owner is side "a".
**Names are placeholders** ("Levi vs Gabe", etc.): the commissioner hasn't named them yet. Rename in the config; `rivalries.json` and the rivalry files pick the name up.
`scripts/rivalries.py` writes `data/processed/protected_rivalries.json`: for each pair, a rich object with the all-time series (also split regular season / playoffs), headline, current streak and longest streaks for each side, last meeting, last 5, upcoming meetings, results by season and seasons won, biggest wins, closest game, highest-scoring game, every playoff meeting (labelled: championship, third-place game, toilet bowl final, etc.), trades between the two, and a side-by-side of both owners (record, titles, sackos, Tegridy Factor, FAAB value, luck). It cross-checks against the all-pairs `rivalries.json`: all six series match exactly.
**Findings while building it:**
1. All six rival pairs are scheduled to meet in **week 14**, the last regular-season week of 2026, which looks deliberate. Ging vs Adam also meet in week 5 (next week).
2. Sleeper lists playoff-week pairings (weeks 15-17) and a phantom week 18 before the playoffs exist. These are placeholders, not real games, so upcoming meetings show **regular-season weeks only**.
3. Sleeper's matchup data is keyed by text week numbers, so "week 10" sorts before "week 5"; everything that lists weeks must sort numerically.
Playoff-game kind comes from the brackets. Note the losers-bracket "final" decides last place (the loser keeps advancing, D17): e.g. Ging beat Adam in the 2022 toilet bowl final, which meant Adam finished last.

### D30 — Legacy Rankings computed automatically; asterisk for 2019+ data — Accepted
Mike used to build the Legacy Rankings by hand from a spreadsheet. They now update on their own. They are the league's de facto all-time record (ESPN years included), and Sleeper data only goes back to 2019.
**Method.** `config/legacy_baseline.json` freezes Mike's published list (post-2025-playoffs, which includes the ESPN years before 2019). `scripts/legacy.py` adds everything since from Sleeper (2026 onward) using his scoring rules: championship +100, sacko -80, division title +15, playoff appearance +5, playoff win +10, led league in scoring +15, last -15, perfect season +100, and +/-20 for every .025 of all-time win% above/below .500. The all-time record counts only games played while still in contention for the Bria Bowl or the Sacko (the same rule as D17). Titles and sackos count when the season is decided, playoff appearances once the playoffs start, the record bonus every week. Output: `legacy_rankings.json`, with a snapshot per week in `legacy/history/` for week-over-week movement. The daily refresh runs it. Full surnames in the post are not stored (first names only).
**Validation.** Subtracting the Sleeper-era (2019-2025) results from Mike's totals gives sensible, non-negative pre-2019 numbers for everyone: owners who were around the whole time have 86-93 pre-2019 games each, late joiners fewer (Ging 28, Gabe 35). Mike's scoring-leader and last-place bonuses match Sleeper's standings for every season from 2019 on, except Adam 2025 (below).
**Differences between Mike's post and his stated rules (listed for Mike in `review_notes_for_mike`).** Totals that don't follow the formula for his own numbers: Kyle +5, Suze -5, Levi +10, Gabe +10, Jon -20, Ging +10, Zaid +20 (5 of 12 reproduce exactly). Jon's win% is printed .493 but 81-94 is .463. Adam was last in scoring in 2025 (1,303.8 pts vs. 1,325.7) with no -15 in his list. Levi went 14-0 in the 2024 regular season but got no +100. Each owner's difference is kept as a frozen `adjustment`, so the app reproduces Mike's published list exactly today and moves on its own from there.
**Interpretations to confirm (all editable):** (1) "every .25%" is read as every .025 of win%, truncated toward zero; a literal .0025 would be off by hundreds. (2) "Perfect season" = champion with no losses (Levi's 14-0 regular season doesn't count). (3) Playoff record and playoff wins = winners-bracket games only. (4) Division title = best record in the division, ties broken by points. (5) Led/last in scoring uses Sleeper's regular-season points-for.
**Asterisks.** `asterisks.json` lists every stat that is 2019+ only (Sleeper-era): Tegridy Factor, points for/against, FAAB and efficiency, luck, trades, head-to-head, runner-ups and the Sleeper-only versions of record/titles/sackos. Owner profiles list them in `asterisk_sections`; the index lists `asterisk_fields` and groups the 2019+ record, titles and sackos under `since_2019`. Legacy-inclusive stats (legacy points/rank, all-time record, titles, sackos, division titles, playoff appearances and record, Bria Bowl record where Mike's post gives it) are under `all_time` and `legacy`. The index is now sorted by legacy rank.
**Index change:** the flat `wins/losses/ties/win_pct/championships/runner_ups/sackos/playoff_appearances` fields became `since_2019` (asterisked), computed on the same "still in contention" basis as the all-time record. `tegridy_alltime`-style ordering moved to `legacy_rank` ordering.
**Bria Bowl appearances:** only Mike (4-0), Kyle (3-1), Dave (0-5), Ging and Adam (none) are known before 2019 from the post; for others finals losses before 2019 are unknown, so their total appearances show as unknown.

---

## Infrastructure

### D13 — Cache the NFL player database for 24h, including in CI — Accepted
`/players/nfl` is a multi-MB endpoint Sleeper asks to be called about once a day. It is cached in `.cache/` with a sidecar timestamp (file mtime does not survive a CI cache restore) and persisted between Actions runs with `actions/cache`, keyed by UTC date. Worst case is one fetch per day.

---

## Open questions

1. Which protected rivalry pairs, and do they carry stakes? (D7)
2. Final Tegridy weights, and does the score have consequences? (D9, D16)
3. ~~Sunday-inactives source for the Questionable→Out gap~~ — mostly closed by D18; revisit only if the active-but-didn't-play ambiguity becomes a problem.
4. Front-end contract: does the Figma design need any fields the JSON doesn't have yet?

---

## Bria Bowl History app

### D31 — The repo is public — Accepted (supersedes D4)
Levi made `hodaeg/qttbb` public on 2026-11-16 so the history site can be served from GitHub Pages. Everything in the repo is therefore public: league data, Tegridy penalties, the commissioner penalty ledger, first names, and the history content with full names. This was Levi's decision, made knowingly. Nothing secret (tokens, cookies) has ever been committed.

### D32 — Bria Bowl History: a scrollytelling site in `history/` — Accepted
Levi's annual league note: a mobile-first single-page site telling the league's story from 2002 to now, with two views on one timeline (roster story, friend web). Brief: `docs/history-brief.md`. Approved plan summary:
- Lives in `history/`. Hand-edited content in `history/content/` (`people`, `roster`, `connections`, `story`, `legacy-manual`), because `/data` belongs to the pipeline.
- Stack: Vite + TypeScript + Svelte 5, GSAP + ScrollTrigger, SVG friend web with hand-rolled ring layout. Deployed to GitHub Pages by a workflow, redeployed after each data refresh.
- **Stats come from the pipeline** (legacy rankings, 2019+ champions/sackos/records), asterisked as 2019+ where Sleeper-derived. Champions for 2011-2018 are hand-filled in `legacy-manual.json` (ESPN data is gone).
- Visual design: Claude proposes, restyles to Levi's Figma when it arrives; all tokens.
- **Bar: showstopper interaction design** (award-level editorial scrollytelling). Scroll is the playhead (fully reversible), nothing teleports, choreographed motion, signature moments prototyped first (the 2011 pour, the dial).
- Review checkpoints after phase 2 (scroll story) and phase 4 (column expansion).
This reverses the earlier working rule that Claude doesn't build front end: Levi asked for this one explicitly.

### D33 — History content: what was assumed — Accepted, open items
Content files were filled from the brief and pass a consistency check (31 people: 22 members, 9 outsiders; 12 unique per season; story joins/exits match the roster grid for every season; the friend web is one connected graph; the current 12 map 1:1 to Sleeper names).
- Kalyn's nickname is "Ging" throughout (the brief also says "Ginge"; the pipeline uses Ging).
- Zaid's column runs through 2026: members are only removed in the offseason (D19).
- Two connections are marked `inferred` (Alex Randall to Alex Hoover and Tim Underhill, from "that weekend brought them into our sphere") for Levi to confirm.
- People ids are `first-last`; story text marks tappable names as `[[id|Name]]`.
**Open:** the 2014 exit-message quote (placeholder), 2011-2018 champions, avatars, member colours (placeholders), per-person stories and anecdotes (TODO).

### D34 — History app: phases 1-2 built (checkpoint 1) — Accepted
Built and verified in a phone-sized preview: title screen; pre-league beat (avatars pop into their future slots as each person is met); the 2011 pour (twelve columns fill, staggered); glass story cards over the columns with tappable names; exits (column caps, avatar arcs to the alumni pile, count updates); entries; Stephen's return with a "returns" badge; the compressed 2017-now era with champion/sacko cards; a finale with the live Legacy Rankings; person and alumni bottom sheets.
**How it works:** one fixed stage; every element's position is a pure function of the scroll position (`history/src/lib/model.ts`), so the whole story scrubs forwards and backwards. No animation library was needed for this phase, so GSAP is not installed (the plan allowed adjusting the stack). Bundle: about 85 KB of JS (29 KB gzipped) against a 200 KB budget.
**Stats wiring:** `history/scripts/build-legacy.mjs` runs before each build and reads `data/processed/legacy_rankings.json`; champions and sackos for 2019+ come from the pipeline and are asterisked. `history/scripts/validate.mjs` checks the content files and fails the build on errors.
**Deploy:** `.github/workflows/pages.yml` (push to main, after each data refresh, or manual). Needs Pages turned on with Source "GitHub Actions".
**The 2014 exit message** is now in `story.json` (transcribed from Levi's screenshot).
**Not done yet / known rough edges:** the dial (phase 3), column expansion (phase 4), friend web (phase 5); the liquid edge is a simple wobble, not yet a real meniscus; the wide-screen layout needs a design pass; nothing has been tried on a real iPhone.


### D35 — History app: checkpoint 1 feedback, first design revision — Accepted
Levi's notes after checkpoint 1, and what changed:
- **Exits.** A leaving column no longer just stops. It drains through a small funnel into a thread that runs under the other columns (shown as a faint groove across them), turns muted grey, runs to the right gutter and climbs to the alumni pile. The avatar slides down its own column and rides the same thread, passing beneath the other columns. Geometry lives in `threadAt` in `history/src/lib/model.ts`; each exit gets its own lane in the gutter.
- **No rounded corners anywhere.** Cards and the sheet have one clipped corner (`--cut`); columns, chips and avatars are square.
- **Glass.** `Glass.svelte`: heavier frosting, plus an edge layer that brightens and saturates the colour behind it, and a glint that travels along the edge as the card moves up the screen. Cards fade per layer, because fading a wrapper switches backdrop filters off.
- **Colour.** Gold is parked: `--accent` now equals the ink colour, so big type is white and the member colours carry the page.
- **Type.** The serif is gone. Three sets to compare, switched with a temporary "Type A/B/C" button (or `?type=a|b|c`): A Big Shoulders Display + Instrument Sans, B Bricolage Grotesque + Hanken Grotesk, C Archivo Expanded + Archivo. All display type goes through the `.display` class and tokens in `tokens.css`.
**Temporary:** the type switcher and loading all three font sets; remove both once Levi picks one.
**Open:** the gutter threads will share space with the dial (phase 3).

### D36 — History app: second design revision (clear columns, docked cards, the dial) — Accepted
Levi's notes on D35: floating cards hid the columns exactly where they change hands, and he did not want a leaving column to shrink into a thread. **The thread idea from D35 is dropped.**
- **Three zones that never overlap:** header avatars, the column field, and a card tray docked at the bottom. The playhead sits just above the tray. Nothing is drawn over the columns except their own markers.
- **Card tray** (`Tray.svelte`): one pane of glass, one card at a time; each card owns a stretch of its year's scroll (`seq` in `makeLayout`), one leaves before the next arrives. Cards that don't fit get "Read more", which opens the whole card in the bottom sheet. In the tray, in/out chips show faces only.
- **Columns are cut, not ended:** a leaving column is sliced on the diagonal at the season line and its replacement starts with the matching slice. Grey then climbs the old ribbon from the cut. A grey copy of the leaver's avatar stays at the cut as a marker.
- **Leaving avatars** swing down over the columns and up to the alumni pile, one after another when several leave in the same year (Levi chose "cut marker + fly").
- **Season markers on columns:** a trophy on the champion's column and an X on the sacko's, for seasons the pipeline has results for (2019 on). Faint lines mark each season.
- **The giant year numeral is gone.** The year lives on the **dial** (`Dial.svelte`, phase 3 pulled forward): a wheel half off the right edge. Scrolling turns it; dragging it scrolls the story by year; a flick carries and settles on a year; tapping a year jumps to it; arrow keys step. Mapping is `stopAt` / `wAtStop` in `model.ts`.
- Type is tabled: set A stays the default and the temporary switcher (now a small "A/B/C" button) stays.
**Tested:** phone-sized preview with simulated pointer events. **Not tested:** real touch (does a dial spin ever scroll the page), haptics, light mode, wide screens.
**Open:** the pre-league years (2002-2010) have an empty field above the tray; the sacko mark is a plain X for now.

### D37 — History app: third design revision (one avatar per person, hanging cut, shake, founders' lattice, real pile) — Accepted
Planned on Fable 5.2, built on Opus 5.5. Levi's notes on D36 and what changed:
- **One avatar per person, always.** The grey marker at the cut is gone. An avatar is the head of its own column: a newcomer pops in just below the cut, rides it up and docks in the header. When the newcomer gets close, the leaver (greyed with their column) is pushed up off the top and drops in from above onto the alumni pile; several leavers land one after another. A returner (Stephen) rises off the pile and rides up from below his new cut with the "returns" badge. All of it is a function of scroll, so scrolling back reverses it (the leaver comes back down from the top; the newcomer rides back down with their column). `avatarState()` in `model.ts`.
- **Hanging cut.** The last stretch of a cut ribbon is a separate tail that tips back into the screen (rotateX), with a shadow growing from the tip up, and jitters with scroll speed.
- **Shake and fade.** When a cut arrives the column does a damped shake (about 750ms) and its colour drains to grey on the same envelope, so it is grey exactly when it settles. This is the one beat that runs on the clock rather than the scroll; scrolling back restores the colour without a shake. `stepCuts()` in `Story.svelte`.
- **Founders' lattice.** Founding members' ribbons carry a faint harlequin lattice (one diamond per column width), weaker once grey. Strength token `--regal`.
- **The pile is a pile.** Every alumnus is stacked with small offsets and rotations, newest on top. Tapping it fans the avatars out to the left and down with names; tapping one there opens their sheet; tap again, tap outside or scroll to close. The alumni drawer (`AlumniPanel.svelte`) is removed.
- **Fix:** the stage is now `overflow: clip`; with `hidden`, focus or scrollIntoView could scroll the whole stage sideways.
**Not tested:** real touch, how the shake reads on a phone, light mode, wide screens.

### D38 — History app: phone feedback round (dial, scroll jump, ribbons under the card, stars) — Accepted
Levi's notes from his iPhone, and what changed:
- **Scrolling up jumped down first.** Cause: the story is laid out in screen heights and was re-laid-out on every resize; on iPhone the address bar returning shrinks the window, so every band shrank and the story leapt forward. Fix: lay out once against the large viewport (a `100lvh` probe) and size the stage to it; the bar now just overlays the bottom.
- **Dial was finicky.** Causes: a grab with no movement counted as a tap and jumped to the year under the finger; one year was only ~18px of travel; after release the wheel snapped back to the smoothed scroll. Fix: 6px slop before a drag starts, ~30px per year, a still grab never moves the story, the dial draws its own value until the scroll catches up. **Hold to zoom:** resting for 320ms (before or during a drag) zooms in like a video scrubber: quarter-year sub-ticks, 4x finer travel, settles on the nearest quarter, "Fine" label, lighter haptic.
- **Dial moved to the bottom right**, level with the card tray.
- **Name links** wear the person's avatar colour (members only).
- **Ribbons run under the card** to the bottom of the screen, darkened, with the card's shadow falling on them just above it. Cuts and avatars still happen at the playhead.
- **Founders' ribbons** get a fine serrated (pinking-shear) edge, via CSS mask.
- **Championship stars:** a trophy rising toward the header merges into its owner's avatar and becomes a gold star; stars sit in a row under the avatar and the newest pushes the others apart as it grows (2019 on, until earlier champions are supplied). Token `--gold`.
**Not tested:** the address-bar fix and the dial on a real iPhone (I can only simulate touch).

### D39 — History app: scrubber, founders grow in, flexible card, year markers, ripple, photos — Accepted
Levi's next round, and what changed:
- **Dial removed; a year scrubber instead.** A rail of tick marks down the right gutter, fading into the alumni pile at the top and the bottom of the screen. Tap = jump to that year. Hold 0.2s = the rail bulges at the finger (a fisheye that magnifies 4x, plus a swell to the left), quarter-year ticks appear inside the bulge, and dragging scrubs at 4x finer travel; letting go settles on the nearest quarter. A swipe that moves before 0.2s is an ordinary page scroll (`touch-action: pan-y`, and touchmove is only blocked once the hold has fired).
- **Founders grow in:** each founder's ribbon grows up from the bottom of the screen with their avatar on its tip. Before the league the ribbons are all in the "under the card" shadow; when 2011 starts the colour pours down them, staggered by column.
- **Every ribbon runs to the bottom of the screen** and falls away into a dark shade there. One continuous element per ribbon now (the separate "under" pieces and the pour lip are gone); the card's shadow is a gradient inside each ribbon that starts at the card's live top edge.
- **The card flexes** with its content (up to the old maximum), springing between sizes; a card that doesn't fit scrolls inside the glass. "Read more" and the card sheet are gone. The playhead stays at the maximum card position so the story never jumps when cards resize.
- **Year markers:** a faint line across the field at every year, badged on Levi's ribbon. Cuts land on them.
- **Ripple, not edge wobble:** the pouring edge's wobble read as a glitch. Now soft bands of light and shade travel down all ribbons while scrolling (opacity follows scroll speed), with a small phase lag per column.
- **Photos:** cards can carry `photos`. They slide in from the left one after another, each later one tucked underneath and a little higher, and all leave right as the next card arrives (cards with photos get more scroll). Tap opens the photo. New "Parallel Dat Park" card after Japs; new outsider Jake.
- **Real avatars** for 21 people (resized to 192px squares in `public/avatars/`); a colour ring is drawn over the photo.
**Not tested:** real touch on iPhone (the hold-vs-scroll handoff in particular), the ripple's look on a phone.

### D40 — History app: scrubber hold rebuilt, calmer motion, quieter glass — Accepted
- **Scrubber hold glitched on iPhone.** Likely cause: the rail allowed vertical panning (`pan-y`), so the browser and the scrubber both moved the page under the finger; and the bulge was a fisheye that re-mapped ticks around a moving finger, so the scale swam. Now the rail never pans the page (`touch-action: none`), and a hold pins a fine (4x, quarter-year) scale where it started: the tick under the finger is the value and nothing on the scale moves; only the swell and the marker follow the finger. Tap still jumps; moving before the hold does nothing.
- **Avatars no longer overshoot** off the top when founders grow in (ease-out, no spring).
- **No ribbons before 2009.** Founders appear with the first card from 2009 on that names them (Levi with "Freshman year", Tim with "On his brother's instruction").
- **Photos stack the other way:** the first one climbs up as each new one arrives on top, where it was.
- **Ripple removed** (flickered, too uniform). Ribbons sway sideways by a pixel or so while scrolling, each on its own phase.
- **Cut seam:** the hanging tail now overlaps the ribbon by 2px so no hairline of background shows at the hinge.
- **Glass restyled** after the iOS look Levi pointed to: frosted fill, a soft light rim along the top edge, a quiet shadow. No clipped corner ("notch"), no moving glint, no saturating edge filter.
- **Eyebrow labels removed:** the era label above cards, the year above card titles, the intro kicker, the finale's kicker and the alumni panel label.
- New avatars: Ging, Levi, Stephen, Luke, Adam. Japs gets the Petey story.

### D41 — History app: honours on the avatars, arrows for ins and outs, two new type sets — Accepted
- **Founders grow at scroll speed** (their ribbon tip rises 1px per px scrolled, like every ribbon that rides up from a cut), instead of shooting up over a tenth of a screen.
- **Newcomers arrive big:** every avatar shows up at 1.55x, spread over its ribbon, and shrinks to size over the last third of a screen before it docks.
- **Colour washes in with "The league is born"**, not at the first 2011 card.
- **Ins and outs:** out = a red arrow, right aligned, pointing right; in = a green arrow, left aligned beneath it, pointing left (in from the edge). Faces only.
- **Honours, all scroll-driven:** a title's star now lands with the avatar swelling (up to 1.24x) and glowing gold. Frames: 1st title a gold-foil frame, 2nd a platinum frame outside it, 3rd gold chevrons on their ribbon (different from the founders' lattice). A sacko's X slams onto the avatar (2.4x to 1x), the avatar shakes, then the X shrinks into a row along the top. Each plays over ~130–240px of scroll so it can be seen.
- **Type sets B and C replaced:** B = Schibsted Grotesk (newsroom, heavy and tight); C = Anybody stretched wide in caps with Figtree for text. A unchanged.
- Story cards get a 2px radius. "Tattoo Adam" is a different person from league Adam: new outsider `tattoo-adam`. Jon's avatar; Josh's crop lowered.

### D42 — History app: the ESPN-era results, title edges on ribbons, silver stars — Accepted
- **2011–2018 champions and sackos** from Levi, in `content/legacy-manual.json`: 2011 Zaid/Adam, 2012 Mike/Adam, 2013 Ben/Andy, 2014 Max*/Zaid, 2015 Kyle/Jon, 2016 Kyle/Max, 2017 Mike/Zaid, 2018 Max/Suze. Max's 2014 title carries an asterisk ("the dubious trade") on its trophy, its star and his person sheet. New manual fields: `asterisks` (year → why) and `silverStars` (year → [{person, why}]); first silver star: Levi 2024, undefeated regular season (14-0). It rides up the ribbon and joins the star row in silver.
- **Title borders go on the ribbon edges, not the avatar** (frames were too busy): 1st title gold foil down both edges, 2nd platinum just inside it, 3rd gold chevrons. With the ESPN years in, Mike and Kyle now have chevrons.
- **Avatars pass behind photos and cards** (avatars 10, photos 11, card 12).
- **In arrow points right too:** red "out" arrow points off the card, green "in" arrow points into it.

### D43 — History app: counts instead of icon rows, ribbon textures, Adam Field — Accepted
- **Counts, not rows:** one gold star, one silver star and one sacko X per avatar, with "×N" once there is more than one. A new one bumps the icon and ticks the count halfway through its landing; the sacko stamp still slams onto the face and shrinks up onto the X.
- **All of a season's honours land together:** the silver star marker sits mid-season like the trophy and sacko X.
- **Ribbon dressing:** 4th title = double chevrons. Chevrons are inset 5px from the edges so they don't run into the foil. Current members who weren't founders get a fine dot texture; founders keep the lattice.
- **Season cards list silver stars** under champion and sacko (2024: Levi, undefeated regular season 14-0).
- **Toby, Jared and Stephen arrive with "Freshman year"** via a new card field `arrive` (ribbons that come in with a card that doesn't name them).
- **Adam Field** is the tattooed Adam. Alex Randall's house photo moved from Japs to "The visit" (2008).

### D44 — History app: honours land while their card is up; scrubber previews instead of scrolling — Accepted
- **Honours ride just under the year line** (cut depth + ~1.2 avatar below it) instead of mid-season, and a season with a champion gets at least a full screen of scroll; its first card stays up a little longer. Measured on a phone-size viewport: the season card appears, ~0.55–0.65 of a screen later the star and the sacko stamp land, and the card changes ~0.3 of a screen after that. A year's generated season card now leads its year (2017's comes before "The lineup holds"), so the honours land on the card that names them.
- **Scrubber hold no longer scrolls the page under the finger.** Even with `touch-action: none`, scrolling the window while a finger is down on iPhone kept fighting the browser. Now, while held, the story draws a preview playhead from the scrubber and the page scroll is untouched; on release the scrubber settles to the quarter and only then commits one `scrollTo`. Taps still scroll directly (no finger down during the animation).

### D45 — History app: honours land at the end of the year; Max's commissioner year — Accepted
- **Honours land as the year ends** (D44 had them landing early). Each marker is placed so the longest moment, the sacko stamp, completes ~0.1 screen before the next year line reaches the playhead; the star lands a little before that. Measured at phone size: the sacko settles 40–60px of scroll before the card changes. The 2017 season card goes back to closing its year.
- **"A tumultuous season" rewritten** around Max's one year as commissioner: the dubious trade with Ben, the (asterisked) title, voted out, Levi reinstated. The exit-message quote is removed from it, and "The coup" card is gone (its content is folded in).

### D46 — History app: a season card for every year — Accepted
- Every season from 2011 gets a generated champion/sacko card that closes its year (previously only 2017 on), so the honours always land on the card that names them; each year's band grows by one card's worth of scroll.
- "The league is born" no longer quotes Levi's own words back at him.
- Toby, Jared and Stephen arrive with "Dorm life" again (the card that names them); the `arrive` field stays available.

### D47 — History app: honours sit on the year line that closes their season — Accepted
- Each season's trophy, silver star and sacko X sit on the ribbon just above the year line that ends that season (~32px above it at phone size), so they land on the avatars just after that line passes.
- To match, each season's champion/sacko card now **leads the next year's stretch** of the timeline (new card field `at`, helper `shownIn()`), with ~0.95 of a screen of its own so the honours land while it's up. The current season, with no closing line yet, keeps its card and markers in its own year. Year lengths are now just the sum of their cards (the season minimum from D44 is gone).
- Measured at phone size: the season card appears as the line passes, the star and stamp land ~0.5–0.7 of a screen later, and the card changes ~0.3 of a screen after that.

### D48 — History app: quicker honours, next card sooner, merged cards — Accepted
- **Markers ride up 2.6x faster than the scroll** once they pass the playhead (star over 0.09 screen, stamp over 0.15 screen after arriving), so a season's honours land within ~0.3 screen of its closing year line.
- **Cut years (to 2016): the next story card follows right after**: the season card leading the next year is ~0.38 screen (+ a little for a fun fact, more for a story card carrying results). Measured: honours land with the year line ~220px from the top; the next card (who left, who joined) arrives with the line at ~115–190px. Later seasons keep ~1 screen each.
- **Merged cards:** "Wrestling" is the 2011 season card's fun fact, "The frat" the 2012 one's (story.json entries with `kind: "season"`). "Suze and Jordan" now precedes "A tumultuous season", which carries the 2014 champion/sacko lines itself (`results: 2014`) instead of a separate card.

### D49 — History app: 2014 twice as long, its own season card again — Accepted
- 2014 order: "A tumultuous season", "Suze and Jordan", then the generated 2014 champion/sacko card (leading 2015, as every season card does). The tumultuous card no longer carries the results (`results` stays supported).
- New `yearLength` map in story.json stretches a year's scrolling; 2014 is 2x.

### D50 — History app: expanded column (phase 4) — Accepted
- Tap a lit ribbon (founders once the colour has poured in; everyone after) and it opens across the field; the other eleven squeeze to thin slices on either side, in order. Tap a slice to switch; the minimize arrow (or Esc) returns to the story. Scrolling back before the league closes it.
- Expanded: no story cards, photos, header avatars or pile. The timeline below the playhead is drawn too, and cuts are flat: just a gap and the colour change.
- A panel sticks to the top of the open column: who holds it, the year under the playhead, the season just decided (it stays up through the next year, since honours land at the year line), and their running tally. At a cut the next person's panel rises with their ribbon and pushes the last one away. Each season's honours sit labelled on the ribbon at its closing line.
- Season card years no longer carry the Sleeper-era asterisk.

### D51 — History app: people open their column; sheets only for those without one — Accepted
- Tapping anyone who holds a column at the year under the playhead (header avatar, a name in a card, a connection) opens their expanded column instead of a sheet. Alumni, friends of the league, and anyone before the league starts still get the sheet.
- The column's panel carries everything the sheet had (seasons bar, legacy stats, titles and sackos, story, anecdotes, connections) under its sticky header, scrolling inside the panel (max ~64% of the screen). Phone slices are 5px with 2px gaps to give the open column more room.
