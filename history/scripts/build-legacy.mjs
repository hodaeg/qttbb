// Builds src/generated/legacy.json from the data pipeline (../data/processed) so the site's stats stay current.
// 2019 and later come from Sleeper (asterisked); earlier seasons come from content/legacy-manual.json.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => JSON.parse(readFileSync(resolve(root, p), 'utf8'));

const people = read('content/people.json').people;
const manual = read('content/legacy-manual.json');
const lr = read('../data/processed/legacy_rankings.json');
const bySleeper = Object.fromEntries(people.filter((p) => p.sleeper).map((p) => [p.sleeper, p.id]));

const rankings = [];
const seasons = {};
for (const r of lr.rankings) {
  const person = bySleeper[r.display_name];
  if (!person) throw new Error(`No person in people.json has the sleeper name "${r.display_name}"`);
  const a = r.all_time;
  rankings.push({
    person,
    rank: r.rank,
    points: r.points,
    rankChangeWeek: r.rank_change_week ?? 0,
    record: a.record,
    winPct: a.win_pct,
    championships: a.championships,
    sackos: a.sackos,
    divisionTitles: a.division_titles,
    playoffAppearances: a.playoff_appearances,
    playoffRecord: a.playoff_record,
  });
  for (const [year, s] of Object.entries(r.sleeper_era_by_season.seasons)) {
    const out = (seasons[year] ??= { champion: null, runnerUp: null, sacko: null, ledScoring: null, complete: s.season_complete, source: 'sleeper' });
    if (s.championship) out.champion = person;
    if (s.bria_bowl_appearance && !s.championship) out.runnerUp = person;
    if (s.sacko) out.sacko = person;
    if (s.led_league_in_scoring) out.ledScoring = person;
  }
}
for (const [year, champ] of Object.entries(manual.champions)) {
  seasons[year] ??= { champion: champ, runnerUp: null, sacko: manual.sackos?.[year] ?? null, ledScoring: null, complete: true, source: 'manual' };
}
for (const [year, why] of Object.entries(manual.asterisks ?? {})) if (seasons[year]) seasons[year].championAsterisk = why;
for (const [year, list] of Object.entries(manual.silverStars ?? {})) if (seasons[year]) seasons[year].silverStars = list;
rankings.sort((a, b) => a.rank - b.rank);

const out = {
  asOf: lr.as_of,
  asterisk: lr.asterisk_legend?.['*'] ?? '2019 and later only.',
  source: "Mike Whiting's Legacy Rankings, kept current from league data",
  rankings,
  seasons,
  notes: manual.notes ?? {},
};
mkdirSync(resolve(root, 'src/generated'), { recursive: true });
writeFileSync(resolve(root, 'src/generated/legacy.json'), JSON.stringify(out, null, 1));
console.log(`legacy: ${rankings.length} ranked, ${Object.keys(seasons).length} seasons (as of ${lr.as_of.season} week ${lr.as_of.last_scored_week})`);
