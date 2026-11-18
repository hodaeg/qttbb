<script lang="ts">
  // The front door. Three picker wheels (two digits and a surname) and one Enter button. Wrong: the
  // button flashes red, lit from behind. Right: a small green light comes on behind the glass, then the
  // controls blur and fade away and the frosted veil melts, bringing the story into focus.
  //
  // This is a curtain, not a safe: the site and its data are public on GitHub, and 5,000 combinations
  // can be tried by anyone who wants to. It keeps casual visitors out. The combination itself isn't in
  // the code, only a SHA-256 fingerprint of it.
  import { onMount } from 'svelte';

  let { onunlock }: { onunlock: () => void } = $props();

  const KEY = '646cb782633388c0238caa63c765db3109e4ad6847db3f888689ef9eb271ea80'; // sha256("qttbb:" + d1-d2-name)
  const DIGITS = Array.from({ length: 10 }, (_, i) => String(i));
  const NAMES = [
    'Adams', 'Allen', 'Anderson', 'Baker', 'Brown', 'Campbell', 'Carter', 'Clark', 'Collins', 'Davis',
    'Flores', 'Garcia', 'Gonzalez', 'Green', 'Hall', 'Harris', 'Hernandez', 'Hill', 'Jackson', 'Johnson',
    'Jones', 'King', 'Lee', 'Lewis', 'Lopez', 'Martin', 'Martinez', 'Miller', 'Mitchell', 'Moore',
    'Nelson', 'Nguyen', 'Perez', 'Ramirez', 'Rivera', 'Roberts', 'Robinson', 'Rodriguez', 'Scott', 'Smith',
    'Taylor', 'Thomas', 'Thompson', 'Torres', 'Walker', 'White', 'Williams', 'Wilson', 'Wright', 'Young',
  ];
  const wheels = [
    { label: 'First digit', items: DIGITS, w: 64 },
    { label: 'Second digit', items: DIGITS, w: 64 },
    { label: 'Surname', items: NAMES, w: 150 },
  ];
  const ITEM = 44; // px per row
  const ROWS = 5; // rows visible

  let pos = $state([0, 0, 0]); // each wheel's scroll, in rows (fractional while moving)
  let els: HTMLDivElement[] = $state([]);
  let phase = $state<'idle' | 'no' | 'yes' | 'gone'>('idle');
  let flash = 0;
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const buzz = (p: number | number[]) => {
    try {
      if (navigator.userActivation?.hasBeenActive) navigator.vibrate?.(p);
    } catch {}
  };

  const sel = (k: number) => Math.max(0, Math.min(wheels[k].items.length - 1, Math.round(pos[k])));
  let lastSel = [0, 0, 0];
  function onScroll(k: number) {
    pos[k] = els[k].scrollTop / ITEM;
    const s = sel(k);
    if (s !== lastSel[k]) {
      lastSel[k] = s;
      buzz(4); // a tick per detent
    }
  }
  function step(k: number, d: number) {
    const to = Math.max(0, Math.min(wheels[k].items.length - 1, sel(k) + d));
    els[k].scrollTo({ top: to * ITEM, behavior: reduced ? 'auto' : 'smooth' });
  }
  function pick(k: number, i: number) {
    els[k].scrollTo({ top: i * ITEM, behavior: reduced ? 'auto' : 'smooth' });
  }

  async function digest(s: string) {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  async function enter() {
    if (phase === 'yes' || phase === 'gone') return;
    const combo = `qttbb:${DIGITS[sel(0)]}-${DIGITS[sel(1)]}-${NAMES[sel(2)]}`;
    const ok = (await digest(combo)) === KEY;
    clearTimeout(flash);
    if (!ok) {
      phase = 'idle';
      requestAnimationFrame(() => (phase = 'no')); // restart the flash on repeat taps
      buzz([30, 40, 30]);
      flash = window.setTimeout(() => (phase = 'idle'), 900);
      return;
    }
    phase = 'yes';
    buzz(20);
    try {
      localStorage.setItem('qttbb-unlocked', KEY);
    } catch {}
    window.setTimeout(() => (phase = 'gone'), reduced ? 0 : 520);
    window.setTimeout(onunlock, reduced ? 0 : 1600);
  }

  onMount(() => {
    // no page scrolling behind the lock
    const html = document.documentElement;
    const prev = html.style.overflow;
    html.style.overflow = 'hidden';
    window.scrollTo(0, 0);
    return () => {
      html.style.overflow = prev;
      clearTimeout(flash);
    };
  });
</script>

<div class="lock" class:gone={phase === 'gone'} role="dialog" aria-modal="true" aria-label="Enter the combination">
  <div class="box">
    <p class="kicker">Members only</p>
    <div class="wheels">
      {#each wheels as wh, k (wh.label)}
        <div
          class="wheel"
          style:width="{wh.w}px"
          style:height="{ITEM * ROWS}px"
          role="spinbutton"
          tabindex="0"
          aria-label={wh.label}
          aria-valuenow={sel(k)}
          aria-valuetext={wh.items[sel(k)]}
          aria-valuemin={0}
          aria-valuemax={wh.items.length - 1}
          onkeydown={(e) => {
            if (e.key === 'ArrowUp') (e.preventDefault(), step(k, -1));
            if (e.key === 'ArrowDown') (e.preventDefault(), step(k, 1));
            if (e.key === 'Enter') enter();
          }}
        >
          <div class="scroller" bind:this={els[k]} onscroll={() => onScroll(k)} style:padding="{ITEM * 2}px 0">
            {#each wh.items as it, i (it)}
              {@const d = i - pos[k]}
              <button
                class="item"
                class:on={i === sel(k)}
                tabindex="-1"
                style:height="{ITEM}px"
                style:transform="rotateX({Math.max(-75, Math.min(75, -d * 22))}deg) translateZ(0)"
                style:opacity={Math.max(0.12, 1 - Math.abs(d) * 0.32)}
                onclick={() => pick(k, i)}
              >{it}</button>
            {/each}
          </div>
        </div>
      {/each}
      <!-- the selection band across all three -->
      <i class="band" style:height="{ITEM}px" style:top="{ITEM * 2}px"></i>
    </div>
    <button class="enter" class:no={phase === 'no'} class:yes={phase === 'yes' || phase === 'gone'} onclick={enter}>
      <span>Enter</span>
    </button>
  </div>
</div>

<style>
  .lock {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    place-items: center;
    padding: 16px;
    /* a heavy frosted veil over the story (nothing behind it is readable), which melts away on unlock:
       as it fades, the story underneath comes into focus */
    background:
      radial-gradient(120% 70% at 20% 0%, color-mix(in srgb, var(--bg-2) 85%, transparent), transparent 70%),
      color-mix(in srgb, var(--bg) 93%, transparent);
    backdrop-filter: blur(30px) saturate(0.8);
    -webkit-backdrop-filter: blur(30px) saturate(0.8);
    transition: opacity 900ms cubic-bezier(0.4, 0, 0.2, 1) 120ms;
  }
  .lock.gone {
    opacity: 0;
    pointer-events: none;
  }
  .box {
    transition:
      opacity 520ms ease,
      filter 520ms ease,
      transform 620ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  .lock.gone .box {
    /* the controls blur and fade away first */
    opacity: 0;
    filter: blur(10px);
    transform: scale(0.94);
  }
  .box {
    display: grid;
    justify-items: center;
    gap: 18px;
  }
  .kicker {
    margin: 0;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .wheels {
    position: relative;
    display: flex;
    gap: 8px;
    padding: 0 10px;
  }
  .wheel {
    position: relative;
    perspective: 420px;
    -webkit-mask-image: linear-gradient(to bottom, transparent, #000 30%, #000 70%, transparent);
    mask-image: linear-gradient(to bottom, transparent, #000 30%, #000 70%, transparent);
    outline: none;
  }
  .wheel:focus-visible {
    box-shadow: 0 0 0 2px var(--ink);
  }
  .scroller {
    height: 100%;
    overflow-y: auto;
    scroll-snap-type: y mandatory;
    overscroll-behavior: contain;
    scrollbar-width: none;
    transform-style: preserve-3d;
  }
  .scroller::-webkit-scrollbar {
    display: none;
  }
  .item {
    display: grid;
    place-items: center;
    width: 100%;
    scroll-snap-align: center;
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-weight: var(--display-weight);
    font-size: calc(24px * var(--display-scale));
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
    backface-visibility: hidden;
    transition: color 120ms;
  }
  .item.on {
    color: #fff;
  }
  .band {
    position: absolute;
    left: 0;
    right: 0;
    pointer-events: none;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.06);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.22),
      inset 0 -1px 0 rgba(255, 255, 255, 0.08);
  }
  /* one pane of glass, lit from behind when you press it */
  .enter {
    position: relative;
    width: 220px;
    height: 52px;
    border-radius: 2px;
    isolation: isolate;
    background: var(--glass-tint);
    backdrop-filter: var(--glass-filter);
    -webkit-backdrop-filter: var(--glass-filter);
    box-shadow: var(--glass-rim), var(--glass-lift);
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-weight: var(--display-weight);
    font-size: calc(20px * var(--display-scale));
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #fff;
    transition: transform 120ms ease-out;
  }
  .enter:active {
    transform: scale(0.97);
  }
  .enter::before {
    /* the light behind the glass */
    content: '';
    position: absolute;
    inset: -14px;
    z-index: -1;
    border-radius: 16px;
    background: radial-gradient(closest-side, var(--lit, transparent), transparent);
    filter: blur(10px);
    opacity: 0;
  }
  .enter span {
    position: relative;
  }
  .enter.no {
    --lit: #ff3b3b;
    animation: glow-no 900ms ease-out;
  }
  .enter.no::before {
    animation: lit 900ms ease-out;
  }
  .enter.yes {
    /* right: a small green light behind the glass, glowing through it (the glass stays glass) */
    --lit: rgba(61, 220, 106, 0.8);
    background: color-mix(in srgb, #3ddc6a 8%, var(--glass-tint));
    box-shadow: var(--glass-rim), var(--glass-lift), 0 0 14px rgba(61, 220, 106, 0.16);
  }
  .enter.yes::before {
    inset: 8px 28%;
    border-radius: 50%;
    filter: blur(9px);
    opacity: 0.9;
    animation: lit 520ms ease-out;
  }
  @keyframes lit {
    0% {
      opacity: 0;
    }
    18% {
      opacity: 1;
    }
    100% {
      opacity: 0.85;
    }
  }
  .enter.no::before {
    animation-name: lit-no;
  }
  @keyframes lit-no {
    0% {
      opacity: 0;
    }
    15% {
      opacity: 1;
    }
    100% {
      opacity: 0;
    }
  }
  @keyframes glow-no {
    0% {
      background: var(--glass-tint);
    }
    15% {
      background: color-mix(in srgb, #ff3b3b 38%, var(--glass-tint));
      box-shadow: var(--glass-rim), 0 0 40px rgba(255, 59, 59, 0.5);
    }
    100% {
      background: var(--glass-tint);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .lock {
      transition-duration: 1ms;
    }
  }
</style>
