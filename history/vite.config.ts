import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served from https://hodaeg.github.io/qttbb/ in production.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/qttbb/' : '/',
  plugins: [svelte()],
  server: { port: Number(process.env.PORT) || 5173 },
  // Don't minify CSS. Vite 8 minifies with Lightning CSS, which was dropping the unprefixed
  // `backdrop-filter` (leaving only `-webkit-backdrop-filter`, which Firefox and current Edge ignore, so
  // no glass blurred) and re-emitting a rule after the override meant to beat it. It's ~10 KB gzipped
  // either way.
  build: { cssMinify: false },
}));
