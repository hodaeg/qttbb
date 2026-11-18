---
name: integridy-rules
description: The league's Tegridy Factor rules and how to verify a penalty. Use before changing anything in scripts/score.py, config/league.json (tegridy), config/commissioner_penalties.json or the penalties shown on the history site, and whenever someone questions a penalty or a refresh adds new ones.
---

# Tegridy Factor rules

A penalty count. Everyone starts at 0, higher is worse, and only **fair-play** violations count, never lineup skill. The full history is in `docs/DECISIONS.md` (D8, D11, D12, D14-D18, D21, D22, D25, D60). The site and the code both call it **Tegridy Factor** (the site briefly said "Integridy"; see D59, D70).

## The one principle that overrides everything

**A starter who took the field that week is never an injury penalty.** It doesn't matter what any status said. If he played, scored points, or got hurt in the game, it's no penalty. (D60, after Gabe's Drake Maye in 2026 week 10 was wrongly penalised: Maye played, got hurt and scored 3.02.)

"Took the field" means `ByeDetector.took_field()`: the player is in `data/raw/player_points/<season>/wkNN.json`, which lists exactly the players with Sleeper `gp >= 1` or non-zero points.

A **stats row is not proof of playing**. Sleeper writes rows for inactive players, so `ByeDetector.played()` (row exists) must not be used to clear or convict anyone on its own.

## Violations (weights in `config/league.json` → `tegridy.weights`)

| Kind | Rule | Base |
|---|---|---|
| `bye_week_starter` | Started a player whose NFL team had no game, and he scored 0 | 10 |
| `injured_starter_out` | Listed Out (official report or a game-day snapshot), started, **did not play**, scored 0 | 8 |
| `questionable_did_not_play` | Listed Questionable, started, did not play, scored 0 | 6 |
| `missed_league_note` | Commissioner's ledger (`config/commissioner_penalties.json`, status `confirmed`) | 5 |
| `injured_starter_doubtful` | Listed Doubtful, started, **did not play**, scored 0 | 3 |

Not penalties: empty slots (D22), stale lineups, bench points or efficiency (D16), and Questionable players who played.

**Multipliers (D21):** ×1.5 three to four weeks before the playoffs, ×1.75 one to two weeks before, ×2 in a playoff game that still counts (D17: winners bracket up to your first loss, losers bracket up to your first win). Commissioner penalties have no multiplier.

**Rosters with no matchup** that week (byes, eliminated teams) are skipped entirely (D14).

## Why the sources can't be trusted on their own

- **Game-day snapshots** (`scripts/snapshot.py`, `.github/workflows/snapshot.yml`) are meant to be pre-kickoff, but GitHub cron drifts by hours. A snapshot often runs mid-game or Monday night, so "Out" there is frequently an in-game injury.
- **Archived NFL injury report pages** can be updated after the game. 2024 week 4 lists Rashee Rice as "Out (Knee)" with "Full Participation in Practice": he got hurt in that game.
- So every injury flag needs **scored 0 AND did not take the field**, whichever source raised it.

## Guard rail

`check_fair_play()` in `scripts/score.py` stops the run, writing nothing, if any counted injury penalty went to a starter who scored or took the field. Don't weaken it to make a run pass. Fix the rule that produced the bad flag instead.

## Verifying a penalty someone disputes

1. Find it in `data/processed/penalties.json` by id (`<season>-w<wk>-r<roster>-<kind>-<player_id>`), and read `evidence` and `sources`.
2. Look up his points in that week's matchup (`data/raw/seasons/<season>.json` → `matchups[wk]` → `players_points`), and whether he's in `data/raw/player_points/<season>/wkNN.json`.
3. If he scored anything, or appears in player_points, he played: it is not a penalty. Fix the rule, not the single entry.
4. When rules change, diff `penalties.json` before and after, and report every removed or added penalty with owner, player and points. Only ever tighten silently; any rule that would **add** penalties needs the commissioner's (Levi's) sign-off first.

## After any change

Run, from the repo root:

```bash
python scripts/score.py && python scripts/faab.py && python scripts/legacy.py && python scripts/profiles.py && python scripts/rivalries.py
```

Then rebuild the site (`history/`: `npm run build`), which regenerates `src/generated/tegridy.json` and checks that each member's penalties add up to their total. Record the change as a new D-entry in `docs/DECISIONS.md`.
