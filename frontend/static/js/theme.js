/**
 * Site-wide appearance: persists to localStorage, applies data-theme on <html>.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'tancoin_theme';
  var DEFAULT_THEME = 'dark';
  var escapeBound = false;
  var VALID = {
    dark: true,
    light: true,
    gold: true,
    ocean: true,
    pink: true,
    aurora: true,
    sunset: true,
    midnight: true,
    forest: true,
  };

  function normalizeTheme(id) {
    if (!id || !VALID[id]) return DEFAULT_THEME;
    return id;
  }

  function readStored() {
    try {
      return normalizeTheme(localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      return DEFAULT_THEME;
    }
  }

  function writeStored(id) {
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch (e) {
      /* ignore */
    }
  }

  function applyTheme(id) {
    var theme = normalizeTheme(id);
    var root = document.documentElement;
    if (theme === DEFAULT_THEME) {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
    writeStored(theme);
    try {
      window.dispatchEvent(new CustomEvent('tancoin-theme', { detail: { theme: theme } }));
    } catch (e) {
      /* ignore */
    }
    syncPickers(theme);
  }

  function currentTheme() {
    var attr = document.documentElement.getAttribute('data-theme');
    return normalizeTheme(attr || readStored());
  }

  function syncPickers(theme) {
    var pickers = document.querySelectorAll('[data-theme-picker]');
    for (var p = 0; p < pickers.length; p++) {
      var picker = pickers[p];
      var opts = picker.querySelectorAll('[data-theme-set]');
      for (var i = 0; i < opts.length; i++) {
        var btn = opts[i];
        var id = btn.getAttribute('data-theme-set');
        var active = id === theme || (theme === DEFAULT_THEME && id === DEFAULT_THEME);
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
      }
    }
  }

  /** Panel may be reparented to document.body while open. */
  function themePanel(picker) {
    var inside = picker.querySelector('[data-theme-panel]');
    if (inside) return inside;
    return document.getElementById('tancoin-theme-listbox');
  }

  function closePicker(picker) {
    var trigger = picker.querySelector('[data-theme-trigger]');
    var panel = themePanel(picker);
    if (!trigger || !panel) return;
    trigger.setAttribute('aria-expanded', 'false');
    panel.hidden = true;
    panel.classList.remove('theme-picker__panel--open');
    var bd = document.querySelector('.theme-picker__backdrop[data-theme-backdrop-root]');
    if (bd) bd.remove();
    if (panel.parentNode !== picker) {
      picker.appendChild(panel);
    }
    document.documentElement.classList.remove('theme-modal-open');
  }

  function openPicker(picker) {
    var trigger = picker.querySelector('[data-theme-trigger]');
    var panel = themePanel(picker);
    if (!trigger || !panel) return;
    trigger.setAttribute('aria-expanded', 'true');
    document.documentElement.classList.add('theme-modal-open');
    var bd = document.createElement('button');
    bd.type = 'button';
    bd.className = 'theme-picker__backdrop';
    bd.setAttribute('data-theme-backdrop-root', '');
    bd.setAttribute(
      'aria-label',
      (window.TANCOIN_THEME_I18N && window.TANCOIN_THEME_I18N.closeBackdrop) || 'Close'
    );
    document.body.appendChild(bd);
    document.body.appendChild(panel);
    panel.hidden = false;
    panel.classList.add('theme-picker__panel--open');
    bd.addEventListener('click', function () {
      closePicker(picker);
    });
  }

  function wirePicker(picker) {
    var trigger = picker.querySelector('[data-theme-trigger]');
    var panel = themePanel(picker);
    if (!trigger || !panel) return;

    var closeBtn = panel.querySelector('[data-theme-close]');
    if (closeBtn) {
      closeBtn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        closePicker(picker);
        trigger.focus();
      });
    }

    trigger.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var open = trigger.getAttribute('aria-expanded') === 'true';
      if (open) {
        closePicker(picker);
      } else {
        openPicker(picker);
      }
    });

    panel.addEventListener('click', function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      var opt = t.closest('[data-theme-set]');
      if (!opt || !panel.contains(opt)) return;
      var next = opt.getAttribute('data-theme-set');
      applyTheme(next);
      closePicker(picker);
      trigger.focus();
    });
  }

  function closeAllThemePickers() {
    var pickers = document.querySelectorAll('[data-theme-picker]');
    var lastTrigger = null;
    for (var i = 0; i < pickers.length; i++) {
      var tr = pickers[i].querySelector('[data-theme-trigger]');
      if (tr && tr.getAttribute('aria-expanded') === 'true') {
        closePicker(pickers[i]);
        lastTrigger = tr;
      }
    }
    if (lastTrigger) lastTrigger.focus();
  }

  window.tancoinApplyTheme = applyTheme;
  window.tancoinCurrentTheme = currentTheme;

  function init() {
    applyTheme(readStored());
    var pickers = document.querySelectorAll('[data-theme-picker]');
    for (var i = 0; i < pickers.length; i++) {
      wirePicker(pickers[i]);
    }
    if (!escapeBound) {
      escapeBound = true;
      document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') closeAllThemePickers();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.addEventListener('storage', function (ev) {
    if (ev.key === STORAGE_KEY && ev.newValue) {
      applyTheme(ev.newValue);
    }
  });
})();
