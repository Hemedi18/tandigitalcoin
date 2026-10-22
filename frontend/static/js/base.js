/**
 * Global frontend scripts (loaded on every page).
 * Keep lightweight: helpers only; feature logic lives in explorer.js / docs.
 */
(function () {
  'use strict';

  /**
   * Copy text to clipboard; shows a brief alert for accessibility.
   * @param {string} text
   */
  window.tancoinCopy = function (text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        alert((window.TANCOIN_I18N && window.TANCOIN_I18N.copied) || 'Copied');
      });
      return;
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      alert((window.TANCOIN_I18N && window.TANCOIN_I18N.copied) || 'Copied');
    } finally {
      document.body.removeChild(ta);
    }
  };

  function wireSiteNavDrawer() {
    var nav = document.getElementById('site-nav-main');
    var toggle = document.getElementById('nav-menu-toggle');
    var scrim = document.getElementById('nav-scrim');
    if (!nav || !toggle) return;

    function setOpen(open) {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      nav.classList.toggle('is-open', open);
      if (scrim) scrim.hidden = !open;
      document.documentElement.classList.toggle('nav-drawer-open', open);
    }

    function close() {
      setOpen(false);
    }

    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    if (scrim) scrim.addEventListener('click', close);
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        if (window.matchMedia('(max-width: 960px)').matches) close();
      });
    });
    window.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && nav.classList.contains('is-open')) close();
    });
  }

  function wireDashNavDrawer() {
    var root = document.getElementById('dash-root');
    var toggle = document.getElementById('dash-menu-toggle');
    var sidebar = document.getElementById('dash-sidebar');
    var scrim = document.getElementById('dash-scrim');
    if (!root || !toggle || !sidebar) return;

    function setOpen(open) {
      root.classList.toggle('dash-nav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (scrim) scrim.hidden = !open;
      document.documentElement.classList.toggle('dash-drawer-open', open);
    }

    function close() {
      setOpen(false);
    }

    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    if (scrim) scrim.addEventListener('click', close);
    sidebar.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        if (window.matchMedia('(max-width: 900px)').matches) close();
      });
    });
    window.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && root.classList.contains('dash-nav-open')) close();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    wireSiteNavDrawer();
    wireDashNavDrawer();
  });
})();
