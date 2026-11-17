<script lang="ts">
  // A pane of glass: frosted, with a soft rim of light along the top edge and a quiet shadow.
  // Two layers, kept as siblings so the frost can filter what is behind the card. Fading is done
  // per layer (--o), because fading a parent would switch the frosting off.
  import type { Snippet } from 'svelte';
  let { children, pad = '16px 18px 18px', full = false }: { children: Snippet; pad?: string; full?: boolean } = $props();
</script>

<div class="glass" class:full>
  <i class="pane"></i>
  <div class="body" style:padding={pad}>{@render children()}</div>
</div>

<style>
  .glass {
    position: relative;
  }
  i {
    position: absolute;
    inset: 0;
    opacity: var(--o, 1);
    pointer-events: none;
  }
  .pane {
    background:
      linear-gradient(to bottom, rgba(255, 255, 255, 0.06), transparent 40%),
      var(--glass-tint);
    backdrop-filter: var(--glass-filter);
    -webkit-backdrop-filter: var(--glass-filter);
    box-shadow: var(--glass-rim), var(--glass-lift);
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
