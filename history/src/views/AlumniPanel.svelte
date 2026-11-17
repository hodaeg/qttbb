<script lang="ts">
  import { alumni, people, tenures, yearsLabel } from '../lib/model';
  import Avatar from './Avatar.svelte';

  let { onperson }: { onperson: (id: string) => void } = $props();
  const list = $derived([...alumni].sort((a, b) => tenures[a][0].start - tenures[b][0].start || tenures[a][0].slot - tenures[b][0].slot));
</script>

<p class="lede">{list.length} people have played and moved on.</p>
<ul>
  {#each list as id}
    <li>
      <button class="row pressable" onclick={() => onperson(id)}>
        <Avatar {id} size={40} />
        <span><b>{people[id].name}</b><small>{yearsLabel(id)}{people[id].founder ? ' · founder' : ''}</small></span>
      </button>
    </li>
  {/each}
</ul>

<style>
  .lede {
    margin: 0 0 10px;
    color: var(--ink-2);
    font-size: 14px;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .row {
    display: flex;
    gap: 14px;
    align-items: center;
    width: 100%;
    min-height: 56px;
    text-align: left;
  }
  b {
    display: block;
    font-size: 16px;
    font-weight: 600;
  }
  small {
    color: var(--ink-2);
    font-size: 13px;
  }
</style>
