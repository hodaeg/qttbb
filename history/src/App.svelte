<script lang="ts">
  import Story from './views/Story.svelte';
  import Sheet from './views/Sheet.svelte';
  import PersonPanel from './views/PersonPanel.svelte';
  import Lock from './views/Lock.svelte';

  let person = $state<string | null>(null);

  let story: ReturnType<typeof Story> | undefined = $state();

  // the front door; once it's opened on a device, it stays open there
  let openedHere = false;
  try {
    openedHere = localStorage.getItem('qttbb-unlocked') === '646cb782633388c0238caa63c765db3109e4ad6847db3f888689ef9eb271ea80';
  } catch {}
  let locked = $state(!openedHere);
  let veiled = $state(!openedHere); // the story is blurred behind the lock, and comes into focus as it opens
  // someone holding a column right now opens it; the sheet is for everyone else
  function openPerson(id: string) {
    if (story?.show(id)) {
      person = null;
      return;
    }
    person = id;
  }
</script>

<Story bind:this={story} onperson={openPerson} veiled={veiled} />

{#if locked}
  <Lock onunlock={() => (locked = false)} onopening={() => (veiled = false)} />
{/if}

{#if person}
  <Sheet onclose={() => (person = null)}>
    <PersonPanel id={person} onperson={openPerson} />
  </Sheet>
{/if}
