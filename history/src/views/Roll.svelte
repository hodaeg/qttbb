<script lang="ts">
  // A number that rolls like an odometer: only the digits that change move. Going forward the old
  // digit rolls up and out and the new one rolls up in from below; going back, the other way.
  // 2018 -> 2019 rolls the 8 into a 9; 2019 -> 2020 rolls the last two.
  import { cubicOut } from 'svelte/easing';
  let { value }: { value: number | string } = $props();

  let last = NaN;
  let dir = 1; // read by the transitions when they start
  const chars = $derived.by(() => {
    const v = Number(value);
    if (!Number.isNaN(v) && v !== last) {
      if (!Number.isNaN(last)) dir = v > last ? 1 : -1;
      last = v;
    }
    return String(value).split('');
  });
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function rollIn(_: Element) {
    const d = dir;
    return {
      duration: reduced ? 0 : 460,
      easing: cubicOut,
      css: (t: number, u: number) => `transform: translateY(${u * d * 100}%) scaleY(${1 + u * 0.18}); filter: blur(${u * 1.4}px); opacity: ${t}`,
    };
  }
  function rollOut(_: Element) {
    const d = dir;
    return {
      duration: reduced ? 0 : 380,
      easing: cubicOut,
      css: (t: number, u: number) => `transform: translateY(${-u * d * 100}%) scaleY(${1 + u * 0.18}); filter: blur(${u * 1.4}px); opacity: ${t}`,
    };
  }
</script>

<span class="roll" aria-label={String(value)}>
  {#each chars as c, i (i)}
    <span class="d" aria-hidden="true">{#key c}<span class="c" in:rollIn out:rollOut>{c}</span>{/key}</span>
  {/each}
</span>

<style>
  .roll {
    display: inline-flex;
    font-variant-numeric: tabular-nums;
  }
  .d {
    display: inline-grid;
    overflow: clip;
    overflow-clip-margin: 0.04em;
  }
  .c {
    grid-area: 1 / 1;
    display: block;
    transform-origin: 50% 50%;
  }
</style>
