# QTTBB — Quest to the Bria Bowl

Data pipeline for our Sleeper league: rivalry tracking and the **Tegridy Factor** (a fair-play penalty count: higher means less tegridy).
No dependencies beyond Python 3.10+ (stdlib only). The Sleeper API is public, free and read-only.

## Run it

```
python scripts/fetch.py      # league data for every Sleeper season -> data/raw/
python scripts/nfl_injuries.py  # official NFL injury reports, every season -> data/raw/nfl_injuries/
python scripts/nfl_context.py  # NFL schedule + each player's team by week (for bye detection)
python scripts/score.py      # -> data/processed/
python scripts/profiles.py   # per-owner profiles -> data/processed/owner_profiles/
python scripts/snapshot.py   # game-day lineup + injury snapshot -> data/raw/snapshots/
```

GitHub Actions does this automatically: `refresh.yml` daily, `snapshot.yml` around kickoff windows.

## Layout

| Path | What |
|---|---|
| `config/league.json` | League ID, protected rivalries, Tegridy Factor weights |
| `scripts/` | Fetch, snapshot and scoring code |
| `data/raw/` | Untouched API data. `snapshots/` is the only injury history that exists; it can't be backfilled |
| `data/processed/` | JSON for the front end (shapes below) |

## Processed data shapes

**`owners.json`** — `{ "<user_id>": { user_id, display_name, team_name, avatar } }`. Join key everywhere is `owner_id`/`user_id`, not `roster_id` (roster ids can change between seasons).

**`<season>/weeks.json`** — `{ "<week>": [ { roster_id, points, optimal_points, efficiency, points_left, empty_slots, zero_point_starters[], bench_misses[], injured_starters{}, stale_lineup, counts_toward_tegridy, excluded_reason, snapshots_available } ] }`. Rows with `counts_toward_tegridy: false` are playoff games that no longer mattered to that manager (see below); they stay in the file but produce no penalties.

**`<season>/playoff_relevance.json`** — `{ "<roster_id>": { bracket: "winners"|"losers", last_week, reason } }`. `last_week` is the last playoff week that counted for that roster (`null` = all of them).

**`<season>/tegridy.json`** — `[ { roster_id, owner_id, tegridy_factor, events: [ { week, kind, base_penalty, multiplier, penalty, detail } ] } ]`, sorted lowest (best) first. Every penalty carries a plain-English `detail`.

**`tegridy_alltime.json`** — `{ "<owner_id>": { total, by_season: { "<season>": n } } }`, sorted lowest first.

**`<season>/efficiency.json`** — `[ { roster_id, owner_id, weeks, points, optimal_points, efficiency } ]`. A *skill* stat (how well a manager sets lineups), deliberately **not** part of Tegridy Factor.

**`penalties.json`** — `{ penalties: [ ... ] }`, the main file for the Tegridy UI: one record per penalty with the data behind it. Includes penalties that did not count (`counts: false`, with `excluded_reason`).
```
{ id, season, week, kind, label, headline, counts, excluded_reason,
  penalty:  { base, multiplier, total },
  manager:  { owner_id, roster_id, display_name, team_name },
  player:   { player_id, name, pos, nfl_team, lineup_slot },
  nfl_game: { nfl_team, opponent, home, date } | null,        // null on a bye
  evidence: { ... },  // kind-specific: report_status, injury, practice_status, played, rule | nfl_team, team_played_that_week, rule
  bench_option: { player_id, name, pos, points, slot } | null, // best bench player who could have filled the slot
  matchup:  { opponent_display_name, points_for, points_against, result, margin, bench_option_would_have_changed_result },
  timing:   { phase, week, playoff_start_week, weeks_before_playoffs, playoff_round, playoff_bracket, multiplier_reason },
  sources:  [ { name, url } ] }
```
`kind` is one of `injured_starter_out`, `injured_starter_doubtful`, `questionable_did_not_play`, `bye_week_starter`. Events in `<season>/tegridy.json` link here through `penalty_id`.

