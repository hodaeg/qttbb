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
