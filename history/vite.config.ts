import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Served from https://hodaeg.github.io/qttbb/ in production.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/qttbb/' : '/',
  plugins: [svelte()],
  server: { port: Number(process.env.PORT) || 5173 },
}));
