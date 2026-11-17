<script lang="ts">
  // A pane of glass with one clipped corner. Three layers, kept as siblings so each can filter
  // what is behind the card: a soft shadow, the frosted pane, and a thin edge that brightens and
  // saturates the colour behind it. Fading is done per layer (--o), because fading a parent would
  // switch the frosting off. A glint runs along the edge as the card moves up the screen (--sheen).
  import type { Snippet } from 'svelte';
  let { children, pad = '16px 18px 18px', full = false }: { children: Snippet; pad?: string; full?: boolean } = $props();
</script>

<div class="glass" class:full>
  <i class="shade"></i>
  <i class="pane"></i>
  <i class="edge"></i>
  <div class="body" style:padding={pad}>{@render children()}</div>
</div>

<style>
  .glass {
    position: relative;
    --t: 1.5px;
    --band: calc(130% - var(--sheen, 0.5) * 160%);
  }
  i {
    position: absolute;
    inset: 0;
    opacity: var(--o, 1);
    pointer-events: none;
  }
  .shade {
    inset: 18px 14px 4px;
    box-shadow: 0 22px 60px 6px rgba(0, 0, 0, 0.55);
  }
  .pane {
    clip-path: polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, 0 100%);
    background:
      linear-gradient(105deg, transparent calc(var(--band) - 34%), rgba(255, 255, 255, 0.075) var(--band), transparent calc(var(--band) + 34%)),
      linear-gradient(165deg, rgba(255, 255, 255, 0.13), transparent 34%),
      var(--glass-tint);
    backdrop-filter: var(--glass-filter);
    -webkit-backdrop-filter: var(--glass-filter);
  }
  .edge {
    /* a frame: the outer outline, then the inner one, with the middle punched out */
    clip-path: polygon(
      evenodd,
      0 0,
      calc(100% - var(--cut)) 0,
      100% var(--cut),
      100% 100%,
      0 100%,
      0 0,
      var(--t) var(--t),
      calc(100% - var(--cut) - var(--t) * 0.41) var(--t),
      calc(100% - var(--t)) calc(var(--cut) + var(--t) * 0.41),
      calc(100% - var(--t)) calc(100% - var(--t)),
      var(--t) calc(100% - var(--t)),
      var(--t) var(--t)
    );
    background:
      linear-gradient(105deg, transparent calc(var(--band) - 9%), var(--glint) var(--band), transparent calc(var(--band) + 9%)),
      linear-gradient(140deg, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.1) 26%, rgba(255, 255, 255, 0.04) 64%, rgba(255, 255, 255, 0.45));
    backdrop-filter: var(--edge-filter);
    -webkit-backdrop-filter: var(--edge-filter);
  }
  .full,
  .full .body {
    height: 100%;
  }
  .body {
    position: relative;
    opacity: var(--o, 1);
  }
</style>
