// The timeline model. Everything on screen is a pure function of one number: the playhead's
// position in "world" pixels (scroll + playhead offset). That is what makes the story scrub
// forwards and backwards identically.
import peopleFile from '../../content/people.json';
import rosterFile from '../../content/roster.json';
import storyFile from '../../content/story.json';
import connFile from '../../content/connections.json';
import legacyFile from '../generated/legacy.json';

export type Person = {
  id: string; name: string; nickname: string | null; initials: string; role: 'member' | 'outsider';
  founder?: boolean; sleeper?: string | null; color?: string; avatar: string | null; story?: string; anecdotes?: string[];
};
export type Card = {
  year: number; title: string; body: string; kind?: string; funFact?: string;
  quote?: { by: string | null; text: string; context?: string; todo?: boolean };
  in?: string[]; out?: string[]; returns?: string[]; founders?: string[]; season?: SeasonInfo;
};
export type SeasonInfo = { champion: string | null; runnerUp: string | null; sacko: string | null; ledScoring: string | null; complete: boolean; source: string };
export type Tenure = { slot: number; start: number; end: number };
export type Segment = Tenure & { person: string };

export const people: Record<string, Person> = Object.fromEntries((peopleFile.people as Person[]).map((p) => [p.id, p]));
export const connections = connFile.connections as { from: string; to: string; year: number | null; how: string; type: string; inferred?: boolean }[];
export const legacy = legacyFile as {
  asOf: { season: string; last_scored_week: number }; asterisk: string; source: string;
  rankings: { person: string; rank: number; points: number; rankChangeWeek: number; record: { wins: number; losses: number; ties: number }; winPct: number; championships: number; sackos: number; divisionTitles: number; playoffAppearances: number }[];
  seasons: Record<string, SeasonInfo>;
};
export const legacyOf = Object.fromEntries(legacy.rankings.map((r) => [r.person, r]));

export const FIRST = rosterFile.firstSeason;
export const LAST = rosterFile.currentThrough;
export const SLOTS = 12;

// Expand the roster: seasons not listed repeat the previous lineup.
export const lineup: Record<number, string[]> = {};
{
  let last: string[] = [];
  for (let y = FIRST; y <= LAST; y++) lineup[y] = last = (rosterFile.seasons as Record<string, string[]>)[y] ?? last;
}

// Column segments per slot, and each person's tenure(s).
export const segments: Segment[] = [];
export const tenures: Record<string, Tenure[]> = {};
for (let slot = 0; slot < SLOTS; slot++) {
  let cur: Segment | null = null;
  for (let y = FIRST; y <= LAST; y++) {
    const p = lineup[y][slot];
    if (cur && cur.person === p) cur.end = y;
    else segments.push((cur = { person: p, slot, start: y, end: y }));
  }
}
for (const s of segments) (tenures[s.person] ??= []).push({ slot: s.slot, start: s.start, end: s.end });
for (const t of Object.values(tenures)) t.sort((a, b) => a.start - b.start);

export const members = Object.keys(tenures);
export const constants = new Set(members.filter((p) => tenures[p].length === 1 && tenures[p][0].start === FIRST && tenures[p][0].end === LAST));
export const isCurrent = (p: string) => tenures[p]?.some((t) => t.end === LAST) ?? false;
export const alumni = members.filter((p) => !isCurrent(p));

// Every time someone left. Each exit gets its own lane in the gutter so the threads run side by side.
export type Exit = Segment & { lane: number };
export const exits: Exit[] = segments
  .filter((s) => s.end !== LAST)
  .sort((a, b) => a.end - b.end || a.slot - b.slot)
  .map((s, i) => ({ ...s, lane: i % 5 }));
const exitOf = (p: string, start: number) => exits.find((e) => e.person === p && e.start === start)!;

export function yearsLabel(p: string): string {
  const t = tenures[p];
  if (!t) return '';
  return t.map((x) => (x.end === LAST ? `${x.start}–now` : x.start === x.end ? `${x.start}` : `${x.start}–${x.end}`)).join(', ');
}

// Story cards, plus a generated card for every season of the steady era (2017 on).
const storyCards = storyFile.cards as Card[];
const lastStoryYear = Math.max(...storyCards.map((c) => c.year));
export const cards: Card[] = [...storyCards];
for (let y = lastStoryYear; y <= LAST; y++) {
  const season = legacy.seasons[String(y)];
  if (season) cards.push({ year: y, title: String(y), body: '', kind: 'season', season });
}

