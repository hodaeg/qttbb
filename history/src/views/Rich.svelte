<script lang="ts">
  import { parseRich, people } from '../lib/model';

  let { text, onperson }: { text: string; onperson: (id: string) => void } = $props();
  const chunks = $derived(parseRich(text));
  // members' names wear their avatar colour; friends of the league stay plain
  const tone = (id: string) => (people[id]?.role === 'member' ? people[id].color : undefined);
</script>

{#each chunks as c}{#if c.person}<button class="name" class:member={!!tone(c.person)} style:--tone={tone(c.person)} onclick={() => onperson(c.person!)}>{c.text}</button>{:else}{c.text}{/if}{/each}

<style>
  .name {
    display: inline;
    font-weight: 600;
    color: var(--ink);
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--ink) 55%, transparent);
    text-decoration-thickness: 1.5px;
    text-underline-offset: 3px;
    transition: opacity var(--dur-micro) var(--ease-out);
  }
  .name.member {
    /* lifted a little toward the ink colour so it stays readable on the glass */
    color: color-mix(in srgb, var(--tone) 78%, var(--ink));
    text-decoration-color: var(--tone);
  }
  .name:active {
    opacity: 0.7;
  }
</style>
