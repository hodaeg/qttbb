<script lang="ts">
  import Story from './views/Story.svelte';
  import Sheet from './views/Sheet.svelte';
  import PersonPanel from './views/PersonPanel.svelte';

  let person = $state<string | null>(null);
  let photo = $state<{ src: string; alt: string } | null>(null);

  let story: ReturnType<typeof Story> | undefined = $state();
  // someone holding a column right now opens it; the sheet is for everyone else
  function openPerson(id: string) {
    photo = null;
    if (story?.show(id)) {
      person = null;
      return;
    }
    person = id;
  }
</script>

<Story bind:this={story} onperson={openPerson} onphoto={(p) => (photo = p)} />

{#if photo}
  <Sheet onclose={() => (photo = null)}>
    <figure class="ph">
      <img src={import.meta.env.BASE_URL + photo.src} alt={photo.alt} />
      <figcaption>{photo.alt}</figcaption>
    </figure>
  </Sheet>
{/if}

{#if person}
  <Sheet onclose={() => (person = null)}>
    <PersonPanel id={person} onperson={openPerson} />
  </Sheet>
{/if}

<style>
  .ph {
    margin: 0;
  }
  .ph img {
    display: block;
    width: 100%;
    height: auto;
  }
  .ph figcaption {
    margin-top: 10px;
    font-size: 13px;
    color: var(--ink-2);
  }
</style>
