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
  photos?: { src: string; alt: string }[];
  arrive?: string[]; // ribbons that come in with this card even though it doesn't name them
  at?: number; // the year whose stretch of the timeline shows this card, if not `year`
};
/** The year whose band a card is shown in. */
export const shownIn = (c: Card) => c.at ?? c.year;
export type SeasonInfo = {
  champion: string | null; runnerUp: string | null; sacko: string | null; ledScoring: string | null; complete: boolean; source: string;
  championAsterisk?: string; // a * on that trophy, and why
  silverStars?: { person: string; why: string }[]; // honours short of a title
};
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

// Story cards, plus a generated champion/sacko card for every season. A season's trophy and sacko X
// sit on the ribbons right at the year line that closes it, so they land on the avatars just after
// that line passes: the season's card therefore leads the *next* year's stretch of the timeline
// (`at`), and stays up until they've landed. The current season has no next year; it closes its own.
const storyCards = storyFile.cards as Card[];
export const cards: Card[] = [...storyCards];
for (let y = FIRST; y <= LAST; y++) {
  const season = legacy.seasons[String(y)];
  if (!season) continue;
  let i = -1;
  cards.forEach((c, k) => {
    if (c.year <= y) i = k;
  });
  cards.splice(i + 1, 0, { year: y, title: String(y), body: '', kind: 'season', season, at: y < LAST ? y + 1 : y });
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
const RIBBONS_FROM = 2009;

/**
 * Three zones that never overlap: header avatars, the column field, the card tray.
 * The year scrubber lives in the right gutter. The playhead ("now") sits just above the tallest
 * the card can be; shorter cards hug their content and leave the playhead where it is.
 */
export function makeLayout(vh: number, W: number) {
  const desktop = W >= 1120;
  const headerY = desktop ? 46 : 38;
  const right = desktop ? 120 : 58; // gutter: the scrubber and the alumni pile
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
  for (const c of cards) (perYear[shownIn(c)] ??= []).push(c);

  // How much scrolling each year gets: every card needs time on the tray, and each photo a little
  // more. A season card leading the next year needs the most: its trophy, star and sacko stamp ride
  // up from the year line and land on the avatars (~0.8 of a screen) while it's showing.
  const weight = (c: Card) => (c.kind === 'season' && shownIn(c) !== c.year ? 0.95 : 0.55 + 0.22 * (c.photos?.length ?? 0));
  const bandH = (y: number) => {
    const list = perYear[y] ?? [];
    return vh * (list.length ? 0.2 + list.reduce((t, c) => t + weight(c), 0) : 0.5) + (y === FIRST ? vh * 0.7 : 0);
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
    const total = list.reduce((t, c) => t + weight(c), 0);
    let acc = 0;
    for (const card of list) {
      seq.push({ card, a: T[y] + (acc / total) * bandH(y), b: 0 });
      acc += weight(card);
    }
  }
  seq.forEach((r, i) => (r.b = i < seq.length - 1 ? seq[i + 1].a : end));
  const cardPos = new Map<Card, number>(seq.map((r) => [r.card, r.a]));

  // When each member first shows up in the header. Nobody gets a ribbon before 2009 (the year we
  // all got to Winona State): founders appear with the first card from then on that names them.
  const appearAt: Record<string, number> = {};
  for (const p of members) {
    const first = tenures[p][0];
    if (first.start === FIRST) {
      const met = cards.find((c) => c.year >= RIBBONS_FROM && (mentions(c).includes(p) || c.arrive?.includes(p)));
      const metW = met ? cardPos.get(met)! + vh * 0.05 : Infinity;
      appearAt[p] = Math.min(metW, T[FIRST] + first.slot * vh * 0.018);
    } else appearAt[p] = T[first.start] + vh * 0.05;
  }

  const pile = { x: W - (desktop ? 60 : 30), y: headerY };
  // the scrubber rail: from just under the pile to the bottom of the screen (clear of the type switch)
  const scrub = { top: headerY + 44, bottom: vh - 44 };
  const finale = end + vh * 0.35;
  const pageHeight = finale - P + vh * 1.15;
  const leviSlot = Math.max(0, lineup[FIRST].indexOf('levi-nellen')); // year badges sit on Levi's ribbon
  const born = cards.find((c) => c.founders);
  const bornAt = born ? cardPos.get(born)! : T[FIRST];

  return {
    vh, W, desktop, P, headerY, right, padL, gap, cw, av, colX, fieldW, cutH, trayH, trayTop, trayW,
    stops, T, top, end, bandH, seq, cardPos, appearAt, pile, scrub, finale, pageHeight, perYear, leviSlot, bornAt,
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
/** The inverse: the playhead position for a fractional stop. Used by the scrubber. */
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

/**
 * Founders' ribbons are there before the league, dark, as if still under a card. When the
 * founding season starts the colour pours down them, staggered by column: 0 = dark, 1 = fully lit.
 */
export function pourAt(L: Layout, slot: number, w: number): number {
  const t0 = L.bornAt; // the colour washes in with "The league is born"
  if (w <= t0) return 0;
  const p = clamp((w - t0) / (L.vh * 0.62));
  return easeOut(clamp(p * 1.75 - slot * 0.065));
}

/**
 * A founder growing in: the screen y of their ribbon's tip (and avatar), rising from the bottom of
 * the screen at scroll speed, like every other ribbon, until it docks in the header. Null before.
 */
export function growTip(L: Layout, p: string, w: number): number | null {
  const a = L.appearAt[p];
  if (a === undefined || w < a) return null;
  return Math.max(L.headerY, L.vh + L.av - (w - a));
}

/**
 * A newcomer's avatar arrives big, spread over their ribbon, and shrinks into place as it docks.
 * `t` runs 0 (just arrived) to 1 (docked).
 */
export const ARRIVE_SCALE = 1.55;
export const arriveScale = (t: number) => lerp(ARRIVE_SCALE, 1, smooth(clamp(t)));

export const PILE_SCALE = 0.72;
export type Spot = { x: number; y: number; rot: number };
export type AvatarState = {
  x: number; y: number; scale: number; rot: number; opacity: number;
  flying: number; // 0..1, in the air (drawn above everything)
  returning: number; // "returns" badge
  landed: number; // 0..1 progress of the drop into the pile (drives the pile's bump)
  gray: number;
  cut: string | null; // waiting in the header after their column was cut: greys with that column (key slot-start)
  pileAt: number | null; // in the pile; the value orders the pile (bigger = newer, on top)
};

/**
 * Where one person's avatar is, for a given playhead. One element per person, for their whole life:
 * - founders grow up from the bottom of the screen with their ribbon as the story meets them;
 * - everyone else rides up from just below their column's cut and docks in the header;
 * - when the newcomer gets close, the leaver is pushed up off the top of the screen and drops
 *   in from above onto the alumni pile;
 * - a returner rises off the pile and rides up from below their new cut.
 * Pure function of w, so scrolling back plays all of it in reverse.
 */
export function avatarState(L: Layout, p: string, w: number, spot: Spot): AvatarState {
  const iv = tenures[p];
  const { vh, headerY, colX, av, P } = L;
  const ride = L.cutH / 2 + CUT_GAP + av / 2 + 4; // avatar centre below the cut line
  const st: AvatarState = { x: colX(iv[0].slot), y: headerY, scale: 0, rot: 0, opacity: 0, flying: 0, returning: 0, landed: 0, gray: 0, cut: null, pileAt: null };

  const rideIn = (seg: Tenure, ret: boolean) => {
    const cut = L.T[seg.start];
    const w0 = cut + ride; // the avatar's spot reaches the playhead: it pops in there
    if (w < w0) return false;
    const q = clamp((w - w0) / (vh * 0.06));
    const y = cut - w + P + ride;
    const wDock = cut + P + ride - headerY;
    Object.assign(st, {
      x: colX(seg.slot), y: Math.max(headerY, y), scale: back(q) * arriveScale(1 - (y - headerY) / (vh * 0.35)), rot: 0, opacity: clamp(q * 3), flying: 0, gray: 0, cut: null, pileAt: null, landed: 0,
      returning: ret ? (w < wDock ? 1 : clamp(1 - (w - wDock) / (vh * 0.5))) : 0,
    });
    return true;
  };

  if (iv[0].start === FIRST) {
    const tip = growTip(L, p, w); // founders grow up from the bottom of the screen on the tip of their ribbon
    if (tip === null) return st;
    st.y = tip;
    st.scale = arriveScale(1 - (tip - headerY) / (vh * 0.35));
    st.opacity = 1;
  } else if (!rideIn(iv[0], false)) return st;

  for (let k = 0; k < iv.length; k++) {
    const seg = iv[k];
    if (seg.end === LAST) break;
    const B = L.top(seg.end + 1); // the cut under this column
    if (w <= B) break;
    st.cut = `${seg.slot}-${seg.start}`; // waits in the header, greying with its column

    // pushed out when the newcomer riding up the same slot gets within reach
    const wPush = B + P + ride - headerY - 1.3 * av;
    const order = exits.filter((x) => x.end === seg.end && x.slot < seg.slot).length; // several leavers land one after another
    const A = clamp((w - wPush) / (vh * 0.07));
    if (A <= 0) break;
    const sx = colX(seg.slot);
    st.x = sx;
    st.y = lerp(headerY, -av, smooth(A));
    st.flying = 1;
    st.opacity = 1;

    const D = clamp((w - wPush - vh * 0.07 - order * vh * 0.035) / (vh * 0.1));
    if (D <= 0) break;
    st.cut = null;
    st.gray = 1;
    st.x = spot.x;
    st.y = lerp(-av, spot.y, back(D));
    st.scale = lerp(1, PILE_SCALE, D);
    st.rot = spot.rot * D;
    st.landed = D;
    if (D < 1) break;
    st.flying = 0;
    st.pileAt = wPush + order;

    const next = iv[k + 1];
    if (!next) break;
    const R = clamp((w - (L.T[next.start] - vh * 0.1)) / (vh * 0.07)); // rise off the pile, up and away
    if (R <= 0) break;
    st.pileAt = null;
    st.landed = 0;
    st.flying = 1;
    st.y = lerp(spot.y, -av, smooth(R));
    st.scale = lerp(PILE_SCALE, 1, R);
    st.rot = spot.rot * (1 - R);
    st.gray = 1 - R;
    if (!rideIn(next, true)) break;
  }
  return st;
}
