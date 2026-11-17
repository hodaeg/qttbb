<script lang="ts">
  import { people, type Card } from '../lib/model';
  import Rich from './Rich.svelte';
  import Avatar from './Avatar.svelte';
  import Glass from './Glass.svelte';

  let { card, onperson }: { card: Card; onperson: (id: string) => void } = $props();
  let open = $state(false);
  const long = $derived((card.quote?.text.length ?? 0) > 220);
  const first = (id: string) => people[id].nickname ?? people[id].name.split(' ')[0];
</script>

{#if card.kind === 'season' && card.season}
  {@const s = card.season}
  <Glass pad="12px 14px">
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
  </Glass>
{:else}
  <Glass>
    <article class:beat={card.kind === 'beat'}>
      <span class="yr">{card.year}</span>
      <h3 class="display">{card.title}</h3>
      {#if card.body}<p><Rich text={card.body} {onperson} /></p>{/if}

      {#if card.quote}
        <blockquote class:clamp={long && !open}>
          {card.quote.text}
          {#if card.quote.by || card.quote.context}
            <cite>{#if card.quote.by}— {first(card.quote.by)}{/if}{#if card.quote.context}{card.quote.by ? ', ' : ''}{card.quote.by ? card.quote.context[0].toLowerCase() + card.quote.context.slice(1) : card.quote.context}{/if}</cite>
          {/if}
        </blockquote>
        {#if long}<button class="more pressable" onclick={() => (open = !open)}>{open ? 'Show less' : 'Read the whole message'}</button>{/if}
      {/if}

      {#if card.out?.length || (card.in?.length && !card.founders)}
        <div class="moves">
          {#if card.out?.length}
            <div><small>Out</small>{#each card.out as id}<button class="chip out pressable" onclick={() => onperson(id)}><Avatar {id} size={20} />{first(id)}</button>{/each}</div>
          {/if}
          {#if card.in?.length}
            <div><small>In</small>{#each card.in as id}<button class="chip pressable" onclick={() => onperson(id)}><Avatar {id} size={20} />{first(id)}{card.returns?.includes(id) ? ' ↩' : ''}</button>{/each}</div>
          {/if}
        </div>
      {/if}

      {#if card.funFact}<p class="fact"><b>Fun fact</b> <Rich text={card.funFact} {onperson} /></p>{/if}
    </article>
  </Glass>
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
    margin: 4px 0 8px;
    font-size: calc(23px * var(--display-scale));
    line-height: 1.06;
  }
  .beat h3 {
    font-size: calc(31px * var(--display-scale));
    line-height: 1;
  }
  p {
    margin: 0;
    font-size: 15.5px;
    line-height: 1.52;
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
  blockquote.clamp {
    display: -webkit-box;
    -webkit-line-clamp: 5;
    line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  cite {
    display: block;
    margin-top: 8px;
    font-style: normal;
    font-weight: 400;
    font-size: 13px;
    color: var(--ink-2);
  }
  .more {
    margin-top: 10px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .moves {
    display: grid;
    gap: 8px;
    margin-top: 14px;
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
  .chip.out {
    color: var(--ink-2);
  }
  .fact {
    margin-top: 14px;
    padding-top: 12px;
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
