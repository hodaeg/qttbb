<script lang="ts">
  // The card tray: docked under the columns so nothing ever covers them. One pane of glass that
  // stays put; the cards change inside it as the playhead moves (two overlap while handing over).
  // It is only as tall as the card needs (up to the tray's maximum); a card that still doesn't fit
  // scrolls inside the glass. The stage springs the height (`top`) so the ribbons' shadow follows.
  import { type Card, type Layout } from '../lib/model';
  import Glass from './Glass.svelte';
  import CardView from './Card.svelte';

  type Item = { card: Card; i: number; o: number; dy: number; t: number };
  let {
    L, items, opacity, era, top, onperson, want = $bindable(0),
  }: { L: Layout; items: Item[]; opacity: number; era: string; top: number; onperson: (id: string) => void; want?: number } = $props();

  const HEAD = 30;
  const main = $derived(items.reduce<Item | null>((m, x) => (!m || x.o > m.o ? x : m), null));
  const siblings = $derived(main ? (L.perYear[main.card.year] ?? []) : []);

  // natural height of each card's content, measured
  let heights = $state<Record<number, number>>({});
  $effect(() => {
    const h = main ? heights[main.i] : undefined;
    want = h ? HEAD + h : L.trayH;
  });
  function measure(node: HTMLElement, i: number) {
    const ro = new ResizeObserver(() => (heights[i] = node.offsetHeight + 14));
    ro.observe(node);
    return { destroy: () => ro.disconnect() };
  }
  // a fade at the bottom edge while there is more to scroll
  function more(node: HTMLElement) {
    const check = () => node.classList.toggle('more', node.scrollTop + node.clientHeight < node.scrollHeight - 4);
    const ro = new ResizeObserver(check);
    ro.observe(node);
    if (node.firstElementChild) ro.observe(node.firstElementChild);
    node.addEventListener('scroll', check, { passive: true });
    return { destroy: () => (ro.disconnect(), node.removeEventListener('scroll', check)) };
  }
  const h = $derived(L.vh - 10 - top);
</script>

<div
  class="tray"
  style:width="{L.trayW}px"
  style:height="{h}px"
  style:--o={opacity}
  style:--sheen={main ? main.t : 0.5}
  style:pointer-events={opacity > 0.6 ? 'auto' : 'none'}
  style:transform="translate3d({L.padL}px,{top + (1 - opacity) * 24}px,0)"
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
        use:more
        style:opacity={it.o}
        style:pointer-events={it.o > 0.6 ? 'auto' : 'none'}
        style:transform="translate3d(0,{it.dy}px,0)"
      >
        <div use:measure={it.i}><CardView card={it.card} {onperson} /></div>
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
    padding: 0 18px 14px;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-width: none;
    will-change: transform, opacity;
  }
  .slot::-webkit-scrollbar {
    display: none;
  }
  .slot:global(.more) {
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 34px), transparent);
    mask-image: linear-gradient(to bottom, #000 calc(100% - 34px), transparent);
  }
</style>
