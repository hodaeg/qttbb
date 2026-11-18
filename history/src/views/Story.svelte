<script lang="ts">
  // The roster story. One fixed stage with three zones that never overlap: header avatars, the
  // column field, and the card tray, plus the year scrubber on the right edge. Everything is drawn
  // from the scroll position, so the whole history scrubs forwards and backwards like a film.
  import { onMount } from 'svelte';
  import {
    makeLayout, cards, segments, members, people, legacy, constants, lineup, exits, isCurrent, statusOf, FIRST, LAST, CUT_GAP, SLOTS,
    pourAt, growTip, landing, LAND, avatarState, stopAt, clamp, lerp, back, smooth, easeOut, yearsLabel, tegridy, type AvatarState, type Spot, type TgMember,
  } from '../lib/model';
  import { scatter, type Spot as BurstSpot } from '../lib/scatter';
  import Avatar from './Avatar.svelte';
  import Glass from './Glass.svelte';
  import CardView from './Card.svelte';
  import HodagLogo from './HodagLogo.svelte';
  import OriginTree, { treeLayout } from './OriginTree.svelte';
  import Scrubber from './Scrubber.svelte';
  import PersonPanel from './PersonPanel.svelte';
  import Roll from './Roll.svelte';
  import { fly, fade } from 'svelte/transition';
  import { backOut } from 'svelte/easing';

  type Photo = { src: string; alt: string };
  // veiled: behind the lock, the story itself is blurred (not left to the lock's backdrop-filter, which
  // some browsers, e.g. Firefox here, don't apply); unveiling animates it into focus
  let { onperson, veiled = false }: { onperson: (id: string) => void; veiled?: boolean } = $props();

  // a tapped photo: the same print lifts out of its stack and grows to fill the screen; tap again (or the
  // dimmed background, or scroll) and it goes back. `zoomMove` turns the easing on just while it moves.
  let zoomKey = $state<string | null>(null);
  let zoomMove = $state(false);
  let zoomY = 0;
  let zoomT = 0;
  function zoomPhoto(key: string | null) {
    zoomKey = zoomKey === key ? null : key;
    zoomY = window.scrollY;
    zoomMove = true;
    clearTimeout(zoomT);
    zoomT = window.setTimeout(() => (zoomMove = false), 620);
  }

  let vh = $state(800);
  let W = $state(390);
  let s = $state(0); // smoothed scroll position
  let vel = $state(0); // how fast we're moving (drives the ripple)
  let time = $state(0);
  // on the title screen, before you've scrolled at all, the ghost ribbons sway on a loop (as they do
  // while scrolling); the first scroll stops it. Its own clock, so the real ribbons don't redraw for it.
  let idle = $state(1);
  let idleT = $state(0);
  let reduced = $state(false);
  // every story card's height, measured off-screen, so the timeline can give each its room
  let cardHs = $state<Record<number, number>>({});
  function measureCard(node: HTMLElement, i: number) {
    const ro = new ResizeObserver(() => {
      const h = Math.round(node.offsetHeight);
      if (h && cardHs[i] !== h) cardHs[i] = h;
    });
    ro.observe(node);
    return { destroy: () => ro.disconnect() };
  }
  // while the scrubber is held, the story follows its preview playhead instead of the page scroll
  let previewW: number | null = null;
  const rawScroll = () => (previewW !== null ? previewW - L.P : window.scrollY);

  // the bottom safe zone (see size() below): only ever grows, so nothing jumps as Safari's bars move
  let inset = $state(0);
  let innerH = $state(800); // what the window actually shows (can be less than vh, the large viewport)
  const L = $derived(makeLayout(vh, W, inset, cardHs));
  const w = $derived(s + L.P); // the playhead, in world pixels

  onMount(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reduced = mq.matches;
    // Lay the story out against the *large* viewport (address bar hidden), measured with a 100lvh
    // probe. On iPhone the bar comes back when you scroll up; if that re-measured the page, every
    // band would shrink and the story would leap forward. The bar just overlays the bottom instead.
    //
    // But iOS Safari's toolbar (on iOS 26 a floating glass bar) sits over the bottom of that large
    // viewport, and the viewport units don't reliably report it there. So keep a bottom safe zone for the
    // card, scrubber and chart: the most the bars have ever covered (large height minus the smallest
    // visible height seen, from 100svh, innerHeight and visualViewport) plus the home indicator. It only
    // ratchets up, a little at a time, so it settles after the first toolbar show/hide and stays put.
    const probe = document.createElement('div');
    probe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:100lvh;visibility:hidden;pointer-events:none';
    const small = document.createElement('div');
    small.style.cssText = 'position:fixed;top:0;left:0;width:0;height:100svh;visibility:hidden;pointer-events:none';
    const safe = document.createElement('div');
    safe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;padding-bottom:env(safe-area-inset-bottom,0px);visibility:hidden;pointer-events:none';
    document.body.append(probe, small, safe);
    const size = () => {
      const tall = probe.offsetHeight || window.innerHeight;
      vh = Math.max(tall, window.innerHeight);
      innerH = window.innerHeight;
      W = document.documentElement.clientWidth;
      const seen = Math.min(small.offsetHeight || vh, window.innerHeight, window.visualViewport?.height ?? vh);
      const want = Math.min(Math.round(Math.max(0, vh - seen) + safe.offsetHeight), Math.round(vh * 0.22));
      if (want > inset + 1) inset = want;
    };
    window.visualViewport?.addEventListener('resize', size);
    size();
    s = window.scrollY;
    window.addEventListener('resize', size);
    const onScroll = () => {
      if (fanned && Math.abs(window.scrollY - fanY) > 40) fanned = false; // a real scroll, not an iOS toolbar nudge
      if (zoomKey && Math.abs(window.scrollY - zoomY) > 40) zoomPhoto(null);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    // dev only: jump straight to a scroll position, skipping the easing (for testing in a throttled pane)
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__jump = (y: number) => (window.scrollTo(0, y), (s = y));
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__dbg = () => ({ trTop, trLen: TR.len, vh, innerH, inset, W, pageH, P: L.P, G: TG.G, uEnd: TG.uEnd, uEndReal, logoOff: TG.logoOff, logoH: TG.logoH, u, s, logoQ, logoRest });
    let raf = 0;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') (focus = null), (tgFocus = null), zoomKey && zoomPhoto(null);
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
      const target = rawScroll();
      const d = target - s;
      if (Math.abs(d) > 0.05) s = reduced ? target : s + d * 0.2;
      else if (d !== 0) s = target;
      // the ripple fades out over ~400ms after the scroll stops
      const v = reduced ? 0 : Math.abs(d) > Math.abs(vel) ? lerp(vel, d, 0.3) : lerp(vel, d, 0.06);
      if (idle > 0) {
        if (reduced || s > 3 || target > 3) idle = reduced ? 0 : Math.max(0, idle - 0.05);
        idleT = now / 1000;
      }
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
      small.remove();
      safe.remove();
      window.visualViewport?.removeEventListener('resize', size);
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
      // sprung in screen space (not relative to the column), so the glass lags and overshoots the same
      // way whichever direction you swipe
      const t = gOf(k).x + anchor(k) + rubber;
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
    pull = { ...pull, [slot]: { x: g.x + (prev === null ? (g.w - PW) / 2 : dir > 0 ? 8 : g.w - 8 - PW), v: 0 } };
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
  // tap a ribbon to open it; tap the open one again to close it
  const tapCol = (slot: number) => (focus === slot ? (focus = null) : openSlot(slot));
  // the burnt-in Return under the glass: tapped, it backs up under the card as the column closes
  const RET = 54; // room kept under each panel for it
  let backing = $state<string | null>(null);
  function goBack(key: string, close: () => void) {
    backing = key;
    window.setTimeout(close, reduced ? 0 : 170);
    window.setTimeout(() => (backing = null), reduced ? 0 : 700);
  }

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
  type Piece = { key: string; person: string; slot: number; x: number; cw: number; y: number; h: number; clip: string; g: number; py: number; lit: number; founder: boolean; constant: boolean; dotted: boolean; gold: number; plat: number; chev: number; chev2: number; gcut: number; pcut: number; ccut: number };
  type Tail = Piece & { tf: string; p: number };
  // while scrolling the ribbons sway a little side to side, each on its own slow phase
  const sway = (slot: number) => {
    const a = clamp(Math.abs(vel) / 30) * (L.desktop ? 2.2 : 1.4);
    return a ? Math.sin(time * 4.2 + slot * 1.37) * a : 0;
  };
  const idleSway = (slot: number) => (idle ? Math.sin(idleT * 4.2 + slot * 1.37) * idle * (L.desktop ? 2.6 : 1.8) : 0);
  const field = $derived.by(() => {
    const cols: Piece[] = [];
    const tails: Tail[] = [];
    const rolls: { key: string; x: number; w: number; y: number; tone: string; dark: number; spin: number }[] = [];
    const px = (n: number) => `${n.toFixed(1)}px`;
    const floor = s + vh + 10; // the bottom of the screen, in world pixels
    // expanded: no card, so nothing is in its shadow, and the timeline below the playhead is drawn
    // too (cuts are a flat gap you can see coming, not a slice that falls away)
    const flat = fz > 0.5;
    // past the last card its shadow lifts off the ribbons too (it used to linger as a dark band)
    const cardTop = vh + 40; // nothing is in a card's shadow now (the founders' pre-league dark pours away below)
    for (const seg of segments) {
      const founding = seg.start === FIRST;
      const cutBot = seg.end !== LAST;
      const key = `${seg.slot}-${seg.start}`;
      const B1 = L.top(seg.end + 1);
      const cut = cutBot && w >= B1; // the cut has reached the playhead
      // today's ribbons run on past the timeline, behind the rankings, until they sink into the screen
      const bottom = cutBot ? B1 + L.cutH / 2 - CUT_GAP / 2 : ribbonEnd;
      const tailTop = cutBot ? bottom - L.cutH - L.cw * 1.8 : bottom; // the last stretch hangs free once cut

      let top: number; // world
      let reach = Infinity; // a landing founder's ribbon pours down from the header: this far so far (screen)
      if (founding) {
        const ld = landing(L, seg.person, w);
        if (ld === null) continue;
        top = L.headerY + s;
        reach = ld.reach;
        // as it pours down the screen, the ribbon's front end is a little denser roll, unrolling
        if (ld.reach < vh + 30 && ld.reach > L.headerY + 4) {
          const gm0 = gOf(seg.slot);
          rolls.push({ key: `roll${seg.person}`, x: gm0.x, w: gm0.w, y: ld.reach, tone: people[seg.person].color ?? "#888", dark: pourAt(L, seg.slot, w), spin: ld.reach });
        }
      } else {
        top = L.T[seg.start] - L.cutH / 2 + CUT_GAP / 2;
        if (!flat && w <= top + 1) continue; // arrives when its cut reaches the playhead
      }
      const f = fx[key] ?? { g: cut ? 1 : 0, x: 0 };
      const gm = gOf(seg.slot);
      const x = gm.x + (f.x + sway(seg.slot)) * (1 - fz);
      const litY = founding ? lerp(L.headerY - 30, cardTop, pourAt(L, seg.slot, w)) : cardTop; // screen
      const base = { person: seg.person, slot: seg.slot, cw: gm.w, g: f.g, founder: !!people[seg.person].founder, constant: constants.has(seg.person), dotted: !people[seg.person].founder && isCurrent(seg.person), ...edgesOf(seg.person) };

      const mEnd = Math.min(flat ? (cutBot ? Math.min(bottom, floor) : floor) : cut ? tailTop : floor, reach + s, cutBot ? Infinity : ribbonEnd);
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
          cols.push({ ...base, key, x, y, h, clip, py: -o, lit: litY - y, gcut: edgeCut(base.gold, y, h), pcut: edgeCut(base.plat, y, h), ccut: edgeCut(base.chev, y, h) });
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
          tails.push({ ...base, key, x, y, h, clip, py: -(y + s), lit: litY - y, tf, p, gcut: edgeCut(base.gold, y, h), pcut: edgeCut(base.plat, y, h), ccut: edgeCut(base.chev, y, h) });
        }
      }
    }
    return { cols, tails, rolls };
  });

  // ---- year markers: a faint line across the field, badged on Levi's ribbon. Cuts land on them.
  const markers = $derived(
    L.stops
      .map((y) => ({ y, sy: L.T[y] - s }))
      .filter((m) => m.sy > L.headerY + 14 && m.sy < vh + 4),
  );

  // ---- photos: a little stack under their card, scrolling with it. Each one settles in as it comes up
  // from the bottom of the screen (a touch small and tilted, then square), later ones on top.
  const photos = $derived.by(() => {
    const out: { key: string; p: Photo; x: number; y: number; rot: number; z: number; o: number; sc: number; e: number }[] = [];
    const { w: pw, h: ph, step, gap } = L.photo;
    for (const [ri, r] of L.seq.entries()) {
      const list = r.card.photos;
      if (!list?.length) continue;
      const top = r.a + r.h + gap - s; // screen y of the stack's top
      if (top > vh + 40 || top + ph + (list.length - 1) * step < -40) continue;
      list.forEach((p, k) => {
        const y = top + ph / 2 + k * step;
        if (y - ph / 2 > vh + 30 || y + ph / 2 < -30) return;
        const t = easeOut(clamp((vh - (y - ph / 2)) / (vh * 0.42)));
        const x = L.cardX + L.trayW / 2 + [-0.12, 0.1, -0.05][k % 3] * L.trayW * 0.5;
        const rot = [-3, 2.5, -1.5][k % 3];
        const f = flick(y - ph / 2, ph, ri); // thrown off the same side as its card
        out.push({ key: p.src, p, x: x + f.x, y: y + (1 - t) * 30, rot: rot + (1 - t) * 7 * (k % 2 ? -1 : 1) + f.rot, z: k + 1, o: clamp(t * 2.5), sc: lerp(0.84, 1, t) * (1 - f.e * 0.3), e: f.e });
      });
    }
    return { list: out, pw, ph };
  });

  // ---- story cards, anchored in the timeline: each scrolls with the ribbons, settling in a touch as
  // it comes up from the bottom of the screen
  // ...and once its top climbs into the header, it's flicked off the side as it keeps rising (alternating
  // left and right), so it never slides under the avatars
  const exitLine = $derived(L.headerY * 2 + 85); // starts leaving here...
  const clearLine = $derived(L.headerY + L.av / 2 + 4); // ...and is off the side by the time it reaches the avatars
  const flick = (top: number, _h: number, i: number) => {
    const e = clamp((exitLine - top) / (exitLine - clearLine));
    const side = i % 2 ? 1 : -1;
    return { x: side * Math.pow(e, 1.6) * (W * 1.05), rot: side * e * 9, e };
  };
  const anchored = $derived(
    L.seq
      .map((r, i) => {
        const y = r.a - s;
        const e = easeOut(clamp((vh - y) / (vh * 0.3)));
        const yy = y + (1 - e) * 26;
        return { r, i, y: yy, o: clamp(e * 1.6), f: flick(yy, r.h, i) };
      })
      .filter((c) => c.y < vh + 30 && c.y + c.r.h > -30 && Math.abs(c.f.x) < W),
  );

  // ---- each season's results, written down the winner's (or loser's) ribbon: CHAMPION in gold foil,
  // SACKO burnt in, UNDEFEATED in platinum, and 2014's "champion*" burnt in, no foil, no explanation.
  // A word is written onto its ribbon as it scrolls into view; once its foot reaches the playhead it
  // rides up into the avatar (swallowed by the fade under the header), and the star, trim or X lands.
  const markFs = $derived(clamp(L.cw * 0.58, 10, 17));
  const marks = $derived.by(() => {
    type Kind = 'champ' | 'sacko' | 'silver';
    const out: { key: string; kind: Kind; person: string; x: number; y: number; o: number; star: boolean; reveal: number; text: string; len: number; bw: number; bh: number; sub: string; subFs: number; subLen: number; pad: number }[] = [];
    const add = (key: string, kind: Kind, person: string, slot: number, world: number, star = false) => {
      const y = markY(world); // the word's foot
      const text = kind === 'sacko' ? 'SACKO' : kind === 'silver' ? 'UNDEFEATED' : star ? 'champion*' : 'CHAMPION';
      const len = text.length * markFs * 0.78;
      if (y - len > vh + 4 || y < 0) return;
      // nearing the avatars it fades into them (the sacko hands over to the X stamp a little earlier)
      const merge = clamp((L.headerY + L.av * 4 - y) / (L.av * 3));
      if (merge >= (kind === 'sacko' ? 0.5 : 1)) return;
      const reveal = clamp((vh - (y - len)) / (len * 1.3)); // written down the ribbon as it comes on screen
      // CHAMPION and SACKO are cut out of a block of gold or charred material, a little narrower than the ribbon
      const bw = Math.max(12, Math.round(L.cw - (L.cw > 40 ? 20 : 4))); // wide ribbons: 10px of ribbon either side
      // the undefeated patch adds "(reg. season)" in small type under the word
      const sub = kind === 'silver' ? '(reg. season)' : '';
      const subFs = markFs * 0.6;
      const subLen = sub ? sub.length * subFs * 0.62 : 0;
      const pad = markFs * 0.65;
      const bh = Math.round(pad * 2 + len + (sub ? markFs * 0.45 + subLen : 0));
      out.push({ key, kind, person, x: gOf(slot).x + gOf(slot).w / 2, y, o: (1 - merge) * (1 - fz), star, reveal, text, len, bw, bh, sub, subFs, subLen, pad });
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
    for (const sv of season.silverStars ?? []) if (sv.person === p) out.push({ kind: 'silver', text: `Undefeated · ${sv.why.replace(/^Undefeated\s*/i, '')}` });
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
      let h = Math.min(m.n, Math.min(vh - 12 - RET, segLimit - RET) - y0);
      let y = y0;
      const minH = Math.min(m.n, m.t + 96);
      if (h < minH) {
        h = minH;
        y = Math.min(y0, segLimit - RET - h);
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
        { n: sv, one: 'undefeated season', many: 'undefeated seasons' },
        { n: k, one: 'Sacko', many: 'Sackos' },
      ].filter((x) => x.n > 0);
      out.push({ key, person: p, y, h, yr, last, lines, tally });
    }
    return out;
  }
  // the open column and, while switching, the one closing
  const panelCols = $derived(
    (prev === null ? [shown] : [shown, prev]).map((k) => ({ k, g: gOf(k), pull: pull[k] ?? { x: gOf(k).x + 8, v: 0 }, list: panelsOf(k) })),
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
    fanSpots = scatter(pileCount, L.pile, 'alumni', { w: 92, h: a + 40, up: a / 2 }, { left: 8, top: 8, right: L.W - 8, bottom: vh - L.inset - 10 });
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
  // - an undefeated regular season lands the same way, as a platinum star with a burst of sparkles;
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
  // A season's result patches are stitched onto the ribbons just after its stories (the layout decides
  // where: `L.honour`, the foot of the patches). They scroll with everything else; as a patch scrolls up
  // into its owner's avatar, the star, trim or X lands.
  function honourAt(y: number) {
    return L.honour[y] ?? L.top(y + 1) - L.cutH - L.av * 0.8;
  }
  const midOf = honourAt;
  /** where a patch's foot is on screen: stitched on, so it just scrolls */
  function markY(world: number) {
    return world - s;
  }
  /** 0..1 progress of an honour once its patch reaches the avatar; it plays over a little more scroll after that. */
  const reach = (world: number) => L.headerY + L.av * 4 - markY(world);
  const starOf = (year: number) => clamp((reach(midOf(year)) - L.av * 2.4) / (vh * 0.09));
  const stampOf = (year: number) => clamp((reach(midOf(year)) - L.av * 1.5) / (vh * 0.15));

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
  // ...and each one grows down the ribbon from the header as you keep scrolling once its star lands
  // (over ~0.4 of a screen), a ripple running down the ribbon with the growing front
  const edgeGrow = (year: number) => clamp((reach(midOf(year)) - L.av * 2.4) / (vh * 0.09) / 4.5);
  const edgesOf = (p: string) => {
    const t = titles[p] ?? [];
    const at = (k: number) => (t[k] ? edgeGrow(t[k]) : 0);
    return { gold: at(0), plat: at(1), chev: at(2), chev2: at(3) };
  };
  /** where a growing edge has got to, on screen */
  const edgeFront = (g: number) => L.headerY + g * (vh + 40 - L.headerY);
  /** how much of a ribbon piece (screen top y, height h) the edge hasn't reached yet, from its bottom */
  const edgeCut = (g: number, y: number, h: number) => (g >= 1 ? 0 : clamp(h - (edgeFront(g) - y), 0, h));
  // the ripple on each edge that's still growing
  const glitz = $derived.by(() => {
    const out: { key: string; x: number; w: number; y: number }[] = [];
    if (fz > 0.5 || sink > 0) return out;
    const yr = L.stops[Math.min(L.stops.length - 1, Math.floor(fi))];
    for (const [p, list] of Object.entries(titles)) {
      const slot = (lineup[yr] ?? []).indexOf(p);
      if (slot < 0) continue;
      list.forEach((y, k) => {
        const g = edgeGrow(y);
        if (g <= 0 || g >= 1 || k > 3) return;
        const gm = gOf(slot);
        out.push({ key: `${p}${y}`, x: gm.x, w: gm.w, y: edgeFront(g) });
      });
    }
    return out;
  });
  // the undefeated star gets its moment: once it's landed, a timed burst plays on the avatar (fast
  // scrolling can't skip it); scrolling back above it re-arms it
  let platBurst = $state<Record<string, number>>({});
  const platArmed: Record<string, boolean> = {};
  $effect(() => {
    for (const p of Object.keys(silvers)) {
      const landed = silvers[p].some((y) => starOf(y) >= 0.4);
      if (landed && !platArmed[p] && !reduced) {
        platArmed[p] = true;
        const n = (platBurst[p] ?? 0) + 1;
        platBurst[p] = n;
        window.setTimeout(() => {
          if (platBurst[p] === n) platBurst[p] = 0;
        }, 1900);
      } else if (!landed) platArmed[p] = false;
    }
  });
  const grayOf = (st: AvatarState) => (st.cut ? (fx[st.cut]?.g ?? 1) : st.gray);

  // ---- where we are in time (the dial and the tray read this)
  const fi = $derived(stopAt(L, w));
  const started = $derived(clamp((w - (L.T[L.stops[0]] - vh * 0.35)) / (vh * 0.2)));

  // the Legacy Rankings' points: green for the highest, through to red for the lowest
  const rankPts = legacy.rankings.map((r) => r.points);
  const rankHeat = (v: number) => heat(Math.max(...rankPts) - v, 0, Math.max(1, Math.max(...rankPts) - Math.min(...rankPts)));
  const finaleCy = $derived((L.finale - w) * 0.94 + vh * 0.52);
  // after the rankings the story winds down (`sink`): the avatars, the pile and the header fade away, and
  // the ribbons, which have run on behind the rankings, meet their end: it scrolls up the screen like the
  // rest of them, their last stretch fading into the dark, as if they run on into the screen
  const sink = $derived(clamp((w - (L.finale + vh * 0.3)) / (vh * 0.6)));
  const avFade = $derived(smooth(clamp(sink / 0.22)));
  const ribbonEnd = $derived(L.finale + vh * 1.5 - L.P - 40); // world: just above where Tegridy comes in
  const endFade = $derived(vh * 0.55);

  // ---- Tegridy Factor (the pipeline calls it Tegridy): the last word. Once the ribbons have fallen away, a header pops in and gets a
  // sticker slapped on it, a paragraph explains the score, and a bar chart rises in which every bar is
  // that member's own ribbon, lowest (best) on the left. Tap a bar and it opens like a column, with
  // everything that went into the number. The scene scrolls up from below like a page.
  const tgM = tegridy.members;
  const TGN = tgM.length;
  let headH = $state(130);
  let paraH = $state(220);
  // ---- the family tree: once the ribbons have run out, how everyone traces back to Dustin and Doug. It
  // scrolls up from below like a page, growing as it goes; Tegridy follows it.
  const TR = $derived(treeLayout(W, L.desktop, vh));
  const trTop = $derived(L.finale + vh * 0.5); // its top enters from the bottom of the screen here
  const uT = $derived(w - trTop);
  const TG = $derived.by(() => {
    const G = trTop + TR.len; // the scene's top enters from the bottom of the screen here
    const side = L.desktop ? 32 : 14;
    const chartW = Math.min(W - side * 2, 880);
    const x0 = (W - chartW) / 2;
    const chartH = clamp((vh - L.inset) * 0.6, 300, 560);
    const gap = L.desktop ? 8 : 4;
    const bw = (chartW - (TGN - 1) * gap) / TGN;
    const av = Math.max(18, Math.min(bw - 2, L.desktop ? 44 : 30));
    const paraOff = headH + 18;
    const chartOff = paraOff + paraH + 40;
    const chartEnd = chartOff + chartH + 34 + L.inset; // scrolled this far, the chart sits at the bottom of the visible screen
    // then the page falls away to black and the logo comes up out of it, ending centred on screen
    const logoW = Math.min(W * 0.86, 620);
    const logoH = (logoW * 1980) / 2560; // the logo's viewBox
    const blackOff = chartEnd + 6;
    const logoOff = chartEnd + vh * 0.36; // comes up sooner after the chart
    const uEnd = logoOff + logoH / 2 + (vh + L.inset) * 0.5; // centred in what's visible
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
  const pageH = $derived(Math.max(L.pageHeight, TG.G + TG.uEnd - L.P + innerH)); // ends with the logo at rest in what's visible
  const headIn = $derived(vh - u < vh * 0.84);
  const paraIn = $derived(vh - u + TG.paraOff < vh * 0.9);
  // Randy comes out of the shadows as the chart comes up: pitch black to dim, with the scroll
  const randyLit = $derived(clamp((vh * 0.95 - (vh - u + TG.chartOff)) / (vh * 0.55)));
  // the logo: its outline draws in as it rises into view, then it fills, then it lights up (DIGITAL pops
  // in, the blood starts to drip). Scrolling back reverses the draw and fill.
  const logoTop = $derived(vh - u + TG.logoOff);
  // where the page really ends: the document can only scroll to its height minus what the window shows,
  // which on a phone with browser bars is less than the large viewport the layout uses
  const uEndReal = $derived(pageH - innerH + L.P - TG.G);
  const logoRest = $derived(vh - uEndReal + TG.logoOff); // where its top comes to rest at the end of the page
  const logoQ = $derived(clamp((vh - logoTop) / Math.max(1, vh - logoRest))); // 0 entering .. 1 at rest
  const logoDraw = $derived(clamp(logoQ / 0.62));
  const logoFill = $derived(clamp((logoQ - 0.62) / 0.24));
  const logoLit = $derived(logoQ >= 0.88);
  // back to top: the whole story rewinds past (the browser's own smooth scroll stalls on a page this long,
  // then jumps). Your own wheel or touch takes over.
  function rewind() {
    const from = window.scrollY;
    if (reduced || from < 2) return void window.scrollTo(0, 0);
    const dur = clamp(900 + from / 14, 1200, 2600);
    const t0 = performance.now();
    let raf = 0;
    const stopIt = () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('wheel', stopIt);
      window.removeEventListener('touchstart', stopIt);
    };
    window.addEventListener('wheel', stopIt, { passive: true });
    window.addEventListener('touchstart', stopIt, { passive: true });
    const step = (now: number) => {
      const q = clamp((now - t0) / dur);
      const e = q < 0.5 ? 4 * q * q * q : 1 - Math.pow(-2 * q + 2, 3) / 2;
      window.scrollTo(0, from * (1 - e));
      if (q < 1) raf = requestAnimationFrame(step);
      else stopIt();
    };
    raf = requestAnimationFrame(step);
  }
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
    // the worst (Zaid, on the right) rises first, down to the best: you can see something's coming
    return grown ? back(clamp((t - (TGN - 1 - i) * 70) / 650)) : 1 - smooth(clamp((t - i * 18) / 320));
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
  // the bars take taps whenever the chart is actually on screen (a tall desktop window can show it well past
  // where a phone would have scrolled it away)
  const chartOnScreen = () => {
    const top = vh - u + TG.chartOff;
    return top + TG.chartH * 0.6 > 0 && top + TG.chartH * 0.4 < vh;
  };
  const tgReady = () => grown && chartOnScreen();
  function tgOpen(i: number) {
    if (tgFocus === i) return void (tgFocus = null); // tap the open bar again to close it
    if (!tgReady()) return;
    tgFocus = tgShown = i;
  }
  function tgSwipe(dx: number, ms: number) {
    drag = 0;
    if (tgFocus === null) return;
    const to = tgFocus + (dx < 0 ? 1 : -1);
    if ((Math.abs(dx) > 60 || Math.abs(dx) / Math.max(ms, 1) > 0.45) && to >= 0 && to < TGN) tgFocus = tgShown = to;
  }
  function stepTg() {
    if (tgFocus !== null && !chartOnScreen()) tgFocus = null; // scrolled the chart away: close
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
  // the league's median, a quiet line through the bars
  const tgMedian = (() => {
    const v = tgM.map((m) => m.total).sort((a, b) => a - b);
    const n = v.length;
    return n ? (n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2) : 0;
  })();
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
  // the title screen: the ghost ribbons are centred on the screen (they aren't the real ribbons, so they
  // don't need the gutter), and the title's letters are cut from a painted copy of them in full colour
  const ghostX0 = $derived((L.W - L.fieldW) / 2);
  const titleRibbons = $derived.by(() => {
    const stops: string[] = [];
    let at = 0;
    lineup[FIRST].forEach((p, slot) => {
      const a = slot * (L.cw + L.gap);
      const b = a + L.cw;
      stops.push(`transparent ${at}px ${a}px`, `${people[p].color} ${a}px ${b}px`);
      at = b;
    });
    stops.push(`transparent ${at}px`);
    return `linear-gradient(to right, ${stops.join(', ')})`;
  });
  // "Origins" is set a little bigger and letter-spaced out to exactly the width of "Bria Bowl", and each
  // line's ribbons are shifted so they line up with the ghost ribbons behind (the lines are centred, so
  // each starts somewhere different). Measured, since the widths depend on the font.
  function fitTitle(node: HTMLElement, x0: number) {
    let left0 = x0;
    const run = () => {
      const [a, b] = node.querySelectorAll('span');
      if (!a || !b) return;
      b.style.letterSpacing = '0px';
      b.style.marginRight = '0px';
      const w1 = a.getBoundingClientRect().width;
      const w2 = b.getBoundingClientRect().width;
      const n = (b.textContent ?? '').length;
      const ls = n > 1 ? (w1 - w2) / (n - 1) : 0;
      b.style.letterSpacing = `${ls}px`;
      b.style.marginRight = `${-ls}px`; // letter-spacing also follows the last letter: take it back
      for (const sp of [a, b]) sp.style.setProperty('--bx', `${left0 - sp.getBoundingClientRect().left}px`);
    };
    run();
    document.fonts?.ready.then(run);
    const ro = new ResizeObserver(run);
    ro.observe(node);
    return {
      update(x: number) {
        left0 = x;
        run();
      },
      destroy: () => ro.disconnect(),
    };
  }
  // the ghost ribbons: they tilt back and sink as you scroll the title away, then sit faint and blurred,
  // and their ends rise away just before the founders land in 2009
  const ghostR = $derived(smooth(clamp(s / (vh * 0.7))));
  const ghostTf = $derived(
    ghostR > 0 ? `perspective(${Math.round(vh)}px) translate3d(0,${(ghostR * vh * 0.1).toFixed(1)}px,${(-ghostR * vh * 0.55).toFixed(1)}px) rotateX(${(ghostR * 24).toFixed(2)}deg)` : null,
  );
  const ghostBlur = $derived(ghostR * 7);
  const firstLand = $derived(Math.min(...Object.values(L.appearAt)) - vh * LAND);
  const ghostEndT = $derived(clamp((w - (firstLand - vh * 0.85)) / (vh * 0.8)));
  const ghostEnd = $derived(lerp(vh + 120, -60, smooth(ghostEndT)));
  const ghostO = $derived(lerp(1, 0.2, ghostR) * (ghostEndT >= 1 ? 0 : 1));
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

<!-- the platinum the undefeated star is made of -->
<svg class="defs" width="0" height="0" aria-hidden="true">
  <defs>
    <linearGradient id="patchgold" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#9c7014" /><stop offset="0.5" stop-color="#c39222" /><stop offset="1" stop-color="#9c7014" />
    </linearGradient>
    <linearGradient id="patchsheen" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0.25" stop-color="#fff" stop-opacity="0" /><stop offset="0.42" stop-color="#fff" stop-opacity="0.22" /><stop offset="0.55" stop-color="#fff" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="patchplat" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a9b3be" /><stop offset="0.5" stop-color="#e9eef3" /><stop offset="1" stop-color="#a9b3be" />
    </linearGradient>
    <linearGradient id="platfoil" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#8d96a0" /><stop offset="0.3" stop-color="#ffffff" /><stop offset="0.5" stop-color="#b9c2cc" />
      <stop offset="0.68" stop-color="#ffffff" /><stop offset="1" stop-color="#7d8792" />
    </linearGradient>
  </defs>
</svg>

<!-- every card, measured off-screen at its real width, so the timeline can make room for it -->
<div class="measure" inert aria-hidden="true" style:width="{L.trayW}px">
  {#each cards as c, i (i)}
    <div use:measureCard={i}><Glass pad="16px 20px 18px"><CardView card={c} {onperson} /></Glass></div>
  {/each}
</div>

<div class="stage" class:reduced class:veiled style:height="{vh}px" style:touch-action={focus !== null || tgFocus !== null ? 'pan-y' : null}>
  <!-- columns: nothing is ever drawn over these except their own markers -->
  <div
    class="field"
    style:--fade="{(L.headerY * 2 + 26) * (1 - avFade)}px"
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
        style:--chev={Math.min(1, c.chev * 4)}
        style:--ccut="{c.ccut}px"
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
        {#if c.gold > 0}<i class="edge gold" style:--cut="{c.gcut}px"></i>{/if}
        {#if c.plat > 0}<i class="edge plat" style:--cut="{c.pcut}px"></i>{/if}
      </button>
    {/each}
    {#each field.rolls as r (r.key)}
      {@const rh = Math.max(12, r.w * 0.8)}
      <i
        class="roll"
        style:--tone={r.tone}
        style:--spin="{(r.spin * 0.6).toFixed(1)}px"
        style:width="{r.w + 3}px"
        style:height="{rh}px"
        style:filter={r.dark < 1 ? `brightness(${lerp(0.5, 1, r.dark).toFixed(2)})` : null}
        style:transform="translate3d({r.x - 1.5}px,{r.y - rh * 0.55}px,0)"
      ></i>
    {/each}
    {#each field.tails as t (t.key)}
      <i
        class="tail"
        class:founder={t.founder}
        class:chev={t.chev > 0}
        class:chev2={t.chev2 > 0.5}
        style:--chev={Math.min(1, t.chev * 4)}
        style:--ccut="{t.ccut}px"
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
        {#if t.gold > 0}<i class="edge gold" style:--cut="{t.gcut}px"></i>{/if}
        {#if t.plat > 0}<i class="edge plat" style:--cut="{t.pcut}px"></i>{/if}
      </i>
    {/each}
    {#each glitz as gz (gz.key)}
      <span class="ripple" style:width="{gz.w}px" style:transform="translate3d({gz.x}px,{gz.y - 70}px,0)"></span>
    {/each}
    {#if ribbonEnd - s - endFade < vh + 10}
      <i class="rend" style:width="{L.fieldW + 8}px" style:height="{endFade + 2}px" style:transform="translate3d({L.padL - 4}px,{ribbonEnd - s - endFade}px,0)"></i>
    {/if}
    <!-- the ribbons falling away at the bottom -->
    <i class="floorshade" style:width="{W}px" style:transform="translate3d(0,{vh - 110}px,0)"></i>
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
      <!-- a result patch, stitched onto the ribbon -->
      <span
        class="mark"
        class:champ={m.kind === 'champ' && !m.star}
        class:brown={m.kind === 'sacko' || m.star}
        class:silver={m.kind === 'silver'}
        style:--reveal="{(100 - m.reveal * 100).toFixed(1)}%"
        style:opacity={m.o}
        title="{m.text}: {people[m.person].name}"
        style:transform="translate3d({m.x}px,{m.y}px,0) translate(-50%,-100%)"
      >
        <svg width={m.bw} height={m.bh} viewBox="0 0 {m.bw} {m.bh}" aria-hidden="true">
          <rect class="base" width={m.bw} height={m.bh} rx="2" />
          {#if m.kind === 'champ' && !m.star}<rect width={m.bw} height={m.bh} rx="2" fill="url(#patchsheen)" />{/if}
          <rect class="stitch" x="2" y="2" width={m.bw - 4} height={m.bh - 4} rx="1" />
          <text
            class="ptext"
            transform="translate({m.bw / 2},{m.pad + m.len / 2}) rotate(90)"
            text-anchor="middle"
            dominant-baseline="central"
            font-size={markFs}
            textLength={m.len}
            lengthAdjust="spacing">{m.text}</text>
          {#if m.sub}
            <text
              class="ptext psub"
              transform="translate({m.bw / 2},{m.pad + m.len + markFs * 0.45 + m.subLen / 2}) rotate(90)"
              text-anchor="middle"
              dominant-baseline="central"
              font-size={m.subFs}
              textLength={m.subLen}
              lengthAdjust="spacing">{m.sub}</text>
          {/if}
        </svg>
      </span>
    {/each}
  </div>


  <!-- story cards, in the timeline (under the header and avatars) -->
  {#if fz < 0.99}
    {#each anchored as c (c.i)}
      <div
        class="acard"
        style:width="{L.trayW}px"
        style:--o={c.o * (1 - fz) * (1 - c.f.e * 0.75)}
        style:--fb="{(c.f.e * 6).toFixed(2)}px"
        style:--fs={1 - c.f.e * 0.9}
        style:pointer-events={fz > 0.5 || c.o < 0.6 ? 'none' : null}
        style:transform="translate3d({(L.cardX + c.f.x).toFixed(1)}px,{c.y.toFixed(1)}px,0) rotate({c.f.rot.toFixed(2)}deg) scale({(1 - c.f.e * 0.3).toFixed(3)})"
      >
        <Glass pad="16px 20px 18px"><CardView card={c.r.card} {onperson} /></Glass>
      </div>
    {/each}
  {/if}

  <!-- photos, in a stack under their card -->
  {#if photos.list.length && fz < 0.99}
    <div class="photos" class:zooming={zoomKey !== null} style:opacity={1 - fz}>
      <button class="pscrim" class:on={zoomKey !== null} aria-label="Put the photo back" tabindex={zoomKey ? 0 : -1} onclick={() => zoomPhoto(null)}></button>
      {#each photos.list as ph (ph.key)}
        {@const big = ph.key === zoomKey}
        {@const zs = Math.min((W - 28) / photos.pw, (vh - L.inset - 110) / photos.ph, 3.2)}
        <button
          class="photo"
          class:big
          class:moving={zoomMove}
          aria-label={big ? `Put back: ${ph.p.alt}` : `Photo: ${ph.p.alt}`}
          aria-expanded={big}
          style:width="{photos.pw}px"
          style:height="{photos.ph}px"
          style:z-index={big ? 50 : ph.z}
          style:opacity={big ? 1 : ph.o}
          style:filter={!big && ph.e > 0.01 ? `blur(${(ph.e * 6).toFixed(2)}px) saturate(${(1 - ph.e * 0.9).toFixed(2)})` : null}
          style:transform={big
            ? `translate3d(${W / 2 - photos.pw / 2}px,${(vh - L.inset) / 2 - photos.ph / 2}px,0) rotate(0deg) scale(${zs})`
            : `translate3d(${ph.x - photos.pw / 2}px,${ph.y - photos.ph / 2}px,0) rotate(${ph.rot}deg) scale(${ph.sc})`}
          onclick={() => zoomPhoto(ph.key)}
        ><img src={import.meta.env.BASE_URL + ph.p.src} alt={big ? ph.p.alt : ''} decoding="async" /></button>
      {/each}
    </div>
  {/if}

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
          <!-- Return, burnt into the ribbon just under the card (drawn beneath the glass, so it can back up under it) -->
          <button
            class="ret"
            class:back={backing === pn.key}
            style:--tone={people[pn.person].color}
            style:opacity={pc.k === shown ? fz : 0}
            style:pointer-events={pc.k === focus && fz > 0.6 ? 'auto' : 'none'}
            style:width="{PW}px"
            style:transform="translate3d({pc.pull.x - pc.g.x}px,{pn.y + pn.h + 6}px,0)"
            onclick={() => goBack(pn.key, () => (focus = null))}
          >Return</button>
          <div
            class="panel"
            style:pointer-events={pc.k === focus && fz > 0.6 ? 'auto' : 'none'}
            style:width="{PW}px"
            style:height="{Math.max(0, pn.h)}px"
            style:--pv="{clamp(-v * 1.6, -16, 16)}px"
            style:transform="translate3d({pc.pull.x - pc.g.x}px,{pn.y}px,0) skewX({clamp(-v * 0.35, -4, 4)}deg) scale({lerp(0.94, 1, pc.k === shown ? fz : 1)})"
          >
            <Glass full pad="0">
              <div class="pbody" use:natural={pn.key}>
                <div class="top">
                  <div class="who">
                    <Avatar id={pn.person} size={L.desktop ? 52 : 40} />
                    <span><b class="display">{people[pn.person].name}</b><small>{#if people[pn.person].nickname}“{people[pn.person].nickname}”{' · '}{/if}{statusOf(pn.person)}</small></span>
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
  {/if}

  <!-- finale -->
  {#if finaleCy < vh * 1.4 && fz < 0.5}
    <div class="cardwrap finale" style:width="{Math.min(L.trayW, 440)}px" style:--o={clamp((vh - finaleCy) / (vh * 0.25))} style:transform="translate3d({L.padL + (L.fieldW - Math.min(L.trayW, 440)) / 2}px,calc({finaleCy}px - 50%),0)">
      <Glass pad="18px 18px 16px"><article class="fin">
        <h3 class="display">The Legacy Rankings</h3>
        <ol>
          {#each legacy.rankings as r}
            <li>
              <button class="pressable" onclick={() => onperson(r.person)}>
                <span class="rk">{r.rank}</span><Avatar id={r.person} size={26} /><b>{first(r.person)}</b><span class="pts" style:color={rankHeat(r.points)}>{r.points}</span>
              </button>
            </li>
          {/each}
        </ol>
        <p class="fine">Mike's rankings, through week {legacy.asOf.last_scored_week} of {legacy.asOf.season}.</p>
      </article></Glass>
    </div>
  {/if}

  <!-- Tegridy Factor: the last word -->
  {#if uT > -60 && uT < TR.len + vh + 200}
    <section class="tree" aria-label="Family tree" style:width="{W}px" style:height="{TR.end + 20}px" style:transform="translate3d(0,{(vh - uT).toFixed(1)}px,0)">
      <OriginTree T={TR} u={uT} {vh} inset={L.inset} desktop={L.desktop} {onperson} />
    </section>
  {/if}

  {#if tgOn}
    <section class="tg" aria-label="Tegridy Factor" style:width="{W}px" style:height="{TG.uEnd}px" style:transform="translate3d(0,{(vh - u).toFixed(1)}px,0)">
      <h2 class="tghead display" class:in={headIn} bind:clientHeight={headH} style:left="{TG.x0}px" style:font-size="calc({L.desktop ? 104 : 64}px * var(--display-scale))">
        Tegridy{#if L.desktop}{' '}{:else}<br />{/if}Facto<span class="r">r<img class="sticker" src="{import.meta.env.BASE_URL}tegridy/sticker.png" alt="An “I got tegridy” sticker" draggable="false" /></span>
      </h2>
      <div class="tgpara" class:in={paraIn} bind:clientHeight={paraH} style:left="{TG.x0}px" style:width="{TG.chartW}px" style:top="{TG.paraOff}px">
        <p class="lede">Every time a member acts without tegridy, they get penalized. Golf scoring with data from Sleeper only.</p>
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
      <!-- Randy, dark, looming over the scores from the left -->
      <img
        class="randy"
        src="{import.meta.env.BASE_URL}tegridy/randy.png"
        alt=""
        aria-hidden="true"
        draggable="false"
        style:height="{TG.chartH * 0.8}px"
        style:left="{TG.x0 - 6}px"
        style:top="{TG.base - TG.chartH * 0.8}px"
        style:opacity={(1 - tfz) * 0.9}
        style:filter="brightness({(0.32 * randyLit).toFixed(3)}) contrast(1.15) drop-shadow(0 0 30px rgba(0, 0, 0, 0.6))"
      />
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
          aria-label="{p.name}: Tegridy Factor {b.m.total}"
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
            aria-label="Open {p.name}'s Tegridy breakdown"
            tabindex={tgReady() ? 0 : -1}
            style:opacity={(1 - tfz) * clamp(b.gr * 3)}
            style:pointer-events={tfz > 0.5 ? 'none' : null}
            style:transform="translate3d({cx - TG.av / 2}px,{b.down ? b.end + 20 : b.end - 21 - TG.av}px,0)"
            onclick={() => tgOpen(b.i)}
          ><Avatar id={b.m.person} size={TG.av} /></button>
        {/if}
      {/each}
      <!-- the median: a quiet line through every bar, labelled at its left end -->
      <span
        class="tgmed"
        style:left="{TG.x0}px"
        style:width="{TG.chartW}px"
        style:top="{TG.base - tgMedian * TG.unit}px"
        style:opacity={growOf(0) > 0.6 ? 1 - tfz : 0}
      ><b>Median {fmtTF(tgMedian)}</b></span>
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
            <button
              class="ret"
              class:back={backing === b.m.person}
              style:--tone={people[b.m.person].color}
              style:opacity={b.g.r}
              style:pointer-events={b.i === tgFocus && tfz > 0.6 ? 'auto' : 'none'}
              style:width="{tgPW}px"
              style:transform="translate3d({(b.g.w - tgPW) / 2}px,{TG.chartH - RET + 2}px,0)"
              onclick={() => goBack(b.m.person, () => (tgFocus = null))}
            >Return</button>
            <div
              class="panel"
              style:pointer-events={b.i === tgFocus && tfz > 0.6 ? 'auto' : 'none'}
              style:width="{tgPW}px"
              style:height="{TG.chartH - 16 - RET}px"
              style:transform="translate3d({(b.g.w - tgPW) / 2}px,8px,0) scale({lerp(0.94, 1, b.g.r)})"
            >
              <Glass full pad="0">
                <div class="pbody">
                  <div class="top">
                    <div class="who">
                      <Avatar id={m.person} size={L.desktop ? 52 : 40} />
                      <span><b class="display">{people[m.person].name}</b><small>Tegridy rank {m.rank} of {TGN}</small></span>
                    </div>
                    <div class="yr display" style:color={tfHeat(m.total)}><Roll value={fmtTF(m.total)} /></div>
                    <p class="tally">
                      {#if m.penalties.length}{m.penalties.length} penalt{m.penalties.length > 1 ? 'ies' : 'y'} · {m.cleanSeasons.length} clean season{m.cleanSeasons.length === 1 ? '' : 's'}{:else}Not one penalty since 2019. A clean sheet.{/if}
                    </p>
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

      <!-- the end: everything falls away to black, the Hodag logo draws itself in, fills, and bleeds onto DIGITAL -->
      <i class="tgblack" style:width="{W}px" style:top="{TG.blackOff}px" style:height="{TG.uEnd - TG.blackOff + vh}px" style:--fall="{Math.round(vh * 0.28)}px"></i>
      <div class="hodag" style:left="{(W - TG.logoW) / 2}px" style:top="{TG.logoOff}px" style:width="{TG.logoW}px" style:height="{TG.logoH}px">
        <HodagLogo draw={logoDraw} fill={logoFill} lit={logoLit} {reduced} />
      </div>
      <!-- and once it's lit, a way back to the start -->
      <button
        class="totop"
        class:on={logoLit}
        tabindex={logoLit ? 0 : -1}
        style:top="{TG.logoOff + TG.logoH + 30}px"
        onclick={rewind}
      >
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" /></svg>
        Back to top
      </button>
      <footer class="foot" style:width="{W}px" style:top="{uEndReal + innerH - vh - 86}px">
        <p>© {new Date().getFullYear()} Hodag Digital. All rights reserved.</p>
        <p>The Quest to the Bria Bowl: its stories, design, artwork and code are original work. Reproduction or redistribution without permission is prohibited.</p>
      </footer>
    </section>
  {/if}

  <!-- the title screen's ribbons: the twelve founders, drained of colour, filling the screen. Scrolling,
       they tilt back and sink into the screen, blurring, a faint ghost until 2009, when their ends rise away -->
  {#if ghostO > 0.005}
    <div
      class="ghosts"
      style:opacity={ghostO}
      style:transform={ghostTf}
      style:filter={ghostBlur > 0.05 ? `blur(${ghostBlur.toFixed(1)}px)` : null}
      style:--end="{ghostEnd.toFixed(0)}px"
      style:--cw="{L.cw}px"
    >
      {#each lineup[FIRST] as p, slot (p)}
        <i
          class="col ghost"
          class:founder={!!people[p].founder}
          style:--tone={people[p].color}
          style:--g="1"
          style:--py="0px"
          style:--lit="99999px"
          style:width="{L.cw}px"
          style:height="{vh + 80}px"
          style:transform="translate3d({ghostX0 + slot * (L.cw + L.gap) + (sway(slot) * (1 - ghostR) + idleSway(slot))}px,-40px,0)"
        ></i>
      {/each}
    </div>
  {/if}

  <!-- intro -->
  {#if introO > 0}
    <div class="intro" style:opacity={introO} style:transform="translate3d(0,{-s * 0.35}px,0)">
      <!-- the title is the founders' ribbons in full colour, bunched up into letters (a painted copy of the
           columns behind, lined up with them, clipped to the type) -->
      <h1 class="display title" style:--ribbons={titleRibbons} style:--rw="{L.fieldW}px" use:fitTitle={ghostX0}><span>Bria Bowl</span><span class="origins">Origins</span></h1>
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
        style:--win-tone={h?.winSilver ? '#f2f7ff' : 'var(--gold)'}        style:--gray={fanned && ip !== undefined ? 0.35 : grayOf(a.st)}
        style:--tone={people[a.p].color}
        style:--av="{L.av}px"
        style:--i={ip ?? 0}
        style:--j={pileCount - 1 - (ip ?? 0)}
        style:transform="translate3d({v.x - L.av / 2 + (h?.shake ?? 0)}px,{v.y - L.av / 2}px,0) rotate({v.rot}deg) scale({v.scale * (1 + (h?.win ?? 0) * 0.24)})"
        onclick={() => tapAvatar(a)}
      >
        <Avatar id={a.p} size={L.av} live />
        {#if platBurst[a.p]}
          <!-- an undefeated season landing: a platinum shockwave and sparkles flying out, on the clock -->
          {#key platBurst[a.p]}
            <span class="pburst" aria-hidden="true">
              <i class="pring"></i>
              {#each { length: 12 } as _, k (k)}
                <i class="pspark" style:--a="{k * 30 + (k % 2) * 11}deg" style:--d="{L.av * (0.95 + (k % 3) * 0.28)}px" style:--s={0.7 + (k % 4) * 0.22} style:--t="{(k % 3) * 70}ms"></i>
              {/each}
            </span>
          {/key}
        {/if}
        {#if h?.stars.length}
          <span class="stars" aria-label={h.stars.map((x) => `${x.n} ${x.kind === 'gold' ? (x.n > 1 ? 'titles' : 'title') : x.n > 1 ? 'undefeated seasons' : 'undefeated season'}`).join(', ')}>
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

</div>

<style>
  .spacer {
    width: 1px;
  }
  .defs {
    position: absolute;
    width: 0;
    height: 0;
  }
  .measure {
    position: absolute;
    top: 0;
    left: -10000px;
    visibility: hidden;
    pointer-events: none;
  }
  .acard :global(.body) {
    /* flicked away: the words blur and lose their colour as it goes (the glass itself fades: a filter
       on the card would switch its frosting off) */
    filter: blur(var(--fb, 0px)) saturate(var(--fs, 1));
  }
  .acard {
    z-index: 12; /* above the avatars (10), under the scrubber (26): thrown off the side before the avatars */
    will-change: transform; /* not opacity: it would switch the glass off (Glass fades via --o) */
    /* heavier, darker glass than elsewhere: the ribbons behind stay a soft blur of colour */
    /* the tint alone has to keep the text readable: browsers without graphics acceleration don't draw
       the blur at all (Levi's Edge and Firefox), so it can't lean on the blur's darkening */
    --glass-tint: rgba(10, 12, 17, 0.68);
    --glass-filter: blur(34px) saturate(1.6) brightness(0.85);
  }
  .stage {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    transition: filter 1000ms cubic-bezier(0.4, 0, 0.2, 1);
    overflow: clip; /* not hidden: a hidden box can still be scrolled sideways by focus or scrollIntoView */
    contain: strict;
    background:
      radial-gradient(120% 70% at 20% 0%, color-mix(in srgb, var(--bg-2) 85%, transparent), transparent 70%),
      var(--bg);
  }
  .stage.veiled {
    filter: blur(28px) saturate(0.6) brightness(0.8);
  }
  .stage > * {
    position: absolute;
    top: 0;
    left: 0;
    will-change: transform, opacity;
  }
  /* anything holding glass must not hint opacity: that makes it a backdrop root and switches the
     frosting off (this outranks the line above, which otherwise wins on specificity) */
  .stage > .acard,
  .stage > .cardwrap,
  .stage > .tg {
    will-change: transform;
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
  .roll {
    /* the rolled-up end of a founder's ribbon as it pours down: a little cylinder of the ribbon, shaded
       round, its ridges turning as it unrolls */
    border-radius: 4px;
    pointer-events: none;
    background:
      repeating-linear-gradient(to bottom, rgba(0, 0, 0, 0.16) 0 1px, transparent 1px 4px) 0 var(--spin) / 100% 4px,
      linear-gradient(
        to bottom,
        color-mix(in srgb, var(--tone) 45%, #000) 0%,
        var(--tone) 30%,
        color-mix(in srgb, var(--tone) 65%, #fff) 52%,
        var(--tone) 72%,
        color-mix(in srgb, var(--tone) 40%, #000) 100%
      );
    box-shadow:
      0 5px 8px -2px rgba(0, 0, 0, 0.55),
      0 1px 0 rgba(0, 0, 0, 0.4);
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
    clip-path: inset(0 0 var(--cut, 0px) 0); /* grows down the ribbon as it's earned */
  }
  /* the trim going on: a single ripple running down the ribbon, like a tablecloth snapped down. A soft
     white glow at its crest, the ribbon shadowed in the troughs either side of it */
  .ripple {
    height: 140px;
    pointer-events: none;
    background: linear-gradient(
      to bottom,
      transparent 0,
      rgba(0, 0, 0, 0.3) 30%,
      rgba(0, 0, 0, 0.08) 44%,
      rgba(255, 255, 255, 0.55) 50%,
      rgba(0, 0, 0, 0.08) 56%,
      rgba(0, 0, 0, 0.32) 72%,
      transparent 100%
    );
  }
  .ripple::after {
    content: '';
    position: absolute;
    left: -4px;
    right: -4px;
    top: 50%;
    height: 22px;
    margin-top: -11px;
    background: radial-gradient(ellipse 60% 50% at 50% 50%, rgba(255, 255, 255, 0.95), rgba(255, 250, 235, 0.35) 55%, transparent 75%);
    filter: blur(2px);
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
       off the edges so they don't run into the foil; a fourth doubles them. They're the same foil as
       the gold edges (cut to chevron shapes), so they catch the light the same way, and they grow
       down the ribbon like the edges do */
    content: '';
    position: absolute;
    inset: 0 5px;
    background: var(--foil-gold);
    background-size: 100% 96px;
    background-position: 0 var(--py);
    -webkit-mask-image: var(--chevrons);
    mask-image: var(--chevrons);
    /* one ribbon's width per chevron, so an expanded column repeats them instead of stretching */
    -webkit-mask-size: calc(var(--cw) - 10px) calc(var(--cw) * 0.8);
    mask-size: calc(var(--cw) - 10px) calc(var(--cw) * 0.8);
    -webkit-mask-position: 50% var(--py);
    mask-position: 50% var(--py);
    clip-path: inset(0 0 var(--ccut, 0px) 0);
    opacity: calc(var(--chev) * 0.9);
    pointer-events: none;
  }
  .col.chev2::after,
  .tail.chev2::after {
    -webkit-mask-image: var(--chevrons2);
    mask-image: var(--chevrons2);
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
    /* under the line: everything below a year line is that year */
    position: absolute;
    top: 1px;
    padding: 0 3px 1px;
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
  .runner svg {
    color: #e3e8ee;
  }
  .silver svg {
    color: #f4f8ff;
    filter: drop-shadow(0 0 4px rgba(225, 236, 255, 0.9));
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

  /* Tegridy Factor */
  .tree {
    z-index: 20;
  }
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
    top: calc(-0.5em + 13px); /* sits a little lower, covering less of the word */
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
    /* not the intro's lede: no 30ch cap, full width, white */
    max-width: none;
    color: #fff;
    margin: 0 0 12px;
    font-size: 14px;
    line-height: 1.45;
  }
  .rules {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); /* fit: the cells stretch across the whole width */
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
  .rend {
    /* the ribbons' end, running on into the dark */
    pointer-events: none;
    background: linear-gradient(to bottom, transparent, color-mix(in srgb, var(--bg) 70%, transparent) 55%, var(--bg));
  }
  .randy {
    /* desaturated, in the shadows, staring down at the scores (his light comes up with the scroll) */
    max-width: none;
    width: auto;
    pointer-events: none;
    user-select: none;
  }
  .tg > .tgmed {
    height: 0;
    border-top: 1px dashed rgba(255, 255, 255, 0.55);
    pointer-events: none;
    transition: opacity 500ms ease;
  }
  .tgmed b {
    position: absolute;
    left: 0; /* over the short bars on the left, clear of the tall ones */
    bottom: 3px;
    padding: 1px 5px;
    background: rgba(8, 9, 12, 0.7);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #fff;
    white-space: nowrap;
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
  }
  /* Return: burnt into the ribbon, a dark shade of its own colour with a lit lower lip, like a brand */
  .ret {
    position: absolute;
    top: 0;
    left: 0;
    height: 44px;
    display: grid;
    place-items: center;
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-weight: var(--display-weight);
    font-size: calc(18px * var(--display-scale));
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--tone) 40%, #000);
    text-shadow:
      0 1px 0 color-mix(in srgb, var(--tone) 72%, #fff 28%),
      0 0 7px color-mix(in srgb, var(--tone) 50%, #000);
    transition:
      translate 420ms cubic-bezier(0.5, 0, 0.25, 1),
      scale 420ms cubic-bezier(0.5, 0, 0.25, 1);
  }
  .ret:active {
    scale: 0.96;
  }
  .ret.back {
    /* backs up under the glass card */
    translate: 0 -64px;
    scale: 0.9;
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
  /* the logo at the end, and the footer under it */
  .tg > .hodag {
    pointer-events: none;
  }
  .tg > .totop {
    left: 50%;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 42px;
    padding: 0 18px 0 14px;
    border-radius: 2px;
    background: var(--glass-tint);
    backdrop-filter: var(--glass-filter);
    -webkit-backdrop-filter: var(--glass-filter);
    box-shadow: var(--glass-rim), var(--glass-lift);
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-weight: var(--display-weight);
    font-size: calc(15px * var(--display-scale));
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #fff;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transform: translate(-50%, 10px);
    transition:
      opacity 500ms var(--ease-out) 600ms,
      transform 500ms var(--ease-out) 600ms;
  }
  .tg > .totop.on {
    opacity: 1;
    pointer-events: auto;
    transform: translate(-50%, 0);
  }
  .tg > .totop:active {
    transform: translate(-50%, 0) scale(0.97);
    transition-delay: 0ms;
  }
  .totop svg {
    width: 14px;
    height: 14px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .tg > .foot {
    pointer-events: auto;
    padding: 0 16px calc(28px + var(--safe-bottom));
    text-align: center;
    font-size: 11px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.42);
  }
  .foot p {
    margin: 0;
  }
  .foot p + p {
    margin-top: 2px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.3);
  }

  /* photos */
  .photos {
    inset: 0;
    z-index: 12; /* with the cards: above the avatars, thrown off before they reach them */
    pointer-events: none;
  }
  .photos.zooming {
    z-index: 70; /* a photo blown up sits over everything */
  }
  .pscrim {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
    background: rgba(5, 6, 9, 0.74);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    opacity: 0;
    pointer-events: none;
    cursor: zoom-out;
    transition: opacity 320ms ease;
  }
  .pscrim.on {
    opacity: 1;
    pointer-events: auto;
  }
  .photo.moving {
    /* only while it lifts out or goes back: otherwise it tracks the scroll exactly */
    transition: transform 560ms cubic-bezier(0.2, 1.05, 0.3, 1);
  }
  .photo.big {
    cursor: zoom-out;
    box-shadow:
      0 30px 70px -10px rgba(0, 0, 0, 0.85),
      0 4px 12px rgba(0, 0, 0, 0.5);
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
  /* season results: a patch stitched onto the ribbon, the word printed down it */
  .mark {
    position: absolute;
    line-height: 0;
    pointer-events: none;
    /* written onto the ribbon from the top down as it comes on screen */
    clip-path: inset(-2px -2px var(--reveal, 0%) -2px);
    filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.32)); /* sewn on: just a whisker of lift */
  }
  .mark svg {
    display: block;
    overflow: visible;
  }
  .ptext {
    font-family: var(--font-display);
    font-weight: var(--display-weight);
  }
  .psub {
    font-family: var(--font-text);
    font-weight: 600;
  }
  .stitch {
    fill: none;
    stroke-width: 0.8;
    stroke-dasharray: 2.2 1.5;
    stroke-linecap: round;
  }
  /* champion: gold, a light sheen, white lettering */
  .mark.champ .base {
    fill: url(#patchgold);
  }
  .mark.champ .stitch {
    stroke: #f6dc8c;
  }
  .mark.champ .ptext {
    fill: #fff;
  }
  /* sacko (and 2014's champion*): brown, no sheen, light brown lettering */
  .mark.brown .base {
    fill: #5b3b24;
  }
  .mark.brown .stitch {
    stroke: #9a6c47;
  }
  .mark.brown .ptext {
    fill: #d8b48c;
  }
  /* undefeated: platinum, dark lettering */
  .mark.silver .base {
    fill: url(#patchplat);
  }
  .mark.silver .stitch {
    stroke: #ffffff;
  }
  .mark.silver .ptext {
    fill: #26303b;
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
    align-items: center;
    text-align: center;
    padding: 0 16px calc(8vh + var(--safe-bottom));
    pointer-events: none;
  }
  h1 {
    margin: 0;
    font-size: calc(clamp(46px, 13.5vw, 104px) * var(--display-scale));
    line-height: 0.92;
  }
  /* the title: the founders' ribbons in full colour, bunched up into the letters. Layers, top to bottom:
     a soft light from above, the folds of the bunched fabric, the founders' faint lattice, the ribbons */
  .title span {
    display: block;
    width: max-content;
    background:
      linear-gradient(to bottom, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0) 40%, rgba(0, 0, 0, 0.12)),
      repeating-linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 0, rgba(255, 255, 255, 0.1) 0.09em, rgba(0, 0, 0, 0.1) 0.18em),
      var(--ribbons);
    background-size: auto, auto, var(--rw) 100%;
    background-position: 0 0, 0 0, var(--bx, 0px) 0;
    background-repeat: repeat, repeat, no-repeat;
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    filter: saturate(1.25) drop-shadow(0 6px 16px rgba(0, 0, 0, 0.7)) drop-shadow(0 1px 0 rgba(0, 0, 0, 0.6));
  }
  .title {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .title .origins {
    font-size: 1.16em;
  }
  /* the ghost ribbons behind the title */
  .ghosts {
    inset: 0;
    z-index: 1;
    pointer-events: none;
    transform-origin: 50% 0;
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(var(--end) - 140px), transparent var(--end));
    mask-image: linear-gradient(to bottom, #000 calc(var(--end) - 140px), transparent var(--end));
  }
  .ghosts > .ghost {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
    filter: saturate(0.1) brightness(0.36); /* drained and dark: the title's colour is the only colour */
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
    left: 50%;
    transform: translateX(-50%);
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
  /* the undefeated star: platinum, mirrored, and it keeps catching the light */
  .stars svg.silver {
    width: 11px;
    height: 11px;
    left: -5.5px;
    top: -1px;
    fill: url(#platfoil);
    animation: plat-star 2.6s ease-in-out infinite;
  }
  @keyframes plat-star {
    0%,
    100% {
      filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9)) drop-shadow(0 0 3px rgba(225, 236, 255, 0.6));
    }
    50% {
      filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.9)) drop-shadow(0 0 7px rgba(240, 247, 255, 1)) drop-shadow(0 0 14px rgba(190, 215, 255, 0.55));
    }
  }
  /* an undefeated season landing: a platinum shockwave ring and sparkles flying out */
  .pburst {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 0;
    height: 0;
    pointer-events: none;
  }
  .pring {
    position: absolute;
    left: calc(var(--av, 30px) * -0.5);
    top: calc(var(--av, 30px) * -0.5);
    width: var(--av, 30px);
    height: var(--av, 30px);
    border-radius: 50%;
    border: 2px solid #f4f8ff;
    box-shadow:
      0 0 12px rgba(235, 244, 255, 0.9),
      inset 0 0 8px rgba(235, 244, 255, 0.7);
    animation: pring 1100ms cubic-bezier(0.15, 0.7, 0.3, 1) forwards;
  }
  @keyframes pring {
    0% {
      transform: scale(0.5);
      opacity: 1;
    }
    100% {
      transform: scale(3.2);
      opacity: 0;
      border-width: 0.5px;
    }
  }
  .pspark {
    position: absolute;
    left: -4px;
    top: -4px;
    width: 8px;
    height: 8px;
    background: conic-gradient(from 0deg, transparent 0 40deg, #fff 45deg, transparent 50deg 130deg, #fff 135deg, transparent 140deg 220deg, #fff 225deg, transparent 230deg 310deg, #fff 315deg, transparent 320deg);
    -webkit-mask: radial-gradient(circle, #000 0 25%, transparent 70%);
    mask: radial-gradient(circle, #000 0 25%, transparent 70%);
    filter: drop-shadow(0 0 4px rgba(235, 244, 255, 1));
    opacity: 0;
    animation: pspark 1500ms cubic-bezier(0.15, 0.75, 0.3, 1) var(--t) forwards;
  }
  @keyframes pspark {
    0% {
      opacity: 1;
      transform: rotate(var(--a)) translateX(0) scale(0.3);
    }
    35% {
      opacity: 1;
    }
    100% {
      opacity: 0;
      transform: rotate(var(--a)) translateX(var(--d)) scale(var(--s)) rotate(180deg);
    }
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
