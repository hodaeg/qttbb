# QTTBB — Quest to the Bria Bowl

Data pipeline for our Sleeper league: rivalry tracking and the **Tegridy Factor** (a fair-play penalty count: higher means less tegridy).
No dependencies beyond Python 3.10+ (stdlib only). The Sleeper API is public, free and read-only.

## Run it

```
python scripts/fetch.py      # league data for every Sleeper season -> data/raw/
python scripts/nfl_injuries.py  # official NFL injury reports, every season -> data/raw/nfl_injuries/
python scripts/nfl_context.py  # NFL schedule + each player's team by week (for bye detection)
python scripts/score.py      # -> data/processed/
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

**`<season>/weeks.json`** — `{ "<week>": [ { roster_id, points, optimal_points, efficiency, points_left, empty_slots, zero_point_starters[], bench_misses[], injured_starters{}, stale_lineup, snapshots_available } ] }`

**`<season>/tegridy.json`** — `[ { roster_id, owner_id, tegridy_factor, events: [ { week, kind, penalty, detail } ] } ]`, sorted lowest (best) first. Every penalty carries a plain-English `detail`.

**`tegridy_alltime.json`** — `{ "<owner_id>": { total, by_season: { "<season>": n } } }`, sorted lowest first.

**`<season>/efficiency.json`** — `[ { roster_id, owner_id, weeks, points, optimal_points, efficiency } ]`. A *skill* stat (how well a manager sets lineups), deliberately **not** part of Tegridy Factor.

**`injury_starts.json`** — every instance of starting an Out/Doubtful player across all seasons: `{ rule, by_owner: { "<owner_id>": { out, doubtful } }, instances: [ { season, week, roster_id, owner_id, player_id, player, pos, status, source, injury } ] }`. `source` is `nfl_report` (retroactive) or `snapshot` (live).

**`bye_starts.json`** — every instance of starting a player whose NFL team was on bye (and who scored 0): `{ rule, by_owner, instances: [ { season, week, roster_id, owner_id, player_id, player, pos } ] }`. Also exposed per week as `bye_starters` in `weeks.json`.

**`rivalries.json`** — one entry per owner pair: `{ a, b, protected_rivalry, a_wins, b_wins, ties, games_played, a_points, b_points, biggest_a_win, biggest_b_win, games[] }`. `protected_rivalry` is the rivalry name when the pair is listed in `config/league.json`, otherwise `null`.

## Tegridy Factor

A running total of fair-play penalties. **Starts at 0, only goes up, lower is better.** There is no 100-point scale to erode. Weights live in `config/league.json` and can be changed without touching code.

| Penalty | Points | Source |
|---|---|---|
| Started a player on their NFL team's bye (and they scored 0) | 10 each | NFL schedule + weekly player teams |
| Started a player listed **Out** on the official NFL injury report (and they scored 0) | 8 each | NFL injury report (all seasons) |
| Empty starting slot | 5 each | Matchups |
| Started a player listed **Doubtful** on the report (and they scored 0) | 3 each | NFL injury report (all seasons) |
| Out/Doubtful at a game-day snapshot and still in the final lineup | same as above | Game-day snapshots (live weeks) |
| Identical lineup to last week | 0 (tracked only) | Matchups |

Lineup efficiency and points left on the bench are **not** penalised: they measure how good a manager is, not whether they play fair. They're published separately in `efficiency.json`. Optimal-lineup math is verified against Sleeper's own `ppts` field.

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for why each choice was made and what's still open.

### Known limits

- Rosters with no matchup in a week (playoff byes, eliminated teams) are skipped entirely: Sleeper returns a stale carried-over lineup for them. They have no row in `weeks.json` for that week.
- The NFL report is the Friday/Saturday version, so a Questionable player who is ruled out on Sunday isn't flagged. Retroactive counts are a floor, not a ceiling.
- Sleeper stores no injury history. Injury flags exist only for weeks where a snapshot was taken.
- Snapshots run on a schedule and GitHub cron can be late, so a flag means "Out at snapshot time and still in the final lineup", not an exact kickoff comparison.
- `/players/nfl` is a multi-MB endpoint Sleeper asks to be called about once a day. The scripts cache it locally for 24h.
