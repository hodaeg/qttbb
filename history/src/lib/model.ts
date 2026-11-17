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

// Every time someone left: where a column gets cut.
export const exits: Segment[] = segments.filter((s) => s.end !== LAST).sort((a, b) => a.end - b.end || a.slot - b.slot);

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
export const CUT_GAP = 7; // px of daylight between a cut column and its replacement

/**
 * Three zones that never overlap: header avatars, the column field, the card tray.
 * The dial lives in the right gutter. The playhead ("now") sits just above the tray.
 */
export function makeLayout(vh: number, W: number) {
  const desktop = W >= 1120;
  const headerY = desktop ? 46 : 38;
  const right = desktop ? 120 : 58; // gutter: the dial and the alumni pile
  const padL = desktop ? 28 : 8;
  const gap = desktop ? 8 : 3;
  const fieldW = Math.min(W - right - padL, SLOTS * 84);
  const cw = (fieldW - (SLOTS - 1) * gap) / SLOTS;
  const av = Math.max(18, Math.min(cw - 1, desktop ? 44 : 30));
  const colX = (slot: number) => padL + slot * (cw + gap) + cw / 2;
  const cutH = Math.round(cw * 0.6); // how far the diagonal cut drops across a column

  const trayH = Math.round(Math.min(vh * 0.4, 360));
  const trayTop = vh - trayH - 10;
  const trayW = Math.min(fieldW, 620);
  const P = trayTop - 12; // playhead: where "now" sits on screen

  const stops = [...new Set([...cards.map((c) => c.year), ...Object.keys(lineup).map(Number)])].sort((a, b) => a - b);
  const perYear: Record<number, Card[]> = {};
  for (const c of cards) (perYear[c.year] ??= []).push(c);

  // How much scrolling each year gets: every card needs time on the tray.
  const bandH = (y: number) => {
    const n = (perYear[y] ?? []).length;
    if (y > lastStoryYear) return vh * 0.5;
    return vh * (n ? 0.2 + 0.55 * n : 0.5) + (y === FIRST ? vh * 0.7 : 0);
  };

  const T: Record<number, number> = {};
  let y0 = P + vh * 0.95; // the intro occupies the first screen
  for (const y of stops) {
    T[y] = y0;
    y0 += bandH(y);
  }
  const end = y0;
  const top = (y: number) => T[y] ?? end; // top of a year's band; past the last year -> end of the timeline

  // The tray shows one card at a time. Each card owns a stretch of its year's band; a card
  // stays up through any card-less years that follow it.
  const seq: { card: Card; a: number; b: number }[] = [];
  for (const y of stops) {
    const list = perYear[y] ?? [];
    list.forEach((card, j) => seq.push({ card, a: T[y] + (j / list.length) * bandH(y), b: 0 }));
  }
  seq.forEach((r, i) => (r.b = i < seq.length - 1 ? seq[i + 1].a : end));
  const cardPos = new Map<Card, number>(seq.map((r) => [r.card, r.a]));

  // When each member first shows up in the header.
  const appearAt: Record<string, number> = {};
  for (const p of members) {
    const first = tenures[p][0];
    if (first.start === FIRST) {
      const met = cards.find((c) => mentions(c).includes(p));
      const metW = met ? cardPos.get(met)! + vh * 0.05 : Infinity;
      appearAt[p] = Math.min(metW, T[FIRST] + first.slot * vh * 0.018);
    } else appearAt[p] = T[first.start] + vh * 0.05;
  }

  const pile = { x: W - (desktop ? 60 : 30), y: headerY };
  const dialR = desktop ? 190 : 150;
  const dial = { r: dialR, sliver: desktop ? 78 : 50, cy: Math.round(P - dialR * 0.35), step: 8 }; // step: degrees per year stop
  const finale = end + vh * 0.35;
  const pageHeight = finale - P + vh * 1.15;

  return {
    vh, W, desktop, P, headerY, right, padL, gap, cw, av, colX, fieldW, cutH, trayH, trayTop, trayW,
    stops, T, top, end, bandH, seq, cardPos, appearAt, pile, dial, finale, pageHeight, perYear,
  };
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
/** The inverse: the playhead position for a fractional stop. Used by the dial. */
export function wAtStop(L: Layout, f: number): number {
  const { stops, T, end } = L;
  const i = clamp(Math.floor(f), 0, stops.length - 1);
  const a = T[stops[i]];
  const b = i < stops.length - 1 ? T[stops[i + 1]] : end;
  return a + clamp(f - i) * (b - a);
}

/** Which card(s) the tray is showing. Two while one hands over to the next. */
export function trayAt(L: Layout, w: number) {
  const d = L.vh * 0.07;
  const out: { card: Card; i: number; o: number; dy: number; t: number }[] = [];
  L.seq.forEach((r, i) => {
    // one leaves, then the next arrives: they never sit on top of each other
    const enter = i === 0 ? 1 : smooth(clamp((w - (r.a - d / 2)) / (d / 2)));
    const exit = i === L.seq.length - 1 ? 0 : smooth(clamp((w - (r.b - d)) / (d / 2)));
    const o = enter * (1 - exit);
    if (o > 0.001) out.push({ card: r.card, i, o, dy: (1 - enter) * 16 - exit * 12, t: clamp((w - r.a) / (r.b - r.a)) });
  });
  return out;
}

/** How far down a slot's column the liquid has reached. In the founding year the columns pour in, staggered. */
export function fillEdge(L: Layout, slot: number, w: number): number {
  const t0 = L.T[FIRST];
  if (w <= t0) return t0;
  const p = clamp((w - t0) / (L.vh * 0.62));
  const e = easeOut(clamp(p * 1.75 - slot * 0.065));
  return t0 + (w - t0) * e;
}

export type AvatarState = { x: number; y: number; scale: number; opacity: number; inPile: boolean; flying: number; returning: number; landed: number; gray: number };

/** Where one person's avatar is, for a given playhead. One element per person, for its whole life. */
export function avatarState(L: Layout, p: string, w: number, pileIndex: number): AvatarState {
  const iv = tenures[p];
  const { vh, headerY, colX, pile } = L;
  const pileX = pile.x - Math.min(pileIndex, 3) * 9;
  const st: AvatarState = { x: colX(iv[0].slot), y: headerY, scale: 0, opacity: 0, inPile: false, flying: 0, returning: 0, landed: 0, gray: 0 };
  const bez = (a: number, c: number, b: number, e: number) => (1 - e) * (1 - e) * a + 2 * (1 - e) * e * c + e * e * b;

  const a = L.appearAt[p];
  if (w < a) return st;
  const q = clamp((w - a) / (vh * 0.16));
  st.scale = back(q);
  st.opacity = clamp(q * 3);
  if (iv[0].start !== FIRST) st.y = headerY - (1 - easeOut(q)) * 22; // late joiners drop in

  for (let k = 0; k < iv.length; k++) {
    if (iv[k].end === LAST) break;
    const B = L.top(iv[k].end + 1); // the cut: the season after their last
    const order = exits.filter((x) => x.end === iv[k].end && x.slot < iv[k].slot).length; // leavers go one after another
    const f = clamp((w - B - order * vh * 0.045) / (vh * 0.3));
    if (f <= 0) break;
    const e = smooth(f);
    const sx = colX(iv[k].slot);
    // swing down over the columns, in the open, and up to the alumni pile
    st.x = bez(sx, lerp(sx, pileX, 0.55), pileX, e);
    st.y = bez(headerY, headerY + vh * 0.22, pile.y, e);
    st.scale = lerp(1, 0.62, e) * (1 + Math.sin(Math.PI * f) * 0.5);
    st.gray = clamp(f * 2.5);
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
    st.x = bez(pileX, lerp(pileX, tx, 0.5), tx, e2);
    st.y = bez(pile.y, headerY + vh * 0.2, headerY, e2);
    st.scale = lerp(0.62, 1, back(g));
    st.gray = 1 - e2;
    st.flying = Math.sin(Math.PI * g);
    st.returning = g < 1 ? Math.sin(Math.PI * g) : clamp(1 - (w - L.T[next.start]) / (vh * 0.9));
    st.inPile = false;
    st.landed = 0;
  }
  return st;
}
