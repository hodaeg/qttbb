<script module lang="ts">
  // The family tree: how every member traces back to one dorm room. One parent per person (the one who
  // brought them in), laid out as an outline: each person's ribbon, in their own colour, peels off the
  // ribbon of whoever brought them in and runs down to the people they brought in. Someone who brought in
  // just one person carries straight on down into them (a lineage, not a step), so long chains like
  // Toby, Krissie, Megan, Kennedy, Callan don't march off the side of a phone. It grows as you scroll.
  import treeFile from '../../content/tree.json';
  import { people } from '../lib/model';

  type Entry = { id: string; via?: string; how: string; year?: number };
  type Row = Entry & { x: number; y: number; depth: number; parent: Row | null; last: number; color: string; straight: boolean };
  const tree = treeFile as { root: Entry; people: Entry[] };
  const kids = (id: string) => tree.people.filter((p) => p.via === id);
  const GREY = '#8d9099'; // friends of the league who aren't members: a plain grey ribbon

  /** Where everything sits, in the section's own pixels (0 = its top). `len`: how much scroll it takes. */
  export function treeLayout(W: number, desktop: boolean, vh: number) {
    const colW = Math.min(W - 32, 600);
    const x0 = (W - colW) / 2;
    const av = desktop ? 40 : 32;
    const ind = desktop ? 44 : 30;
    const rh = desktop ? 66 : 58;
    const title = desktop ? 104 : 64;
    const head = title * 0.92 + 18 + (desktop ? 56 : 84) + 44; // the title, the lede, then room
    const rows: Row[] = [];
    const add = (e: Entry, parent: Row | null, depth: number) => {
      const p = people[e.id];
      const straight = !!parent && kids(parent.id).length === 1;
      const r: Row = {
        ...e, depth, parent, last: 0, straight,
        x: parent ? parent.x + (straight ? 0 : ind) : x0 + av / 2,
        y: head + rows.length * rh + av / 2,
        color: p?.role === 'member' && p.color ? p.color : GREY,
      };
      rows.push(r);
      for (const k of kids(e.id)) add(k, r, depth + 1);
      // the ribbon runs down to the last person this one brought in
      const ch = rows.filter((c) => c.parent === r && !c.straight);
      r.last = ch.length ? ch[ch.length - 1].y : r.y;
    };
    add(tree.root, null, 0);
    const end = rows[rows.length - 1].y + av / 2;
    return { x0, colW, av, ind, rh, title, rows, end, len: end + vh * 0.42 };
  }
  export type TreeLayout = ReturnType<typeof treeLayout>;
</script>

<script lang="ts">
  import Avatar from './Avatar.svelte';

  // u: how far the section has scrolled up from the bottom of the screen (its top is at vh - u);
  // inset: the bottom safe zone (a browser toolbar can cover that much of the screen)
  let { T, u, vh, inset = 0, desktop, onperson }: { T: TreeLayout; u: number; vh: number; inset?: number; desktop: boolean; onperson: (id: string) => void } = $props();

  const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const back = (t: number) => 1 + 2.4 * Math.pow(t - 1, 3) + 1.4 * Math.pow(t - 1, 2);
  const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
  const R = $derived(Math.min(10, T.ind - T.av / 2 - 3)); // the elbow's radius
  // the tree comes up out of the dark at the bottom of the screen: `floor` is where it's black (just
  // above any toolbar), and it's fully there `FADE` px above that
  const floor = $derived(u - inset);
  const FADE = $derived(vh * 0.24);
  const headIn = $derived(u > vh * 0.16);
  const ledeIn = $derived(u > vh * 0.24);
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
  /** 0..1: how far a row has risen out of the dark (0 at the floor, 1 settled) */
  const rise = (r: Row, lag = 0) => clamp((floor - r.y - lag) / FADE);

  const stem = (r: Row) => `M${r.x} ${r.y + T.av / 2 - 2}V${r.last - R}`;
  const elbow = (r: Row) => {
    const px = r.parent!.x;
    if (r.straight) return `M${px} ${r.parent!.y + T.av / 2 - 2}V${r.y - T.av / 2 + 2}`;
    return `M${px} ${r.y - R - 0.5}Q${px} ${r.y} ${px + R} ${r.y}H${r.x - T.av / 2 + 1}`;
  };
</script>

