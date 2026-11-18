<script lang="ts">
  // The year scrubber: a rail of tick marks down the right edge, melting into the alumni pile at
  // the top and the bottom of the screen.
  // - tap: jump to that year;
  // - hold (0.2s): the rail bulges out under the finger, quarter-year ticks appear inside the
  //   bulge, and dragging scrubs finely (4x the travel per year). Let go: it settles on a quarter;
  // - moving before the hold kicks in does nothing (the rail never pans the page, so the browser
  //   and the scrubber never fight over the finger).
  // While the scrubber is in charge it draws its own value, not the (smoothed, lagging) scroll, so
  // it never fights itself; it hands back to the scroll once the two agree.
  import { onMount } from 'svelte';
  import { wAtStop, clamp, easeOut, type Layout } from '../lib/model';

  // `onpreview`: while a hold is in progress the page scroll is left alone entirely (on iPhone,
  // scrolling the page under a finger that's down fights the browser); the story draws this
  // playhead instead. Letting go commits it to the real scroll position.
  let {
    L, fi, opacity = 1, reduced = false, onpreview,
  }: { L: Layout; fi: number; opacity?: number; reduced?: boolean; onpreview: (w: number | null) => void } = $props();

  const HOLD_MS = 200;
  const SLOP = 8;
  const FINE = 4; // the bulge magnifies this much; also quarters per year
  const R = 92; // reach of the bulge, px either side of the finger
  const SWELL = 16; // how far the rail swells out to the left

  const n = $derived(L.stops.length);
  const CW = $derived(L.right); // the strip we own: the gutter at the right of the centred container
  const H = $derived(L.scrub.bottom - L.scrub.top);
  const gap = $derived(H / n); // px per year on the flat rail
  const railX = $derived(CW - (L.desktop ? 26 : 14));

  let f = $state(0); // our own value, in fractional stops
  let driving = $state(false);
  let b = $state(0); // 0 flat … 1 bulging (animated)
  let fy = $state(0); // the finger, in rail coordinates
  let scrubbing = $state(false);

  const shown = $derived(driving ? f : fi);
  const cur = $derived(clamp(Math.floor(shown), 0, n - 1));
  const yOf = (v: number) => (v + 0.5) * gap; // a value's place on the flat rail
  const fAt = (y: number) => clamp(y / gap - 0.5, 0, n - 1);

  // Holding lays a fine scale (4x the spacing, quarter-year ticks) over the rail, pinned where the
  // hold started: the tick under the finger is always the current value, and nothing on the scale
  // moves while you drag. Only the bulge (a swell of the rail to the left) follows the finger.
  let ay = $state(0); // where the hold started, rail coordinates
  let af = $state(0); // the value there
  const bell = (d: number, sigma: number) => Math.exp(-(d * d) / (2 * sigma * sigma));
  const swell = (y: number) => -SWELL * b * bell(y - fy, R * 0.42);

  const ticks = $derived(
    L.stops.map((year, i) => {
      const y = yOf(i);
      const core = bell(y - fy, R * 0.5); // the fine scale takes over inside the bulge
      const label = i === 0 || i === n - 1 || year === 2011 || year % 5 === 0;
      return { year, i, y, x: swell(y), o: 1 - b * (0.55 + 0.45 * core), label };
    }),
  );
  const fine = $derived.by(() => {
    if (b < 0.01) return [];
    const out: { key: number; y: number; x: number; o: number; whole: boolean }[] = [];
    const px = gap * FINE;
    for (let q = Math.ceil((af + (fy - R * 1.3 - ay) / px) * FINE); q <= Math.floor((af + (fy + R * 1.3 - ay) / px) * FINE); q++) {
      const v = q / FINE;
      if (v < 0 || v > n - 1) continue;
      const y = ay + (v - af) * px;
      out.push({ key: q, y, x: swell(y), o: b * bell(y - fy, R * 0.6), whole: q % FINE === 0 });
    }
    return out;
  });
  const rail = $derived.by(() => {
    if (b < 0.01) return `M${railX} 0V${H}`;
    let d = `M${railX} 0`;
    for (let y = Math.max(0, fy - R * 1.4); y <= Math.min(H, fy + R * 1.4); y += 4) d += `L${(railX + swell(y)).toFixed(1)} ${y.toFixed(1)}`;
    return d + `L${railX} ${H}`;
  });
  // the label: while scrubbing, the value to the nearest quarter (what it will settle on)
  const q4 = $derived(Math.round(shown * FINE) / FINE);
  const labelYear = $derived(L.stops[clamp(Math.floor(scrubbing ? q4 : shown), 0, n - 1)]);
  const labelFrac = $derived(scrubbing ? ['', '¼', '½', '¾'][Math.round((q4 % 1) * FINE) % FINE] : '');
  const markY = $derived(scrubbing ? fy : yOf(shown));
  const markX = $derived(scrubbing ? swell(fy) : 0);

  // ---- driving the story
  let tweenRaf = 0;
  let bRaf = 0;
  let previewing = false;
  const go = (v: number) => {
    f = clamp(v, 0, n - 1);
    if (previewing) onpreview(wAtStop(L, f));
    else window.scrollTo(0, wAtStop(L, f) - L.P);
  };
  /** Hand the preview over to the real scroll position. */
  function commit() {
    if (!previewing) return;
    previewing = false;
    window.scrollTo(0, wAtStop(L, f) - L.P);
    onpreview(null);
  }
  function stop() {
    cancelAnimationFrame(tweenRaf);
    tweenRaf = 0;
  }
  function tween(to: number, then?: () => void) {
    stop();
    to = clamp(to, 0, n - 1);
    if (reduced || Math.abs(to - f) < 0.01) {
      go(to);
      return then?.();
    }
    const from = f;
    const dur = clamp(260 + Math.abs(to - from) * 110, 200, 850);
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = clamp((now - t0) / dur);
      go(from + (to - from) * easeOut(t));
      tweenRaf = t < 1 ? requestAnimationFrame(tick) : 0;
      if (t >= 1) then?.();
    };
    tweenRaf = requestAnimationFrame(tick);
  }
  function setBulge(to: number) {
    cancelAnimationFrame(bRaf);
    if (reduced) return void (b = to);
    const from = b;
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = clamp((now - t0) / (to > from ? 160 : 220));
      b = from + (to - from) * easeOut(t);
      bRaf = t < 1 ? requestAnimationFrame(tick) : 0;
    };
    bRaf = requestAnimationFrame(tick);
  }
  // after letting go, keep drawing our value until the smoothed scroll has caught up
  $effect(() => {
    if (driving && !g && !tweenRaf && Math.abs(fi - f) < 0.01) driving = false;
  });
  function buzz() {
    try {
      if ((navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation?.hasBeenActive !== false) navigator.vibrate?.(8);
    } catch {}
  }

  // ---- the gesture
  type Gesture = { id: number; y0: number; f0: number; t0: number; held: boolean };
  let g: Gesture | null = $state(null);
  let el: HTMLDivElement | undefined = $state();
  let holdTimer = 0;
  const localY = (e: PointerEvent) => e.clientY - L.scrub.top;

  function down(e: PointerEvent) {
    if (e.button > 0) return;
    stop();
    commit(); // a settle still in progress hands over first
    const y = localY(e);
    g = { id: e.pointerId, y0: y, f0: f, t0: e.timeStamp, held: false };
    fy = clamp(y, 0, H);
    try {
      el?.setPointerCapture(e.pointerId);
    } catch {}
    clearTimeout(holdTimer);
    holdTimer = window.setTimeout(() => {
      if (!g) return;
      // held: go to the spot under the finger and bulge there
      g.held = true;
      scrubbing = true;
      driving = true;
      previewing = true;
      ay = fy;
      af = fAt(fy);
      go(af);
      setBulge(1);
      buzz();
    }, HOLD_MS);
  }
  function move(e: PointerEvent) {
    if (!g || e.pointerId !== g.id) return;
    const y = localY(e);
    if (!g.held) {
      if (Math.abs(y - g.y0) > SLOP) cancel(); // moved before the hold: not a tap, not a scrub
      return;
    }
    fy = clamp(y, 0, H);
    go(af + (fy - ay) / (gap * FINE)); // the fine tick under the finger is the value
  }
  function up(e: PointerEvent) {
    if (!g || e.pointerId !== g.id) return;
    const d = g;
    clearTimeout(holdTimer);
    g = null;
    if (d.held) {
      scrubbing = false;
      setBulge(0);
      tween(Math.round(f * FINE) / FINE, commit); // settle on the quarter, then hand over to the page
    } else {
      f = fi;
      driving = true;
      tween(Math.round(fAt(d.y0)));
    }
  }
  function cancel() {
    clearTimeout(holdTimer);
    if (g?.held) {
      scrubbing = false;
      setBulge(0);
      commit();
    }
    g = null;
  }
  function key(e: KeyboardEvent) {
    const d = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    f = fi;
    driving = true;
    tween(Math.round(fi) + d);
  }

  onMount(() => {
    // belt and braces for iOS: the rail's touches never scroll the page (must be non-passive)
    const block = (e: TouchEvent) => {
      if (e.cancelable) e.preventDefault();
    };
    el?.addEventListener('touchmove', block, { passive: false });
    // the reader taking over (wheel, touch on the page) cancels a scrubber animation
    const takeover = (e: Event) => {
      if (g || (e.target instanceof Node && el?.contains(e.target))) return;
      stop();
      driving = false;
    };
    window.addEventListener('wheel', takeover, { passive: true });
    window.addEventListener('touchstart', takeover, { passive: true });
    return () => {
      stop();
      cancelAnimationFrame(bRaf);
      clearTimeout(holdTimer);
      el?.removeEventListener('touchmove', block);
      window.removeEventListener('wheel', takeover);
      window.removeEventListener('touchstart', takeover);
    };
  });
</script>

<div
  bind:this={el}
  class="scrub"
  class:on={scrubbing}
  role="slider"
  tabindex="0"
  aria-label="Year. Tap to jump, hold to scrub."
  aria-valuemin={L.stops[0]}
  aria-valuemax={L.stops[n - 1]}
  aria-valuenow={L.stops[cur]}
  style:width="{CW}px"
  style:height="{H}px"
  style:opacity
  style:pointer-events={opacity > 0.5 ? 'auto' : 'none'}
  style:transform="translate3d({L.rightEdge - CW}px,{L.scrub.top}px,0)"
  onpointerdown={down}
  onpointermove={move}
  onpointerup={up}
  onpointercancel={cancel}
  onkeydown={key}
>
  <div class="fade">
    <svg class="rail" width={CW} height={H} aria-hidden="true"><path d={rail} /></svg>
    {#each ticks as t (t.year)}
      <span class="tick" class:major={t.label} class:now={t.i === cur && !scrubbing} style:opacity={t.o} style:transform="translate3d({railX + t.x}px,{t.y}px,0)">
        <i></i>{#if t.label}<b>{t.year}</b>{/if}
      </span>
    {/each}
    {#each fine as t (t.key)}
      <span class="tick fine" class:whole={t.whole} style:opacity={t.o} style:transform="translate3d({railX + t.x}px,{t.y}px,0)"><i></i></span>
    {/each}
  </div>
  <span class="mark" class:big={b > 0.5} style:transform="translate3d({railX + markX}px,{markY}px,0)">
    <i></i><b>{labelYear}{#if labelFrac}<small>{labelFrac}</small>{/if}</b>
  </span>
</div>

<style>
  .scrub {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 26;
    touch-action: none; /* the rail never pans the page: nothing fights the finger */
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
    cursor: pointer;
    will-change: transform;
  }
  .scrub:focus-visible {
    outline: none;
  }
  .scrub:focus-visible .mark i {
    box-shadow: 0 0 0 2px var(--ink);
  }
  .fade {
    position: absolute;
    inset: 0;
    /* melts into the pile above and the bottom of the screen */
    -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 46px, #000 calc(100% - 56px), transparent);
    mask-image: linear-gradient(to bottom, transparent 0, #000 46px, #000 calc(100% - 56px), transparent);
  }
  .rail {
    position: absolute;
    inset: 0;
    overflow: visible;
  }
  .rail path {
    fill: none;
    stroke: var(--line);
    stroke-width: 1;
  }
  /* a tick is a zero-size point on the rail; its line and label hang off to the left */
  .tick,
  .mark {
    position: absolute;
    top: 0;
    left: 0;
    width: 0;
    height: 0;
    pointer-events: none;
  }
  .tick {
    color: var(--ink-3);
  }
  .tick i {
    position: absolute;
    right: 0;
    top: -0.5px;
    width: 6px;
    height: 1px;
    background: currentColor;
  }
  .tick.major i {
    width: 10px;
    background: var(--ink-2);
  }
  .tick b {
    position: absolute;
    right: 14px;
    top: -6px;
    line-height: 12px;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .tick.now {
    color: var(--ink);
  }
  .tick.fine i {
    width: 5px;
    background: var(--ink-2);
  }
  .tick.fine.whole i {
    top: -0.75px;
    width: 12px;
    height: 1.5px;
    background: var(--ink);
  }
  .mark {
    transition: transform 90ms linear;
  }
  .scrub.on .mark {
    transition: none;
  }
  .mark i {
    position: absolute;
    right: -4px;
    top: -1px;
    width: 18px;
    height: 2px;
    background: var(--ink);
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
  }
  .mark b {
    position: absolute;
    right: 20px;
    top: 0;
    transform: translateY(-50%);
    padding: 2px 5px;
    background: var(--ink);
    color: var(--bg);
    font-size: 10px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    transition: font-size var(--dur-micro) var(--ease-out);
  }
  .mark.big b {
    right: 26px;
    padding: 4px 8px;
    font-size: 15px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  }
  .mark small {
    margin-left: 2px;
    font-size: 0.75em;
  }
  @media (prefers-reduced-motion: reduce) {
    .mark,
    .mark b {
      transition: none;
    }
  }
</style>
