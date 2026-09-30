/* Apply the saved appearance before styles paint; independent of authentication. */
(() => {
  'use strict';
  const key = 'lineWorkspaceAppearance';
  const valid = value => ['system', 'light', 'dark'].includes(value) ? value : 'system';
  const system = matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { preference = valid(localStorage.getItem(key)); } catch (_) {}
  function apply() {
    const theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.appearance = preference;
    document.querySelectorAll('[data-appearance]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.appearance === preference));
    });
    document.querySelectorAll('.brand-logo, .topbar-brand img').forEach(img => {
      img.src = `/assets/brand/line-automation-logo-${theme}.png`;
    });
    const favicon = document.querySelector('#theme-favicon');
    if (favicon) favicon.href = `/assets/brand/line-automation-logo-${theme}.ico`;
  }
  apply();
  system.addEventListener('change', apply);
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { preference = valid(event.newValue); apply(); }
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-appearance]').forEach(button => {
      button.addEventListener('click', () => {
        preference = valid(button.dataset.appearance);
        try { localStorage.setItem(key, preference); } catch (_) {}
        apply();
      });
    });
    apply();
  });
})();
