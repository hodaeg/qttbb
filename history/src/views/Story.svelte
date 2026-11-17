<script lang="ts">
  // The roster story. One fixed stage; everything on it is drawn from the scroll position,
  // so the whole history scrubs forwards and backwards like a film.
  import { onMount } from 'svelte';
  import {
    makeLayout, segments, members, tenures, people, cards, legacy, constants, FIRST, LAST,
    fillEdge, avatarState, stopAt, clamp, lerp, smooth, type AvatarState,
  } from '../lib/model';
  import Avatar from './Avatar.svelte';
  import CardView from './Card.svelte';

  let { onperson, onalumni }: { onperson: (id: string) => void; onalumni: () => void } = $props();

  let vh = $state(800);
  let W = $state(390);
  let s = $state(0); // smoothed scroll position
  let vel = $state(0); // how fast we're moving (drives the liquid wobble)
  let time = $state(0);
  let reduced = $state(false);

  const L = $derived(makeLayout(vh, W));
  const w = $derived(s + L.P); // the playhead, in world pixels
  const fieldW = $derived(12 * L.cw + 11 * L.gap);

  onMount(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reduced = mq.matches;
    const size = () => {
      vh = window.innerHeight;
      W = document.documentElement.clientWidth;
    };
    size();
    s = window.scrollY;
    window.addEventListener('resize', size);
    let raf = 0;
    const tick = (now: number) => {
      const target = window.scrollY;
      const d = target - s;
      if (Math.abs(d) > 0.05) s = reduced ? target : s + d * 0.2;
      else if (d !== 0) s = target;
      const v = reduced ? 0 : lerp(vel, d, 0.25);
      if (Math.abs(v) > 0.02 || vel !== 0) {
        vel = Math.abs(v) < 0.02 ? 0 : v;
        time = now / 1000;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
    };
  });

  // ---- columns
  type Col = { key: string; person: string; slot: number; x: number; y: number; h: number; growing: boolean; rTop: boolean; pulse: number; dim: number; constant: boolean };
  const cols = $derived.by(() => {
    const out: Col[] = [];
    const amp = clamp(Math.abs(vel) / 26) * 5;
    for (const seg of segments) {
      const top = L.T[seg.start] + (seg.start > FIRST ? 5 : 0);
      const bottom = seg.end === LAST ? L.end : L.top(seg.end + 1) - 5;
      const edge = fillEdge(L, seg.slot, w);
      const growing = edge < bottom;
      let fill = Math.min(bottom, edge);
      if (growing) fill += Math.sin(time * 9 + seg.slot * 1.7) * amp;
      if (fill <= top + 1) continue;
      const y = Math.max(top - s, -40);
      const h = fill - s - y;
      if (h <= 0 || y > vh) continue;
      const after = w - bottom;
      out.push({
        key: `${seg.slot}-${seg.start}`, person: seg.person, slot: seg.slot, x: L.colX(seg.slot) - L.cw / 2, y, h, growing,
        rTop: top - s > -40, pulse: growing || seg.end === LAST ? 0 : 1 - clamp(after / (vh * 0.16)), dim: growing || seg.end === LAST ? 0 : clamp(after / (vh * 0.35)), constant: constants.has(seg.person),
      });
    }
    return out;
  });

  // ---- avatars and the alumni pile
  const pileOrder = $derived.by(() => {
    const inPile: { p: string; at: number }[] = [];
    for (const p of members) {
      const iv = tenures[p];
      for (let k = 0; k < iv.length; k++) {
        if (iv[k].end === LAST) break;
        const B = L.top(iv[k].end + 1);
        if (w <= B - vh * 0.1) break;
        const next = iv[k + 1];
        if (next && w > L.T[next.start] - vh * 0.04) continue; // on the way back
        inPile.push({ p, at: B + iv[k].slot });
      }
    }
    inPile.sort((a, b) => b.at - a.at); // newest on top
    return inPile.map((x) => x.p);
  });
  const avatars = $derived(
    members.map((p) => {
      const i = pileOrder.indexOf(p);
      return { p, st: avatarState(L, p, w, Math.max(i, 0)), pileIndex: i };
    }),
  );
  const pileCount = $derived(avatars.filter((a) => a.pileIndex >= 0 && a.st.landed > 0.6).length);
  const pileBump = $derived(Math.max(0, ...avatars.map((a) => (a.st.landed > 0.8 && a.st.landed < 1 ? Math.sin((Math.PI * (a.st.landed - 0.8)) / 0.2) : 0))));
  const zOf = (a: { st: AvatarState; pileIndex: number }) => (a.st.flying > 0.02 ? 30 : a.pileIndex >= 0 ? 20 - a.pileIndex : 10);

  // ---- the giant year
  const fi = $derived(stopAt(L, w));
  const yearRoll = $derived(Math.floor(fi) + smooth(clamp((fi - Math.floor(fi) - 0.8) / 0.2)));
  const yearNow = $derived(L.stops[Math.min(L.stops.length - 1, Math.floor(fi))]);
  const era = $derived(yearNow < FIRST ? 'Before' : yearNow === FIRST ? 'Founding' : yearNow < 2016 ? 'Shake-ups' : 'Current era');
  const yearOpacity = $derived(clamp((w - (L.T[L.stops[0]] - vh * 0.35)) / (vh * 0.25)) * (1 - clamp((w - L.end) / (vh * 0.3))));

  // ---- cards
  const cardViews = $derived.by(() => {
    const out: { card: (typeof cards)[number]; i: number; cy: number; o: number; x: number; width: number }[] = [];
    cards.forEach((card, i) => {
      const cy = (L.cardPos.get(card)! - w) * 0.94 + vh * 0.34;
      if (cy < -vh * 0.5 || cy > vh * 1.35) return;
      const o = Math.min(clamp((vh * 1.0 - cy) / (vh * 0.2)), clamp((cy - vh * 0.03) / (vh * 0.13)));
      const season = card.kind === 'season';
      const width = season ? Math.min(210, fieldW * 0.66) : Math.min(L.desktop ? 400 : fieldW + 34, W - 20);
      const left = L.desktop ? L.padL + fieldW + 28 : i % 2 ? Math.max(10, L.padL + fieldW + 34 - width) : 10;
      const x = season && !L.desktop ? L.padL + fieldW + 34 - width : left;
      out.push({ card, i, cy, o, x, width });
    });
    return out;
  });
  const finaleCy = $derived((L.finale - w) * 0.94 + vh * 0.42);
  const introO = $derived(1 - clamp(s / (vh * 0.45)));
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