// Rich text: "[[id|Name]]" -> tappable name.
export type Chunk = { text: string; person?: string };
export function parseRich(text: string): Chunk[] {
  const out: Chunk[] = [];
  let i = 0;
  for (const m of text.matchAll(/\[\[([a-z0-9-]+)\|([^\]]+)\]\]/g)) {
    if (m.index! > i) out.push({ text: text.slice(i, m.index) });
    out.push({ text: m[2], person: m[1] });
    i = m.index! + m[0].length;
  }
  if (i < text.length) out.push({ text: text.slice(i) });
  return out;
}
const mentions = (c: Card) => [...(c.body + (c.funFact ?? '')).matchAll(/\[\[([a-z0-9-]+)\|/g)].map((m) => m[1]);

// ---------------------------------------------------------------- layout

export type Layout = ReturnType<typeof makeLayout>;

export function makeLayout(vh: number, W: number) {
  const desktop = W >= 1120; // side-by-side cards need the room; below this, cards float over the columns
  const P = Math.round(vh * 0.56); // playhead: where "now" sits on screen
  const headerY = desktop ? 46 : 38;
  const right = desktop ? 120 : 58; // gutter kept for the dial (phase 3) and the alumni pile
  const padL = desktop ? 28 : 8;
  const gap = desktop ? 8 : 3;
  const fieldW = Math.min(W - right - padL, SLOTS * 84);
  const cw = (fieldW - (SLOTS - 1) * gap) / SLOTS;
  const av = Math.max(18, Math.min(cw - 1, desktop ? 44 : 30));
  const colX = (slot: number) => padL + slot * (cw + gap) + cw / 2;

  const stops = [...new Set([...cards.map((c) => c.year), ...Object.keys(lineup).map(Number)])].sort((a, b) => a - b);
  const perYear: Record<number, Card[]> = {};
  for (const c of cards) (perYear[c.year] ??= []).push(c);

  const bandH = (y: number) => {
    const n = (perYear[y] ?? []).filter((c) => c.kind !== 'season').length;
    if (y > lastStoryYear) return vh * 0.52;
    if (y === lastStoryYear) return vh * 1.05;
    return vh * (n ? 0.3 + 0.6 * n : 0.5) + (y === FIRST ? vh * 0.8 : 0);
  };

  const T: Record<number, number> = {};
  let y0 = P + vh * 0.95; // the intro occupies the first screen
  for (const y of stops) {
    T[y] = y0;
    y0 += bandH(y);
  }
  const end = y0;
  const top = (y: number) => T[y] ?? end; // top of a year's band; past the last year -> end of the timeline
  const nextTop = (y: number) => {
    const i = stops.indexOf(y);
    return i >= 0 && i < stops.length - 1 ? T[stops[i + 1]] : end;
  };

  // Where each card sits in the world. A card is "in focus" (upper-middle of the screen) when the
  // playhead reaches its world position.
  const cardPos = new Map<Card, number>();
  for (const y of stops) {
    const list = perYear[y] ?? [];
    const h = bandH(y);
    const pour = y === FIRST ? vh * 0.55 : 0;
    list.forEach((c, j) => cardPos.set(c, T[y] + pour + ((j + 0.5) / list.length) * (h - pour) * 0.94));
  }

  // When each member first shows up in the header.
  const appearAt: Record<string, number> = {};
  for (const p of members) {
    const first = tenures[p][0];
    if (first.start === FIRST) {
      const met = cards.find((c) => mentions(c).includes(p));
      const metW = met ? cardPos.get(met)! - vh * 0.1 : Infinity;
      appearAt[p] = Math.min(metW, T[FIRST] + first.slot * vh * 0.018);
    } else appearAt[p] = T[first.start] + vh * 0.07;
  }

  const pile = { x: W - (desktop ? 60 : 30), y: headerY };
  const finale = end + vh * 0.35;
  const pageHeight = finale - P + vh * 1.15;

  return { vh, W, desktop, P, headerY, right, padL, gap, cw, av, colX, fieldW, stops, T, top, nextTop, end, bandH, cardPos, appearAt, pile, finale, pageHeight, perYear };
}

// ---------------------------------------------------------------- pure functions of the playhead

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smooth = (t: number) => t * t * (3 - 2 * t);
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
/** Overshoot-and-settle, like a spring landing. */
export const back = (t: number) => {
  const c = 1.9;
  return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
};

/** Fractional position in the list of year stops: 3.4 = 40% through the 4th stop. */
export function stopAt(L: Layout, w: number): number {
  const { stops, T, end } = L;
  if (w <= T[stops[0]]) return 0;
  for (let i = 0; i < stops.length; i++) {
    const a = T[stops[i]];
    const b = i < stops.length - 1 ? T[stops[i + 1]] : end;
    if (w < b) return i + (w - a) / (b - a);
  }
  return stops.length - 0.0001;
}

/** How far down a slot's column the liquid has reached. In the founding year the columns pour in, staggered. */
export function fillEdge(L: Layout, slot: number, w: number): number {
  const t0 = L.T[FIRST];
  if (w <= t0) return t0;
  const p = clamp((w - t0) / (L.vh * 0.62));
  const e = easeOut(clamp(p * 1.75 - slot * 0.065));
  return t0 + (w - t0) * e;
}

// ---- leaving: a column doesn't stop, it drains into a thread that ducks under the other
// columns, runs to the gutter and climbs to the alumni pile. The avatar rides the same line.

export const DRAIN = 18; // world px a leaving column stops short of the season line, to make room for the funnel
const DROP = 0.2; // share of the exit spent sliding down the column before riding the thread
type Pt = [number, number];
const pathLen = (pts: Pt[]) => pts.slice(1).reduce((n, p, i) => n + Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]), 0);
function pointAt(pts: Pt[], d: number): Pt {
  for (let i = 1; i < pts.length; i++) {
    const seg = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    if (d <= seg || i === pts.length - 1) {
      const t = seg ? clamp(d / seg) : 1;
      return [lerp(pts[i - 1][0], pts[i][0], t), lerp(pts[i - 1][1], pts[i][1], t)];
    }
    d -= seg;
  }
  return pts[0];
}

