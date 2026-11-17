<script lang="ts">
  import { parseRich } from '../lib/model';

  let { text, onperson }: { text: string; onperson: (id: string) => void } = $props();
  const chunks = $derived(parseRich(text));
</script>

{#each chunks as c}{#if c.person}<button class="name" onclick={() => onperson(c.person!)}>{c.text}</button>{:else}{c.text}{/if}{/each}

<style>
  .name {
    display: inline;
    font-weight: 600;
    color: var(--ink);
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--accent) 70%, transparent);
    text-decoration-thickness: 1.5px;
    text-underline-offset: 3px;
    transition: color var(--dur-micro) var(--ease-out);
  }
  .name:active {
    color: var(--accent);
  }
</style>
