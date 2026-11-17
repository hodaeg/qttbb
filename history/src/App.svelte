<script lang="ts">
  import Story from './views/Story.svelte';
  import Sheet from './views/Sheet.svelte';
  import PersonPanel from './views/PersonPanel.svelte';
  import AlumniPanel from './views/AlumniPanel.svelte';
  import CardView from './views/Card.svelte';
  import type { Card } from './lib/model';

  let person = $state<string | null>(null);
  let showAlumni = $state(false);
  let card = $state<Card | null>(null);

  function openPerson(id: string) {
    showAlumni = false;
    card = null;
    person = id;
  }
</script>

<Story onperson={openPerson} onalumni={() => (showAlumni = true)} oncard={(c) => (card = c)} />

{#if card}
  <Sheet onclose={() => (card = null)}>
    <CardView {card} onperson={openPerson} full />
  </Sheet>
{/if}

{#if showAlumni}
  <Sheet title="Alumni" onclose={() => (showAlumni = false)}>
    <AlumniPanel onperson={openPerson} />
  </Sheet>
{/if}

{#if person}
  <Sheet onclose={() => (person = null)}>
    <PersonPanel id={person} onperson={openPerson} />
  </Sheet>
{/if}