<div class="spacer" style:height="{L.pageHeight}px"></div>

<div class="stage" class:reduced>
  <!-- the giant year -->
  <div class="year" style:opacity={yearOpacity} style:left="{L.padL + 2}px" aria-hidden="true">
    <span class="era">{era}</span>
    <div class="window">
      <div class="strip" style:transform="translate3d(0,{-yearRoll * 0.9}em,0)">
        {#each L.stops as y}<span>{y}</span>{/each}
      </div>
    </div>
  </div>

  <!-- columns -->
  <div class="field" style:--fade="{L.headerY * 2 + 26}px">
    {#each cols as c (c.key)}
      <button
        class="col"
        class:growing={c.growing}
        class:rtop={c.rTop}
        class:constant={c.constant}
        aria-label={people[c.person].name}
        style:--tone={people[c.person].color}
        style:--pulse={c.pulse}
        style:width="{L.cw}px"
        style:height="{c.h}px"
        style:opacity={1 - c.dim * 0.5}
        style:transform="translate3d({c.x}px,{c.y}px,0)"
        onclick={() => onperson(c.person)}
      ></button>
    {/each}
  </div>

  <!-- the playhead: a hairline where "now" is -->
  <div class="now" style:top="{L.P}px" style:left="{L.padL}px" style:width="{fieldW}px" style:opacity={yearOpacity * 0.9}></div>

  <!-- story cards -->
  {#each cardViews as v (v.i)}
    <div
      class="cardwrap"
      style:width="{v.width}px"
      style:opacity={v.o}
      style:pointer-events={v.o > 0.6 ? 'auto' : 'none'}
      style:transform="translate3d({v.x}px,calc({v.cy + (1 - v.o) * 12}px - 50%),0)"
    >
      <CardView card={v.card} {onperson} />
    </div>
  {/each}

  <!-- finale -->
  {#if finaleCy < vh * 1.4}
    <div class="cardwrap finale" style:width="{Math.min(W - 20, 440)}px" style:opacity={clamp((vh - finaleCy) / (vh * 0.25))} style:transform="translate3d({L.desktop ? L.padL : 10}px,calc({finaleCy}px - 50%),0)">
      <article class="fin">
        <span class="k">Now · {legacy.asOf.season}, week {legacy.asOf.last_scored_week}</span>
        <h3>The Legacy Rankings</h3>
        <ol>
          {#each legacy.rankings as r}
            <li>
              <button class="pressable" onclick={() => onperson(r.person)}>
                <span class="rk">{r.rank}</span><Avatar id={r.person} size={26} /><b>{first(r.person)}</b><span class="pts">{r.points}</span>
              </button>
            </li>
          {/each}
        </ol>
        <p class="fine">Mike's rankings, kept current from league data. The friend web comes next.</p>
      </article>
    </div>
  {/if}

  <!-- intro -->
  {#if introO > 0}
    <div class="intro" style:opacity={introO} style:transform="translate3d(0,{-s * 0.35}px,0)">
      <p class="kicker">A history, 2002 → now</p>
      <h1>The Quest to the <em>Bria Bowl</em></h1>
      <p class="lede">How twelve friends ended up in one fantasy football league, and who we lost along the way.</p>
      <span class="hint" aria-hidden="true">Scroll<i></i></span>
    </div>
  {/if}

  <!-- header -->
  <div class="header" style:height="{L.headerY * 2 - 6}px" style:opacity={clamp((w - (L.T[L.stops[0]] - vh * 0.5)) / (vh * 0.2))}></div>
  {#each avatars as a (a.p)}
    {#if a.st.opacity > 0.01 && (a.pileIndex < 4 || a.st.flying > 0.02)}
      <button
        class="av"
        aria-label={people[a.p].name}
        style:width="{L.av}px"
        style:height="{L.av}px"
        style:z-index={zOf(a)}
        style:opacity={a.st.opacity}
        style:--glow={a.st.flying}
        style:--tone={people[a.p].color}
        style:transform="translate3d({a.st.x - L.av / 2}px,{a.st.y - L.av / 2}px,0) scale({a.st.scale})"
        onclick={() => (a.st.inPile ? onalumni() : onperson(a.p))}
      >
        <Avatar id={a.p} size={L.av} />
        {#if a.st.returning > 0.02}<span class="returns" style:opacity={a.st.returning}>returns</span>{/if}
      </button>
    {/if}
  {/each}
  {#if pileCount > 0}
    <button
      class="pile"
      aria-label="Alumni, {pileCount} people"
      style:transform="translate3d({L.pile.x - 44}px,{L.pile.y - 22}px,0) scale({1 + pileBump * 0.12})"
      onclick={onalumni}
    >
      <span class="count">+{pileCount}</span>
    </button>
  {/if}
</div>

<style>
  .spacer {
    width: 1px;
  }
  .stage {
    position: fixed;
    inset: 0;
    overflow: hidden;
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

  /* giant year */
  .year {
    top: auto;
    bottom: calc(4vh + var(--safe-bottom));
    pointer-events: none;
    font-family: var(--font-display);
    font-weight: 800;
    font-size: clamp(92px, 31vw, 230px);
    line-height: 0.9;
    letter-spacing: -0.045em;
    color: var(--ghost);
    font-variant-numeric: tabular-nums;
  }
  .year .era {
    display: block;
    margin: 0 0 0.9em 0.3em;
    font-family: var(--font-text);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.22em;
    line-height: 1;
    text-transform: uppercase;
    color: var(--ink-3);
  }
  .window {
    height: 0.9em;
    overflow: hidden;
  }
  .strip span {
    display: block;
    height: 0.9em;
  }

  /* columns */
  .field {
    inset: 0;
    -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 var(--fade));
    mask-image: linear-gradient(to bottom, transparent 0, #000 var(--fade));
    pointer-events: none;
  }
  .col {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: auto;
    border-radius: 0 0 999px 999px;
    background: linear-gradient(to bottom, color-mix(in srgb, var(--tone) 78%, #000 22%), var(--tone));
    box-shadow: 0 0 calc(var(--pulse) * 22px) calc(var(--pulse) * 3px) color-mix(in srgb, var(--tone) 80%, transparent);
    will-change: transform, height;
  }
  .col.rtop {
    border-top-left-radius: 999px;
    border-top-right-radius: 999px;
  }
  .col.growing {
    box-shadow: 0 10px 26px -6px color-mix(in srgb, var(--tone) 75%, transparent);
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
  .now {
    height: 1px;
    background: linear-gradient(to right, transparent, var(--ink-3) 12%, var(--ink-3) 88%, transparent);
    pointer-events: none;
  }

  /* cards */
  .cardwrap {
    z-index: 5;
  }
  .fin {
    padding: 18px 18px 16px;
    border-radius: var(--radius-card);
    background: var(--glass);
    backdrop-filter: blur(var(--blur)) saturate(1.5);
    -webkit-backdrop-filter: blur(var(--blur)) saturate(1.5);
    border: 1px solid var(--glass-line);
  }
  .fin .k {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .fin h3 {
    margin: 4px 0 10px;
    font-family: var(--font-display);
    font-size: 30px;
    font-weight: 700;
    letter-spacing: -0.02em;
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
    font-family: var(--font-display);
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
  .kicker {
    margin: 0 0 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent);
  }
  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(46px, 13.5vw, 104px);
    line-height: 0.96;
    letter-spacing: -0.035em;
  }
  h1 em {
    font-weight: 500;
    color: var(--accent);
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
    border-radius: 50%;
    filter: drop-shadow(0 0 calc(var(--glow) * 10px) var(--tone));
  }
  .av::after {
    /* keeps the tap target at 44px even though the avatar is ~26px */
    content: '';
    position: absolute;
    inset: -9px;
  }
  .returns {
    position: absolute;
    right: -2px;
    top: 100%;
    margin-top: 5px;
    padding: 2px 6px;
    border-radius: 8px;
    background: var(--accent);
    color: #1a1204;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .pile {
    z-index: 25;
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
    .col.constant,
    .hint i {
      animation: none;
    }
  }
</style>
