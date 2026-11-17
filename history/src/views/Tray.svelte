<script lang="ts">
  // The card tray: docked under the columns so nothing ever covers them. One pane of glass that
  // stays put; the cards change inside it as the playhead moves (two overlap while handing over).
  import { type Card, type Layout } from '../lib/model';
  import Glass from './Glass.svelte';
  import CardView from './Card.svelte';

  type Item = { card: Card; i: number; o: number; dy: number; t: number };
  let { L, items, opacity, era, onperson, oncard }: { L: Layout; items: Item[]; opacity: number; era: string; onperson: (id: string) => void; oncard: (c: Card) => void } = $props();

  const main = $derived(items.reduce<Item | null>((m, x) => (!m || x.o > m.o ? x : m), null));
  const siblings = $derived(main ? (L.perYear[main.card.year] ?? []) : []);

  // Mark a card that doesn't fit, so it can offer "Read more".
  function fit(node: HTMLElement) {
    const check = () => node.classList.toggle('over', node.scrollHeight > node.clientHeight + 6);
    const ro = new ResizeObserver(check);
    ro.observe(node);
    if (node.firstElementChild) ro.observe(node.firstElementChild);
    return { destroy: () => ro.disconnect() };
  }
</script>

<div
  class="tray"
  style:width="{L.trayW}px"
  style:height="{L.trayH}px"
  style:--o={opacity}
  style:--sheen={main ? main.t : 0.5}
  style:pointer-events={opacity > 0.6 ? 'auto' : 'none'}
  style:transform="translate3d({L.padL}px,{L.trayTop + (1 - opacity) * 24}px,0)"
>
  <Glass full pad="0">
    <div class="head">
      <span>{era}</span>
      {#if siblings.length > 1}
        <span class="pips" aria-hidden="true">{#each siblings as c}<i class:on={c === main?.card}></i>{/each}</span>
      {/if}
    </div>
    {#each items as it (it.i)}
      <div
        class="slot"
        class:long={(it.card.quote?.text.length ?? 0) > 160}
        use:fit
        style:opacity={it.o}
        style:pointer-events={it.o > 0.6 ? 'auto' : 'none'}
        style:transform="translate3d(0,{it.dy}px,0)"
      >
        <div><CardView card={it.card} {onperson} /></div>
        <button class="more pressable" onclick={() => oncard(it.card)}>Read more</button>
      </div>
    {/each}
  </Glass>
</div>

<style>
  .tray {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 5;
    will-change: transform; /* never fade this wrapper: it would switch the glass off. Layers fade via --o */
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 30px;
    padding: 0 calc(var(--cut) + 8px) 0 18px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ink-3);
  }
  .pips {
    display: flex;
    gap: 4px;
  }
  .pips i {
    width: 10px;
    height: 2px;
    background: var(--ink-3);
    opacity: 0.5;
  }
  .pips i.on {
    background: var(--ink);
    opacity: 1;
  }
  .slot {
    position: absolute;
    inset: 30px 0 0 0;
    padding: 0 18px 12px;
    overflow: hidden;
    will-change: transform, opacity;
  }
  .more {
    display: none;
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    height: 64px;
    padding: 0 18px 14px;
    align-items: flex-end;
    justify-content: flex-end;
    background: linear-gradient(to bottom, transparent, var(--glass-strong) 62%);
    font-size: 13px;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .slot:global(.over) .more,
  .slot.long .more {
    display: flex;
  }
</style>
