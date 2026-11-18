<script lang="ts">
  // "Connected to", as a pile: the people someone is linked to, stacked messily like the alumni pile.
  // Tap it and it bursts: each avatar flies out to its own spot, scattered at random (seeded, so the
  // same person always flares the same way) and captioned with how they're connected. No box, no grid.
  // Tap anywhere and they all fall back into the pile; tap someone to go to them.
  import { people } from '../lib/model';
  import Avatar from './Avatar.svelte';

  let { id, links, onperson }: { id: string; links: { other: string; how: string; year: number | null }[]; onperson: (id: string) => void } = $props();

  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PILE = 34; // avatar size in the pile
  const BIG = 46; // and burst out
  const BOX = { w: 104, h: 104 }; // room each burst avatar and its caption needs

  const hash = (s: string) => {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
  };
  function rng(seed: number) {
    let a = seed;
    return () => {
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // where each avatar sits in the pile (the first five show; the rest hide underneath)
  const stack = $derived.by(() => {
    const r = rng(hash(id + 'pile'));
    return links.map((_, i) => (i < 5 ? { x: (i - 2) * 6 + (r() - 0.5) * 10, y: (r() - 0.5) * 9, rot: (r() - 0.5) * 36, o: 1 } : { x: 0, y: 0, rot: 0, o: 0 }));
  });

  let pileEl: HTMLButtonElement | undefined = $state();
  let live = $state(false); // the burst layer exists
  let open = $state(false); // and is flared out
  let c = $state({ x: 0, y: 0 }); // the pile's centre, on screen
  let spots = $state<{ x: number; y: number; rot: number }[]>([]);
  // the burst avatars only take taps once they've flown out; until then (and while falling back) a
  // quick second tap would land on whoever was on top of the pile and open them by accident
  let settled = $state(false);
  let timer = 0;
  let settleTimer = 0;

  // scatter: each avatar tries random spots near the pile, moving outward until it fits
  function scatter() {
    const W = innerWidth, H = innerHeight, m = 10;
    const r = rng(hash(id + 'burst'));
    const placed: { x: number; y: number }[] = [];
    const fits = (x: number, y: number) =>
      Math.hypot(x - c.x, (y - c.y) * 1.3) > 52 && placed.every((p) => Math.abs(p.x - x) > BOX.w + 4 || Math.abs(p.y - y) > BOX.h + 2);
    return links.map(() => {
      let best = { x: c.x, y: c.y };
      for (let k = 0; k < 600; k++) {
        const rad = 70 + k * 0.7 + r() * 50;
        const a = r() * Math.PI * 2;
        const x = Math.min(W - m - BOX.w / 2, Math.max(m + BOX.w / 2, c.x + Math.cos(a) * rad));
        const y = Math.min(H - m - BOX.h + BIG / 2, Math.max(m + BIG / 2 + 40, c.y + Math.sin(a) * rad * 1.15));
        best = { x, y };
        if (fits(x, y)) break;
      }
      placed.push(best);
      return { x: best.x - c.x, y: best.y - c.y, rot: (r() - 0.5) * 12 };
    });
  }

  function burst() {
    if (!pileEl) return;
    clearTimeout(timer);
    const b = pileEl.querySelector('.stack')!.getBoundingClientRect();
    c = { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    spots = scatter();
    live = true;
    // one frame in the pile, then fly
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        open = true;
        settleTimer = window.setTimeout(() => (settled = true), reduced ? 0 : 380);
      }),
    );
  }
  function collapse() {
    if (!open) return;
    clearTimeout(settleTimer);
    settled = false;
    // aim at where the pile is now (the panel may have moved), so they land exactly on it
    const b = pileEl?.querySelector('.stack')?.getBoundingClientRect();
    if (b) {
      const nc = { x: b.left + b.width / 2, y: b.top + b.height / 2 };
      spots = spots.map((s) => ({ ...s, x: s.x + c.x - nc.x, y: s.y + c.y - nc.y }));
      c = nc;
    }
    open = false;
    timer = window.setTimeout(() => (live = false), reduced ? 0 : 420 + links.length * 14 + 60); // once the last one has landed
  }
  function go(other: string) {
    collapse();
    onperson(other);
  }

  // anything that moves the page (or Escape) puts them back
  $effect(() => {
    if (!live) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation();
        collapse();
      }
    };
    // a real scroll, not the few pixels iOS nudges the page when its toolbars show or hide
    const y0 = window.scrollY;
    const away = () => Math.abs(window.scrollY - y0) > 40 && collapse();
    window.addEventListener('keydown', key, true);
    window.addEventListener('scroll', away, { passive: true });
    return () => {
      window.removeEventListener('keydown', key, true);
      window.removeEventListener('scroll', away);
    };
  });
  $effect(() => () => (clearTimeout(timer), clearTimeout(settleTimer)));

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy: () => node.remove() };
  }
  const n = $derived(links.length);
