<script lang="ts">
  // The year dial: a wheel half off the bottom-right edge. Scrolling turns it; turning it scrolls.
  // Years sit on the rim; the one at the notch (9 o'clock) is "now".
  //
  // Feel:
  // - drag: one year per ~30px of finger travel, settles on a year when let go; a flick carries;
  // - hold still for a moment (before or during a drag): the dial zooms in, like zooming a
  //   scrubber in an editing suite. Quarter-year sub-ticks appear, the same finger travel now
  //   moves a quarter of a year, and it settles on the nearest quarter;
  // - quick tap: jump to the year under the finger.
  // While the dial is in charge it draws its own value, not the (smoothed, lagging) scroll, so it
  // never fights itself; it hands back to the scroll once the two agree.
  import { onMount } from 'svelte';
  import { wAtStop, clamp, easeOut, lerp, type Layout } from '../lib/model';

  let { L, fi, opacity = 1, reduced = false }: { L: Layout; fi: number; opacity?: number; reduced?: boolean } = $props();

  const ZOOM = 4; // sub-ticks per year when zoomed in
  const HOLD_MS = 320; // resting this long zooms in
  const SLOP = 6; // px of finger wobble that doesn't count as a drag

  let active = $state(false); // being touched: slides further in
  let zoom = $state(0); // 0 coarse … 1 zoomed in (animated)
  let pulse = $state(0); // flips on every detent, for the visual tick
  let f = $state(0); // the dial's own value, in fractional stops
  let driving = $state(false); // the dial, not the scroll, decides what is drawn

  const n = $derived(L.stops.length);
  const step = $derived(L.dial.step * lerp(1, ZOOM, zoom)); // degrees per year, right now
  const pxPerYear = (z: number) => (L.dial.r - 22) * ((L.dial.step * lerp(1, ZOOM, z) * Math.PI) / 180);
  const shown = $derived(driving ? f : fi);
  const cur = $derived(clamp(Math.round(shown), 0, n - 1));
  const shift = $derived(active ? (L.desktop ? 30 : 22) : 0);
  const grain = $derived(zoom > 0.5 ? ZOOM : 1); // detents per year

  type Drag = { y0: number; f0: number; t0: number; moved: boolean; restY: number; lastY: number; lastT: number; v: number };
  let drag: Drag | null = null;
  let raf = 0;
  let zoomRaf = 0;
  let holdTimer = 0;
  let rest = 0;

  const go = (v: number) => {
    const next = clamp(v, 0, n - 0.001);
    if (Math.floor(next * grain) !== Math.floor(f * grain)) detent();
    f = next;
    window.scrollTo(0, wAtStop(L, f) - L.P);
  };
  function detent() {
    pulse++;
    try {
      if ((navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation?.hasBeenActive !== false) navigator.vibrate?.(zoom > 0.5 ? 3 : 6);
    } catch {}
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }
  function tween(to: number) {
    stop();
    to = clamp(to, 0, n - 1);
    if (reduced || Math.abs(to - f) < 0.01) return go(to);
    const from = f;
    const dur = clamp(260 + Math.abs(to - from) * 130, 220, 900);
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = clamp((now - t0) / dur);
      go(from + (to - from) * easeOut(t));
      raf = t < 1 ? requestAnimationFrame(tick) : 0;
    };
    raf = requestAnimationFrame(tick);
  }
  function setZoom(to: number) {
    cancelAnimationFrame(zoomRaf);
    if (reduced) return void (zoom = to);
    const from = zoom;
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = clamp((now - t0) / 240);
      zoom = from + (to - from) * easeOut(t);
      zoomRaf = t < 1 ? requestAnimationFrame(tick) : 0;
    };
    zoomRaf = requestAnimationFrame(tick);
  }
  // after the dial lets go, keep drawing its value until the smoothed scroll has caught up
  $effect(() => {
    if (driving && !drag && !raf && Math.abs(fi - f) < 0.01) driving = false;
  });

  function armHold() {
    clearTimeout(holdTimer);
    if (zoom > 0.5) return;
    holdTimer = window.setTimeout(() => {
      if (!drag) return;
      drag.y0 = drag.lastY; // rebase, so zooming doesn't move the story
      drag.f0 = f;
      drag.v = 0;
      setZoom(1);
      detent();
    }, HOLD_MS);
  }

  function down(e: PointerEvent) {
    stop();
    clearTimeout(rest);
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {}
    f = fi;
    driving = true;
    drag = { y0: e.clientY, f0: fi, t0: e.timeStamp, moved: false, restY: e.clientY, lastY: e.clientY, lastT: e.timeStamp, v: 0 };
    active = true;
    armHold();
  }
  function move(e: PointerEvent) {
    if (!drag) return;
    const d = drag;
    if (!d.moved && Math.abs(e.clientY - d.y0) <= SLOP) return; // wobble, not a drag
    if (!d.moved) {
      d.moved = true;
      d.y0 = e.clientY; // start from here, so crossing the slop doesn't jump
    }
    // resting re-arms the zoom: any pause of HOLD_MS zooms in
    if (Math.abs(e.clientY - d.restY) > 3) {
      d.restY = e.clientY;
      armHold();
    }
    const dt = Math.max(1, e.timeStamp - d.lastT);
    const px = pxPerYear(zoom);
    d.v = d.v * 0.6 + ((d.lastY - e.clientY) / px / dt) * 1000 * 0.4; // stops per second
    d.lastY = e.clientY;
    d.lastT = e.timeStamp;
    go(d.f0 + (d.y0 - e.clientY) / px); // finger up = time forward
  }
  function up(e: PointerEvent) {
    if (!drag) return;
    const d = drag;
    drag = null;
    clearTimeout(holdTimer);
    rest = window.setTimeout(() => (active = false), 700);
    const zoomed = zoom > 0.5;
    if (zoomed) setZoom(0);
    if (!d.moved) {
      // a grab that never moved leaves the story where it is; only a quick tap jumps
      if (!zoomed && e.timeStamp - d.t0 < 260) tween(Math.round(f + (e.clientY - L.dial.cy) / pxPerYear(0)));
    } else if (zoomed) {
      tween(Math.round(f * ZOOM) / ZOOM); // fine: settle on the nearest quarter
    } else {
      const fling = e.timeStamp - d.lastT < 80 ? clamp(d.v * 0.22, -6, 6) : 0;
      tween(Math.round(f + fling)); // a flick carries, then settles on a year
    }
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
    // the reader taking over (wheel, touch on the page) cancels a dial animation
    const cancel = (e: Event) => {
      if (drag || (e.target instanceof Node && dialEl?.contains(e.target))) return;
      stop();
      driving = false;
    };
    window.addEventListener('wheel', cancel, { passive: true });
    window.addEventListener('touchstart', cancel, { passive: true });
    return () => {
      stop();
      cancelAnimationFrame(zoomRaf);
      clearTimeout(holdTimer);
      window.removeEventListener('wheel', cancel);
      window.removeEventListener('touchstart', cancel);
    };
  });
  let dialEl: HTMLDivElement | undefined = $state();
  const visible = (i: number) => Math.abs(i - shown) * step < 110;
