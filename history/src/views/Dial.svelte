<script lang="ts">
  // The year dial: a wheel half off the right edge. Scrolling turns it; turning it scrolls.
  // Years sit on the rim; the one at the notch (9 o'clock) is "now".
  import { onMount } from 'svelte';
  import { wAtStop, clamp, easeOut, type Layout } from '../lib/model';

  let { L, fi, opacity = 1, reduced = false }: { L: Layout; fi: number; opacity?: number; reduced?: boolean } = $props();

  let active = $state(false); // being touched: slides further in
  let pulse = $state(0); // flips on every detent, for the visual tick
  const n = $derived(L.stops.length);
  const cur = $derived(clamp(Math.floor(fi + 0.001), 0, n - 1));
  const spacing = $derived((L.dial.r - 22) * ((L.dial.step * Math.PI) / 180)); // px between years along the rim
  const shift = $derived(active ? (L.desktop ? 30 : 22) : 0);

  let f = 0; // where the dial is driving the story to, in fractional stops
  let drag: { y0: number; f0: number; moved: number; lastY: number; lastT: number; v: number } | null = null;
  let raf = 0;
  let rest = 0;

  const go = (v: number) => {
    const next = clamp(v, 0, n - 0.001);
    if (Math.round(next) !== Math.round(f)) detent();
    f = next;
    window.scrollTo(0, wAtStop(L, f) - L.P);
  };
  function detent() {
    pulse++;
    try {
      navigator.vibrate?.(6);
    } catch {}
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }
  function tween(to: number) {
    stop();
    to = clamp(Math.round(to), 0, n - 1);
    if (reduced) return go(to);
    const from = f;
    const dur = clamp(260 + Math.abs(to - from) * 130, 260, 900);
    const t0 = performance.now();
    const step = (now: number) => {
      const t = clamp((now - t0) / dur);
      go(from + (to - from) * easeOut(t));
      raf = t < 1 ? requestAnimationFrame(step) : 0;
    };
    raf = requestAnimationFrame(step);
  }

  function down(e: PointerEvent) {
    stop();
    clearTimeout(rest);
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {}
    f = fi;
    drag = { y0: e.clientY, f0: fi, moved: 0, lastY: e.clientY, lastT: e.timeStamp, v: 0 };
    active = true;
  }
  function move(e: PointerEvent) {
    if (!drag) return;
    drag.moved = Math.max(drag.moved, Math.abs(e.clientY - drag.y0));
    const dt = Math.max(1, e.timeStamp - drag.lastT);
    drag.v = drag.v * 0.6 + (((drag.lastY - e.clientY) / spacing / dt) * 1000) * 0.4; // stops per second
    drag.lastY = e.clientY;
    drag.lastT = e.timeStamp;
    if (drag.moved > 4) go(drag.f0 + (drag.y0 - e.clientY) / spacing); // finger up = time forward
  }
  function up(e: PointerEvent) {
    if (!drag) return;
    const d = drag;
    drag = null;
    rest = window.setTimeout(() => (active = false), 700);
    if (d.moved <= 4) tween(fi + (e.clientY - L.dial.cy) / spacing); // a tap: jump to the year under the finger
    else tween(f + (e.timeStamp - d.lastT < 80 ? d.v * 0.22 : 0)); // a flick carries, then settles on a year
  }
  function key(e: KeyboardEvent) {
    const d = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    f = fi;
    tween(Math.floor(fi + 0.001) + d);
  }

  onMount(() => {
    // the reader taking over (wheel, touch on the page) cancels a dial animation
    const cancel = () => !drag && stop();
    window.addEventListener('wheel', cancel, { passive: true });
    window.addEventListener('touchstart', cancel, { passive: true });
    return () => {
      stop();
      window.removeEventListener('wheel', cancel);
      window.removeEventListener('touchstart', cancel);
    };
  });
</script>

<div
  class="dial"
  class:active
  role="slider"
  tabindex="0"
  aria-label="Year"
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
  <div class="wheel" style:transform="rotate({fi * L.dial.step}deg)">
    {#each L.stops as y, i (y)}
      {#if Math.abs(i - fi) < 9}
        <span class="mark" class:on={i === cur} style:transform="rotate({-i * L.dial.step}deg)"><i></i><b>{y}</b></span>
      {/if}
    {/each}
  </div>
  {#key pulse}<i class="notch"></i>{/key}
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