</script>

<button
  class="pile pressable"
  bind:this={pileEl}
  aria-label="Connected to {n} {n === 1 ? 'person' : 'people'}"
  aria-expanded={open}
  onclick={() => (open ? collapse() : burst())}
>
  <span class="stack" style:opacity={live ? 0 : 1}>
    {#each links.slice(0, 5) as l, i (l.other)}
      <span class="sa" style:z-index={10 - i} style:transform="translate({stack[i].x}px,{stack[i].y}px) rotate({stack[i].rot}deg)">
        <Avatar id={l.other} size={PILE} />
      </span>
    {/each}
  </span>
  <span class="count">{n}</span>
</button>

{#if live}
  <div class="burst" class:open class:settled class:reduced role="dialog" aria-label="Connected to" use:portal style:--n={n}>
    <button class="scrim" aria-label="Back into the pile" style:--cx="{c.x}px" style:--cy="{c.y}px" onclick={collapse} ontouchmove={collapse} onwheel={collapse}></button>
    {#each links as l, i (l.other)}
      {@const s = open ? spots[i] : stack[i]}
      <button
        class="node"
        aria-label="{people[l.other].name}: {l.how}"
        style:--i={i}
        style:--j={n - 1 - i}
        style:z-index={open ? 2 : 10 - i}
        style:opacity={open ? 1 : stack[i].o}
        style:transform="translate({c.x + s.x}px,{c.y + s.y}px) rotate({s.rot}deg) scale({open ? 1 : PILE / BIG})"
        onclick={() => go(l.other)}
      >
        <Avatar id={l.other} size={BIG} />
        <small>{l.how}</small>
      </button>
    {/each}
  </div>
{/if}

<style>
  .pile {
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 52px;
    padding: 4px 0;
  }
  .stack {
    position: relative;
    display: grid;
    width: 64px;
    height: 46px;
    place-items: center;
    transition: opacity 80ms;
  }
  .sa {
    grid-area: 1 / 1;
    display: grid; /* hugs the avatar exactly, so nothing peeks out around the photos */
    line-height: 0;
  }
  .sa {
    filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.45));
  }
  .count {
    font-size: 12px;
    font-weight: 700;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }

  .burst {
    position: fixed;
    inset: 0;
    z-index: 80;
    pointer-events: none; /* falling back, it lets taps through to the pile */
  }
  .burst.open .scrim,
  .burst.settled .node {
    pointer-events: auto;
  }
  .scrim {
    position: absolute;
    inset: 0;
    width: 100%;
    background: radial-gradient(circle at var(--cx) var(--cy), rgba(0, 0, 0, 0.62), rgba(0, 0, 0, 0.45) 70%);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    opacity: 0;
    transition: opacity 260ms ease-out 60ms;
    cursor: default;
  }
  .open .scrim {
    opacity: 1;
    transition-delay: 0ms;
  }
  .node {
    position: absolute;
    left: 0;
    top: 0;
    transform-origin: 52px 23px; /* the avatar's centre, so it pivots and shrinks exactly like the pile's */
    display: grid;
    justify-items: center;
    gap: 5px;
    width: 104px;
    margin: -23px 0 0 -52px; /* the avatar's centre sits on the spot */
    padding: 0;
    /* falling back: quick, the last out goes in first */
    transition:
      transform 420ms cubic-bezier(0.55, 0, 0.75, 0.15) calc(var(--j) * 14ms),
      opacity 200ms ease-in calc(var(--j) * 14ms + 220ms);
  }
  .open .node {
    /* flaring out: an overshooting spring, one after another */
    transition:
      transform 680ms cubic-bezier(0.22, 1.5, 0.4, 1) calc(var(--i) * 32ms),
      opacity 120ms ease-out calc(var(--i) * 32ms);
  }
  .node :global(.avatar) {
    filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.6));
  }
  .node small {
    max-width: 100px;
    font-size: 11px;
    line-height: 1.25;
    font-weight: 600;
    color: #fff;
    text-align: center;
    text-wrap: balance;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
    display: -webkit-box;
    -webkit-line-clamp: 4;
    line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
    opacity: 0;
    transform: translateY(-6px);
    transition:
      opacity 120ms ease-in,
      transform 120ms ease-in;
  }
  .open .node small {
    opacity: 1;
    transform: none;
    transition:
      opacity 260ms ease-out calc(260ms + var(--i) * 32ms),
      transform 360ms cubic-bezier(0.22, 1.4, 0.4, 1) calc(260ms + var(--i) * 32ms);
  }
  .reduced .node,
  .reduced .node small,
  .reduced .scrim {
    transition-duration: 1ms !important;
    transition-delay: 0ms !important;
  }
</style>
