// One light tap of haptic feedback. Android (and anything with the Vibration API) gets a short
// vibration. iOS Safari has no Vibration API, but since iOS 18 toggling a native switch control gives a
// light haptic tick, so there we toggle a hidden one. That works best inside a tap; during a scroll
// iOS may not fire it. Calls within 120ms of the last are dropped, so several things landing at once
// make one tap, not a stack of them.
let last = 0;
let label: HTMLLabelElement | null = null;

export function haptic(ms = 10) {
  const now = performance.now();
  if (now - last < 120) return;
  last = now;
  try {
    if (typeof navigator.vibrate === 'function') {
      if (navigator.userActivation?.hasBeenActive === false) return; // vibrating before any tap is blocked anyway
      navigator.vibrate(ms);
      return;
    }
  } catch {}
  try {
    if (!label) {
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.setAttribute('switch', '');
      input.id = 'haptic-switch';
      input.tabIndex = -1;
      input.setAttribute('aria-hidden', 'true');
      label = document.createElement('label');
      label.htmlFor = input.id;
      label.setAttribute('aria-hidden', 'true');
      const hide = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0;pointer-events:none';
      input.style.cssText = hide;
      label.style.cssText = hide;
      document.body.append(input, label);
    }
    label.click();
  } catch {}
}
