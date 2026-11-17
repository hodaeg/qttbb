<script lang="ts">
  import { people, isCurrent } from '../lib/model';

  let { id, size = 30 }: { id: string; size?: number } = $props();
  const p = $derived(people[id]);
  const src = $derived(p.avatar ? import.meta.env.BASE_URL + p.avatar : null);
  const tone = $derived(p.role === 'outsider' ? 'var(--ink-3)' : (p.color ?? 'var(--ink-3)'));
</script>

<span
  class="avatar"
  class:alum={p.role === 'member' && !isCurrent(id)}
  class:outsider={p.role === 'outsider'}
  style:width="{size}px"
  style:height="{size}px"
  style:font-size="{Math.max(8, size * 0.36)}px"
  style:--tone={tone}
>
  {#if src}<img {src} alt="" loading="lazy" />{:else}{p.initials}{/if}
</span>

<style>
  .avatar {
    display: inline-grid;
    place-items: center;
    flex: none;
    border-radius: 50%;
    overflow: hidden;
    background: var(--tone);
    color: #fff;
    font-weight: 700;
    letter-spacing: 0.02em;
    line-height: 1;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
    box-shadow:
      0 0 0 1.5px var(--bg),
      0 0 0 2.5px color-mix(in srgb, var(--tone) 70%, white 30%);
  }
  .avatar.alum {
    background: color-mix(in srgb, var(--tone) 55%, #777 45%);
  }
  .avatar.outsider {
    background: transparent;
    color: var(--ink-2);
    text-shadow: none;
    box-shadow: 0 0 0 1.5px var(--ink-3);
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
</style>