<div class="wrap" style:height="{T.end + 20}px" style:--f="{floor.toFixed(1)}px" style:--fh="{FADE.toFixed(0)}px">
  <h2 class="head display" class:in={headIn} style:left="{T.x0}px" style:font-size="calc({T.title}px * var(--display-scale))">Family Tree</h2>
  <p class="lede" class:in={ledeIn} style:left="{T.x0}px" style:width="{T.colW}px" style:top="{T.title * 0.92 + 18}px">
    The whole league traces back to one dorm room: Dustin and Doug, freshman roommates at Winona State in 2002.
  </p>

  <svg class="ribbons" width="100%" height={T.end + 20} aria-hidden="true" style:--w="{desktop ? 5 : 4}px">
    <defs>
      <!-- each branch blends from the colour of whoever brought them in to their own -->
      {#each T.rows as r (r.id)}
        {#if r.parent}
          {#if r.straight}
            <linearGradient id="tg-{r.id}" gradientUnits="userSpaceOnUse" x1={r.x} x2={r.x} y1={r.parent.y + T.av / 2} y2={r.y - T.av / 2}>
              <stop offset="0" stop-color={r.parent.color} /><stop offset="1" stop-color={r.color} />
            </linearGradient>
          {:else}
            <linearGradient id="tg-{r.id}" gradientUnits="userSpaceOnUse" x1={r.parent.x - 2} x2={r.x - T.av / 2} y1={r.y} y2={r.y}>
              <stop offset="0" stop-color={r.parent.color} /><stop offset="1" stop-color={r.color} />
            </linearGradient>
          {/if}
        {/if}
      {/each}
    </defs>
    {#each T.rows as r (r.id)}
      {#if r.last > r.y}<path d={stem(r)} stroke={r.color} />{/if}
      {#if r.parent}<path d={elbow(r)} stroke="url(#tg-{r.id})" />{/if}
    {/each}
  </svg>

  {#each T.rows as r (r.id)}
    {@const a = rise(r)}
    {@const b = rise(r, 18)}
    <button
      class="row"
      style:left="{r.x - T.av / 2}px"
      style:top="{r.y - T.av / 2}px"
      style:width="{T.x0 + T.colW - (r.x - T.av / 2)}px"
      style:height="{T.av}px"
      style:pointer-events={a > 0.3 ? null : 'none'}
      tabindex={a > 0.3 ? 0 : -1}
      aria-label="{people[r.id].name}: {r.how}{r.year ? `, ${r.year}` : ''}"
      onclick={() => onperson(r.id)}
    >
      <!-- rising up out of the dark and settling: the avatar first, then its words -->
      <span class="av" style:transform="translateY({((1 - easeOut(a)) * 34).toFixed(1)}px) scale({(0.72 + 0.28 * back(a)).toFixed(3)})">
        <Avatar id={r.id} size={T.av} live />
      </span>
      <span class="words" style:opacity={b} style:transform="translateY({((1 - easeOut(b)) * 22).toFixed(1)}px)">
        <b class="display" style:color={r.color === GREY ? null : `color-mix(in srgb, ${r.color} 70%, white)`}>{people[r.id].name}{#if people[r.id].nickname && people[r.id].nickname !== people[r.id].name}<small>{' “' + first(r.id) + '”'}</small>{/if}</b>
        <small class="how">{r.how}</small>
      </span>
      {#if r.year}<i class="yr" style:opacity={b}>{r.year}</i>{/if}
    </button>
  {/each}
</div>

<style>
  .wrap {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    /* everything comes up out of the dark at the bottom of the screen */
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(var(--f) - var(--fh)), transparent var(--f));
    mask-image: linear-gradient(to bottom, #000 calc(var(--f) - var(--fh)), transparent var(--f));
  }
  .head,
  .lede,
  .ribbons,
  .row {
    position: absolute;
    top: 0;
    left: 0;
  }
  .head {
    margin: 0;
    line-height: 0.92;
    color: #fff;
    text-transform: uppercase;
    transform-origin: 0 100%;
    opacity: 0;
    transform: translateY(18px) scale(0.86);
    transition:
      opacity 160ms ease-in,
      transform 200ms ease-in;
  }
  .head.in {
    opacity: 1;
    transform: none;
    transition:
      opacity 300ms ease-out,
      transform 560ms cubic-bezier(0.2, 1.5, 0.4, 1);
  }
  .lede {
    margin: 0;
    font-size: 15px;
    line-height: 1.5;
    color: var(--ink-2);
    opacity: 0;
    transform: translateY(12px);
    transition:
      opacity 200ms ease-in,
      transform 200ms ease-in;
  }
  .lede.in {
    opacity: 1;
    transform: none;
    transition:
      opacity 500ms ease-out,
      transform 700ms cubic-bezier(0.2, 1, 0.3, 1);
  }
  .ribbons {
    overflow: visible;
    pointer-events: none;
  }
  .ribbons path {
    fill: none;
    stroke-width: var(--w);
    stroke-linecap: butt;
    stroke-linejoin: round;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0;
    text-align: left;
    color: #fff;
  }
  .row:active .av {
    filter: brightness(0.85);
  }
  .row:focus-visible {
    outline: 1px solid var(--ink-2);
    outline-offset: 3px;
  }
  .av {
    display: grid;
    flex: none;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
  }
  .words {
    display: grid;
    flex: 1;
    min-width: 0;
    gap: 1px;
  }
  .words b {
    font-size: calc(17px * var(--display-scale));
    line-height: 1.05;
    letter-spacing: 0.01em;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .words b small {
    font-size: 0.8em;
    color: var(--ink-2);
  }
  .how {
    font-size: 12px;
    line-height: 1.3;
    color: var(--ink-2);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .yr {
    flex: none;
    align-self: center;
    font-style: normal;
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--ink-3);
  }
</style>
