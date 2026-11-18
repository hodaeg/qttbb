// Burst a pile: each item tries random spots around the pile's centre, moving outward until it
// fits without overlapping the others. Seeded, so the same pile always flares the same way.
// Returns offsets from the centre, plus a small random tilt.

export const hashStr = (s: string) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
};

export function rng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type Spot = { x: number; y: number; rot: number };

/**
 * @param n      how many to place
 * @param c      the pile's centre, on screen
 * @param seed   any string; the same seed gives the same burst
 * @param box    room each item needs (w, h), measured from the avatar's centre: `up` above it, the rest below
 * @param bounds the screen area items may land in
 */
export function scatter(
  n: number,
  c: { x: number; y: number },
  seed: string,
  box: { w: number; h: number; up: number },
  bounds: { left: number; top: number; right: number; bottom: number },
): Spot[] {
  const r = rng(hashStr(seed));
  const placed: { x: number; y: number }[] = [];
  const fits = (x: number, y: number) =>
    Math.hypot(x - c.x, (y - c.y) * 1.3) > 52 && placed.every((p) => Math.abs(p.x - x) > box.w + 4 || Math.abs(p.y - y) > box.h + 2);
  return Array.from({ length: n }, () => {
    let best = { x: c.x, y: c.y };
    for (let k = 0; k < 600; k++) {
      const rad = 70 + k * 0.7 + r() * 50;
      const a = r() * Math.PI * 2;
      const x = Math.min(bounds.right - box.w / 2, Math.max(bounds.left + box.w / 2, c.x + Math.cos(a) * rad));
      const y = Math.min(bounds.bottom - (box.h - box.up), Math.max(bounds.top + box.up, c.y + Math.sin(a) * rad * 1.15));
      best = { x, y };
      if (fits(x, y)) break;
    }
    placed.push(best);
    return { x: best.x - c.x, y: best.y - c.y, rot: (r() - 0.5) * 12 };
  });
}
