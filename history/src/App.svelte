<script lang="ts">
  import Story from './views/Story.svelte';
  import Sheet from './views/Sheet.svelte';
  import PersonPanel from './views/PersonPanel.svelte';
  import AlumniPanel from './views/AlumniPanel.svelte';

  let person = $state<string | null>(null);
  let showAlumni = $state(false);

  function openPerson(id: string) {
    showAlumni = false;
    person = id;
  }
</script>

<Story onperson={openPerson} onalumni={() => (showAlumni = true)} />

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
