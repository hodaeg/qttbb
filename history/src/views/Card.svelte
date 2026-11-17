<script lang="ts">
  import { people, type Card } from '../lib/model';
  import Rich from './Rich.svelte';
  import Avatar from './Avatar.svelte';

  // `full`: names on the in/out chips. In the tray they are faces only. (Long cards scroll in the tray.)
  let { card, onperson, full = false }: { card: Card; onperson: (id: string) => void; full?: boolean } = $props();
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

{#if card.kind === 'season' && card.season}
  {@const s = card.season}
    <article class="season">
      <span class="yr">{card.year}{s.source === 'sleeper' ? '*' : ''}</span>
      {#if s.champion}
        <button class="line pressable" onclick={() => onperson(s.champion!)}>
          <Avatar id={s.champion} size={28} /><span><small>Champion</small><b class="display">{people[s.champion].name}</b></span>
        </button>
      {:else}
        <p class="tbd">{s.complete ? 'Champion not on record yet' : 'Season in progress'}</p>
      {/if}
      {#if s.sacko}
        <button class="line pressable" onclick={() => onperson(s.sacko!)}>
          <Avatar id={s.sacko} size={28} /><span><small>Sacko</small><b class="display">{people[s.sacko].name}</b></span>
        </button>
      {/if}
    </article>
{:else}
    <article class:beat={card.kind === 'beat'}>
      <span class="yr">{card.year}</span>
      <h3 class="display">{card.title}</h3>
      {#if card.body}<p><Rich text={card.body} {onperson} /></p>{/if}

      {#if card.quote}
        <blockquote>
          {card.quote.text}
          {#if card.quote.by || card.quote.context}
            <cite>{#if card.quote.by}— {first(card.quote.by)}{/if}{#if card.quote.context}{card.quote.by ? ', ' : ''}{card.quote.by ? card.quote.context[0].toLowerCase() + card.quote.context.slice(1) : card.quote.context}{/if}</cite>
          {/if}
        </blockquote>
      {/if}

      {#if card.out?.length || (card.in?.length && !card.founders)}
        <div class="moves" class:compact={!full}>
          {#if card.out?.length}
            <div><small>Out</small>{#each card.out as id}<button class="chip out pressable" onclick={() => onperson(id)}><Avatar {id} size={20} /><span>{first(id)}</span></button>{/each}</div>
          {/if}
          {#if card.in?.length}
            <div><small>In</small>{#each card.in as id}<button class="chip pressable" onclick={() => onperson(id)}><Avatar {id} size={20} /><span>{first(id)}{card.returns?.includes(id) ? ' ↩' : ''}</span></button>{/each}</div>
          {/if}
        </div>
      {/if}

      {#if card.funFact}<p class="fact"><b>Fun fact</b> <Rich text={card.funFact} {onperson} /></p>{/if}
    </article>
{/if}

<style>
  .yr {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.16em;
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  h3 {
    margin: 2px 0 6px;
    font-size: calc(22px * var(--display-scale));
    line-height: 1.06;
  }
  .beat h3 {
    font-size: calc(26px * var(--display-scale));
    line-height: 1;
  }
  p {
    margin: 0;
    font-size: 15px;
    line-height: 1.46;
    color: var(--ink);
  }
  blockquote {
    margin: 12px 0 0;
    padding-left: 14px;
    border-left: 2px solid var(--ink);
    font-size: 16px;
    font-weight: 500;
    line-height: 1.46;
    white-space: pre-line;
  }
  cite {
    display: block;
    margin-top: 8px;
    font-style: normal;
    font-weight: 400;
    font-size: 13px;
    color: var(--ink-2);
  }
  .moves {
    display: grid;
    gap: 6px;
    margin-top: 12px;
  }
  .moves div {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .moves small {
    width: 26px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    height: 30px;
    padding: 0 10px 0 5px;
    border: 1px solid var(--glass-line);
    background: rgba(255, 255, 255, 0.05);
    font-size: 13px;
    font-weight: 600;
  }
  /* in the tray: one row, faces only (names are in the full card) */
  .moves.compact {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
  }
  .moves.compact small {
    width: auto;
    margin-right: 2px;
  }
  .moves.compact .chip {
    padding: 0 4px;
    height: 28px;
  }
  .moves.compact .chip > span:last-child {
    display: none;
  }
  .chip.out {
    color: var(--ink-2);
  }
  .fact {
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid var(--glass-line);
    font-size: 14px;
    color: var(--ink-2);
  }
  .fact b {
    margin-right: 4px;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink);
  }
  .season {
    display: grid;
    gap: 8px;
  }
  .line {
    display: flex;
    gap: 10px;
    align-items: center;
    text-align: left;
    min-height: 34px;
  }
  .line small {
    display: block;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .line b {
    font-size: calc(17px * var(--display-scale));
    line-height: 1.05;
  }
  .tbd {
    font-size: 13px;
    color: var(--ink-3);
  }
</style>
