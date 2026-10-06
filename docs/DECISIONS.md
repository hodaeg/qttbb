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

### D8 — Score design: start at 100, itemised deductions — Proposed
Starts at 100; weights are in `config/league.json` so they change without code changes. Every deduction carries a plain-English `detail` so the score is an audit trail rather than an opinion. Clamped to 0–100.
Signals: empty starting slot, Out/Doubtful starter, points left on the bench, stale lineup (weight 0 for now), high lineup efficiency (small bonus).
**Open:** the actual weights are first guesses. Early-season scores are tightly bunched (91–99) and need tuning once more data is in.

### D9 — Keep the objective score separate from "drama" — Proposed
The score is computed automatically from data only. Subjective things (drama, conduct) should not be folded into it, or arguments about the score become arguments about people.
**Open:** whether the score has consequences (draft position, playoff penalty) or is bragging-rights only. Get the league's buy-in on the rules first.

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

---

## Infrastructure

### D13 — Cache the NFL player database for 24h, including in CI — Accepted
`/players/nfl` is a multi-MB endpoint Sleeper asks to be called about once a day. It is cached in `.cache/` with a sidecar timestamp (file mtime does not survive a CI cache restore) and persisted between Actions runs with `actions/cache`, keyed by UTC date. Worst case is one fetch per day.

---

## Open questions

1. Which protected rivalry pairs, and do they carry stakes? (D7)
2. Final integrity weights, and does the score have consequences? (D8, D9)
3. Do we want a Sunday-inactives source to close the Questionable→Out gap? (D11)
4. Front-end contract: does the Figma design need any fields the JSON doesn't have yet?
