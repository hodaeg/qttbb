// One light tap of haptic feedback. Android (and anything with the Vibration API) gets a short
// vibration. iOS Safari has no Vibration API, but since iOS 18 toggling a native switch control gives a
// light haptic tick, so there we toggle a hidden one: a <label> wrapping an <input type=checkbox switch>,
// clicked and removed (the same approach as the ios-haptics library).
//
// iOS only honours it during a user gesture, so call haptic() synchronously inside a tap/click handler.
// From a scroll, a timer or an $effect it's silently ignored there (Android still buzzes).
// Calls within 120ms of the last are dropped, so several things at once make one tap.
let last = 0;

export function haptic(ms = 10) {
  const now = performance.now();
  if (now - last < 120) return;
  last = now;
  try {
    if (typeof navigator.vibrate === 'function') {
      if (navigator.userActivation?.hasBeenActive === false) return; // blocked before any tap anyway
      navigator.vibrate(ms);
      return;
    }
  } catch {}
  try {
    const label = document.createElement('label');
    label.ariaHidden = 'true';
    label.style.display = 'none';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.setAttribute('switch', '');
    label.appendChild(input);
    document.head.appendChild(label);
    label.click();
    document.head.removeChild(label);
  } catch {}
}
