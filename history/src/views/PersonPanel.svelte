<script lang="ts">
  import { people, tenures, yearsLabel, isCurrent, legacyOf, legacy, connections, constants, FIRST, LAST } from '../lib/model';
  import Avatar from './Avatar.svelte';

  let { id, onperson }: { id: string; onperson: (id: string) => void } = $props();
  const p = $derived(people[id]);
  const lg = $derived(legacyOf[id]);
  const links = $derived(
    connections
      .filter((c) => c.from === id || c.to === id)
      .map((c) => ({ other: c.from === id ? c.to : c.from, how: c.how, year: c.year })),
  );
  const status = $derived(
    p.role === 'outsider' ? 'Friend of the league' : isCurrent(id) ? (p.founder ? 'Founder, current member' : 'Current member') : p.founder ? 'Founder, alumni' : 'Alumni',
  );
  const years = $derived(Array.from({ length: LAST - FIRST + 1 }, (_, i) => FIRST + i));
  const played = $derived(new Set((tenures[id] ?? []).flatMap((t) => Array.from({ length: t.end - t.start + 1 }, (_, i) => t.start + i))));
  const titles = $derived(Object.entries(legacy.seasons).filter(([, s]) => s.champion === id).map(([y]) => y));
  const sackos = $derived(Object.entries(legacy.seasons).filter(([, s]) => s.sacko === id).map(([y]) => y));
  const silver = $derived(
    Object.entries(legacy.seasons).flatMap(([y, s]) => (s.silverStars ?? []).filter((x) => x.person === id).map((x) => ({ year: y, why: x.why }))),
  );
</script>

<header>
  <Avatar {id} size={64} />
  <div>
    <h3 class="display">{p.name}</h3>
    <p class="sub">{#if p.nickname}“{p.nickname}” · {/if}{status}</p>
  </div>
</header>

{#if tenures[id]}
  <div class="years" aria-label="Seasons played: {yearsLabel(id)}">
    {#each years as y}<i class:on={played.has(y)} style:--tone={p.color}></i>{/each}
  </div>
  <p class="cap">{yearsLabel(id)}{#if constants.has(id)} · every season{/if}</p>
{/if}

{#if lg}
  <div class="stats">
    <div><b>#{lg.rank}</b><span>Legacy rank</span></div>
    <div><b>{lg.points}</b><span>Legacy points</span></div>
    <div><b>{lg.record.wins}–{lg.record.losses}{lg.record.ties ? `–${lg.record.ties}` : ''}</b><span>All-time record</span></div>
    <div><b>{lg.championships}</b><span>Bria Bowls</span></div>
    <div><b>{lg.sackos}</b><span>Sackos</span></div>
    <div><b>{lg.playoffAppearances}</b><span>Playoffs</span></div>
  </div>
{/if}
{#if titles.length || sackos.length || silver.length}
  <p class="cap">
    {#if titles.length}Champion {titles.map((y) => y + (legacy.seasons[y].championAsterisk ? '*' : '')).join(', ')}{/if}{#if titles.length && sackos.length} · {/if}{#if sackos.length}Sacko {sackos.join(', ')}{/if}
    {#each silver as s}<br />Silver star {s.year}: {s.why}{/each}
    {#each titles.filter((y) => legacy.seasons[y].championAsterisk) as y}<br /><span class="fine">* {y}: {legacy.seasons[y].championAsterisk}</span>{/each}
  </p>
{/if}

{#if p.story && p.story !== 'TODO'}<p class="story">{p.story}</p>{/if}
{#each p.anecdotes ?? [] as a}<blockquote>{a}</blockquote>{/each}

{#if links.length}
  <h4>Connected to</h4>
  <ul>
    {#each links as l}
      <li>
        <button class="link pressable" onclick={() => onperson(l.other)}>
          <Avatar id={l.other} size={32} />
          <span><b>{people[l.other].name}</b><small>{l.how}{l.year ? ` · ${l.year}` : ''}</small></span>
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  header {
    display: flex;
    gap: 16px;
    align-items: center;
    margin: 4px 0 18px;
  }
  h3 {
    margin: 0;
    font-size: calc(28px * var(--display-scale));
    line-height: 1.02;
  }
  .sub {
    margin: 4px 0 0;
    color: var(--ink-2);
    font-size: 14px;
  }
  .years {
    display: flex;
    gap: 3px;
  }
  .years i {
    flex: 1;
    height: 8px;
    background: var(--glass-line);
  }
  .years i.on {
    background: var(--tone);
  }
  .cap {
    margin: 8px 0 18px;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.5;
  }
  .fine {
    color: var(--ink-3);
    font-size: 12px;
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 10px;
  }
  .stats div {
    padding: 12px 10px;
    border: 1px solid var(--glass-line);
    background: rgba(255, 255, 255, 0.04);
  }
  .stats b {
    display: block;
    font-family: var(--font-display);
    font-stretch: var(--display-stretch);
    font-size: calc(22px * var(--display-scale));
    font-weight: var(--display-weight);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .stats span {
    font-size: 11px;
    color: var(--ink-2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .story {
    font-size: 16px;
    line-height: 1.55;
  }
  blockquote {
    margin: 0 0 12px;
    padding: 2px 0 2px 14px;
    border-left: 2px solid var(--ink);
    font-weight: 500;
    font-size: 16px;
    line-height: 1.45;
  }
  h4 {
    margin: 22px 0 8px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-2);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .link {
    display: flex;
    gap: 12px;
    align-items: center;
    width: 100%;
    min-height: 48px;
    padding: 6px 0;
    text-align: left;
  }
  .link b {
    display: block;
    font-weight: 600;
    font-size: 15px;
  }
  .link small {
    color: var(--ink-2);
    font-size: 13px;
  }
</style>