</script>

<div
  bind:this={dialEl}
  class="dial"
  class:active
  class:zoomed={zoom > 0.5}
  role="slider"
  tabindex="0"
  aria-label="Year. Hold to fine-tune."
  aria-valuemin={L.stops[0]}
  aria-valuemax={L.stops[n - 1]}
  aria-valuenow={L.stops[cur]}
  style:width="{L.dial.r * 2}px"
  style:height="{L.dial.r * 2}px"
  style:opacity
  style:pointer-events={opacity > 0.5 ? 'auto' : 'none'}
  style:transform="translate3d({L.W - L.dial.sliver - shift}px,{L.dial.cy - L.dial.r}px,0)"
  onpointerdown={down}
  onpointermove={move}
  onpointerup={up}
  onpointercancel={up}
  onkeydown={key}
>
  <div class="wheel" style:transform="rotate({shown * step}deg)">
    {#each L.stops as y, i (y)}
      {#if visible(i)}
        <span class="mark" class:on={i === cur} style:transform="rotate({-i * step}deg)"><i></i><b>{y}</b></span>
        {#if zoom > 0.01 && i < n - 1}
          {#each [1, 2, 3] as j}
            <span class="mark sub" style:opacity={zoom} style:transform="rotate({-(i + j / ZOOM) * step}deg)"><i class:half={j === 2}></i></span>
          {/each}
        {/if}
      {/if}
    {/each}
  </div>
  {#key pulse}<i class="notch"></i>{/key}
  <span class="fine" style:opacity={zoom}>Fine</span>
</div>

<style>
  .dial {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 26;
    border-radius: 50%; /* the one round thing: it is a wheel */
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
    cursor: grab;
    background:
      radial-gradient(circle at 50% 50%, transparent 58%, rgba(255, 255, 255, 0.05) 59%, transparent 72%),
      var(--glass-strong);
    box-shadow:
      inset 0 0 0 1.5px var(--line),
      inset 10px 0 30px -12px rgba(255, 255, 255, 0.22),
      -14px 0 40px -10px rgba(0, 0, 0, 0.7);
    transition:
      transform var(--dur-ui) var(--ease-out),
      box-shadow var(--dur-ui) var(--ease-out);
    will-change: transform;
  }
  .dial.active {
    cursor: grabbing;
    box-shadow:
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.5),
      inset 10px 0 30px -12px rgba(255, 255, 255, 0.4),
      -14px 0 40px -10px rgba(0, 0, 0, 0.7);
  }
  .dial.zoomed {
    box-shadow:
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.85),
      inset 14px 0 36px -10px rgba(255, 255, 255, 0.5),
      -14px 0 40px -10px rgba(0, 0, 0, 0.7);
  }
  .dial:focus-visible {
    outline: none;
    box-shadow: inset 0 0 0 2px var(--ink);
  }
  .wheel {
    position: absolute;
    inset: 0;
    will-change: transform;
  }
  .mark {
    /* runs from the rim to the hub, so rotating it carries the label around the rim */
    position: absolute;
    left: 0;
    top: 50%;
    width: 50%;
    height: 0;
    transform-origin: 100% 50%;
    display: flex;
    align-items: center;
    gap: 5px;
    color: var(--ink-3);
  }
  .mark i {
    width: 5px;
    height: 1.5px;
    background: currentColor;
  }
  .mark.sub i {
    width: 3px;
    height: 1px;
  }
  .mark.sub i.half {
    width: 5px;
  }
  .mark b {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
    transition:
      color var(--dur-ui) var(--ease-out),
      transform var(--dur-ui) var(--ease-out);
    transform-origin: 0 50%;
  }
  .mark.on {
    color: var(--ink);
  }
  .mark.on b {
    transform: scale(1.25);
  }
  .notch {
    position: absolute;
    left: -3px;
    top: 50%;
    width: 9px;
    height: 2px;
    margin-top: -1px;
    background: var(--ink);
    animation: tick 220ms var(--ease-out);
  }
  .fine {
    position: absolute;
    left: 12px;
    top: calc(50% + 12px);
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-2);
    pointer-events: none;
  }
  @keyframes tick {
    from {
      transform: scaleX(2.4);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .notch {
      animation: none;
    }
    .dial {
      transition: none;
    }
  }
</style>
