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
      <h3 class="display">{card.year}{s.source === 'sleeper' ? '*' : ''}</h3>
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
        <!-- who left rides a red arrow out to the right; who joined, a green arrow in from the right -->
        <div class="moves" class:compact={!full}>
          {#if card.out?.length}
            <div class="arrow out" role="group" aria-label="Out">{#each card.out as id}<button class="chip pressable" aria-label="{people[id].name} (out)" onclick={() => onperson(id)}><Avatar {id} size={22} /><span>{first(id)}</span></button>{/each}</div>
          {/if}
          {#if card.in?.length}
            <div class="arrow in" role="group" aria-label="In">{#each card.in as id}<button class="chip pressable" aria-label="{people[id].name} (in{card.returns?.includes(id) ? ', returning' : ''})" onclick={() => onperson(id)}><Avatar {id} size={22} /><span>{first(id)}{card.returns?.includes(id) ? ' ↩' : ''}</span></button>{/each}</div>
          {/if}
        </div>
      {/if}

      {#if card.funFact}<p class="fact"><b>Fun fact</b> <Rich text={card.funFact} {onperson} /></p>{/if}
    </article>
{/if}

<style>
  h3 {
    margin: 4px 0 6px;
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
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 12px;
  }
  .arrow {
    --head: 13px;
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    align-items: center;
    max-width: 100%;
    padding: 4px 6px;
  }
  .arrow.out {
    /* right aligned, pointing out to the right */
    align-self: flex-end;
    padding-right: calc(var(--head) + 6px);
    background: linear-gradient(to bottom, #e0474d, #b8282e);
    clip-path: polygon(0 0, calc(100% - var(--head)) 0, 100% 50%, calc(100% - var(--head)) 100%, 0 100%);
  }
  .arrow.in {
    /* left aligned under it, pointing in to the left */
    align-self: flex-start;
    padding-left: calc(var(--head) + 6px);
    background: linear-gradient(to bottom, #36b26f, #208a50);
    clip-path: polygon(var(--head) 0, 100% 0, 100% 100%, var(--head) 100%, 0 50%);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 24px;
    font-size: 13px;
    font-weight: 600;
    color: #fff;
  }
  /* in the tray: faces only */
  .moves.compact .chip > span:last-child {
    display: none;
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
