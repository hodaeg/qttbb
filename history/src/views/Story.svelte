<script lang="ts">
  // The roster story. One fixed stage with three zones that never overlap: header avatars, the
  // column field, and the card tray, plus the year scrubber on the right edge. Everything is drawn
  // from the scroll position, so the whole history scrubs forwards and backwards like a film.
  import { onMount } from 'svelte';
  import {
    makeLayout, segments, members, people, legacy, constants, lineup, exits, isCurrent, FIRST, LAST, CUT_GAP,
    pourAt, growTip, avatarState, stopAt, trayAt, clamp, lerp, back, smooth, easeOut, type AvatarState, type Spot,
  } from '../lib/model';
  import Avatar from './Avatar.svelte';
  import Glass from './Glass.svelte';
  import Tray from './Tray.svelte';
  import Scrubber from './Scrubber.svelte';

  type Photo = { src: string; alt: string };
  let { onperson, onphoto }: { onperson: (id: string) => void; onphoto: (p: Photo) => void } = $props();

  let vh = $state(800);
  let W = $state(390);
  let s = $state(0); // smoothed scroll position
  let vel = $state(0); // how fast we're moving (drives the ripple)
  let time = $state(0);
  let reduced = $state(false);
  let want = $state(0); // how tall the current card wants to be (reported by the tray)
  let tt = $state(0); // where the card's top actually is right now (springs toward `want`)

  const L = $derived(makeLayout(vh, W));
  const w = $derived(s + L.P); // the playhead, in world pixels

  // Temporary, for the design review: cycle through the type sets (also ?type=a|b|c).
  const TYPES = ['a', 'b', 'c'];
  let type = $state('a');
  function setType(t: string) {
    type = TYPES.includes(t) ? t : 'a';
    document.documentElement.dataset.type = type;
    try {
      localStorage.setItem('type', type);
    } catch {}
  }

  onMount(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem('type');
    } catch {}
    setType(new URLSearchParams(location.search).get('type') ?? saved ?? 'a');
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reduced = mq.matches;
    // Lay the story out against the *large* viewport (address bar hidden), measured with a 100lvh
    // probe. On iPhone the bar comes back when you scroll up; if that re-measured the page, every
    // band would shrink and the story would leap forward. The bar just overlays the bottom instead.
    const probe = document.createElement('div');
    probe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:100lvh;visibility:hidden;pointer-events:none';
    document.body.append(probe);
    const size = () => {
      const tall = probe.offsetHeight || window.innerHeight;
      vh = Math.max(tall, window.innerHeight);
      W = document.documentElement.clientWidth;
    };
    size();
    s = window.scrollY;
    window.addEventListener('resize', size);
    const onScroll = () => {
      if (fanned && Math.abs(window.scrollY - fanY) > 12) fanned = false;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    let raf = 0;
    tt = L.trayTop;
    const tick = (now: number) => {
      stepCuts(now);
      const tTarget = L.vh - 10 - (want ? Math.min(want, L.trayH) : L.trayH);
      if (Math.abs(tTarget - tt) > 0.3) tt = reduced ? tTarget : tt + (tTarget - tt) * 0.2;
      else if (tt !== tTarget) tt = tTarget;
      const target = window.scrollY;
      const d = target - s;
      if (Math.abs(d) > 0.05) s = reduced ? target : s + d * 0.2;
      else if (d !== 0) s = target;
      // the ripple fades out over ~400ms after the scroll stops
      const v = reduced ? 0 : Math.abs(d) > Math.abs(vel) ? lerp(vel, d, 0.3) : lerp(vel, d, 0.06);
      if (Math.abs(v) > 0.02 || vel !== 0) {
        vel = Math.abs(v) < 0.02 ? 0 : v;
        time = now / 1000;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      probe.remove();
      window.removeEventListener('resize', size);
      window.removeEventListener('scroll', onScroll);
    };
  });

  // ---- the moment a column is cut. This one beat runs on the clock, not the scroll: tension
  // releasing plays out by itself. The column shakes and its colour drains to grey on the same
  // envelope, so it is grey exactly when it comes to rest. Scrolling back up restores the colour.
  type Fx = { g: number; x: number };
  let fx = $state<Record<string, Fx>>({});
  const cutAnim: Record<string, { passed: boolean; t0: number; mode: 'idle' | 'shake' | 'unfade'; g0: number }> = {};
  function stepCuts(now: number) {
    const wNow = window.scrollY + L.P; // the raw scroll: the shake starts the moment the cut arrives
    const amp = L.desktop ? 5 : 3;
    const next: Record<string, Fx> = {};
    let changed = false;
    for (const ex of exits) {
      const key = `${ex.slot}-${ex.start}`;
      const passed = wNow > L.top(ex.end + 1);
      let a = cutAnim[key];
      if (!a) a = cutAnim[key] = { passed, t0: 0, mode: 'idle', g0: 0 }; // already past on load: settled
      if (passed !== a.passed) {
        a.passed = passed;
        a.t0 = now;
        a.g0 = fx[key]?.g ?? (passed ? 0 : 1);
        a.mode = passed ? 'shake' : 'unfade';
      }
      let g = passed ? 1 : 0;
      let x = 0;
      if (a.mode === 'shake') {
        const q = clamp((now - a.t0) / (reduced ? 200 : 750));
        const env = (1 - q) * (1 - q);
        g = reduced ? q : 1 - env;
        x = reduced ? 0 : Math.sin(q * Math.PI * 2 * 4.5) * amp * env;
        if (q >= 1) a.mode = 'idle';
      } else if (a.mode === 'unfade') {
        const q = clamp((now - a.t0) / 250);
        g = a.g0 * (1 - q);
        if (q >= 1) a.mode = 'idle';
      }
      next[key] = { g, x };
      const prev = fx[key];
      if (!prev || Math.abs(prev.g - g) > 0.001 || Math.abs(prev.x - x) > 0.01) changed = true;
    }
    if (changed) fx = next;
  }

  // ---- columns. A leaving column is sliced on the diagonal; its replacement starts with the matching slice.
  // Every ribbon runs to the bottom of the screen. Below the card's top edge it is in the card's
  // shadow (--lit: where the shadow starts, in the element's own pixels). Founders' ribbons are
  // there before the league, all in shadow, and the colour pours down them when 2011 starts.
  type Piece = { key: string; person: string; slot: number; x: number; y: number; h: number; clip: string; g: number; py: number; lit: number; founder: boolean; constant: boolean; dotted: boolean; gold: number; plat: number; chev: number; chev2: number };
  type Tail = Piece & { tf: string; p: number };
  // while scrolling the ribbons sway a little side to side, each on its own slow phase
  const sway = (slot: number) => {
    const a = clamp(Math.abs(vel) / 30) * (L.desktop ? 2.2 : 1.4);
    return a ? Math.sin(time * 4.2 + slot * 1.37) * a : 0;
  };
  const field = $derived.by(() => {
    const cols: Piece[] = [];
    const tails: Tail[] = [];
    const px = (n: number) => `${n.toFixed(1)}px`;
    const floor = s + vh + 10; // the bottom of the screen, in world pixels
    for (const seg of segments) {
      const founding = seg.start === FIRST;
      const cutBot = seg.end !== LAST;
      const key = `${seg.slot}-${seg.start}`;
      const B1 = L.top(seg.end + 1);
      const cut = cutBot && w >= B1; // the cut has reached the playhead
      const bottom = cutBot ? B1 + L.cutH / 2 - CUT_GAP / 2 : L.end;
      const tailTop = cutBot ? bottom - L.cutH - L.cw * 1.8 : bottom; // the last stretch hangs free once cut

      let top: number; // world
      if (founding) {
        const tip = growTip(L, seg.person, w);
        if (tip === null) continue;
        top = tip + s;
      } else {
        top = L.T[seg.start] - L.cutH / 2 + CUT_GAP / 2;
        if (w <= top + 1) continue; // arrives when its cut reaches the playhead
      }
      const f = fx[key] ?? { g: cut ? 1 : 0, x: 0 };
      const x = L.colX(seg.slot) - L.cw / 2 + f.x + sway(seg.slot);
      const litY = founding ? lerp(L.headerY - 30, tt, pourAt(L, seg.slot, w)) : tt; // screen
      const base = { person: seg.person, slot: seg.slot, g: f.g, founder: !!people[seg.person].founder, constant: constants.has(seg.person), dotted: !people[seg.person].founder && isCurrent(seg.person), ...edgesOf(seg.person) };

      const mEnd = cut ? tailTop : floor;
      if (mEnd > top + 1) {
        const y = Math.max(top - s, -40);
        const h = mEnd - s - y;
        if (h > 0 && y < vh) {
          const o = y + s; // the element's top, in world pixels
          const clip = !founding ? `polygon(0 ${px(top + L.cutH - o)},100% ${px(top - o)},100% ${px(h + 60)},0 ${px(h + 60)})` : 'none';
          cols.push({ ...base, key, x, y, h, clip, py: -o, lit: litY - y });
        }
      }
      if (cut) {
        // the tail starts 2px up inside the body, so no hairline of background shows at the hinge
        const y = tailTop - s - 2;
        const h = bottom - tailTop + 2;
        if (y < vh && y + h > -60) {
          const p = clamp((w - B1) / (vh * 0.12)); // how far it has fallen away
          const clip = `polygon(0 0,100% 0,100% ${px(bottom - L.cutH - tailTop + 2)},0 ${px(bottom - tailTop + 2)})`;
          const tf = `translate3d(${px(x)},${px(y)},0) perspective(260px) rotateX(${(-22 * p).toFixed(2)}deg)`;
          tails.push({ ...base, key, x, y, h, clip, py: -(y + s), lit: litY - y, tf, p });
        }
      }
    }
    return { cols, tails };
  });

  // ---- year markers: a faint line across the field, badged on Levi's ribbon. Cuts land on them.
  const markers = $derived(
    L.stops
      .map((y) => ({ y, sy: L.T[y] - s }))
      .filter((m) => m.sy > L.headerY + 14 && m.sy < vh + 4),
  );

  // ---- photos: they slide in from the left, one after another. Each new one lands on top, where
  // the last one was, and pushes the ones before it up the stack. All leave right as the next card arrives.
  const photos = $derived.by(() => {
    const out: { key: string; p: Photo; x: number; y: number; rot: number; z: number; o: number }[] = [];
    const pw = Math.min(L.fieldW * 0.7, 330);
    const ph = pw * 0.75;
    const regionTop = L.headerY + L.av + 14;
    const regionBot = tt - 18;
    for (const r of L.seq) {
      const list = r.card.photos;
      if (!list?.length || w < r.a - vh * 0.5 || w > r.b + vh * 0.25) continue;
      const n = list.length;
      const span = r.b - r.a;
      const base = regionBot - ph / 2 - 4;
      const step = n > 1 ? Math.min(ph * 0.58, (base - ph / 2 - regionTop) / (n - 1)) : 0;
      const exit = smooth(clamp((w - (r.b - vh * 0.12)) / (vh * 0.14)));
      const ents = list.map((_, k) => easeOut(clamp((w - (r.a + span * (0.06 + (0.6 * k) / n))) / ((span * 0.6) / n))));
      list.forEach((p, k) => {
        const e = ents[k];
        if (e <= 0) return;
        const climb = ents.slice(k + 1).reduce((t, v) => t + v, 0); // pushed up by every later arrival
        const tx = L.padL + L.fieldW / 2 + [-10, 14, -6][k % 3] * (L.fieldW / 300);
        const rot = [-3, 2.5, -1.5][k % 3];
        const x = lerp(-pw * 0.6, tx, e) + exit * (L.W + pw * 0.6 - tx) + (n - 1 - k) * exit * exit * 30;
        out.push({ key: p.src, p, x, y: base - climb * step, rot: rot - (1 - e) * 12 + exit * 10, z: k + 1, o: 1 });
      });
    }
    return { list: out, pw, ph };
  });

  // ---- markers that live on the columns: each season's champion and sacko
  const marks = $derived.by(() => {
    type Kind = 'champ' | 'sacko' | 'silver';
    const out: { key: string; kind: Kind; person: string; x: number; y: number; pop: number; o: number; star: boolean }[] = [];
    const add = (key: string, kind: Kind, person: string, slot: number, world: number, star = false) => {
      const y = world - s;
      if (w <= world || y < 0 || y > L.P + 20) return;
      // a trophy or sacko X nearing the header merges into its owner's avatar (see honours below)
      const merge = clamp((L.headerY + L.av * 4 - y) / (L.av * 3));
      if (merge >= (kind === 'sacko' ? 0.5 : 1)) return; // the sacko X hands over to the stamp
      out.push({ key, kind, person, x: L.colX(slot), y, pop: clamp((w - world) / (vh * 0.07)) * (1 - merge * 0.55), o: 1 - merge, star });
    };
    for (const [year, season] of Object.entries(legacy.seasons)) {
      const y = Number(year);
      if (!lineup[y]) continue;
      const mid = L.T[y] + L.bandH(y) * 0.5;
      const slotOf = (id: string | null) => (id ? lineup[y].indexOf(id) : -1);
      if (slotOf(season.champion) >= 0) add(`champ${y}`, 'champ', season.champion!, slotOf(season.champion), mid, !!season.championAsterisk);
      if (slotOf(season.sacko) >= 0) add(`sacko${y}`, 'sacko', season.sacko!, slotOf(season.sacko), mid);
      for (const sv of season.silverStars ?? []) if (slotOf(sv.person) >= 0) add(`silver${y}${sv.person}`, 'silver', sv.person, slotOf(sv.person), mid);
    }
    return out;
  });

  // ---- avatars and the alumni pile. The pile is a literal pile: everyone who left, stacked
  // messily. One tap fans it out to the left and down; tap again, tap elsewhere or scroll to close.
  const hash = (str: string) => {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
    return h >>> 0;
  };
  const spotOf = (p: string): Spot => {
    const h = hash(p);
    const r = (n: number) => (((h >>> n) & 255) / 255) * 2 - 1;
    return { x: L.pile.x + r(0) * 7, y: L.pile.y + r(8) * 5, rot: r(16) * 14 };
  };
  const avatars = $derived(members.map((p) => ({ p, st: avatarState(L, p, w, spotOf(p)) })));
  const piled = $derived(avatars.filter((a) => a.st.pileAt !== null).sort((a, b) => a.st.pileAt! - b.st.pileAt!)); // oldest first
  const pileIx = $derived(Object.fromEntries(piled.map((a, i) => [a.p, i])) as Record<string, number>);
  const pileCount = $derived(piled.length);
  const pileBump = $derived(Math.max(0, ...avatars.map((a) => (a.st.landed > 0.8 && a.st.landed < 1 ? Math.sin((Math.PI * (a.st.landed - 0.8)) / 0.2) : 0))));

  let fanned = $state(false);
  let fanY = 0;
  $effect(() => {
    if (pileCount === 0) fanned = false;
  });
  const FAN_COLS = 4;
  const cell = $derived(L.desktop ? 78 : 62);
  const fanPos = (i: number) => ({
    x: L.pile.x - 6 - (FAN_COLS - 1 - (i % FAN_COLS)) * cell,
    y: L.headerY + 52 + Math.floor(i / FAN_COLS) * cell,
  });
  const fanBox = $derived.by(() => {
    const rows = Math.max(1, Math.ceil(pileCount / FAN_COLS));
    const x0 = L.pile.x - 6 - (FAN_COLS - 1) * cell - cell / 2 - 4;
    return { x: x0, y: L.headerY + 20, w: Math.min(L.W - 6 - x0, FAN_COLS * cell + 16), h: rows * cell + 34 };
  });
  function toggleFan() {
    fanned = !fanned;
    fanY = window.scrollY;
  }
  function tapAvatar(a: { p: string; st: AvatarState }) {
    const p = a.p;
    if (pileIx[p] === undefined && a.st.landed > 0 && pileCount) return toggleFan(); // still dropping onto the pile
    if (pileIx[p] === undefined) return onperson(p);
    if (!fanned) return toggleFan();
    fanned = false;
    onperson(p);
  }
  function view(a: { p: string; st: AvatarState }) {
    const i = pileIx[a.p];
    if (fanned && i !== undefined) {
      const f = fanPos(i);
      return { x: f.x, y: f.y, scale: L.desktop ? 1.05 : 1.2, rot: 0 };
    }
    return { x: a.st.x, y: a.st.y, scale: a.st.scale, rot: a.st.rot };
  }
  const zOf = (a: { p: string; st: AvatarState }) =>
    pileIx[a.p] !== undefined ? (fanned ? 45 : 12 + pileIx[a.p]) : a.st.flying > 0.02 ? 30 : 10;
  // ---- honours. A season's trophy (or sacko X) rides up its owner's column and merges into their
  // avatar as it nears the header. All of it is a pure function of the scroll, so it reverses.
  // - title: a gold star grows under the avatar (middle out) and the avatar swells with a gold glow.
  //   Their ribbon earns edges: 1 title gold foil, 2 platinum just inside it, 3+ gold chevrons;
  // - a silver star (an honour short of a title, e.g. an undefeated regular season) lands the same way;
  // - sacko: an X stamps onto the avatar, which shakes, then the X shrinks into a row along the top.
  const titles: Record<string, number[]> = {};
  const sackos: Record<string, number[]> = {};
  const silvers: Record<string, number[]> = {};
  for (const [year, season] of Object.entries(legacy.seasons)) {
    const y = Number(year);
    if (!lineup[y]) continue;
    if (season.champion && lineup[y].includes(season.champion)) (titles[season.champion] ??= []).push(y);
    if (season.sacko && lineup[y].includes(season.sacko)) (sackos[season.sacko] ??= []).push(y);
    for (const sv of season.silverStars ?? []) if (lineup[y].includes(sv.person)) (silvers[sv.person] ??= []).push(y);
  }
  // every marker (trophy, silver star, sacko X) sits mid-season, so a season's honours land together
  const midOf = (y: number) => L.T[y] + L.bandH(y) * 0.5;
  /** 0..1 progress of an honour once its marker reaches the avatar; it plays over more scroll after that. */
  const reach = (world: number) => L.headerY + L.av * 4 - (world - s);
  const starOf = (year: number) => clamp((reach(midOf(year)) - L.av * 2.4) / (vh * 0.16));
  const stampOf = (year: number) => clamp((reach(midOf(year)) - L.av * 1.5) / (vh * 0.3));

  // One icon per kind, with a count once there is more than one (x2, x3 ...), instead of a row of icons.
  // A new one: the first grows in; later ones bump the icon and tick the count up halfway through.
  type Group = { kind: 'gold' | 'silver'; n: number; sc: number; ast: boolean; grow: number };
  function group(kind: 'gold' | 'silver', list: { g: number; ast: boolean }[]): Group | null {
    const got = list.filter((x) => x.g > 0);
    if (!got.length) return null;
    const g = got[got.length - 1].g;
    const n = got.length - (g < 0.5 && got.length > 1 ? 1 : 0);
    const sc = got.length === 1 ? back(g) : 1 + 0.35 * Math.sin(Math.PI * g);
    const ast = got.some((x, k) => x.ast && (k < got.length - 1 || g >= 0.5));
    return { kind, n, sc, ast, grow: got.length === 1 ? clamp(g * 1.5) : 1 };
  }
  function honoursOf(p: string) {
    const gold = group('gold', (titles[p] ?? []).map((y) => ({ g: starOf(y), ast: !!legacy.seasons[y].championAsterisk })));
    const silver = group('silver', (silvers[p] ?? []).map((y) => ({ g: starOf(y), ast: false })));
    // lay the groups out side by side under the avatar, centred; a group just arriving slides in
    const groups = [gold, silver].filter((x): x is Group => !!x);
    const width = (x: Group) => (9 + (x.n > 1 ? 11 : 0) + (x.ast ? 4 : 0)) * x.grow;
    const total = groups.reduce((t, x) => t + width(x), 0) + Math.max(0, groups.length - 1) * 3;
    let at = -total / 2;
    const stars = groups.map((x) => {
      const left = at;
      at += width(x) + 3;
      return { ...x, x: left + 4.5 * x.grow };
    });
    const newestG = Math.max(
      0,
      ...[...(titles[p] ?? []), ...(silvers[p] ?? [])].map(starOf).filter((g) => g > 0 && g < 1),
    );
    const win = newestG > 0 ? Math.sin(Math.PI * newestG) : 0; // the swell and glow as a star lands
    const winSilver = !!(silvers[p] ?? []).some((y) => starOf(y) === newestG) && !(titles[p] ?? []).some((y) => starOf(y) === newestG);

    // sacko X: stamp onto the face, sit while the avatar shakes, then shrink up to the X along the top
    const lost = (sackos[p] ?? []).map(stampOf).filter((g) => g > 0);
    const landed = lost.filter((g) => g >= 1).length;
    const flying = lost
      .filter((g) => g < 1)
      .map((g) => {
        const stamp = easeOut(clamp(g / 0.25));
        const fly = smooth(clamp((g - 0.65) / 0.35));
        return { x: 0, y: lerp(0, -L.av / 2 - 5, fly), size: lerp(L.av * 0.95, 8, fly), sc: lerp(2.4, 1, stamp), o: clamp(g / 0.12) };
      });
    const q = lost.length ? (lost[lost.length - 1] - 0.25) / 0.4 : -1; // the shake, right after the stamp lands
    const shake = q > 0 && q < 1 && !reduced ? Math.sin(q * Math.PI * 2 * 3.5) * (1 - q) * (L.desktop ? 4 : 3) : 0;
    return { stars, win, winSilver, landed, flying, shake, sackoCount: lost.length };
  }
  // the ribbon's dressing for a person's titles (0..1 each, as each star lands):
  // 1st gold foil edges, 2nd platinum inside them, 3rd gold chevrons, 4th double chevrons
  const edgesOf = (p: string) => {
    const t = titles[p] ?? [];
    const at = (k: number) => (t[k] ? starOf(t[k]) : 0);
    return { gold: at(0), plat: at(1), chev: at(2), chev2: at(3) };
  };
  const grayOf = (st: AvatarState) => (st.cut ? (fx[st.cut]?.g ?? 1) : st.gray);

  // ---- where we are in time (the dial and the tray read this)
  const fi = $derived(stopAt(L, w));
  const started = $derived(clamp((w - (L.T[L.stops[0]] - vh * 0.35)) / (vh * 0.2)));
  const trayItems = $derived(trayAt(L, w));
  const trayO = $derived(started * (1 - clamp((w - L.end) / (vh * 0.2))));

  const finaleCy = $derived((L.finale - w) * 0.94 + vh * 0.52);
  const introO = $derived(1 - clamp(s / (vh * 0.45)));
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

