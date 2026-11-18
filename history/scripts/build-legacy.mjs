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

// ---- Tegridy Factor: each current member's total, rank and every penalty that counted (2019+, Sleeper era)
const config = read('../config/league.json').tegridy;
const allPen = read('../data/processed/penalties.json').penalties;
const index = read('../data/processed/owner_profiles/index.json');
const owners = (Array.isArray(index) ? index : (index.owners ?? index.profiles ?? Object.values(index))).filter((o) => o && o.owner_id);
const tg = [];
const firstOf = (id) => {
  const p = people.find((x) => x.id === id);
  return p.nickname ?? p.name.split(' ')[0];
};
for (const o of owners) {
  const prof = read(`../data/processed/owner_profiles/${o.owner_id}.json`);
  if (!prof.in_current_league) continue;
  const person = bySleeper[prof.display_name];
  if (!person) throw new Error(`No person in people.json has the sleeper name "${prof.display_name}"`);
  const t = prof.tegridy_factor;
  const pens = allPen
    .filter((p) => p.counts && p.manager.owner_id === o.owner_id)
    .map((p) => ({
      id: p.id,
      kind: p.kind,
      label: p.label,
      season: Number(p.season),
      week: p.week ?? null,
      headline: p.headline
        .split(prof.display_name)
        .join(firstOf(person))
        .replace(/ at \d{4}-\d\d-\d\dT[\d:.]+(?:Z|[+-]\d\d:\d\d)/g, '') // "Out at 2026-11-10T04:36:01+00:00" -> "Out"
        .replace(/, so \$0 of FAAB was taken\./, '.'),
      sources: (p.sources ?? []).filter((s) => s && s.name).map((s) => ({ name: s.name, url: s.url ?? null })),
      base: p.penalty.base,
      mult: p.penalty.multiplier,
      total: p.penalty.total,
      when: p.timing?.phase ?? null,
    }))
    .sort((a, b) => a.season - b.season || (a.week ?? 99) - (b.week ?? 99));
  const sum = pens.reduce((s, p) => s + p.total, 0);
  if (Math.abs(sum - t.total) > 0.01) throw new Error(`Tegridy for ${person}: penalties add to ${sum}, profile says ${t.total}`);
  tg.push({ person, total: t.total, rank: t.rank, bySeason: t.by_season, cleanSeasons: t.clean_seasons ?? [], penalties: pens });
}
tg.sort((a, b) => a.total - b.total || a.person.localeCompare(b.person));
writeFileSync(
  resolve(root, 'src/generated/tegridy.json'),
  JSON.stringify({ weights: config.weights, multipliers: config.multipliers, asOf: lr.as_of, members: tg }, null, 1),
);
console.log(`tegridy: ${tg.length} members, ${tg.reduce((n, m) => n + m.penalties.length, 0)} penalties`);
