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