**`owner_profiles/<owner_id>.json`** — one rich object per owner (`owner_profiles/index.json` has a summary row each, for league tables). Sections: `tegridy_factor` (total, rank, by_season, by_kind, penalty_ids), `record` (regular_season / postseason / total), `trophies` (championships, runner_up, third_place, sackos, playoff_appearances, first_round_byes, regular_season_titles; each `{count, seasons}`), `scoring` (highest/lowest score, biggest win, worst loss, close games, streaks), `luck`, `efficiency`, `faab_and_transactions` (spent, traded in/out, claims won/lost, adds/drops, trades, biggest bid, trade partner), `head_to_head` (by opponent, nemesis, favorite victim) and `seasons` (the same, per season). Join key is `owner_id`. See D24 for definitions and known differences from Sleeper's own totals.

**`injury_starts.json`** — every instance of starting an Out/Doubtful player across all seasons: `{ rule, by_owner: { "<owner_id>": { out, doubtful } }, instances: [ { season, week, roster_id, owner_id, player_id, player, pos, status, source, injury } ] }`. `source` is `nfl_report`, `nfl_report_dnp` (Questionable who didn't play) or `snapshot` (live).

**`bye_starts.json`** — every instance of starting a player whose NFL team was on bye (and who scored 0): `{ rule, by_owner, instances: [ { season, week, roster_id, owner_id, player_id, player, pos } ] }`. Also exposed per week as `bye_starters` in `weeks.json`.

**`rivalries.json`** — one entry per owner pair: `{ a, b, protected_rivalry, a_wins, b_wins, ties, games_played, a_points, b_points, biggest_a_win, biggest_b_win, games[] }`. `protected_rivalry` is the rivalry name when the pair is listed in `config/league.json`, otherwise `null`.

## Tegridy Factor

A running total of fair-play penalties. **Starts at 0, only goes up, lower is better.** There is no 100-point scale to erode. Weights live in `config/league.json` and can be changed without touching code.

| Penalty | Base points | Source |
|---|---|---|
| Started a player on their NFL team's bye (and they scored 0) | 10 each | NFL schedule + weekly player teams |
| Started a player listed **Out** on the official NFL injury report (and they scored 0) | 8 each | NFL injury report (all seasons) |
| Empty starting slot | 0 (tracked only; a tactic, D22) | Matchups |
| Started a player listed **Questionable** who then didn't play and scored 0 | 6 each | NFL report + Sleeper weekly stats |
| Started a player listed **Doubtful** on the report (and they scored 0) | 3 each | NFL injury report (all seasons) |
| Out/Doubtful at a game-day snapshot and still in the final lineup | same as above | Game-day snapshots (live weeks) |
| Identical lineup to last week | 0 (tracked only) | Matchups |

**Timing multiplier** (D21), applied to every penalty: in the playoffs 2.0x, 1-2 weeks before 1.75x, 3-4 weeks before 1.5x, otherwise 1.0x. Measured from each season's own playoff start (week 14 in 2019-2020, week 15 since 2021). Configurable in `tegridy.multipliers`.

**Playoffs:** only first place and last place matter. In the winners bracket, games count up to and including your first loss; in the losers bracket, up to and including your first win. Later games (third-place, consolation) are ignored. Excluded penalties are listed under `excluded` in `injury_starts.json` and `bye_starts.json`.

Lineup efficiency and points left on the bench are **not** penalised: they measure how good a manager is, not whether they play fair. They're published separately in `efficiency.json`. Optimal-lineup math is verified against Sleeper's own `ppts` field.

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for why each choice was made and what's still open.

### Known limits

- Rosters with no matchup in a week (playoff byes, eliminated teams) are skipped entirely: Sleeper returns a stale carried-over lineup for them. They have no row in `weeks.json` for that week.
- The NFL report is the Friday/Saturday version. A Questionable player who is ruled out on Sunday is caught only if they also had no stats row that week (D18); that can't distinguish a true inactive from an active player who never got in. Retroactive counts are a floor, not a ceiling.
- Don't spot-check old weeks against Sleeper's app for bye/team labels: it appears to show a player's *current* team (D20).
- Sleeper stores no injury history. Injury flags exist only for weeks where a snapshot was taken.
- Snapshots run on a schedule and GitHub cron can be late, so a flag means "Out at snapshot time and still in the final lineup", not an exact kickoff comparison.
- `/players/nfl` is a multi-MB endpoint Sleeper asks to be called about once a day. The scripts cache it locally for 24h.
