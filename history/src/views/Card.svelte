<script lang="ts">
  import { people, type Card } from '../lib/model';
  import Rich from './Rich.svelte';
  import Avatar from './Avatar.svelte';

  // `full`: names on the in/out chips (otherwise faces only)
  let { card, onperson, full = false }: { card: Card; onperson: (id: string) => void; full?: boolean } = $props();
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

{#if card.kind === 'season'}
    <!-- a season's fun fact: its results are written on the ribbons, so this is all the card holds -->
    <article class="season">
      <p class="kicker"><b class="display">{card.year}</b> Fun fact</p>
      {#if card.funFact}<p class="factonly"><Rich text={card.funFact} {onperson} /></p>{/if}
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
        <!-- who left rides a red arrow off the card (right); who joined, a green arrow into it (from the left) -->
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
    /* left aligned under it, pointing right: into the card */
    align-self: flex-start;
    padding-right: calc(var(--head) + 6px);
    background: linear-gradient(to bottom, #36b26f, #208a50);
    clip-path: polygon(0 0, calc(100% - var(--head)) 0, 100% 50%, calc(100% - var(--head)) 100%, 0 100%);
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
    gap: 6px;
  }
  .kicker {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ink-2);
  }
  .kicker b {
    font-size: calc(20px * var(--display-scale));
    letter-spacing: 0;
    color: var(--ink);
  }
  .factonly {
    font-size: 14px;
  }
</style>