/** One exit's thread, in screen pixels, for a given playhead. */
export function threadAt(L: Layout, ex: Exit, w: number) {
  const endY = L.top(ex.end + 1) - DRAIN - w + L.P; // where the column ends, on screen
  const f = clamp((w - (L.top(ex.end + 1) - DRAIN)) / (L.vh * 0.42)); // 0 → 1 over the exit
  const go = f <= DROP ? 0 : smooth((f - DROP) / (1 - DROP)); // progress along the thread
  const x = L.colX(ex.slot);
  const gx = L.pile.x - 10 + ex.lane * 5;
  const y0 = endY + 9; // tip of the funnel
  const yH = endY + 17; // the run under the columns, in the gap between seasons
  const yTop = Math.min(L.pile.y + 14, yH - 8);
  const c = 6; // corner cut
  const pts: Pt[] = [[x, y0], [x, yH - c], [x + c, yH], [gx - c, yH], [gx, yH - c], [gx, yTop]];
  return { ex, f, go, x, endY, y0, yH, gx, pts, len: pathLen(pts) };
}

export type AvatarState = { x: number; y: number; scale: number; opacity: number; inPile: boolean; flying: number; returning: number; landed: number; gray: number; under: boolean };

/** Where one person's avatar is, for a given playhead. One element per person, for its whole life. */
export function avatarState(L: Layout, p: string, w: number, pileIndex: number): AvatarState {
  const iv = tenures[p];
  const { vh, headerY, colX, pile } = L;
  const pileX = pile.x - Math.min(pileIndex, 3) * 9;
  const st: AvatarState = { x: colX(iv[0].slot), y: headerY, scale: 0, opacity: 0, inPile: false, flying: 0, returning: 0, landed: 0, gray: 0, under: false };

  const a = L.appearAt[p];
  if (w < a) return st;
  const q = clamp((w - a) / (vh * 0.16));
  st.scale = back(q);
  st.opacity = clamp(q * 3);
  if (iv[0].start !== FIRST) st.y = headerY - (1 - easeOut(q)) * 22; // late joiners drop in

  for (let k = 0; k < iv.length; k++) {
    if (iv[k].end === LAST) break;
    const th = threadAt(L, exitOf(p, iv[k].start), w);
    const f = th.f;
    if (f <= 0) break;
    const sx = colX(iv[k].slot);
    if (f <= DROP) {
      // slide down their own column to where it ends
      const u = smooth(f / DROP);
      st.x = sx;
      st.y = lerp(headerY, th.y0, u);
      st.scale = lerp(1, 0.62, u);
      st.gray = u * 0.5;
    } else {
      // then ride the thread: under the other columns, out to the gutter, up to the pile
      const path: Pt[] = [...th.pts, [pileX, pile.y]];
      [st.x, st.y] = pointAt(path, th.go * pathLen(path));
      st.scale = 0.62;
      st.gray = lerp(0.5, 1, clamp(th.go * 4));
      st.under = st.x > sx + 2 && st.x < L.padL + L.fieldW + 4;
    }
    st.flying = Math.sin(Math.PI * f);
    st.landed = f;
    st.inPile = f >= 1;
    st.opacity = 1;

    const next = iv[k + 1];
    if (!next) break;
    const g = clamp((w - (L.T[next.start] - vh * 0.04)) / (vh * 0.3));
    if (g <= 0) break;
    const e2 = smooth(g);
    const tx = colX(next.slot);
    const cx2 = lerp(pileX, tx, 0.5);
    st.x = (1 - e2) * (1 - e2) * pileX + 2 * (1 - e2) * e2 * cx2 + e2 * e2 * tx;
    st.y = (1 - e2) * (1 - e2) * pile.y + 2 * (1 - e2) * e2 * (headerY - 52) + e2 * e2 * headerY;
    st.scale = lerp(0.62, 1, back(g));
    st.flying = Math.sin(Math.PI * g);
    st.returning = g < 1 ? Math.sin(Math.PI * g) : clamp(1 - (w - L.T[next.start]) / (vh * 0.9));
    st.inPile = false;
    st.landed = 0;
    st.gray = 1 - e2;
    st.under = false;
  }
  return st;
}
