<script lang="ts">
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';

  let { title = '', onclose, children }: { title?: string; onclose: () => void; children: Snippet } = $props();
  let closing = $state(false);

  function close() {
    if (closing) return;
    closing = true;
    setTimeout(onclose, 240);
  }

  onMount(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const key = (e: KeyboardEvent) => e.key === 'Escape' && close();
    window.addEventListener('keydown', key);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', key);
    };
  });
</script>

<div class="scrim" class:closing onclick={close} role="presentation"></div>
<div class="sheet" class:closing role="dialog" aria-modal="true" aria-label={title || 'Details'}>
  <button class="grab pressable" onclick={close} aria-label="Close"><span></span></button>
  {#if title}<h2>{title}</h2>{/if}
  <div class="body">{@render children()}</div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: var(--scrim);
    animation: fade var(--dur-ui) var(--ease-out);
  }
  .scrim.closing {
    opacity: 0;
    transition: opacity 240ms var(--ease-out);
  }
  .sheet {
    position: fixed;
    z-index: 41;
    left: 0;
    right: 0;
    bottom: 0;
    max-height: 86vh;
    margin: 0 auto;
    max-width: 560px;
    display: flex;
    flex-direction: column;
    background: var(--glass-strong);
    backdrop-filter: blur(24px) saturate(1.3);
    -webkit-backdrop-filter: blur(24px) saturate(1.3);
    border: 1px solid var(--glass-line);
    border-bottom: 0;
    border-radius: 24px 24px 0 0;
    padding-bottom: var(--safe-bottom);
    animation: rise 420ms var(--ease-spring);
  }
  .sheet.closing {
    transform: translateY(105%);
    transition: transform 240ms var(--ease-in-out);
  }
  .grab {
    display: grid;
    place-items: center;
    height: 28px;
    width: 100%;
    flex: none;
  }
  .grab span {
    width: 40px;
    height: 4px;
    border-radius: 2px;
    background: var(--ink-3);
    opacity: 0.6;
  }
  h2 {
    margin: 0 20px 8px;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 26px;
    letter-spacing: -0.01em;
  }
  .body {
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 0 20px 28px;
  }
  @keyframes rise {
    from {
      transform: translateY(100%);
    }
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sheet,
    .scrim {
      animation: none;
    }
  }
</style>