<div class="spacer" style:height="{L.pageHeight}px"></div>

<div class="stage" class:reduced style:height="{vh}px">
  <!-- columns: nothing is ever drawn over these except their own markers -->
  <div
    class="field"
    style:--fade="{L.headerY * 2 + 26}px"
    style:--cw="{L.cw}px"
  >
    {#each field.cols as c (c.key)}
      <button
        class="col"
        class:founder={c.founder}
        class:constant={c.constant}
        class:chev={c.chev > 0}
        class:chev2={c.chev2 > 0.5}
        class:dotted={c.dotted}
        style:--chev={c.chev}
        aria-label={people[c.person].name}
        style:--tone={people[c.person].color}
        style:--g={c.g}
        style:--py="{c.py}px"
        style:--lit="{c.lit}px"
        style:width="{L.cw}px"
        style:height="{c.h}px"
        style:clip-path={c.clip}
        style:transform="translate3d({c.x}px,{c.y}px,0)"
        onclick={() => onperson(c.person)}
      >
        {#if c.gold > 0}<i class="edge gold" style:opacity={c.gold}></i>{/if}
        {#if c.plat > 0}<i class="edge plat" style:opacity={c.plat}></i>{/if}
      </button>
    {/each}
    {#each field.tails as t (t.key)}
      <i
        class="tail"
        class:founder={t.founder}
        style:--tone={people[t.person].color}
        style:--g={t.g}
        style:--p={t.p}
        style:--py="{t.py}px"
        style:width="{L.cw}px"
        style:height="{t.h}px"
        style:clip-path={t.clip}
        style:transform={t.tf}
      ></i>
    {/each}
    <!-- the card's shadow falling on the ribbons just above it, and the ribbons falling away at the bottom -->
    <i class="cardshade" style:opacity={started} style:width="{L.fieldW + 8}px" style:transform="translate3d({L.padL - 4}px,{tt - 44}px,0)"></i>
    <i class="floorshade" style:width="{L.fieldW + 8}px" style:transform="translate3d({L.padL - 4}px,{vh - 110}px,0)"></i>
    {#each markers as m (m.y)}
      <span class="marker" style:opacity={started} style:width="{L.fieldW}px" style:transform="translate3d({L.padL}px,{m.sy}px,0)">
        <b class="display" style:left="{L.colX(L.leviSlot) - L.cw / 2 - L.padL}px">{m.y}</b>
      </span>
    {/each}
    {#each marks as m (m.key)}
      <span class="mark {m.kind}" style:opacity={m.o} title="{m.kind === 'champ' ? 'Champion' : m.kind === 'silver' ? 'Silver star' : 'Sacko'}: {people[m.person].name}" style:transform="translate3d({m.x}px,{m.y}px,0) translate(-50%,-50%) scale({back(m.pop)})">
          <svg viewBox="0 0 16 16" width={Math.min(L.cw - 5, 18)} height={Math.min(L.cw - 5, 18)} aria-hidden="true">
            {#if m.kind === 'champ'}
              <path d="M4 2h8v3.2a4 4 0 0 1-8 0zM1.8 3H4v1.3H3.1A1.7 1.7 0 0 0 4.2 6l-.5 1.2A3 3 0 0 1 1.8 4.4zM12 3h2.2v1.4a3 3 0 0 1-1.9 2.8L11.8 6a1.7 1.7 0 0 0 1.1-1.7H12zM7.2 9h1.6v2.4H11V13H5v-1.6h2.2z" />
            {:else if m.kind === 'silver'}
              <path d="M8 .8l2.2 4.6 5 .5-3.8 3.4 1.1 5L8 11.8l-4.5 2.5 1.1-5L.8 5.9l5-.5z" />
            {:else}
              <path d="M3.2 3.2l9.6 9.6M12.8 3.2l-9.6 9.6" />
            {/if}
          </svg>
          {#if m.star}<b class="ast" aria-label="with an asterisk">*</b>{/if}
        </span>
    {/each}
  </div>

  <!-- photos, between the ribbons and the card -->
  {#if photos.list.length}
    <div class="photos">
      {#each photos.list as ph (ph.key)}
        <button
          class="photo"
          aria-label="Photo: {ph.p.alt}"
          style:width="{photos.pw}px"
          style:height="{photos.ph}px"
          style:z-index={ph.z}
          style:transform="translate3d({ph.x - photos.pw / 2}px,{ph.y - photos.ph / 2}px,0) rotate({ph.rot}deg)"
          onclick={() => onphoto(ph.p)}
        ><img src={import.meta.env.BASE_URL + ph.p.src} alt="" decoding="async" /></button>
      {/each}
    </div>
  {/if}

  <!-- the card tray -->
  <Tray {L} items={trayItems} opacity={trayO} top={tt} {onperson} bind:want />

  <!-- finale -->
  {#if finaleCy < vh * 1.4}
    <div class="cardwrap finale" style:width="{Math.min(L.trayW, 440)}px" style:--o={clamp((vh - finaleCy) / (vh * 0.25))} style:transform="translate3d({L.padL}px,calc({finaleCy}px - 50%),0)">
      <Glass pad="18px 18px 16px"><article class="fin">
        <h3 class="display">The Legacy Rankings</h3>
        <ol>
          {#each legacy.rankings as r}
            <li>
              <button class="pressable" onclick={() => onperson(r.person)}>
                <span class="rk">{r.rank}</span><Avatar id={r.person} size={26} /><b>{first(r.person)}</b><span class="pts">{r.points}</span>
              </button>
            </li>
          {/each}
        </ol>
        <p class="fine">Mike's rankings, through week {legacy.asOf.last_scored_week} of {legacy.asOf.season}. The friend web comes next.</p>
      </article></Glass>
    </div>
  {/if}

  <!-- intro -->
  {#if introO > 0}
    <div class="intro" style:opacity={introO} style:transform="translate3d(0,{-s * 0.35}px,0)">
      <h1 class="display">The Quest <span>to the</span> <em>Bria Bowl</em></h1>
      <p class="lede">How twelve friends ended up in one fantasy football league, and who we lost along the way.</p>
      <span class="hint" aria-hidden="true">Scroll<i></i></span>
    </div>
  {/if}

  <!-- header -->
  <div class="header" style:height="{L.headerY * 2 - 6}px" style:opacity={started}></div>
  {#if fanned}
    <button class="closer" aria-label="Close the alumni" onclick={() => (fanned = false)}></button>
  {/if}
  {#if pileCount > 0}
    <div class="fanback" class:show={fanned} style:width="{fanBox.w}px" style:height="{fanBox.h}px" style:transform="translate3d({fanBox.x}px,{fanBox.y}px,0)">
    </div>
  {/if}
  {#each avatars as a (a.p)}
    {#if a.st.opacity > 0.01 && a.st.y > -L.av * 1.2}
      {@const v = view(a)}
      {@const ip = pileIx[a.p]}
      {@const h = titles[a.p] || sackos[a.p] || silvers[a.p] ? honoursOf(a.p) : null}
      <button
        class="av"
        class:piled={ip !== undefined}
        class:fanned={fanned && ip !== undefined}
        aria-label={people[a.p].name}
        style:width="{L.av}px"
        style:height="{L.av}px"
        style:z-index={zOf(a)}
        style:opacity={a.st.opacity}
        style:--glow={a.st.flying}
        style:--win={h?.win ?? 0}
        style:--win-tone={h?.winSilver ? '#dfe5ea' : 'var(--gold)'}        style:--gray={fanned && ip !== undefined ? 0.35 : grayOf(a.st)}
        style:--tone={people[a.p].color}
        style:--i={ip ?? 0}
        style:transform="translate3d({v.x - L.av / 2 + (h?.shake ?? 0)}px,{v.y - L.av / 2}px,0) rotate({v.rot}deg) scale({v.scale * (1 + (h?.win ?? 0) * 0.24)})"
        onclick={() => tapAvatar(a)}
      >
        <Avatar id={a.p} size={L.av} live />
        {#if h?.stars.length}
          <span class="stars" aria-label={h.stars.map((x) => `${x.n} ${x.kind === 'gold' ? 'title' : 'silver star'}${x.n > 1 ? 's' : ''}`).join(', ')}>
            {#each h.stars as st (st.kind)}
              <svg class:silver={st.kind === 'silver'} viewBox="0 0 10 10" style:transform="translate({st.x}px,0) scale({st.sc})" aria-hidden="true"><path d="M5 .4l1.4 3 3.2.3-2.4 2.2.7 3.2L5 7.5 2.1 9.1l.7-3.2L.4 3.7l3.2-.3z" /></svg>
              {#if st.ast}<b class="ast" style:transform="translate({st.x + 4}px,-3px)">*</b>{/if}
              {#if st.n > 1}<b class="cnt" class:silver={st.kind === 'silver'} style:transform="translate({st.x + (st.ast ? 8 : 5)}px,0)">×{st.n}</b>{/if}
            {/each}
          </span>
        {/if}
        {#if h && h.sackoCount}
          <span class="sackos" aria-label="{h.sackoCount} sacko{h.sackoCount > 1 ? 's' : ''}">
            {#if h.landed}
              <svg viewBox="0 0 10 10" style:width="8px" style:height="8px" style:transform="translate(0px,{-L.av / 2 - 5}px) translate(-50%,-50%)" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7" /></svg>
              {#if h.landed > 1}<b class="cnt sk" style:transform="translate(5px,{-L.av / 2 - 10}px)">×{h.landed}</b>{/if}
            {/if}
            {#each h.flying as x, k (k)}
              <svg
                class="big"
                viewBox="0 0 10 10"
                style:width="{x.size}px"
                style:height="{x.size}px"
                style:opacity={x.o}
                style:transform="translate({x.x}px,{x.y}px) translate(-50%,-50%) scale({x.sc})"
                aria-hidden="true"
              ><path d="M1.5 1.5l7 7M8.5 1.5l-7 7" /></svg>
            {/each}
          </span>
        {/if}
        {#if a.st.returning > 0.02}<span class="returns" style:opacity={a.st.returning}>returns</span>{/if}
        {#if ip !== undefined}<span class="nm">{first(a.p)}</span>{/if}
      </button>
    {/if}
  {/each}
  {#if pileCount > 0}
    <button
      class="pile"
      aria-label="Alumni, {pileCount} people"
      aria-expanded={fanned}
      style:transform="translate3d({L.pile.x - 31}px,{L.pile.y - 22}px,0) scale({1 + pileBump * 0.12})"
      onclick={toggleFan}
    >
      <span class="count">+{pileCount}</span>
    </button>
  {/if}

  <!-- the year scrubber -->
  <Scrubber {L} {fi} opacity={started} {reduced} />

  <!-- temporary: type set switcher for the design review -->
  <button class="typeswitch" onclick={() => setType(TYPES[(TYPES.indexOf(type) + 1) % TYPES.length])} aria-label="Switch typeface set, now {type.toUpperCase()}">{type.toUpperCase()}</button>
</div>

<style>
  .spacer {
    width: 1px;
  }
  .stage {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    overflow: clip; /* not hidden: a hidden box can still be scrolled sideways by focus or scrollIntoView */
    contain: strict;
    background:
      radial-gradient(120% 70% at 20% 0%, color-mix(in srgb, var(--bg-2) 85%, transparent), transparent 70%),
      var(--bg);
  }
  .stage > * {
    position: absolute;
    top: 0;
    left: 0;
    will-change: transform, opacity;
  }

  /* columns */
  .field {
    z-index: 2;
    inset: 0;
    -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 var(--fade));
    mask-image: linear-gradient(to bottom, transparent 0, #000 var(--fade));
    pointer-events: none;
  }
  .field > * {
    position: absolute;
    top: 0;
    left: 0;
  }
  .col,
  .tail {
    /* --g: 0 = the member's colour, 1 = muted grey (a column that has been cut) */
    --dead: color-mix(in srgb, var(--thread) 80%, var(--tone));
    --now: color-mix(in srgb, var(--dead) calc(var(--g, 0) * 100%), var(--tone));
    will-change: transform, height;
  }
  .col {
    pointer-events: auto;
    background:
      /* in the card's shadow from --lit down (and, before the league, all the way up) */
      linear-gradient(to bottom, transparent calc(var(--lit) - 14px), rgba(0, 0, 0, 0.46) calc(var(--lit) + 6px)),
      linear-gradient(to bottom, color-mix(in srgb, var(--now) 78%, #000 22%), var(--now) 240px);
  }
  .tail {
    /* the cut-off end, falling away into the screen; its shadow grows from the tip up */
    transform-origin: 50% 0;
    background:
      linear-gradient(to top, rgba(0, 0, 0, calc(var(--p) * 0.6)) 0, transparent calc(var(--p) * 100%)),
      var(--now);
  }
  .cardshade {
    /* the card's shadow falling on the ribbons just above it */
    height: 44px;
    background: linear-gradient(to bottom, transparent, rgba(0, 0, 0, 0.42));
    pointer-events: none;
  }
  .floorshade {
    /* the ribbons fall down and away into the screen at the bottom edge */
    height: 120px;
    background: linear-gradient(to bottom, transparent, rgba(0, 0, 0, 0.35) 45%, rgba(0, 0, 0, 0.82));
    pointer-events: none;
  }
  .founder {
    /* founders' ribbons get a fine serrated edge */
    --teeth: linear-gradient(#000, #000), conic-gradient(from 45deg at 0 50%, #000 90deg, transparent 0), conic-gradient(from 225deg at 100% 50%, #000 90deg, transparent 0);
    -webkit-mask-image: var(--teeth);
    mask-image: var(--teeth);
    -webkit-mask-size: calc(100% - 3px) 100%, 1.5px 4px, 1.5px 4px;
    mask-size: calc(100% - 3px) 100%, 1.5px 4px, 1.5px 4px;
    -webkit-mask-position: center, 0 var(--py), 100% var(--py);
    mask-position: center, 0 var(--py), 100% var(--py);
    -webkit-mask-repeat: no-repeat, repeat-y, repeat-y;
    mask-repeat: no-repeat, repeat-y, repeat-y;
  }
  .founder::before {
    /* founders' ribbons carry a faint harlequin lattice, anchored to the timeline so it scrolls with them */
    content: '';
    position: absolute;
    inset: 0;
    background-image: var(--lattice);
    background-size: var(--cw) calc(var(--cw) * 1.5);
    background-position: 0 var(--py);
    opacity: calc(var(--regal) * (1 - var(--g, 0) * 0.45));
    pointer-events: none;
  }  /* championship edges down the ribbon: gold foil for the first title, platinum inside it for the second */
  .edge {
    position: absolute;
    inset: 0;
    background-repeat: repeat-y;
    pointer-events: none;
  }
  .edge.gold {
    background-image: var(--foil-gold), var(--foil-gold);
    background-size: 2px 96px;
    background-position:
      0 var(--py),
      100% var(--py);
  }
  .edge.plat {
    background-image: var(--foil-plat), var(--foil-plat);
    background-size: 1.5px 96px;
    background-position:
      2px calc(var(--py) + 40px),
      calc(100% - 2px) calc(var(--py) + 40px);
  }
  .col.chev::after {
    /* a third title: gold chevrons running down the ribbon (anchored to the timeline), kept in
       off the edges so they don't run into the foil; a fourth doubles them */
    content: '';
    position: absolute;
    inset: 0 5px;
    background-image: var(--chevrons);
    background-size: 100% calc(var(--cw) * 0.8);
    background-position: 0 var(--py);
    opacity: calc(var(--chev) * 0.55);
    pointer-events: none;
  }
  .col.chev2::after {
    background-image: var(--chevrons2);
  }
  .col.dotted::before {
    /* current members who weren't founders: a fine dot texture, so they pop */
    content: '';
    position: absolute;
    inset: 0;
    background-image: radial-gradient(circle, rgba(255, 255, 255, 0.5) 0.7px, transparent 1.1px);
    background-size: 5px 5px;
    background-position: 0 var(--py);
    opacity: calc(0.32 * (1 - var(--g, 0) * 0.5));
    pointer-events: none;
  }
  .col.constant {
    animation: hue 9s var(--ease-in-out) infinite alternate;
  }
  @keyframes hue {
    from {
      filter: hue-rotate(-14deg) saturate(1.05);
    }
    to {
      filter: hue-rotate(14deg) saturate(1.2);
    }
  }
  .marker {
    /* a year line: cuts happen here */
    height: 1px;
    background: linear-gradient(to right, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.16));
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
  }
  .marker b {
    position: absolute;
    bottom: 1px;
    padding: 1px 3px 0;
    background: rgba(8, 9, 12, 0.72);
    color: var(--ink);
    font-size: 10px;
    line-height: 12px;
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* photos */
  .photos {
    inset: 0;
    z-index: 11; /* above the avatars (10): a rising avatar passes behind photos and the card */
    pointer-events: none;
  }
  .photo {
    position: absolute;
    top: 0;
    left: 0;
    padding: 5px;
    background: #f4f1ea;
    box-shadow:
      0 18px 40px -8px rgba(0, 0, 0, 0.75),
      0 2px 6px rgba(0, 0, 0, 0.4);
    pointer-events: auto;
    will-change: transform;
  }
  .photo img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: 50% 30%;
  }
  .mark {
    display: grid;
    place-items: center;
    pointer-events: auto;
  }
  .mark.champ path {
    fill: #fff;
  }
  .mark.champ {
    filter: drop-shadow(0 0 5px rgba(255, 255, 255, 0.75));
  }
  .mark.sacko path {
    fill: none;
    stroke: rgba(8, 9, 12, 0.85);
    stroke-width: 2.6;
  }

  /* finale */
  .cardwrap {
    z-index: 12;
    will-change: transform; /* never fade this wrapper: it would switch the glass off. Layers fade via --o */
  }
  .fin h3 {
    margin: 0 0 10px;
    font-size: calc(30px * var(--display-scale));
    line-height: 1;
  }
  .fin ol {
    list-style: none;
    margin: 0;
    padding: 0;
    columns: 2;
    column-gap: 14px;
  }
  .fin li button {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-height: 38px;
    text-align: left;
    break-inside: avoid;
  }
  .rk {
    width: 18px;
    font-weight: 700;
    font-size: 15px;
    color: var(--ink-2);
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .fin b {
    flex: 1;
    font-size: 15px;
    font-weight: 600;
  }
  .pts {
    font-size: 13px;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .fine {
    margin: 12px 0 0;
    font-size: 12px;
    color: var(--ink-3);
  }

  /* intro */
  .intro {
    inset: 0;
    z-index: 6;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 26px calc(8vh + var(--safe-bottom));
    max-width: 720px;
    pointer-events: none;
  }
  h1 {
    margin: 0;
    font-size: calc(clamp(46px, 13.5vw, 104px) * var(--display-scale));
    line-height: 0.92;
  }
  h1 span {
    display: block;
    color: var(--ink-3);
  }
  h1 em {
    display: block;
    font-style: normal;
  }
  .lede {
    margin: 22px 0 0;
    max-width: 30ch;
    font-size: 17px;
    line-height: 1.5;
    color: var(--ink-2);
  }
  .hint {
    position: absolute;
    left: 26px;
    bottom: calc(5vh + var(--safe-bottom));
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ink-3);
  }
  .hint i {
    width: 1px;
    height: 34px;
    background: linear-gradient(to bottom, var(--ink-2), transparent);
    animation: drip 1.8s var(--ease-in-out) infinite;
    transform-origin: top;
  }
  @keyframes drip {
    0% {
      transform: scaleY(0);
    }
    60% {
      transform: scaleY(1);
      opacity: 1;
    }
    100% {
      transform: scaleY(1);
      opacity: 0;
    }
  }

  /* header */
  .header {
    right: 0;
    z-index: 8;
    width: 100%;
    padding-top: var(--safe-top);
    background: linear-gradient(to bottom, var(--bg) 35%, transparent);
    pointer-events: none;
  }
  .av {
    z-index: 10;
    display: grid;
    place-items: center;
    filter: grayscale(var(--gray, 0)) drop-shadow(0 0 calc(var(--glow) * 12px) var(--tone))
      drop-shadow(0 0 calc(var(--win, 0) * 14px) color-mix(in srgb, var(--win-tone, var(--gold)) calc(var(--win, 0) * 100%), transparent));
  }
  /* sacko: the X stamps onto the face, then sits in a row along the top */
  .sackos {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 0;
    height: 0;
    pointer-events: none;
  }
  .sackos svg {
    position: absolute;
    left: 0;
    top: 0;
    overflow: visible;
  }
  .sackos path {
    fill: none;
    stroke: #e5484d;
    stroke-width: 2;
    stroke-linecap: square;
    filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9));
  }
  .sackos svg.big path {
    stroke-width: 1.6;
  }
  .av::after {
    /* keeps the tap target at 44px even though the avatar is ~26px */
    content: '';
    position: absolute;
    inset: -9px;
  }
  .stars {
    position: absolute;
    left: 50%;
    bottom: -5px;
    width: 0;
    height: 9px;
    pointer-events: none;
  }
  .stars svg {
    position: absolute;
    left: -4.5px;
    top: 0;
    width: 9px;
    height: 9px;
    fill: var(--gold);
    filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9)) drop-shadow(0 0 4px color-mix(in srgb, var(--gold) 70%, transparent));
  }
  .stars svg.silver {
    fill: #e3e8ee;
    filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9)) drop-shadow(0 0 4px rgba(227, 232, 238, 0.6));
  }
  .cnt {
    position: absolute;
    left: 0;
    top: -0.5px;
    font-size: 8.5px;
    line-height: 10px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--gold);
    text-shadow:
      0 0 2px #000,
      0 0 1px #000;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .cnt.silver {
    color: #e3e8ee;
  }
  .cnt.sk {
    color: #ff6b70;
  }
  .stars .ast {
    position: absolute;
    left: 0;
    top: 0;
    font-size: 9px;
    line-height: 1;
    font-weight: 800;
    color: var(--gold);
    text-shadow: 0 0 2px #000;
  }
  .mark .ast {
    position: absolute;
    right: -6px;
    top: -5px;
    font-size: 11px;
    line-height: 1;
    font-weight: 800;
    color: #fff;
    text-shadow: 0 0 3px #000;
  }
  .mark.silver path {
    fill: #e3e8ee;
  }
  .mark.silver {
    filter: drop-shadow(0 0 5px rgba(227, 232, 238, 0.7));
  }
  .returns {
    position: absolute;
    right: -2px;
    top: 100%;
    margin-top: 5px;
    padding: 2px 6px;
    background: var(--ink);
    color: var(--bg);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .av.piled {
    transition:
      transform 520ms var(--ease-spring) calc(var(--i) * 30ms),
      filter var(--dur-ui) var(--ease-out);
  }
  .nm {
    position: absolute;
    top: 100%;
    left: 50%;
    margin-top: 3px;
    transform: translateX(-50%);
    font-size: 9px;
    font-weight: 600;
    white-space: nowrap;
    color: var(--ink);
    opacity: 0;
    transition: opacity var(--dur-micro) var(--ease-out);
    pointer-events: none;
  }
  .av.fanned .nm {
    opacity: 1;
    transition-delay: calc(180ms + var(--i) * 30ms);
  }
  .closer {
    inset: 0;
    z-index: 38;
    background: transparent;
    cursor: default;
  }
  .fanback {
    z-index: 39;
    background: var(--glass-strong);
    backdrop-filter: var(--glass-filter);
    -webkit-backdrop-filter: var(--glass-filter);
    box-shadow: var(--glass-rim), var(--glass-lift);
    opacity: 0;
    transform-origin: 100% 0;
    scale: 0.6;
    pointer-events: none;
    transition:
      opacity var(--dur-ui) var(--ease-out),
      scale var(--dur-expand) var(--ease-spring);
  }
  .fanback.show {
    opacity: 1;
    scale: 1;
  }
  .pile {
    z-index: 27;
    width: 62px;
    height: 44px;
    display: grid;
    place-items: end center;
  }
  .count {
    transform: translateY(15px);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }

  .typeswitch {
    top: auto;
    left: auto;
    right: 8px;
    bottom: calc(8px + var(--safe-bottom));
    z-index: 35;
    width: 30px;
    height: 30px;
    background: var(--glass-strong);
    box-shadow: var(--glass-rim);
    font-size: 11px;
    font-weight: 600;
    color: var(--ink-2);
  }

  @media (prefers-reduced-motion: reduce) {
    .av.piled,
    .fanback {
      transition-duration: 1ms;
    }
    .col.constant,
    .hint i {
      animation: none;
    }
  }
</style>
