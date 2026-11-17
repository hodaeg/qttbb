// Checks the hand-edited content files agree with each other. Run: npm run validate
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => JSON.parse(readFileSync(resolve(root, p), 'utf8'));
const people = Object.fromEntries(read('content/people.json').people.map((p) => [p.id, p]));
const R = read('content/roster.json');
const conns = read('content/connections.json').connections;
const cards = read('content/story.json').cards;
const errs = [];

const seasons = {};
let last = null;
for (let y = R.firstSeason; y <= R.currentThrough; y++) seasons[y] = last = R.seasons[y] ?? last;
for (const [y, l] of Object.entries(seasons)) {
  if (!l || l.length !== 12 || new Set(l).size !== 12) errs.push(`${y}: needs exactly 12 different people`);
  for (const p of l ?? []) if (people[p]?.role !== 'member') errs.push(`${y}: "${p}" is not a member in people.json`);
}

const io = {};
for (const c of cards) {
  for (const m of (c.body + (c.funFact ?? '')).matchAll(/\[\[([a-z0-9-]+)\|/g)) {
    if (!people[m[1]]) errs.push(`story ${c.year} "${c.title}": unknown person "${m[1]}"`);
  }
  const e = (io[c.year] ??= { in: new Set(), out: new Set() });
  (c.in ?? []).forEach((p) => e.in.add(p));
  (c.out ?? []).forEach((p) => e.out.add(p));
}
const same = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));
for (let y = R.firstSeason; y <= R.currentThrough; y++) {
  const prev = new Set(seasons[y - 1] ?? []);
  const cur = new Set(seasons[y]);
  const joined = new Set([...cur].filter((p) => !prev.has(p)));
  const left = new Set([...prev].filter((p) => !cur.has(p)));
  const e = io[y] ?? { in: new Set(), out: new Set() };
  if (!same(joined, e.in) || !same(left, e.out)) {
    errs.push(`${y}: roster says in=[${[...joined]}] out=[${[...left]}] but the story cards say in=[${[...e.in]}] out=[${[...e.out]}]`);
  }
}

const g = {};
for (const e of conns) {
  for (const k of ['from', 'to']) if (!people[e[k]]) errs.push(`connection: unknown person "${e[k]}"`);
  (g[e.from] ??= new Set()).add(e.to);
  (g[e.to] ??= new Set()).add(e.from);
}
const seen = new Set([Object.keys(people)[0]]);
const queue = [...seen];
while (queue.length) {
  for (const n of g[queue.pop()] ?? []) {
    if (!seen.has(n)) {
      seen.add(n);
      queue.push(n);
    }
  }
}
const lonely = Object.keys(people).filter((p) => !seen.has(p));
if (lonely.length) errs.push(`not connected to anyone in the friend web: ${lonely.join(', ')}`);

if (errs.length) {
  console.error('Content problems:\n - ' + errs.join('\n - '));
  process.exit(1);
}
console.log(`content ok: ${Object.keys(people).length} people, ${Object.keys(seasons).length} seasons, ${conns.length} connections, ${cards.length} cards`);
