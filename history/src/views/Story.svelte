<script lang="ts">
  // The roster story. One fixed stage with three zones that never overlap: header avatars, the
  // column field, and the card tray, plus the year scrubber on the right edge. Everything is drawn
  // from the scroll position, so the whole history scrubs forwards and backwards like a film.
  import { onMount } from 'svelte';
  import {
    makeLayout, segments, members, people, legacy, constants, lineup, exits, isCurrent, statusOf, FIRST, LAST, CUT_GAP, SLOTS,
    pourAt, growTip, avatarState, stopAt, trayAt, clamp, lerp, back, smooth, easeOut, yearsLabel, tegridy, type AvatarState, type Spot, type TgMember,
  } from '../lib/model';
  import { scatter, type Spot as BurstSpot } from '../lib/scatter';
  import Avatar from './Avatar.svelte';
  import Glass from './Glass.svelte';
  import Tray from './Tray.svelte';
  import Scrubber from './Scrubber.svelte';
  import PersonPanel from './PersonPanel.svelte';
  import Roll from './Roll.svelte';
  import { fly, fade } from 'svelte/transition';
  import { backOut } from 'svelte/easing';

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
  // while the scrubber is held, the story follows its preview playhead instead of the page scroll
  let previewW: number | null = null;
  const rawScroll = () => (previewW !== null ? previewW - L.P : window.scrollY);

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
      if (fanned && Math.abs(window.scrollY - fanY) > 40) fanned = false; // a real scroll, not an iOS toolbar nudge
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    let raf = 0;
    tt = L.trayTop;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') (focus = null), (tgFocus = null);
      if (focus !== null && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) openSlot(clamp(focus + (e.key === 'ArrowRight' ? 1 : -1), 0, SLOTS - 1));
      if (tgFocus !== null && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) tgFocus = tgShown = clamp(tgFocus + (e.key === 'ArrowRight' ? 1 : -1), 0, TGN - 1);
    };
    window.addEventListener('keydown', onKey);
    // sideways swipes on an open column (touch), and sideways trackpad scrolls (desktop)
    let sx = 0, sy = 0, t0 = 0, track = false, side = false;
    const tStart = (e: TouchEvent) => {
      track = false;
      if ((focus === null && tgFocus === null) || e.touches.length !== 1) return;
      const t = e.touches[0];
      if ((focus !== null && t.clientX > L.padL + L.fieldW + 4) || (e.target as Element).closest?.('[role="dialog"]')) return; // the scrubber, sheets
      (sx = t.clientX), (sy = t.clientY), (t0 = performance.now()), (track = true), (side = false);
    };
    const tMove = (e: TouchEvent) => {
      if (!track) return;
      const t = e.touches[0];
      const dx = t.clientX - sx;
      const dy = t.clientY - sy;
      if (!side) {
        if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.3) side = true;
        else if (Math.abs(dy) > 10) return void (track = false);
        else return;
      }
      e.preventDefault();
      drag = dx;
    };
    const tEnd = () => {
      if (track && side) (tgFocus !== null ? tgSwipe : swipeEnd)(drag, performance.now() - t0);
      track = side = false;
    };
    let wx = 0, wIdle = 0, wCool = 0;
    const onWheel = (e: WheelEvent) => {
      if ((focus === null && tgFocus === null) || Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return;
      e.preventDefault();
      clearTimeout(wIdle);
      if (performance.now() < wCool) return;
      wx += e.deltaX;
      drag = clamp(-wx, -140, 140);
      if (Math.abs(wx) > 90) {
        (tgFocus !== null ? tgSwipe : swipeEnd)(-wx, 1000);
        wx = 0;
        wCool = performance.now() + 450;
      } else wIdle = window.setTimeout(() => ((wx = 0), (drag = 0)), 140);
    };
    window.addEventListener('touchstart', tStart, { passive: true });
    window.addEventListener('touchmove', tMove, { passive: false });
    window.addEventListener('touchend', tEnd);
    window.addEventListener('touchcancel', tEnd);
    window.addEventListener('wheel', onWheel, { passive: false });
    const tick = (now: number) => {
      stepCuts(now);
      stepFocus();
      stepTg();
      stepGrow(now);
      const tTarget = L.vh - 10 - (want ? Math.min(want, L.trayH) : L.trayH);
      if (Math.abs(tTarget - tt) > 0.3) tt = reduced ? tTarget : tt + (tTarget - tt) * 0.2;
      else if (tt !== tTarget) tt = tTarget;
      const target = rawScroll();
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
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('touchstart', tStart);
      window.removeEventListener('touchmove', tMove);
      window.removeEventListener('touchend', tEnd);
      window.removeEventListener('touchcancel', tEnd);
      window.removeEventListener('wheel', onWheel);
    };
  });

  // ---- the expanded column. Tap a lit ribbon and it opens up across the field; everyone else
  // squeezes down to thin slices on either side (tap a slice to switch). The years scroll as usual,
  // the ribbon's own panel follows them, and no story cards show. Cuts here are just a gap.
  let focus = $state<number | null>(null); // the open column's slot
  let shown = $state(0); // the slot the panel shows (kept while it closes)
  let fz = $state(0); // 0 = the story, 1 = expanded; springs between
  let geo = $state<{ x: number; w: number }[]>([]); // each slot's left edge and width, springing to target
  let prev = $state<number | null>(null); // the column closing while another opens
  let dir = $state(1); // which way we're moving through the columns: 1 = to the right
  let drag = $state(0); // a sideways swipe in progress, in finger px (negative: pulling the next column in from the right)
  const slice = $derived({ w: L.desktop ? 12 : 5, gap: L.desktop ? 6 : 2 });
  const openW = $derived(L.fieldW - (SLOTS - 1) * (slice.w + slice.gap));
  const PW = $derived(openW - 16); // the glass panel's width (fixed, so its text never reflows)
  /** The neighbour a swipe in progress is pulling in, if there is one. */
  const peekSlot = () => (focus === null || !drag ? -1 : focus + (drag < 0 ? 1 : -1));
  function geoTarget(slot: number, f: number | null) {
    if (f === null) return { x: L.colX(slot) - L.cw / 2, w: L.cw };
    // mid-swipe the neighbour opens up a little under the finger, taking room from the open column
    const nb = peekSlot();
    const peek = nb >= 0 && nb < SLOTS ? Math.min(Math.abs(drag) * 0.45, openW * 0.4) : 0;
    const width = (i: number) => (i === f ? openW - peek : i === nb ? slice.w + peek : slice.w);
    let x = L.padL;
    for (let i = 0; i < slot; i++) x += width(i) + slice.gap;
    return { x, w: width(slot) };
  }
  const gOf = (slot: number) => geo[slot] ?? geoTarget(slot, null);
  const litFor = (slot: number) => pourAt(L, slot, rawScroll() + L.P) >= 0.9;

  // The glass panel rides inside its column (clipped to it) on a soft spring, so it's pulled along
  // behind the column's edge, overshoots a touch and settles. Opening from the story it's revealed
  // from the middle. Switching, the incoming glass rides in on the edge facing the outgoing column,
  // and the outgoing one is dragged out by the edge facing the incoming one.
  let pull = $state<Record<number, { x: number; v: number }>>({});
  function anchor(k: number) {
    const g = gOf(k);
    const near = 8;
    const far = g.w - 8 - PW;
    if (k === shown && prev === null) return drag < 0 ? far : drag > 0 ? near : (g.w - PW) / 2;
    if (k === shown) return dir > 0 ? near : far;
    return dir > 0 ? far : near;
  }
  function stepPull() {
    const next: Record<number, { x: number; v: number }> = {};
    let changed = false;
    for (const k of prev === null ? [shown] : [shown, prev]) {
      const nb = peekSlot();
      const rubber = k === shown ? drag * (nb >= 0 && nb < SLOTS ? 0.12 : 0.18) : 0; // at the ends it just stretches
      const t = anchor(k) + rubber;
      const c = pull[k] ?? { x: t, v: 0 };
      let v = reduced ? 0 : c.v * 0.7 + (t - c.x) * 0.17;
      let x = reduced ? t : c.x + v;
      if (Math.abs(t - x) < 0.05 && Math.abs(v) < 0.05) (x = t), (v = 0);
      next[k] = { x, v };
      if (x !== c.x || v !== c.v) changed = true;
    }
    if (changed || Object.keys(next).length !== Object.keys(pull).length) pull = next;
  }
  function openSlot(slot: number) {
    if (focus === slot || !litFor(slot) || sink > 0.05) return;
    fanned = false;
    if (focus !== null) {
      dir = slot > focus ? 1 : -1;
      prev = focus;
    } else prev = null;
    focus = shown = slot;
    // the incoming glass starts on its column's leading edge, hidden by the clip until the column opens
    const g = gOf(slot);
    pull = { ...pull, [slot]: { x: prev === null ? (g.w - PW) / 2 : dir > 0 ? 8 : g.w - 8 - PW, v: 0 } };
  }
  function stepFocus() {
    if (focus !== null && (!litFor(focus) || sink > 0.05)) focus = null; // scrolled back before the league, or past the end: close
    if (focus === null && prev !== null) prev = null;
    if (focus === null && tgFocus === null && drag) drag = 0;
    if (prev !== null && gOf(prev).w < slice.w + 0.6) prev = null; // done closing
    stepPull();
    const k = reduced ? 1 : drag ? 0.3 : 0.15; // under the finger it follows closely; let go, it eases over

    const ease = (c: number, t: number) => (Math.abs(t - c) < 0.2 ? t : c + (t - c) * k);
    let changed = geo.length !== SLOTS;
    const next = Array.from({ length: SLOTS }, (_, i) => {
      const t = geoTarget(i, focus);
      const c = geo[i] ?? t;
      const n = { x: ease(c.x, t.x), w: ease(c.w, t.w) };
      if (n.x !== c.x || n.w !== c.w) changed = true;
      return n;
    });
    if (changed) geo = next;
    const fT = focus === null ? 0 : 1;
    const nf = Math.abs(fT - fz) < 0.003 ? fT : fz + (fT - fz) * k;
    if (nf !== fz) fz = nf;
  }
  /**
   * Anyone holding a column right now opens it instead of a sheet; sheets are for everyone else
   * (alumni, friends of the league, and anyone before the league starts). True if it opened.
   */
  export function show(id: string): boolean {
    const yr = L.stops[Math.min(L.stops.length - 1, Math.floor(stopAt(L, rawScroll() + L.P)))];
    const slot = lineup[yr]?.indexOf(id) ?? -1;
    if (slot < 0 || !litFor(slot)) return false;
    openSlot(slot);
    return true;
  }
  const tapCol = openSlot;

  // Swiping sideways on an open column moves to the next one. The neighbour opens a little under
  // the finger as you drag; let go past ~60px (or flick) and it takes over, otherwise it springs back.
  // Vertical drags stay the page's: the story keeps scrolling through the years.
  function swipeEnd(dx: number, ms: number) {
    drag = 0;
    if (focus === null) return;
    const to = focus + (dx < 0 ? 1 : -1);
    if ((Math.abs(dx) > 60 || Math.abs(dx) / Math.max(ms, 1) > 0.45) && to >= 0 && to < SLOTS) openSlot(to);
  }

  // ---- the moment a column is cut. This one beat runs on the clock, not the scroll: tension
  // releasing plays out by itself. The column shakes and its colour drains to grey on the same
  // envelope, so it is grey exactly when it comes to rest. Scrolling back up restores the colour.
  type Fx = { g: number; x: number };
  let fx = $state<Record<string, Fx>>({});
  const cutAnim: Record<string, { passed: boolean; t0: number; mode: 'idle' | 'shake' | 'unfade'; g0: number }> = {};
  function stepCuts(now: number) {
    const wNow = rawScroll() + L.P; // the raw scroll: the shake starts the moment the cut arrives
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
  type Piece = { key: string; person: string; slot: number; x: number; cw: number; y: number; h: number; clip: string; g: number; py: number; lit: number; founder: boolean; constant: boolean; dotted: boolean; gold: number; plat: number; chev: number; chev2: number };
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
    // expanded: no card, so nothing is in its shadow, and the timeline below the playhead is drawn
    // too (cuts are a flat gap you can see coming, not a slice that falls away)
    const flat = fz > 0.5;
    // past the last card its shadow lifts off the ribbons too (it used to linger as a dark band)
    const cardGone = clamp((w - L.end) / (vh * 0.2));
    const cardTop = lerp(tt, vh + 40, Math.max(fz, cardGone));
    for (const seg of segments) {
      const founding = seg.start === FIRST;
      const cutBot = seg.end !== LAST;
      const key = `${seg.slot}-${seg.start}`;
      const B1 = L.top(seg.end + 1);
      const cut = cutBot && w >= B1; // the cut has reached the playhead
      // today's ribbons run on past the timeline, behind the rankings, until they sink into the screen
      const bottom = cutBot ? B1 + L.cutH / 2 - CUT_GAP / 2 : L.end + vh * 3;
      const tailTop = cutBot ? bottom - L.cutH - L.cw * 1.8 : bottom; // the last stretch hangs free once cut

      let top: number; // world
      if (founding) {
        const tip = growTip(L, seg.person, w);
        if (tip === null) continue;
        top = tip + s;
      } else {
        top = L.T[seg.start] - L.cutH / 2 + CUT_GAP / 2;
        if (!flat && w <= top + 1) continue; // arrives when its cut reaches the playhead
      }
      const f = fx[key] ?? { g: cut ? 1 : 0, x: 0 };
      const gm = gOf(seg.slot);
      const x = gm.x + (f.x + sway(seg.slot)) * (1 - fz);
      const litY = founding ? lerp(L.headerY - 30, cardTop, pourAt(L, seg.slot, w)) : cardTop; // screen
      const base = { person: seg.person, slot: seg.slot, cw: gm.w, g: f.g, founder: !!people[seg.person].founder, constant: constants.has(seg.person), dotted: !people[seg.person].founder && isCurrent(seg.person), ...edgesOf(seg.person) };

      const mEnd = flat ? (cutBot ? Math.min(bottom, floor) : floor) : cut ? tailTop : floor;
      if (mEnd > top + 1) {
        // once they fall, every ribbon starts above the screen: founders' tops sit under the header
        // (where they grew from), which made them look shorter than everyone else's as they dropped
        const y = sink > 0 ? -40 : Math.max(top - s, -40);
        const h = mEnd - s - y;
        if (h > 0 && y < vh) {
          const o = y + s; // the element's top, in world pixels
          // the diagonal flattens as the column opens; expanded, the bottom is cut flat too
          const tl = founding ? 0 : top + L.cutH * (1 - fz / 2) - o;
          const tr = founding ? 0 : top + (L.cutH * fz) / 2 - o;
          const b = flat && cutBot ? bottom - L.cutH / 2 - o : h + 60;
          const clip = founding && !(flat && cutBot) ? 'none' : `polygon(0 ${px(tl)},100% ${px(tr)},100% ${px(b)},0 ${px(b)})`;
          cols.push({ ...base, key, x, y, h, clip, py: -o, lit: litY - y });
        }
      }
      if (cut && !flat) {
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

  // ---- photos: they rise up from behind the card one after another, growing as they come. Each new
  // one lands on top, where the last one was, and pushes the ones before it up the stack. As the next
  // card arrives they drift up and shrink away into the top, the highest first.
  const photos = $derived.by(() => {
    const out: { key: string; p: Photo; x: number; y: number; rot: number; z: number; o: number; sc: number }[] = [];
    const pw = Math.min(L.fieldW * 0.7, 330);
    const ph = pw * 0.75;
    const regionTop = L.headerY + L.av + 14;
    const regionBot = L.trayTop - 18; // a fixed line (the tallest card's top): a shorter next card mustn't drag leaving photos down
    for (const r of L.seq) {
      const list = r.card.photos;
      const span = r.b - r.a;
      if (!list?.length || w < r.a - vh * 0.5 || w > r.b + span * 0.6) continue;
      const n = list.length;
      // leaving takes each photo about as long as arriving did (the mirror of its ease), the top of
      // the stack first, overlapping a little more than the arrivals so the last isn't left alone
      const dIn = (span * 0.6) / n;
      const dOut = dIn * 0.85;
      const exitAt = (k: number) => r.b - span * 0.18 + k * dOut * 0.45;
      const base = regionBot - ph / 2 - 4;
      const step = n > 1 ? Math.min(ph * 0.58, (base - ph / 2 - regionTop) / (n - 1)) : 0;
      const ents = list.map((_, k) => easeOut(clamp((w - (r.a + span * 0.06 + k * dIn)) / dIn)));
      list.forEach((p, k) => {
        const e = ents[k];
        if (e <= 0) return;
        const climb = ents.slice(k + 1).reduce((t, v) => t + v, 0); // pushed up by every later arrival
        const tx = L.padL + L.fieldW / 2 + [-10, 14, -6][k % 3] * (L.fieldW / 300);
        const rot = [-3, 2.5, -1.5][k % 3];
        const ty = base - climb * step;
        const ex = 1 - easeOut(1 - clamp((w - exitAt(k)) / dOut));
        if (ex >= 1) return;
        const enterY = lerp(Math.max(tt, L.trayTop) + ph * 0.25, ty, e); // from behind the card
        const y = lerp(enterY, L.headerY - ph * 0.15, ex);
        const sc = lerp(0.5, 1, e) * lerp(1, 0.32, ex);
        out.push({ key: p.src, p, x: tx, y, rot: rot * (0.4 + 0.6 * e) + (1 - e) * 5 - ex * rot * 1.5, z: k + 1, o: clamp(e * 3) * (1 - ex * ex), sc });
      });
    }
    return { list: out, pw, ph };
  });

  // ---- markers that live on the columns: each season's champion and sacko
  const marks = $derived.by(() => {
    type Kind = 'champ' | 'sacko' | 'silver';
    const out: { key: string; kind: Kind; person: string; x: number; y: number; pop: number; o: number; star: boolean }[] = [];
    const add = (key: string, kind: Kind, person: string, slot: number, world: number, star = false) => {
      const y = markY(world);
      if (w <= world || y < 0 || y > L.P + 20) return;
      // a trophy or sacko X nearing the header merges into its owner's avatar (see honours below)
      const merge = clamp((L.headerY + L.av * 4 - y) / (L.av * 3));
      if (merge >= (kind === 'sacko' ? 0.5 : 1)) return; // the sacko X hands over to the stamp
      out.push({ key, kind, person, x: gOf(slot).x + gOf(slot).w / 2, y, pop: clamp((w - world) / (vh * 0.07)) * (1 - merge * 0.55), o: (1 - merge) * (1 - fz), star });
    };
    if (fz > 0.99) return out;
    for (const [year, season] of Object.entries(legacy.seasons)) {
      const y = Number(year);
      if (!lineup[y]) continue;
      const mid = honourAt(y);
      const slotOf = (id: string | null) => (id ? lineup[y].indexOf(id) : -1);
      if (slotOf(season.champion) >= 0) add(`champ${y}`, 'champ', season.champion!, slotOf(season.champion), mid, !!season.championAsterisk);
      if (slotOf(season.sacko) >= 0) add(`sacko${y}`, 'sacko', season.sacko!, slotOf(season.sacko), mid);
      for (const sv of season.silverStars ?? []) if (slotOf(sv.person) >= 0) add(`silver${y}${sv.person}`, 'silver', sv.person, slotOf(sv.person), mid);
    }
    return out;
  });

  // ---- the expanded column's content. Each season's honours sit on the ribbon at the line that
  // closes it, labelled. A panel at the top follows the years: who holds this column, the season
  // under the playhead, and their running tally. At a cut the next person's panel rises with their
  // ribbon and pushes the last one up and away.
  type Line = { kind: 'champ' | 'runner' | 'sacko' | 'silver' | 'points'; text: string };
  function linesOf(y: number, p: string): Line[] {
    const season = legacy.seasons[String(y)];
    if (!season) return [];
    const out: Line[] = [];
    if (season.champion === p) out.push({ kind: 'champ', text: `Champion${season.championAsterisk ? '*' : ''}` });
    if (season.runnerUp === p) out.push({ kind: 'runner', text: 'Runner-up' });
    for (const sv of season.silverStars ?? []) if (sv.person === p) out.push({ kind: 'silver', text: `Silver star · ${sv.why}` });
    if (season.ledScoring === p) out.push({ kind: 'points', text: 'Most points' });
    if (season.sacko === p) out.push({ kind: 'sacko', text: 'Sacko' });
    return out;
  }
  const focusMarks = $derived.by(() => {
    const out: { key: string; y: number; year: number; lines: Line[] }[] = [];
    if (fz < 0.01) return out;
    for (const year of Object.keys(legacy.seasons)) {
      const y = Number(year);
      if (!lineup[y]) continue;
      const sy = honourAt(y) - s;
      if (sy < L.headerY || sy > vh + 20) continue;
      const lines = linesOf(y, lineup[y][shown]);
      if (lines.length) out.push({ key: `f${y}`, y: sy, year: y, lines });
    }
    return out;
  });
  // each panel's natural height (n) and its fixed top part (t), measured
  let nat = $state<Record<string, { n: number; t: number }>>({});
  function natural(node: HTMLElement, key: string) {
    const top = node.querySelector('.top') as HTMLElement;
    const inner = node.querySelector('.inner') as HTMLElement;
    const ro = new ResizeObserver(() => {
      const t = top.offsetHeight;
      const n = t + inner.offsetHeight + 19; // .more's padding and rule
      const c = nat[key];
      if (!c || c.n !== n || c.t !== t) nat[key] = { n, t };
    });
    ro.observe(top);
    ro.observe(inner);
    return { destroy: () => ro.disconnect() };
  }
  // a fade at the bottom edge while there's more to scroll
  function moreFade(node: HTMLElement) {
    const check = () => node.classList.toggle('more-below', node.scrollTop + node.clientHeight < node.scrollHeight - 4);
    const ro = new ResizeObserver(check);
    ro.observe(node);
    if (node.firstElementChild) ro.observe(node.firstElementChild);
    node.addEventListener('scroll', check, { passive: true });
    return { destroy: () => (ro.disconnect(), node.removeEventListener('scroll', check)) };
  }
  type Panel = { key: string; person: string; y: number; h: number; yr: number; last: number; lines: Line[]; tally: { n: number; one: string; many: string }[] };
  /**
   * The panels for one column. A panel sits under the header and reaches down as far as its content
   * goes, to the bottom of the screen if need be. Only a member who leaves has a limit: as their
   * cut rises the panel gives way (its content scrolls inside it), and once it's down to its top
   * part it's pushed up and away, so it never runs into the next person's ribbon.
   */
  function panelsOf(slot: number): Panel[] {
    const out: Panel[] = [];
    if (fz < 0.01) return out;
    const yrNow = L.stops[Math.min(L.stops.length - 1, Math.floor(fi))];
    const stick = L.headerY * 2 - 4;
    for (const seg of segments) {
      if (seg.slot !== slot) continue;
      const key = `${seg.slot}-${seg.start}`;
      const tip = seg.start === FIRST ? growTip(L, seg.person, w) : L.T[seg.start] + CUT_GAP / 2 - s;
      if (tip === null) continue;
      const bot = (seg.end !== LAST ? L.top(seg.end + 1) - CUT_GAP / 2 : Infinity) - s;
      if (bot < 0 || tip > vh) continue;
      const m = nat[key] ?? { n: vh * 0.6, t: 150 };
      const y0 = Math.max(stick, tip + 10);
      const segLimit = bot - 10;
      let h = Math.min(m.n, Math.min(vh - 12, segLimit) - y0);
      let y = y0;
      const minH = Math.min(m.n, m.t + 96);
      if (h < minH) {
        h = minH;
        y = Math.min(y0, segLimit - h);
      }
      const yr = clamp(yrNow, seg.start, seg.end);
      const p = seg.person;
      const done = (y: number) => w >= honourAt(y); // a season counts once its line has passed
      // the season just decided stays up through the next one (honours land right at the year line)
      const last = done(yr) ? yr : yr - 1;
      const lines = last >= seg.start ? linesOf(last, p).map((l) => ({ ...l, text: `${last} ${l.text}` })) : [];
      const n = (list: number[] | undefined) => (list ?? []).filter(done).length;
      const t = n(titles[p]);
      const k = n(sackos[p]);
      const sv = n(silvers[p]);
      const tally = [
        { n: t, one: 'title', many: 'titles' },
        { n: sv, one: 'silver star', many: 'silver stars' },
        { n: k, one: 'Sacko', many: 'Sackos' },
      ].filter((x) => x.n > 0);
      out.push({ key, person: p, y, h, yr, last, lines, tally });
    }
    return out;
  }
  // the open column and, while switching, the one closing
  const panelCols = $derived(
    (prev === null ? [shown] : [shown, prev]).map((k) => ({ k, g: gOf(k), pull: pull[k] ?? { x: 8, v: 0 }, list: panelsOf(k) })),
  );

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
  // Tapped, the pile bursts like a "Connected to" pile: everyone flies out to their own random spot
  // (seeded, so it always flares the same way), captioned with their name and years. No box, no grid;
  // the screen dims behind them. Tap anywhere and they fall back into the pile.
  const fanScale = $derived(L.desktop ? 1.15 : 1.25);
  let fanSpots = $state<BurstSpot[]>([]);
  // they only take taps once they've flown out, so a quick double tap can't open whoever was on top
  let fanSettled = $state(false);
  let settleT = 0;
  // `falling`: just closed, so the avatars take the quick fall-back easing home
  let falling = $state(false);
  let wasFanned = false;
  let fallT = 0;
  $effect(() => {
    if (!fanned) {
      clearTimeout(settleT);
      fanSettled = false;
      if (wasFanned) {
        falling = true;
        clearTimeout(fallT);
        fallT = window.setTimeout(() => (falling = false), 420 + pileCount * 14 + 60);
      }
    } else {
      clearTimeout(fallT);
      falling = false;
    }
    wasFanned = fanned;
  });
  function toggleFan() {
    if (fanned) return void (fanned = false);
    const a = L.av * fanScale;
    fanSpots = scatter(pileCount, L.pile, 'alumni', { w: 92, h: a + 40, up: a / 2 }, { left: 8, top: 8, right: L.W - 8, bottom: vh - 10 });
    fanned = true;
    fanY = window.scrollY;
    clearTimeout(settleT);
    settleT = window.setTimeout(() => (fanSettled = true), reduced ? 0 : 380);
  }
  function tapAvatar(a: { p: string; st: AvatarState }) {
    const p = a.p;
    if (pileIx[p] === undefined && a.st.landed > 0 && pileCount) return toggleFan(); // still dropping onto the pile
    if (pileIx[p] === undefined) return onperson(p);
    if (!fanned) return toggleFan();
    if (!fanSettled) return; // still flying out
    fanned = false;
    onperson(p);
  }
  function view(a: { p: string; st: AvatarState }) {
    const i = pileIx[a.p];
    if (fanned && i !== undefined && fanSpots[i]) {
      const f = fanSpots[i];
      return { x: L.pile.x + f.x, y: L.pile.y + f.y, scale: fanScale, rot: f.rot };
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
  // Every marker (trophy, silver star, sacko X) sits on its ribbon right at the year line that closes
  // its season, and lands on the avatars just after that line passes, while the season's card (which
  // leads the next year, see model.ts) is up. The current season has no closing line yet: its
  // markers sit early in its own year.
  function honourAt(y: number) {
    if (y >= LAST) return L.T[y] + L.cutH + L.av;
    return L.top(y + 1) - L.cutH - L.av * 0.8;
  }
  const midOf = honourAt;
  /**
   * Where a marker is on screen. Until it reaches the playhead it sits on its ribbon; from there it
   * rides up to the avatars MARK_SPEED times faster than the scroll, so a season's honours land
   * within ~0.4 of a screen and the next card (who left, who joined) can follow quickly.
   */
  const MARK_SPEED = 2.6;
  function markY(world: number) {
    return w < world ? world - s : L.P - (w - world) * MARK_SPEED;
  }
  /** 0..1 progress of an honour once its marker reaches the avatar; it plays over more scroll after that. */
  const reach = (world: number) => L.headerY + L.av * 4 - markY(world);
  const starOf = (year: number) => clamp((reach(midOf(year)) - L.av * 2.4) / (MARK_SPEED * vh * 0.09));
  const stampOf = (year: number) => clamp((reach(midOf(year)) - L.av * 1.5) / (MARK_SPEED * vh * 0.15));

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
  // after the rankings, the ribbons (and everyone riding them) drop down the page, gathering speed,
  // and run out into a dark abyss that rises from the bottom of the screen
  const sink = $derived(clamp((w - (L.finale + vh * 0.3)) / (vh * 0.6)));
  const fallY = $derived(sink * sink * vh * 1.15);
  const sinkTf = $derived(sink > 0 ? `translate3d(0,${fallY.toFixed(1)}px,0)` : null);
  // the avatars, the pile and the header don't fall with them: they just fade away as the fall begins
  const avFade = $derived(smooth(clamp(sink / 0.22)));

  // ---- Integridy Factor (the pipeline calls it Tegridy): the last word. Once the ribbons have fallen away, a header pops in and gets a
  // sticker slapped on it, a paragraph explains the score, and a bar chart rises in which every bar is
  // that member's own ribbon, lowest (best) on the left. Tap a bar and it opens like a column, with
  // everything that went into the number. The scene scrolls up from below like a page.
  const tgM = tegridy.members;
  const TGN = tgM.length;
  let headH = $state(130);
  let paraH = $state(220);
  const TG = $derived.by(() => {
    const G = L.finale + vh * 0.5; // the scene's top enters from the bottom of the screen here
    const side = L.desktop ? 32 : 14;
    const chartW = Math.min(W - side * 2, 880);
    const x0 = (W - chartW) / 2;
    const chartH = clamp(vh * 0.6, 300, 560);
    const gap = L.desktop ? 8 : 4;
    const bw = (chartW - (TGN - 1) * gap) / TGN;
    const av = Math.max(18, Math.min(bw - 2, L.desktop ? 44 : 30));
    const paraOff = headH + 18;
    const chartOff = paraOff + paraH + 40;
    const chartEnd = chartOff + chartH + 34; // scrolled this far, the chart sits at the bottom of the screen
    // then the page falls away to black and the logo comes up out of it, ending centred on screen
    const logoW = Math.min(W * 0.78, 520);
    const logoH = (logoW * 505) / 900;
    const blackOff = chartEnd + 6;
    const logoOff = chartEnd + vh * 0.62;
    const uEnd = logoOff + logoH / 2 + vh * 0.5;
    // bars rise from a baseline at the chart's foot; if anyone ever goes negative, the baseline lifts
    // so their bar can hang below it, with the avatar at its lower end
    const pos = Math.max(0, ...tgM.map((m) => m.total));
    const neg = Math.max(0, ...tgM.map((m) => -m.total));
    const room = chartH - (av + 30) * (neg ? 2 : 1);
    const unit = room / Math.max(1, pos + neg);
    const base = chartOff + chartH - (neg ? neg * unit + av + 30 : 0);
    return { G, x0, chartW, chartH, gap, bw, av, paraOff, chartOff, chartEnd, logoW, logoH, blackOff, logoOff, uEnd, base, unit };
  });
  const u = $derived(w - TG.G); // how far the scene has scrolled up
  const tgOn = $derived(u > -60);
  const pageH = $derived(Math.max(L.pageHeight, TG.G + TG.uEnd - L.P + vh));
  const headIn = $derived(vh - u < vh * 0.84);
  const paraIn = $derived(vh - u + TG.paraOff < vh * 0.9);
  const logoIn = $derived(vh - u + TG.logoOff < vh * 0.78);
  // the bars grow on the clock (left to right, overshooting a touch) once the chart is well in view
  let grown = $state(false);
  let growT0 = 0;
  let tgNow = $state(0);
  function stepGrow(now: number) {
    const want = vh - u + TG.chartOff < vh * 0.62;
    if (want !== grown) {
      grown = want;
      growT0 = now;
    }
    if (now - growT0 < 2400 || tgNow < growT0) tgNow = now;
  }
  const growOf = (i: number) => {
    if (reduced) return grown ? 1 : 0;
    const t = tgNow - growT0;
    return grown ? back(clamp((t - i * 70) / 650)) : 1 - smooth(clamp((t - (TGN - 1 - i) * 18) / 320));
  };
  /** 59.75 -> "59.75", 9.5 -> "9.5", 10 -> "10" */
  const fmtTF = (v: number) => (v < 0 ? '−' : '') + String(Math.round(Math.abs(v) * 100) / 100);
  /** a total's colour: green at 0, red at the league's worst */
  const tfMax = Math.max(1, ...tegridy.members.map((m) => m.total));
  const tfHeat = (v: number) => heat(v, 0, tfMax);

  // the open bar: same idea as an open column. It widens, rises to the top of the chart, and the
  // others squeeze into slices (tap one, or swipe, to switch)
  let tgFocus = $state<number | null>(null);
  let tgShown = $state(0);
  let tfz = $state(0);
  let tgGeo = $state<{ x: number; w: number; r: number }[]>([]);
  const tgSlice = $derived({ w: L.desktop ? 12 : 6, gap: L.desktop ? 6 : 3 });
  const tgOpenW = $derived(TG.chartW - (TGN - 1) * (tgSlice.w + tgSlice.gap));
  const tgPW = $derived(tgOpenW - 16);
  function tgTarget(i: number, f: number | null) {
    if (f === null) return { x: TG.x0 + i * (TG.bw + TG.gap), w: TG.bw, r: 0 };
    const nb = drag ? f + (drag < 0 ? 1 : -1) : -1;
    const peek = nb >= 0 && nb < TGN ? Math.min(Math.abs(drag) * 0.45, tgOpenW * 0.4) : 0;
    const width = (k: number) => (k === f ? tgOpenW - peek : k === nb ? tgSlice.w + peek : tgSlice.w);
    let x = TG.x0;
    for (let k = 0; k < i; k++) x += width(k) + tgSlice.gap;
    return { x, w: width(i), r: i === f ? 1 : 0 };
  }
  const tgG = (i: number) => tgGeo[i] ?? tgTarget(i, null);
  const tgReady = () => grown && u > TG.chartEnd - vh * 0.22 && u < TG.chartEnd + vh * 0.3;
  function tgOpen(i: number) {
    if (!tgReady() || tgFocus === i) return;
    tgFocus = tgShown = i;
  }
  function tgSwipe(dx: number, ms: number) {
    drag = 0;
    if (tgFocus === null) return;
    const to = tgFocus + (dx < 0 ? 1 : -1);
    if ((Math.abs(dx) > 60 || Math.abs(dx) / Math.max(ms, 1) > 0.45) && to >= 0 && to < TGN) tgFocus = tgShown = to;
  }
  function stepTg() {
    if (tgFocus !== null && (u < TG.chartEnd - vh * 0.3 || u > TG.chartEnd + vh * 0.35)) tgFocus = null; // scrolled away from the chart: close
    const k = reduced ? 1 : drag ? 0.3 : 0.15;
    const ease = (c: number, t: number, eps = 0.2) => (Math.abs(t - c) < eps ? t : c + (t - c) * k);
    let changed = tgGeo.length !== TGN;
    const next = Array.from({ length: TGN }, (_, i) => {
      const t = tgTarget(i, tgFocus);
      const c = tgGeo[i] ?? t;
      const n = { x: ease(c.x, t.x), w: ease(c.w, t.w), r: ease(c.r, t.r, 0.003) };
      if (n.x !== c.x || n.w !== c.w || n.r !== c.r) changed = true;
      return n;
    });
    if (changed) tgGeo = next;
    const fT = tgFocus === null ? 0 : 1;
    const nf = Math.abs(fT - tfz) < 0.003 ? fT : tfz + (fT - tfz) * k;
    if (nf !== tfz) tfz = nf;
  }
  // what each bar shows: its top edge (container px), and where the avatar and number sit
  const tgBars = $derived(
    tgM.map((m, i) => {
      const g = tgG(i);
      const gr = growOf(i);
      const hNat = Math.max(Math.abs(m.total) * TG.unit * gr, gr > 0.01 ? 6 : 0); // a zero still shows a nub
      const down = m.total < 0;
      const top = down ? TG.base : TG.base - hNat;
      const bot = down ? TG.base + hNat : TG.base;
      // open, the bar runs from the top of the chart to its foot
      const t2 = lerp(top, TG.chartOff, g.r);
      const b2 = lerp(bot, TG.chartOff + TG.chartH, g.r);
      return { m, i, g, gr, top: t2, h: Math.max(0, b2 - t2), end: down ? bot : top, down };
    }),
  );
  const kindsOf = (m: TgMember) => {
    const by: Record<string, { label: string; n: number; pts: number }> = {};
    for (const p of m.penalties) {
      const k = (by[p.kind] ??= { label: p.label, n: 0, pts: 0 });
      k.n++;
      k.pts += p.total;
    }
    return Object.values(by).sort((a, b) => b.pts - a.pts);
  };
  const tgSeasons = Array.from({ length: Number(tegridy.asOf.season) - 2019 + 1 }, (_, i) => String(2019 + i));
  const wt = tegridy.weights;
  const mt = tegridy.multipliers;
  const wb = [...mt.weeks_before_playoffs].sort((a, b) => b.max_weeks - a.max_weeks); // 3-4 weeks out, then 1-2
  // the explainer, as a grid: what each violation costs (worst first), then the playoff multipliers
  const tgRules = [
    { v: wt.bye_week_starter, label: 'Started a bye' },
    { v: wt.injured_starter_out, label: 'Started an Out' },
    { v: wt.questionable_did_not_play, label: 'Questionable, sat' },
    { v: wt.missed_league_note, label: 'Missed league note' },
    { v: wt.injured_starter_doubtful, label: 'Doubtful, 0 pts' },
  ]
    .sort((a, b) => b.v - a.v)
    .map((r, i) => ({ ...r, i }));
  const tgMults = [
    { v: wb[0]?.multiplier ?? 1.5, label: '3–4 wks out' },
    { v: wb[1]?.multiplier ?? 1.75, label: 'Last 2 wks' },
    { v: mt.in_playoffs, label: 'Playoffs' },
  ].map((r, i) => ({ ...r, i }));
  /** higher is redder, lower is greener */
  const heat = (v: number, lo: number, hi: number) => `hsl(${Math.round(130 * (1 - clamp((v - lo) / (hi - lo))))} 78% 62%)`;
  const introO = $derived(1 - clamp(s / (vh * 0.45)));
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

{#snippet icon(kind: string)}
  {#if kind === 'champ'}
    <path d="M4 2h8v3.2a4 4 0 0 1-8 0zM1.8 3H4v1.3H3.1A1.7 1.7 0 0 0 4.2 6l-.5 1.2A3 3 0 0 1 1.8 4.4zM12 3h2.2v1.4a3 3 0 0 1-1.9 2.8L11.8 6a1.7 1.7 0 0 0 1.1-1.7H12zM7.2 9h1.6v2.4H11V13H5v-1.6h2.2z" />
  {:else if kind === 'silver'}
    <path d="M8 .8l2.2 4.6 5 .5-3.8 3.4 1.1 5L8 11.8l-4.5 2.5 1.1-5L.8 5.9l5-.5z" />
  {:else if kind === 'runner'}
    <path d="M8 1.5a4.3 4.3 0 1 1 0 8.6 4.3 4.3 0 0 1 0-8.6zM5.4 10.4l-1 4.3L8 12.8l3.6 1.9-1-4.3A5.6 5.6 0 0 1 8 11a5.6 5.6 0 0 1-2.6-.6z" />
  {:else if kind === 'points'}
    <path d="M2 14h3V8H2zM6.5 14h3V4.5h-3zM11 14h3V2h-3z" />
  {:else}
    <path class="x" d="M3.2 3.2l9.6 9.6M12.8 3.2l-9.6 9.6" />
  {/if}
{/snippet}

<div class="spacer" style:height="{pageH}px"></div>

<div class="stage" class:reduced style:height="{vh}px" style:touch-action={focus !== null || tgFocus !== null ? 'pan-y' : null}>
  <!-- columns: nothing is ever drawn over these except their own markers -->
  <div
    class="field"
    style:--fade="{L.headerY * 2 + 26}px"
    style:--cw="{L.cw}px"
    style:transform={sinkTf}
    style:opacity={sink > 0.75 ? 1 - smooth((sink - 0.75) / 0.25) : null}
    style:visibility={sink >= 1 ? 'hidden' : null}
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
        aria-label={focus === c.slot ? people[c.person].name : `Open ${first(c.person)}'s column`}
        style:--tone={people[c.person].color}
        style:--g={c.g}
        style:--py="{c.py}px"
        style:--lit="{c.lit}px"
        style:width="{c.cw}px"
        style:height="{c.h}px"
        style:clip-path={c.clip}
        style:transform="translate3d({c.x}px,{c.y}px,0)"
        onclick={() => tapCol(c.slot)}
      >
        {#if c.gold > 0}<i class="edge gold" style:opacity={c.gold}></i>{/if}
        {#if c.plat > 0}<i class="edge plat" style:opacity={c.plat}></i>{/if}
      </button>
    {/each}
    {#each field.tails as t (t.key)}
      <i
        class="tail"
        class:founder={t.founder}
        class:chev={t.chev > 0}
        class:chev2={t.chev2 > 0.5}
        style:--chev={t.chev}
        style:--tone={people[t.person].color}
        style:--g={t.g}
        style:--p={t.p}
        style:--py="{t.py}px"
        style:width="{t.cw}px"
        style:height="{t.h}px"
        style:clip-path={t.clip}
        style:transform={t.tf}
      >
        <!-- a title's foil runs all the way to the end of the cut -->
        {#if t.gold > 0}<i class="edge gold" style:opacity={t.gold}></i>{/if}
        {#if t.plat > 0}<i class="edge plat" style:opacity={t.plat}></i>{/if}
      </i>
    {/each}
    <!-- the card's shadow falling on the ribbons just above it, and the ribbons falling away at the bottom -->
    <i class="cardshade" style:opacity={started * (1 - fz) * (1 - clamp((w - L.end) / (vh * 0.2)))} style:width="{L.fieldW + 8}px" style:transform="translate3d({L.padL - 4}px,{tt - 44}px,0)"></i>
    <i class="floorshade" style:width="{L.fieldW + 8}px" style:transform="translate3d({L.padL - 4}px,{vh - 110}px,0)"></i>
    {#each markers as m (m.y)}
      <span class="marker" style:opacity={started} style:width="{L.fieldW}px" style:transform="translate3d({L.padL}px,{m.sy}px,0)">
        <b class="display" style:left="{lerp(L.colX(L.leviSlot) - L.cw / 2, gOf(shown).x, fz) - L.padL}px">{m.y}</b>
      </span>
    {/each}
    {#each focusMarks as m (m.key)}
      <span class="fmark" style:opacity={fz} style:transform="translate3d({gOf(shown).x + 8}px,{m.y}px,0) translateY(-50%)">
        {#each m.lines as l}<b class={l.kind}><svg viewBox="0 0 16 16" aria-hidden="true">{@render icon(l.kind)}</svg>{m.year} {l.text}</b>{/each}
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

  <!-- the abyss the ribbons fall into at the end -->
  {#if sink > 0}
    {@const abH = 160 + sink * vh * 0.6}
    <i class="abyss" style:width="{W}px" style:height="{abH}px" style:opacity={clamp(sink * 3)} style:transform="translate3d(0,{vh - abH}px,0)"></i>
  {/if}

  <!-- photos, between the ribbons and the card -->
  {#if photos.list.length && fz < 0.99}
    <div class="photos" style:opacity={1 - fz}>
      {#each photos.list as ph (ph.key)}
        <button
          class="photo"
          aria-label="Photo: {ph.p.alt}"
          style:width="{photos.pw}px"
          style:height="{photos.ph}px"
          style:z-index={ph.z}
          style:opacity={ph.o}
          style:transform="translate3d({ph.x - photos.pw / 2}px,{ph.y - photos.ph / 2}px,0) rotate({ph.rot}deg) scale({ph.sc})"
          onclick={() => onphoto(ph.p)}
        ><img src={import.meta.env.BASE_URL + ph.p.src} alt="" decoding="async" /></button>
      {/each}
    </div>
  {/if}

  <!-- the card tray -->
  <Tray {L} items={trayItems} opacity={trayO * (1 - fz)} top={tt} {onperson} bind:want />

  <!-- the expanded column: tap a slice to switch, the arrow to go back to the story -->
  {#if fz > 0.01}
    {#if focus !== null}
      {#each Array.from({ length: SLOTS }, (_, i) => i).filter((i) => i !== focus) as i (i)}
        <button
          class="slicehit"
          aria-label="Open {first(lineup[clamp(L.stops[Math.floor(fi)] ?? LAST, FIRST, LAST)][i])}'s column"
          style:width="{gOf(i).w + slice.gap}px"
          style:height="{vh - L.headerY * 2}px"
          style:transform="translate3d({gOf(i).x - slice.gap / 2}px,{L.headerY * 2}px,0)"
          onclick={() => tapCol(i)}
        ></button>
      {/each}
    {/if}
    <!-- each column's glass, clipped to its column: it's pulled in and out with the column's edge -->
    {#each panelCols as pc (pc.k)}
      {@const v = pc.pull.v}
      <div
        class="pclip"
        style:--o={pc.k === shown ? fz : 1}
        style:width="{Math.max(0, pc.g.w)}px"
        style:height="{vh}px"
        style:transform="translate3d({pc.g.x}px,0,0)"
      >
        {#each pc.list as pn (pn.key)}
          <div
            class="panel"
            style:pointer-events={pc.k === focus && fz > 0.6 ? 'auto' : 'none'}
            style:width="{PW}px"
            style:height="{Math.max(0, pn.h)}px"
            style:--pv="{clamp(-v * 1.6, -16, 16)}px"
            style:transform="translate3d({pc.pull.x}px,{pn.y}px,0) skewX({clamp(-v * 0.35, -4, 4)}deg) scale({lerp(0.94, 1, pc.k === shown ? fz : 1)})"
          >
            <Glass full pad="0">
              <div class="pbody" use:natural={pn.key}>
                <div class="top">
                  <div class="who">
                    <Avatar id={pn.person} size={L.desktop ? 52 : 40} />
                    <span><b class="display">{people[pn.person].name}</b><small>{#if people[pn.person].nickname}“{people[pn.person].nickname}” · {/if}{statusOf(pn.person)}</small></span>
                  </div>
                  <div class="yr display"><Roll value={pn.yr} /></div>
                  {#each pn.lines as l (l.text)}
                    <p class="res {l.kind}" in:fly={{ y: 10, duration: reduced ? 0 : 420, easing: backOut }} out:fade={{ duration: reduced ? 0 : 160 }}>
                      <svg viewBox="0 0 16 16" aria-hidden="true">{@render icon(l.kind)}</svg>{l.text}
                    </p>
                  {/each}
                  {#if pn.tally.length}
                    <p class="tally">
                      Through <Roll value={pn.yr} />:
                      {#each pn.tally as x, i (x.one)}{i ? ' · ' : ''}<Roll value={x.n} />&nbsp;{x.n > 1 ? x.many : x.one}{/each}
                    </p>
                  {/if}
                </div>
                <!-- everything the person sheet has; it scrolls inside the glass when it doesn't fit -->
                <div class="more" use:moreFade><div class="inner"><PersonPanel id={pn.person} {onperson} bare /></div></div>
              </div>
            </Glass>
          </div>
        {/each}
      </div>
    {/each}
    <button
      class="minimize"
      aria-label="Back to the story"
      style:opacity={fz}
      style:pointer-events={focus !== null ? 'auto' : 'none'}
      style:transform="translate3d({gOf(shown).x + gOf(shown).w - 44}px,{Math.max(0, L.headerY - 22)}px,0)"
      onclick={() => (focus = null)}
    ><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5" /></svg></button>
  {/if}

  <!-- finale -->
  {#if finaleCy < vh * 1.4 && fz < 0.5}
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
        <p class="fine">Mike's rankings, through week {legacy.asOf.last_scored_week} of {legacy.asOf.season}.</p>
      </article></Glass>
    </div>
  {/if}

  <!-- Integridy Factor: the last word -->
  {#if tgOn}
    <section class="tg" aria-label="Integridy Factor" style:width="{W}px" style:height="{TG.uEnd}px" style:transform="translate3d(0,{(vh - u).toFixed(1)}px,0)">
      <h2 class="tghead display" class:in={headIn} bind:clientHeight={headH} style:left="{TG.x0}px" style:font-size="calc({L.desktop ? 104 : 64}px * var(--display-scale))">
        Integridy<br />Facto<span class="r">r<img class="sticker" src="{import.meta.env.BASE_URL}tegridy/sticker.png" alt="An “I got tegridy” sticker" draggable="false" /></span>
      </h2>
      <div class="tgpara" class:in={paraIn} bind:clientHeight={paraH} style:left="{TG.x0}px" style:width="{Math.min(TG.chartW, 560)}px" style:top="{TG.paraOff}px">
        <p class="lede">Golf rules: lower is better. Everyone starts at 0 and only fair-play violations count, costing more near the playoffs. 2019 on.</p>
        <div class="rdiv"><span>Penalties</span></div>
        <div class="rules">
          {#each tgRules as r (r.label)}
            <span style:--i={r.i}><b style:color={heat(r.v, 3, 10)}>{r.v}</b><small>{r.label}</small></span>
          {/each}
        </div>
        <div class="rdiv"><span>Multiplier</span></div>
        <div class="rules mults">
          {#each tgMults as r (r.label)}
            <span style:--i={r.i + tgRules.length}><b style:color={heat(r.v, 1.5, 2)}>×{r.v}</b><small>{r.label}</small></span>
          {/each}
        </div>
      </div>

      <!-- the chart: every bar is that member's ribbon -->
      <i class="tgbase" style:left="{TG.x0}px" style:width="{TG.chartW}px" style:top="{TG.base}px" style:opacity={growOf(0) > 0 ? 1 : 0}></i>
      {#each tgBars as b (b.m.person)}
        {@const e = edgesOf(b.m.person)}
        {@const p = people[b.m.person]}
        <button
          class="col tgbar"
          class:founder={!!p.founder}
          class:dotted={!p.founder}
          class:chev={e.chev > 0}
          class:chev2={e.chev2 > 0.5}
          aria-label="{p.name}: Integridy Factor {b.m.total}"
          style:--chev={e.chev}
          style:--tone={p.color}
          style:--g="0"
          style:--py="0px"
          style:--lit="99999px"
          style:--cw="{TG.bw}px"
          style:width="{b.g.w}px"
          style:height="{b.h}px"
          style:transform="translate3d({b.g.x}px,{b.top}px,0)"
          onclick={() => tgOpen(b.i)}
        >
          {#if e.gold > 0}<i class="edge gold" style:opacity={e.gold}></i>{/if}
          {#if e.plat > 0}<i class="edge plat" style:opacity={e.plat}></i>{/if}
        </button>
        {#if b.gr > 0.01 && tfz < 0.99}
          <!-- the number at the bar's end, the avatar just past it -->
          {@const cx = b.g.x + b.g.w / 2}
          <b class="tgval" style:color={tfHeat(b.m.total)} style:opacity={(1 - tfz) * clamp(b.gr * 3)} style:transform="translate3d({cx}px,{b.down ? b.end + 4 : b.end - 17}px,0) translateX(-50%)">{b.gr >= 0.999 ? fmtTF(b.m.total) : Math.round(b.m.total * Math.min(1, b.gr))}</b>
          <button
            class="tgav"
            aria-label="Open {p.name}'s Integridy breakdown"
            tabindex={tgReady() ? 0 : -1}
            style:opacity={(1 - tfz) * clamp(b.gr * 3)}
            style:pointer-events={tfz > 0.5 ? 'none' : null}
            style:transform="translate3d({cx - TG.av / 2}px,{b.down ? b.end + 20 : b.end - 21 - TG.av}px,0)"
            onclick={() => tgOpen(b.i)}
          ><Avatar id={b.m.person} size={TG.av} /></button>
        {/if}
      {/each}
      {#if tfz > 0.01}
        <!-- slices are thin; give them a fatter target -->
        {#each tgBars as b (b.m.person)}
          {#if b.i !== tgFocus}
            <button class="slicehit tgslice" aria-label="Open {people[b.m.person].name}" style:width="{b.g.w + tgSlice.gap}px" style:height="{TG.chartH}px" style:transform="translate3d({b.g.x - tgSlice.gap / 2}px,{TG.chartOff}px,0)" onclick={() => tgOpen(b.i)}></button>
          {/if}
        {/each}
      {/if}
      <!-- the open bar's glass: clipped to its bar, so it's pulled in and out with it -->
      {#each tgBars as b (b.m.person)}
        {#if b.g.r > 0.02}
          {@const m = b.m}
          <div class="pclip tgclip" style:--o={b.g.r} style:width="{Math.max(0, b.g.w)}px" style:height="{TG.chartH}px" style:transform="translate3d({b.g.x}px,{TG.chartOff}px,0)">
            <div
              class="panel"
              style:pointer-events={b.i === tgFocus && tfz > 0.6 ? 'auto' : 'none'}
              style:width="{tgPW}px"
              style:height="{TG.chartH - 16}px"
              style:transform="translate3d({(b.g.w - tgPW) / 2}px,8px,0) scale({lerp(0.94, 1, b.g.r)})"
            >
              <Glass full pad="0">
                <div class="pbody">
                  <div class="top">
                    <div class="who">
                      <Avatar id={m.person} size={L.desktop ? 52 : 40} />
                      <span><b class="display">{people[m.person].name}</b><small>Integridy rank {m.rank} of {TGN} · lower is better</small></span>
                    </div>
                    <div class="yr display" style:color={tfHeat(m.total)}><Roll value={fmtTF(m.total)} /></div>
                    <p class="tally">
                      {#if m.penalties.length}{m.penalties.length} penalt{m.penalties.length > 1 ? 'ies' : 'y'} · {m.cleanSeasons.length} clean season{m.cleanSeasons.length === 1 ? '' : 's'}{:else}Not one penalty since 2019. A clean sheet.{/if}
                    </p>
                    <button class="minimize tgmin" aria-label="Back to the chart" onclick={() => (tgFocus = null)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5" /></svg></button>
                  </div>
                  <div class="more" use:moreFade>
                    <div class="inner tgx">
                      {#if m.penalties.length}
                        <h4>What it’s made of</h4>
                        {#each kindsOf(m) as k (k.label)}
                          <div class="kind">
                            <i style:width="{(k.pts / m.total) * 100}%"></i>
                            <span>{k.label}{k.n > 1 ? ` ×${k.n}` : ''}</span><b style:color={tfHeat(k.pts)}>{fmtTF(k.pts)}</b>
                          </div>
                        {/each}
                      {/if}
                      <h4>By season</h4>
                      <div class="seasons">
                        {#each tgSeasons as y (y)}
                          {@const v = m.bySeason[y] ?? 0}
                          <span class:clean={!v}><small>{y.slice(2)}</small><b style:color={tfHeat(v)}>{v ? fmtTF(v) : '✓'}</b></span>
                        {/each}
                      </div>
                      {#if m.penalties.length}
                        <h4>Every penalty</h4>
                        <ul class="pens">
                          {#each m.penalties as pn (pn.id)}
                            <li>
                              <small>{pn.season}{pn.week ? ` · Week ${pn.week}` : ''}</small>
                              <p>{pn.headline}</p>
                              <b>{pn.base}{pn.mult !== 1 ? ` × ${pn.mult}` : ''} = {fmtTF(pn.total)}</b>
                              {#if pn.sources.length}
                                <span class="src">Source: {#each pn.sources as sr, k (k)}{k ? ', ' : ''}{#if sr.url}<a href={sr.url} target="_blank" rel="noopener noreferrer">{sr.name}</a>{:else}{sr.name}{/if}{/each}</span>
                              {/if}
                            </li>
                          {/each}
                        </ul>
                      {/if}
                    </div>
                  </div>
                </div>
              </Glass>
            </div>
          </div>
        {/if}
      {/each}
      <p class="tgfine" style:left="{TG.x0}px" style:width="{TG.chartW - 44}px" style:top="{TG.chartOff + TG.chartH + 10}px" style:opacity={growOf(TGN - 1) > 0.5 ? 1 : 0}>
        Current members · through week {tegridy.asOf.last_scored_week} of {tegridy.asOf.season}. Tap a bar for the receipts.
      </p>

      <!-- the end: everything falls away to black, and the logo comes up out of the abyss, chomping -->
      <i class="tgblack" style:width="{W}px" style:top="{TG.blackOff}px" style:height="{TG.uEnd - TG.blackOff + vh}px" style:--fall="{Math.round(vh * 0.28)}px"></i>
      <div class="hodag" class:in={logoIn} class:reduced role="img" aria-label="Hodag" style:left="{(W - TG.logoW) / 2}px" style:top="{TG.logoOff}px" style:width="{TG.logoW}px" style:height="{TG.logoH}px">
        {#each ['jaw-top', 'jaw-bot', 'horn-l', 'horn-r'] as part (part)}
          <img class="hp {part}" src="{import.meta.env.BASE_URL}tegridy/hodag.png" alt="" draggable="false" />
        {/each}
      </div>
    </section>
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
  <div class="header" style:height="{L.headerY * 2 - 6}px" style:opacity={started * (1 - avFade)}></div>
  {#if pileCount > 0}
    <!-- the dim behind a burst pile; tap it to put them back -->
    <button
      class="closer"
      class:show={fanned}
      aria-label="Put the alumni back"
      tabindex={fanned ? 0 : -1}
      style:--cx="{L.pile.x}px"
      style:--cy="{L.pile.y}px"
      onclick={() => (fanned = false)}
    ></button>
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
        class:falling={falling && ip !== undefined}
        aria-label={people[a.p].name}
        style:width="{L.av}px"
        style:height="{L.av}px"
        style:z-index={zOf(a)}
        style:opacity={a.st.opacity * (1 - fz) * (1 - avFade)}
        style:pointer-events={fz > 0.5 || sink > 0.5 ? 'none' : null}
        style:--glow={a.st.flying}
        style:--win={h?.win ?? 0}
        style:--win-tone={h?.winSilver ? '#dfe5ea' : 'var(--gold)'}        style:--gray={fanned && ip !== undefined ? 0.35 : grayOf(a.st)}
        style:--tone={people[a.p].color}
        style:--i={ip ?? 0}
        style:--j={pileCount - 1 - (ip ?? 0)}
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
        {#if ip !== undefined}<span class="nm">{first(a.p)}<small>{yearsLabel(a.p)}</small></span>{/if}
      </button>
    {/if}
  {/each}
  {#if pileCount > 0}
    <button
      class="pile"
      aria-label="Alumni, {pileCount} people"
      aria-expanded={fanned}
      style:opacity={(1 - fz) * (1 - avFade)}
      style:pointer-events={fz > 0.5 || sink > 0.5 ? 'none' : null}
      style:transform="translate3d({L.pile.x - 31}px,{L.pile.y - 22}px,0) scale({1 + pileBump * 0.12})"
      onclick={toggleFan}
    >
      <span class="count">+{pileCount}</span>
    </button>
  {/if}

  <!-- the year scrubber -->
  <Scrubber {L} {fi} opacity={started * (1 - sink)} {reduced} onpreview={(pw) => (previewW = pw)} />

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
  .col.chev::after,
  .tail.chev::after {
    /* a third title: gold chevrons running down the ribbon (anchored to the timeline), kept in
       off the edges so they don't run into the foil; a fourth doubles them */
    content: '';
    position: absolute;
    inset: 0 5px;
    background-image: var(--chevrons);
    /* one ribbon's width per chevron, so an expanded column repeats them instead of stretching */
    background-size: calc(var(--cw) - 10px) calc(var(--cw) * 0.8);
    background-position: 50% var(--py);
    opacity: calc(var(--chev) * 0.55);
    pointer-events: none;
  }
  .col.chev2::after,
  .tail.chev2::after {
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

  /* the expanded column */
  .fmark {
    display: grid;
    gap: 3px;
    justify-items: start;
    pointer-events: none;
  }
  .fmark b {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 7px 3px 5px;
    background: rgba(8, 9, 12, 0.62);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--ink);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .fmark svg,
  .res svg {
    width: 12px;
    height: 12px;
    flex: none;
    fill: currentColor;
  }
  .fmark .x,
  .res .x {
    fill: none;
    stroke: currentColor;
    stroke-width: 2.4;
  }
  .champ svg {
    color: var(--gold);
  }
  .silver svg,
  .runner svg {
    color: #e3e8ee;
  }
  .sacko svg {
    color: #ff6b70;
  }
  .slicehit {
    z-index: 3;
  }
  .pclip {
    z-index: 9;
    overflow: hidden; /* not clip-path or opacity: either would switch the glass's frosting off */
    will-change: transform;
    pointer-events: none;
  }
  .panel {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 50% 0;
    color: var(--ink);
    will-change: transform;
    /* clear glass, not the cards' frost: a light blur so the ribbon's pattern still reads through it,
       darkened with brightness (which keeps the ribbon's hue) rather than a tint or extra saturation
       (which turned yellow ribbons orange and read as a solid block). A soft shadow on the type keeps
       it readable over bright ribbons. */
    --glass-tint: var(--glass-thin);
    --glass-filter: blur(1.5px) brightness(0.72);
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.55);
    /* every bit of type in here is pure white: no greys */
    --ink: #fff;
    --ink-2: #fff;
    --ink-3: #fff;
    color: #fff;
  }
  .pbody {
    display: flex;
    flex-direction: column;
    height: 100%;
    /* the content lags the glass a little as it's pulled, like it's sitting in something thick */
    transform: translate3d(var(--pv, 0px), 0, 0);
  }
  .panel .top {
    display: grid;
    gap: 6px;
    justify-items: start;
    padding: 10px 12px 10px;
    flex: none;
  }
  .panel .more {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 4px 12px 14px;
    border-top: 1px solid var(--glass-line);
    scrollbar-width: none;
  }
  .panel .more::-webkit-scrollbar {
    display: none;
  }
  .panel .more:global(.more-below) {
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 30px), transparent);
    mask-image: linear-gradient(to bottom, #000 calc(100% - 30px), transparent);
  }
  .who {
    display: flex;
    align-items: center;
    gap: 10px;
    text-align: left;
  }
  .who b {
    display: block;
    font-size: calc(19px * var(--display-scale));
    line-height: 1.05;
  }
  .who small {
    display: block;
    margin-top: 2px;
    font-size: 11px;
    color: var(--ink-2);
  }
  .yr {
    font-size: calc(40px * var(--display-scale));
    line-height: 0.95;
    font-variant-numeric: tabular-nums;
  }
  .res {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    font-size: 13px;
    font-weight: 700;
  }
  .tally {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--ink-2);
  }
  .minimize {
    z-index: 9;
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    color: var(--ink);
  }
  .minimize svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.6));
  }

  /* Integridy Factor */
  .tg {
    z-index: 20;
    pointer-events: none;
    will-change: transform; /* not opacity: that would switch the glass's frosting off */
  }
  .tg > * {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: auto;
  }
  .tghead {
    margin: 0;
    line-height: 0.92;
    letter-spacing: 0.005em;
    color: #fff;
    text-transform: uppercase;
    transform-origin: 0 100%;
    opacity: 0;
    transform: translateY(18px) scale(0.86);
    transition:
      opacity 160ms ease-in,
      transform 200ms ease-in;
  }
  .tghead.in {
    opacity: 1;
    transform: none;
    transition: none;
    /* pops in, then takes the sticker's thud */
    animation:
      tgpop 560ms cubic-bezier(0.2, 1.5, 0.4, 1) both,
      tgthud 300ms ease-out 640ms;
  }
  @keyframes tgpop {
    from {
      opacity: 0;
      transform: translateY(26px) scale(0.6);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @keyframes tgthud {
    0% {
      transform: none;
    }
    30% {
      transform: translateY(3px) scaleY(0.98);
    }
    100% {
      transform: none;
    }
  }
  .tghead .r {
    position: relative;
    display: inline-block;
  }
  .sticker {
    /* slapped on, overlapping the r a little */
    position: absolute;
    left: 0.36em;
    top: -0.5em;
    width: 1.32em;
    height: 1.32em;
    max-width: none;
    pointer-events: none;
    user-select: none;
    opacity: 0;
    transform: translate(18%, -30%) rotate(-42deg) scale(2.5);
    transition:
      opacity 120ms ease-in,
      transform 160ms ease-in;
  }
  .in .sticker {
    opacity: 1;
    transform: rotate(-13deg);
    transition:
      opacity 90ms linear 600ms,
      transform 300ms cubic-bezier(0.3, 1.35, 0.5, 1) 600ms;
  }
  .tgpara {
    margin: 0;
    font-size: 15px;
    line-height: 1.55;
    color: #fff;
    opacity: 0;
    transform: translateY(16px);
    transition:
      opacity 200ms ease-in,
      transform 200ms ease-in;
  }
  .tgpara.in {
    opacity: 1;
    transform: none;
    transition:
      opacity 500ms ease-out 120ms,
      transform 700ms cubic-bezier(0.2, 1, 0.3, 1) 120ms;
  }
  .tgpara .lede {
    margin: 0 0 12px;
    font-size: 14px;
    line-height: 1.45;
  }
  .rules {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 3px;
  }
  .rules.mults {
    margin-top: 4px;
  }
  .rules span {
    display: grid;
    gap: 2px;
    padding: 6px 9px 7px;
    background: rgba(255, 255, 255, 0.05);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.07);
    /* the cells deal in one after another */
    opacity: 0;
    transform: translateY(8px);
    transition:
      opacity 160ms ease-in,
      transform 160ms ease-in;
  }
  .tgpara.in .rules span {
    opacity: 1;
    transform: none;
    transition:
      opacity 360ms ease-out calc(220ms + var(--i) * 55ms),
      transform 520ms cubic-bezier(0.2, 1.4, 0.4, 1) calc(220ms + var(--i) * 55ms);
  }
  .rules b {
    flex: none;
    min-width: 1.6em;
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-weight: var(--display-weight);
    font-size: calc(21px * var(--display-scale));
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .rules small {
    font-size: 11px;
    white-space: nowrap;
    line-height: 1.25;
    color: #fff;
  }
  .src {
    display: block;
    margin-top: 2px;
    font-size: 11px;
  }
  .src a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .abyss {
    /* where the ribbons fall to: dark rising from the bottom of the screen */
    z-index: 11;
    pointer-events: none;
    background: linear-gradient(to bottom, transparent, color-mix(in srgb, var(--bg) 75%, transparent) 45%, var(--bg) 80%);
  }
  .tgbase {
    height: 1px;
    background: var(--line);
    transition: opacity 300ms;
  }
  .tgbar {
    will-change: transform, width, height;
  }
  .tgval {
    font-size: 10.5px;
    letter-spacing: -0.02em;
    font-weight: 800;
    color: #fff;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
    pointer-events: none;
  }
  .tgav {
    line-height: 0;
    filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.5));
  }
  .tgfine {
    margin: 0;
    font-size: 11px;
    color: var(--ink-2);
    transition: opacity 400ms;
  }
  .tg > .tgclip {
    z-index: 9;
    pointer-events: none;
  }
  .tg .panel .top {
    position: relative;
    padding-right: 44px;
  }
  .tgmin {
    position: absolute;
    top: 2px;
    right: 0;
  }
  .tgx h4 {
    margin: 14px 0 8px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .kind {
    position: relative;
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 8px;
    margin-bottom: 4px;
    font-size: 13px;
    overflow: hidden;
  }
  .kind > * {
    position: relative;
  }
  .kind i {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.34);
  }
  .kind {
    background: rgba(0, 0, 0, 0.12);
  }
  .kind b {
    font-variant-numeric: tabular-nums;
  }
  .seasons {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(38px, 1fr));
    gap: 4px;
  }
  .seasons span {
    display: grid;
    justify-items: center;
    padding: 5px 0;
    background: rgba(0, 0, 0, 0.28);
    font-variant-numeric: tabular-nums;
  }
  .seasons span.clean {
    background: rgba(255, 255, 255, 0.1);
  }
  .seasons small {
    font-size: 10px;
  }
  .seasons b {
    font-size: 13px;
  }
  .pens {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .pens li {
    padding: 9px 0;
    border-top: 1px solid rgba(255, 255, 255, 0.18);
  }
  .pens small {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
  }
  .pens p {
    margin: 3px 0;
    font-size: 13px;
    line-height: 1.4;
  }
  .pens b {
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }

  /* explainer dividers: a label sitting on a hairline */
  .rdiv {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 10px 0 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #fff;
  }
  .rdiv::after {
    content: '';
    flex: 1;
    height: 1px;
    background: rgba(255, 255, 255, 0.22);
  }
  /* the end: down to pure black */
  .tg > .tgblack {
    pointer-events: none;
    background: linear-gradient(to bottom, transparent 0, #000 var(--fall));
  }
  /* the logo, up out of the abyss: four copies of one image, clipped into a top jaw, a bottom jaw
     (split through the middle of the letters) and the two horn tips, so it can chomp */
  .tg > .hodag {
    pointer-events: none;
    opacity: 0;
    transform: translateY(45%) scale(0.78);
    filter: blur(10px);
    transition:
      opacity 300ms ease-in,
      transform 300ms ease-in,
      filter 300ms ease-in;
  }
  .tg > .hodag.in {
    opacity: 1;
    transform: none;
    filter: drop-shadow(0 0 22px rgba(255, 255, 255, 0.12));
    transition:
      opacity 700ms ease-out,
      transform 1000ms cubic-bezier(0.2, 1.1, 0.3, 1),
      filter 900ms ease-out;
  }
  .hp {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    max-width: none;
    user-select: none;
  }
  .jaw-top {
    clip-path: polygon(12.2% 0, 87.8% 0, 87.8% 29.6%, 100% 29.6%, 100% 45.3%, 0 45.3%, 0 29.6%, 12.2% 29.6%); /* overlaps the others a hair, so no seam shows */
    transform-origin: 50% 45%;
  }
  .jaw-bot {
    clip-path: inset(44.7% 0 0 0);
    transform-origin: 50% 45%;
  }
  .horn-l {
    clip-path: polygon(0 0, 12.5% 0, 12.5% 30%, 0 30%);
    transform-origin: 12.5% 30%;
  }
  .horn-r {
    clip-path: polygon(87.5% 0, 100% 0, 100% 30%, 87.5% 30%);
    transform-origin: 87.5% 30%;
  }
  .hodag.in .jaw-top {
    animation: chomp-top 1500ms cubic-bezier(0.45, 0, 0.3, 1) 650ms both;
  }
  .hodag.in .jaw-bot {
    animation: chomp-bot 1500ms cubic-bezier(0.45, 0, 0.3, 1) 650ms both;
  }
  .hodag.in .horn-l {
    animation: chomp-horn-l 1500ms cubic-bezier(0.45, 0, 0.3, 1) 650ms both;
  }
  .hodag.in .horn-r {
    animation: chomp-horn-r 1500ms cubic-bezier(0.45, 0, 0.3, 1) 650ms both;
  }
  .hodag.reduced .hp {
    animation: none !important;
  }
  /* three bites, each smaller, snapping shut with a little bounce, then it settles */
  @keyframes chomp-top {
    0% { transform: none; }
    13% { transform: translateY(-10%) rotate(-1.5deg); }
    22% { transform: translateY(1.5%); }
    28% { transform: none; }
    42% { transform: translateY(-7%) rotate(1deg); }
    51% { transform: translateY(1%); }
    57% { transform: none; }
    70% { transform: translateY(-4%) rotate(-0.5deg); }
    79% { transform: translateY(0.6%); }
    100% { transform: none; }
  }
  @keyframes chomp-bot {
    0% { transform: none; }
    13% { transform: translateY(8%) rotate(1deg); }
    22% { transform: translateY(-1.2%); }
    28% { transform: none; }
    42% { transform: translateY(5.5%) rotate(-0.8deg); }
    51% { transform: translateY(-0.8%); }
    57% { transform: none; }
    70% { transform: translateY(3%); }
    79% { transform: translateY(-0.5%); }
    100% { transform: none; }
  }
  /* the horns ride the top jaw and flick outward on each bite */
  @keyframes chomp-horn-l {
    0% { transform: none; }
    13% { transform: translateY(-10%) rotate(-14deg); }
    22% { transform: translateY(1.5%) rotate(3deg); }
    28% { transform: none; }
    42% { transform: translateY(-7%) rotate(-10deg); }
    51% { transform: translateY(1%) rotate(2deg); }
    57% { transform: none; }
    70% { transform: translateY(-4%) rotate(-6deg); }
    79% { transform: translateY(0.6%) rotate(1deg); }
    100% { transform: none; }
  }
  @keyframes chomp-horn-r {
    0% { transform: none; }
    13% { transform: translateY(-10%) rotate(14deg); }
    22% { transform: translateY(1.5%) rotate(-3deg); }
    28% { transform: none; }
    42% { transform: translateY(-7%) rotate(10deg); }
    51% { transform: translateY(1%) rotate(-2deg); }
    57% { transform: none; }
    70% { transform: translateY(-4%) rotate(6deg); }
    79% { transform: translateY(0.6%) rotate(-1deg); }
    100% { transform: none; }
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
  .av.piled.fanned {
    /* bursting out: an overshooting spring, one after another */
    transition:
      transform 680ms cubic-bezier(0.22, 1.5, 0.4, 1) calc(var(--i) * 32ms),
      filter var(--dur-ui) var(--ease-out);
  }
  .av.piled.falling {
    /* falling back: quick, the last out goes in first */
    transition:
      transform 420ms cubic-bezier(0.55, 0, 0.75, 0.15) calc(var(--j) * 14ms),
      filter var(--dur-ui) var(--ease-out);
  }
  .nm {
    position: absolute;
    top: 100%;
    left: 50%;
    display: grid;
    justify-items: center;
    margin-top: 3px;
    font-size: 9px;
    line-height: 1.2;
    font-weight: 700;
    white-space: nowrap;
    color: #fff;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
    opacity: 0;
    transform: translate(-50%, -4px);
    transition:
      opacity 120ms ease-in,
      transform 120ms ease-in;
    pointer-events: none;
  }
  .nm small {
    font-size: 7.5px;
    font-weight: 600;
  }
  .av.fanned .nm {
    opacity: 1;
    transform: translate(-50%, 0);
    transition:
      opacity 260ms ease-out calc(260ms + var(--i) * 32ms),
      transform 360ms cubic-bezier(0.22, 1.4, 0.4, 1) calc(260ms + var(--i) * 32ms);
  }
  .closer {
    inset: 0;
    z-index: 38;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle at var(--cx) var(--cy), rgba(0, 0, 0, 0.62), rgba(0, 0, 0, 0.45) 70%);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    opacity: 0;
    pointer-events: none;
    transition: opacity 260ms ease-out 60ms;
    cursor: default;
  }
  .closer.show {
    opacity: 1;
    pointer-events: auto;
    transition-delay: 0ms;
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
    .av.piled.fanned,
    .av.piled.falling,
    .closer {
      transition-duration: 1ms;
      transition-delay: 0ms;
    }
    .col.constant,
    .hint i {
      animation: none;
    }
  }
</style>
