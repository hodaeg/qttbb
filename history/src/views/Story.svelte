<script lang="ts">
  // The roster story. One fixed stage with three zones that never overlap: header avatars, the
  // column field, and the card tray, plus the year dial on the right edge. Everything is drawn
  // from the scroll position, so the whole history scrubs forwards and backwards like a film.
  import { onMount } from 'svelte';
  import {
    makeLayout, segments, members, tenures, people, legacy, constants, lineup, exits, FIRST, LAST, CUT_GAP,
    fillEdge, avatarState, stopAt, trayAt, clamp, lerp, back, type AvatarState, type Card,
  } from '../lib/model';
  import Avatar from './Avatar.svelte';
  import Glass from './Glass.svelte';
  import Tray from './Tray.svelte';
  import Dial from './Dial.svelte';

  let { onperson, onalumni, oncard }: { onperson: (id: string) => void; onalumni: () => void; oncard: (c: Card) => void } = $props();

  let vh = $state(800);
  let W = $state(390);
  let s = $state(0); // smoothed scroll position
  let vel = $state(0); // how fast we're moving (drives the liquid wobble)
  let time = $state(0);
  let reduced = $state(false);

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

  // ---- columns. A leaving column is sliced on the diagonal; its replacement starts with the matching slice.
  type Col = { key: string; person: string; x: number; y: number; h: number; clip: string; leaving: boolean; drain: number; constant: boolean };
  const field = $derived.by(() => {
    const cols: Col[] = [];
    const lips: { key: string; x: number; y: number; tone: string }[] = [];
    const amp = clamp(Math.abs(vel) / 26) * 5;
    for (const seg of segments) {
      const cutTop = seg.start > FIRST;
      const cutBot = seg.end !== LAST;
      const B1 = L.top(seg.end + 1);
      const top = cutTop ? L.T[seg.start] - L.cutH / 2 + CUT_GAP / 2 : L.T[seg.start];
      const bottom = cutBot ? B1 + L.cutH / 2 - CUT_GAP / 2 : L.end;
      const edge = fillEdge(L, seg.slot, w);
      const growing = edge < bottom;
      let fill = Math.min(bottom, edge);
      if (growing) fill += Math.sin(time * 9 + seg.slot * 1.7) * amp;
      if (fill <= top + 1) continue;
      const y = Math.max(top - s, -40);
      const h = fill - s - y;
      if (h <= 0 || y > vh) continue;
      const o = y + s; // the element's top, in world pixels
      const far = h + 60;
      const px = (n: number) => `${n.toFixed(1)}px`;
      const clip = `polygon(0 ${px(cutTop ? top + L.cutH - o : -1)},100% ${px(cutTop ? top - o : -1)},100% ${px(cutBot ? bottom - L.cutH - o : far)},0 ${px(cutBot ? bottom - o : far)})`;
      const key = `${seg.slot}-${seg.start}`;
      const x = L.colX(seg.slot) - L.cw / 2;
      cols.push({ key, person: seg.person, x, y, h, clip, leaving: cutBot, drain: cutBot ? clamp((w - B1) * 3, -90, 5000) - 90 : 0, constant: constants.has(seg.person) });
      if (growing && fill - s < L.P + 8) lips.push({ key, x, y: fill - s, tone: people[seg.person].color ?? '#fff' });
    }
    return { cols, lips };
  });

  // ---- season lines across the field, once the liquid has passed them
  const seasonLines = $derived(
    Object.keys(lineup).map(Number).filter((y) => y > FIRST && w > L.T[y] && L.T[y] - s > L.headerY && L.T[y] - s < L.P).map((y) => ({ y, sy: L.T[y] - s })),
  );

  // ---- markers that live on the columns: who left where, and each season's champion and sacko
  const marks = $derived.by(() => {
    const out: { key: string; kind: 'left' | 'champ' | 'sacko'; person: string; x: number; y: number; pop: number }[] = [];
    const add = (key: string, kind: 'left' | 'champ' | 'sacko', person: string, slot: number, world: number) => {
      const y = world - s;
      if (w <= world || y < 0 || y > L.P + 20) return;
      out.push({ key, kind, person, x: L.colX(slot), y, pop: clamp((w - world) / (vh * 0.07)) });
    };
    for (const ex of exits) add(`x${ex.slot}-${ex.start}`, 'left', ex.person, ex.slot, L.top(ex.end + 1) - L.cutH / 2 - L.av * 0.5 - 5);
    for (const [year, season] of Object.entries(legacy.seasons)) {
      const y = Number(year);
      if (!lineup[y]) continue;
      const mid = L.T[y] + L.bandH(y) * 0.5;
      for (const kind of ['champ', 'sacko'] as const) {
        const id = kind === 'champ' ? season.champion : season.sacko;
        const slot = id ? lineup[y].indexOf(id) : -1;
        if (id && slot >= 0) add(`${kind}${y}`, kind, id, slot, mid);
      }
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
        if (w <= B) break;
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

  // ---- where we are in time (the dial and the tray read this)
  const fi = $derived(stopAt(L, w));
  const yearNow = $derived(L.stops[Math.min(L.stops.length - 1, Math.floor(fi))]);
  const era = $derived(yearNow < FIRST ? 'Before the league' : yearNow === FIRST ? 'Founding' : yearNow < 2016 ? 'Shake-ups' : 'Current era');
  const started = $derived(clamp((w - (L.T[L.stops[0]] - vh * 0.35)) / (vh * 0.2)));
  const trayItems = $derived(trayAt(L, w));
  const trayO = $derived(started * (1 - clamp((w - L.end) / (vh * 0.2))));

  const finaleCy = $derived((L.finale - w) * 0.94 + vh * 0.52);
  const introO = $derived(1 - clamp(s / (vh * 0.45)));
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

<div class="spacer" style:height="{L.pageHeight}px"></div>

<div class="stage" class:reduced>
  <!-- columns: nothing is ever drawn over these except their own markers -->
  <div class="field" style:--fade="{L.headerY * 2 + 26}px">
    {#each field.cols as c (c.key)}
      <button
        class="col"
        class:leaving={c.leaving}
        class:constant={c.constant}
        aria-label={people[c.person].name}
        style:--tone={people[c.person].color}
        style:--drain="{c.drain}px"
        style:width="{L.cw}px"
        style:height="{c.h}px"
        style:clip-path={c.clip}
        style:transform="translate3d({c.x}px,{c.y}px,0)"
        onclick={() => onperson(c.person)}
      ></button>
    {/each}
    {#each field.lips as l (l.key)}
      <i class="lip" style:--tone={l.tone} style:width="{L.cw}px" style:transform="translate3d({l.x}px,{l.y - 2}px,0)"></i>
    {/each}
    {#each seasonLines as sl (sl.y)}
      <i class="season" style:width="{L.fieldW}px" style:transform="translate3d({L.padL}px,{sl.sy}px,0)"></i>
    {/each}
    {#each marks as m (m.key)}
      {#if m.kind === 'left'}
        <button class="mark left" aria-label="{people[m.person].name} left here" style:transform="translate3d({m.x}px,{m.y}px,0) translate(-50%,-50%) scale({back(m.pop) * 0.84})" onclick={() => onperson(m.person)}>
          <Avatar id={m.person} size={L.av} />
        </button>
      {:else}
        <span class="mark {m.kind}" title="{m.kind === 'champ' ? 'Champion' : 'Sacko'}: {people[m.person].name}" style:transform="translate3d({m.x}px,{m.y}px,0) translate(-50%,-50%) scale({back(m.pop)})">
          <svg viewBox="0 0 16 16" width={Math.min(L.cw - 5, 18)} height={Math.min(L.cw - 5, 18)} aria-hidden="true">
            {#if m.kind === 'champ'}
              <path d="M4 2h8v3.2a4 4 0 0 1-8 0zM1.8 3H4v1.3H3.1A1.7 1.7 0 0 0 4.2 6l-.5 1.2A3 3 0 0 1 1.8 4.4zM12 3h2.2v1.4a3 3 0 0 1-1.9 2.8L11.8 6a1.7 1.7 0 0 0 1.1-1.7H12zM7.2 9h1.6v2.4H11V13H5v-1.6h2.2z" />
            {:else}
              <path d="M3.2 3.2l9.6 9.6M12.8 3.2l-9.6 9.6" />
            {/if}
          </svg>
        </span>
      {/if}
    {/each}
  </div>

  <!-- the card tray -->
  <Tray {L} items={trayItems} opacity={trayO} {era} {onperson} {oncard} />

  <!-- finale -->
  {#if finaleCy < vh * 1.4}
    <div class="cardwrap finale" style:width="{Math.min(L.trayW, 440)}px" style:--o={clamp((vh - finaleCy) / (vh * 0.25))} style:--sheen={1 - finaleCy / vh} style:transform="translate3d({L.padL}px,calc({finaleCy}px - 50%),0)">
      <Glass pad="18px 18px 16px"><article class="fin">
        <span class="k">Now · {legacy.asOf.season}, week {legacy.asOf.last_scored_week}</span>
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
        <p class="fine">Mike's rankings, kept current from league data. The friend web comes next.</p>
      </article></Glass>
    </div>
  {/if}

  <!-- intro -->
  {#if introO > 0}
    <div class="intro" style:opacity={introO} style:transform="translate3d(0,{-s * 0.35}px,0)">
      <p class="kicker">A history, 2002 → now</p>
      <h1 class="display">The Quest <span>to the</span> <em>Bria Bowl</em></h1>
      <p class="lede">How twelve friends ended up in one fantasy football league, and who we lost along the way.</p>
      <span class="hint" aria-hidden="true">Scroll<i></i></span>
    </div>
  {/if}

  <!-- header -->
  <div class="header" style:height="{L.headerY * 2 - 6}px" style:opacity={started}></div>
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
        style:--gray={a.st.gray}
        style:--tone={people[a.p].color}
        style:transform="translate3d({a.st.x - L.av / 2}px,{a.st.y - L.av / 2}px,0) scale({a.st.scale})"
        onclick={() => (a.st.inPile ? onalumni() : onperson(a.p))}
      >
        <Avatar id={a.p} size={L.av} live />
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

  <!-- the year dial -->
  <Dial {L} {fi} opacity={started} {reduced} />

  <!-- temporary: type set switcher for the design review -->
  <button class="typeswitch" onclick={() => setType(TYPES[(TYPES.indexOf(type) + 1) % TYPES.length])} aria-label="Switch typeface set, now {type.toUpperCase()}">{type.toUpperCase()}</button>
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
  .col {
    pointer-events: auto;
    background: linear-gradient(to bottom, color-mix(in srgb, var(--tone) 78%, #000 22%), var(--tone) 240px);
    will-change: transform, height;
  }
  .col.leaving {
    /* once it's cut, grey climbs the ribbon from the cut upwards */
    --dead: color-mix(in srgb, var(--thread) 80%, var(--tone));
    background: linear-gradient(to top, var(--dead) 0, var(--dead) var(--drain), var(--tone) calc(var(--drain) + 90px));
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
  .lip {
    /* the pouring edge: a bright lip with a glow under it */
    height: 2px;
    background: color-mix(in srgb, var(--tone) 35%, white 65%);
    box-shadow: 0 6px 22px 3px color-mix(in srgb, var(--tone) 85%, transparent);
  }
  .season {
    height: 1px;
    background: rgba(0, 0, 0, 0.3);
  }
  .mark {
    display: grid;
    place-items: center;
    pointer-events: auto;
  }
  .mark.left {
    box-shadow: 0 0 0 2px var(--bg);
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
    z-index: 6;
    will-change: transform; /* never fade this wrapper: it would switch the glass off. Layers fade via --o */
  }
  .fin .k {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .fin h3 {
    margin: 4px 0 10px;
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
  .kicker {
    margin: 0 0 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ink-2);
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
    filter: grayscale(var(--gray, 0)) drop-shadow(0 0 calc(var(--glow) * 12px) var(--tone));
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
    background: var(--ink);
    color: var(--bg);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
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
    border: 1px solid var(--line);
    background: var(--glass-strong);
    font-size: 11px;
    font-weight: 600;
    color: var(--ink-2);
  }

  @media (prefers-reduced-motion: reduce) {
    .col.constant,
    .hint i {
      animation: none;
    }
  }
</style>
