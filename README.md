# QTTBB — Quest to the Bria Bowl

Data pipeline for our Sleeper league: rivalry tracking and an Integrity score.
No dependencies beyond Python 3.10+ (stdlib only). The Sleeper API is public, free and read-only.

## Run it

```
python scripts/fetch.py      # league data for every Sleeper season -> data/raw/
python scripts/nfl_injuries.py  # official NFL injury reports, every season -> data/raw/nfl_injuries/
python scripts/score.py      # -> data/processed/
python scripts/snapshot.py   # game-day lineup + injury snapshot -> data/raw/snapshots/
```

GitHub Actions does this automatically: `refresh.yml` daily, `snapshot.yml` around kickoff windows.

## Layout

| Path | What |
|---|---|
| `config/league.json` | League ID, protected rivalries, integrity weights |
| `scripts/` | Fetch, snapshot and scoring code |
| `data/raw/` | Untouched API data. `snapshots/` is the only injury history that exists; it can't be backfilled |
| `data/processed/` | JSON for the front end (shapes below) |

## Processed data shapes

**`owners.json`** — `{ "<user_id>": { user_id, display_name, team_name, avatar } }`. Join key everywhere is `owner_id`/`user_id`, not `roster_id` (roster ids can change between seasons).

**`<season>/weeks.json`** — `{ "<week>": [ { roster_id, points, optimal_points, efficiency, points_left, empty_slots, zero_point_starters[], bench_misses[], injured_starters{}, stale_lineup, snapshots_available } ] }`

**`<season>/integrity.json`** — `[ { roster_id, owner_id, score, events: [ { week, kind, delta, detail } ] } ]`, sorted best-first. Every deduction carries a plain-English `detail`.

**`injury_starts.json`** — every instance of starting an Out/Doubtful player across all seasons: `{ rule, by_owner: { "<owner_id>": { out, doubtful } }, instances: [ { season, week, roster_id, owner_id, player_id, player, pos, status, source, injury } ] }`. `source` is `nfl_report` (retroactive) or `snapshot` (live).

**`rivalries.json`** — one entry per owner pair: `{ a, b, protected_rivalry, a_wins, b_wins, ties, games_played, a_points, b_points, biggest_a_win, biggest_b_win, games[] }`. `protected_rivalry` is the rivalry name when the pair is listed in `config/league.json`, otherwise `null`.

## Integrity score

Starts at 100. Weights live in `config/league.json` and can be changed without touching code.

| Signal | Source |
|---|---|
| Empty starting slot | Matchups |
| Starter listed Out/Doubtful on the official NFL injury report who scored 0 | NFL injury report (all seasons) |
| Starter who was Out/IR/Doubtful at a game-day snapshot and stayed in | Game-day snapshots (live weeks) |
| Points left on the bench vs. the best possible lineup | Matchups |
| Identical lineup to last week | Matchups (weight 0 by default) |
| High lineup efficiency (bonus) | Matchups |

Optimal-lineup math is verified against Sleeper's own `ppts` field.

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for why each choice was made and what's still open.

### Known limits

- The NFL report is the Friday/Saturday version, so a Questionable player who is ruled out on Sunday isn't flagged. Retroactive counts are a floor, not a ceiling.
- Sleeper stores no injury history. Injury flags exist only for weeks where a snapshot was taken.
- Snapshots run on a schedule and GitHub cron can be late, so a flag means "Out at snapshot time and still in the final lineup", not an exact kickoff comparison.
- `/players/nfl` is a multi-MB endpoint Sleeper asks to be called about once a day. The scripts cache it locally for 24h.
