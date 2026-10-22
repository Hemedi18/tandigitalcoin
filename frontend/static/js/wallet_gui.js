/**
 * Wallet GUI: keyring in sessionStorage, dashboard, onboarding wizard, local privacy hints for images.
 */
(function () {
  'use strict';

  var LEGACY_KEYRING_KEY = 'tancoin_keyring_v2';
  var OLD_KEY = 'tancoin_wallet_v1';

  function keyringStorageKey() {
    return window.WALLET_KEYRING_NS || null;
  }

  function getCsrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  var fundAddressOverride = null;
  var fundOpenPreserveOverride = false;
  var dashAccountPick = '';

  function dashPickStorageKey() {
    return (window.WALLET_KEYRING_NS || 'tancoin_wallet') + '_dash_pick';
  }

  function shortAddr(addr) {
    if (!addr || String(addr).length < 18) return addr || '—';
    var a = String(addr);
    return a.slice(0, 10) + '…' + a.slice(-6);
  }

  function setFundAddressOverride(addr) {
    fundAddressOverride = addr && String(addr).trim() ? String(addr).trim() : null;
  }

  function i18n(key) {
    var w = window.WALLET_I18N || {};
    return w[key] || key;
  }

  function toast(msg, ok) {
    var stack = document.getElementById('wallet-toast-stack');
    if (!stack) return;
    var el = document.createElement('div');
    el.className = 'wallet-toast ' + (ok ? 'wallet-toast--ok' : 'wallet-toast--err');
    el.textContent = msg;
    stack.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transform = 'translateX(12px)';
      el.style.transition = 'opacity 0.3s, transform 0.3s';
      setTimeout(function () {
        el.remove();
      }, 320);
    }, 4200);
  }

  async function postWallet(url, body, opts) {
    opts = opts || {};
    var r = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(body || {}),
    });
    if (r.status === 401 && window.WALLET_URLS && window.WALLET_URLS.login) {
      toast(i18n('signInRequired'), false);
      window.location.href = window.WALLET_URLS.login;
      return { ok: false, error: '401' };
    }
    var data = await r.json().catch(function () {
      return { ok: false, error: 'Invalid JSON response' };
    });
    if (!r.ok || data.ok === false) {
      toast(data.error || 'Request failed', false);
      return data;
    }
    if (data.message && !opts.silent) toast(data.message, true);
    return data;
  }

  function setOut(el, data, ok) {
    if (!el) return;
    el.hidden = false;
    el.classList.remove('wallet-out--ok', 'wallet-out--err');
    el.classList.add(ok ? 'wallet-out--ok' : 'wallet-out--err');
    el.textContent = JSON.stringify(data, null, 2);
  }

  function rid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'k' + Date.now() + Math.random().toString(36).slice(2, 9);
  }

  function normalizeKeyring(kr) {
    var changed = false;
    if (!kr || typeof kr !== 'object') return;
    if (typeof kr.displayName !== 'string') {
      kr.displayName = '';
      changed = true;
    }
    if (!Array.isArray(kr.keys)) {
      kr.keys = [];
      changed = true;
    }
    kr.keys.forEach(function (k) {
      if (!k.createdAt) {
        k.createdAt = new Date().toISOString();
        changed = true;
      }
    });
    if (changed) saveKeyring(kr);
  }

  function loadKeyring() {
    var k = keyringStorageKey();
    if (!k) {
      return { keys: [], primaryId: null, avatarDataUrl: null, displayName: '' };
    }
    try {
      var raw = sessionStorage.getItem(k);
      if (!raw) {
        var legacy = sessionStorage.getItem(LEGACY_KEYRING_KEY);
        if (legacy) {
          sessionStorage.setItem(k, legacy);
          sessionStorage.removeItem(LEGACY_KEYRING_KEY);
        }
        raw = sessionStorage.getItem(k);
      }
      if (raw) {
        var o = JSON.parse(raw);
        if (o && Array.isArray(o.keys)) {
          normalizeKeyring(o);
          return o;
        }
      }
      var old = sessionStorage.getItem(OLD_KEY);
      if (old) {
        var v1 = JSON.parse(old);
        if (v1 && v1.wif && v1.address) {
          var id = rid();
          var kr = {
            keys: [
              {
                id: id,
                label: 'Wallet 1',
                wif: v1.wif,
                address: v1.address,
                pubkey_hex: '',
              },
            ],
            primaryId: id,
            avatarDataUrl: null,
            displayName: '',
          };
          sessionStorage.removeItem(OLD_KEY);
          saveKeyring(kr);
          return kr;
        }
      }
    } catch (e) {}
    return { keys: [], primaryId: null, avatarDataUrl: null, displayName: '' };
  }

  function saveKeyring(kr) {
    var k = keyringStorageKey();
    if (!k) return;
    sessionStorage.setItem(k, JSON.stringify(kr));
  }

  function getPrimary(kr) {
    kr = kr || loadKeyring();
    if (!kr.keys.length) return null;
    var p = kr.keys.find(function (k) {
      return k.id === kr.primaryId;
    });
    return p || kr.keys[0];
  }

  function syncFundAddressDisplay() {
    var inp = document.getElementById('wallet-fund-address-display');
    if (!inp) return;
    if (fundAddressOverride) {
      inp.value = fundAddressOverride;
      return;
    }
    var p = getPrimary();
    inp.value = p ? p.address : '';
  }

  function applyDashboardAccountView() {
    var sel = document.getElementById('wallet-account-picker');
    var ov = document.getElementById('wallet-dash-overview');
    var kp = document.getElementById('wallet-dash-key-page');
    if (!ov || !kp) return;
    dashAccountPick = sel && sel.value ? sel.value : '';
    try {
      if (dashAccountPick) sessionStorage.setItem(dashPickStorageKey(), dashAccountPick);
      else sessionStorage.removeItem(dashPickStorageKey());
    } catch (e) {}
    if (!dashAccountPick) {
      setFundAddressOverride(null);
      ov.hidden = false;
      kp.hidden = true;
    } else {
      ov.hidden = true;
      kp.hidden = false;
      renderKeyAccountPage(dashAccountPick).catch(function () {});
    }
  }

  function syncAccountPicker(kr) {
    var sel = document.getElementById('wallet-account-picker');
    if (!sel) return;
    try {
      var st = sessionStorage.getItem(dashPickStorageKey()) || '';
      if (st && kr.keys.some(function (k) { return k.id === st; })) dashAccountPick = st;
      else if (dashAccountPick && !kr.keys.some(function (k) { return k.id === dashAccountPick; }))
        dashAccountPick = '';
    } catch (e) {}
    sel.innerHTML = '';
    var o0 = document.createElement('option');
    o0.value = '';
    o0.textContent = i18n('dashOverviewOption');
    sel.appendChild(o0);
    kr.keys.forEach(function (k) {
      var o = document.createElement('option');
      o.value = k.id;
      var lab = (k.label || '').trim();
      o.textContent = lab ? lab + ' · ' + shortAddr(k.address) : shortAddr(k.address);
      sel.appendChild(o);
    });
    sel.value = dashAccountPick || '';
    applyDashboardAccountView();
  }

  async function renderKeyAccountPage(kid) {
    var kr = loadKeyring();
    var k = kr.keys.find(function (x) {
      return x.id === kid;
    });
    var title = document.getElementById('wallet-key-page-title');
    var lead = document.getElementById('wallet-key-page-lead');
    var addrEl = document.getElementById('wallet-key-page-addr');
    var tag = document.getElementById('wallet-key-page-primary-tag');
    var tanEl = document.getElementById('wallet-key-page-tan');
    var satEl = document.getElementById('wallet-key-page-sat');
    var utxoEl = document.getElementById('wallet-key-page-utxo');
    var ex = document.getElementById('wallet-key-page-explorer');
    if (!k) {
      if (kid) {
        dashAccountPick = '';
        try {
          sessionStorage.removeItem(dashPickStorageKey());
        } catch (e) {}
        var pSel = document.getElementById('wallet-account-picker');
        if (pSel) pSel.value = '';
        applyDashboardAccountView();
      }
      return;
    }
    if (!title || !addrEl) return;
    await ensurePubkey(k);
    saveKeyring(kr);
    title.textContent = (k.label || '').trim() || shortAddr(k.address);
    if (lead) lead.textContent = i18n('keyAccountLead');
    addrEl.textContent = k.address;
    if (tag) tag.hidden = k.id !== kr.primaryId;
    if (ex) ex.href = '/address/' + encodeURIComponent(k.address) + '/';
    if (tanEl) tanEl.textContent = '…';
    if (satEl) satEl.textContent = '';
    if (utxoEl) utxoEl.textContent = '';
    if (!window.WALLET_URLS.balance) return;
    var d = await postWallet(window.WALLET_URLS.balance, { address: k.address }, { silent: true });
    if (!d.ok) return;
    if (tanEl) tanEl.textContent = d.tan != null ? String(d.tan) : '0';
    if (satEl) satEl.textContent = d.satoshis != null ? String(d.satoshis) + ' sat' : '—';
    if (utxoEl) utxoEl.textContent = (d.utxo_count != null ? d.utxo_count : 0) + ' ' + i18n('utxoLabel');
  }

  function activateTab(id) {
    var tabs = document.querySelectorAll('.wallet-sidebar__nav [data-tab]');
    var panels = document.querySelectorAll('.wallet-panel');
    tabs.forEach(function (btn) {
      var is = btn.getAttribute('data-tab') === id;
      btn.classList.toggle('is-active', is);
      btn.setAttribute('aria-selected', is ? 'true' : 'false');
    });
    panels.forEach(function (p) {
      p.classList.toggle('is-visible', p.getAttribute('data-panel') === id);
    });
    if (id === 'fund') {
      if (!fundOpenPreserveOverride) setFundAddressOverride(null);
      fundOpenPreserveOverride = false;
      syncFundAddressDisplay();
    }
    if (id === 'send') syncSendWifFromKeySelect();
    if (id === 'history') {
      loadHistory().catch(function () {});
    }
    if (id === 'miner') {
      loadMinerPanel().catch(function () {});
    }
  }

  async function loadHistory() {
    if (!window.WALLET_URLS || !window.WALLET_URLS.activity) return;
    var kr = loadKeyring();
    var chart = document.getElementById('wallet-history-chart');
    var tb = document.getElementById('wallet-history-body');
    var sumEl = document.getElementById('wallet-history-summary');
    if (!sumEl || !chart || !tb) return;
    if (!kr.keys.length) {
      sumEl.innerHTML = '<p class="page-lead">' + escapeHtml(i18n('historyEmpty')) + '</p>';
      chart.innerHTML = '';
      tb.innerHTML = '';
      return;
    }
    var d = await postWallet(
      window.WALLET_URLS.activity,
      { addresses: kr.keys.map(function (k) { return k.address; }) },
      { silent: true }
    );
    if (!d.ok) return;
    renderHistoryUi(d);
  }

  function renderHistoryLineChart(host, points) {
    host.innerHTML = '';
    if (!points || !points.length) return;
    var padX = 10;
    var padY = 14;
    var n = points.length;
    var W = Math.max(260, Math.min(880, 40 + n * 12));
    var H = 132;
    var ns = points.map(function (p) {
      return typeof p.net_sat === 'number' ? p.net_sat : 0;
    });
    var mx = 0;
    for (var m = 0; m < ns.length; m++) mx = Math.max(mx, Math.abs(ns[m]));
    if (!mx) mx = 1;
    var midY = H / 2;
    var plotH = midY - padY;
    var plotW = W - 2 * padX;
    var coords = [];
    for (var i = 0; i < n; i++) {
      var x = n === 1 ? padX + plotW / 2 : padX + (i / (n - 1)) * plotW;
      var y = midY - (ns[i] / mx) * plotH;
      coords.push({ x: x, y: y, sat: ns[i] });
    }
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('class', 'wallet-history-line-svg');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', i18n('historyLineAria'));
    var zl = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    zl.setAttribute('class', 'wallet-history-line-zero');
    zl.setAttribute('x1', padX);
    zl.setAttribute('x2', W - padX);
    zl.setAttribute('y1', midY);
    zl.setAttribute('y2', midY);
    svg.appendChild(zl);
    if (coords.length > 1) {
      for (var j = 1; j < coords.length; j++) {
        var pl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pl.setAttribute(
          'd',
          'M ' + coords[j - 1].x + ',' + coords[j - 1].y + ' L ' + coords[j].x + ',' + coords[j].y
        );
        var avg = (coords[j - 1].sat + coords[j].sat) / 2;
        pl.setAttribute('class', avg >= 0 ? 'wallet-history-line-seg wallet-history-line-seg--in' : 'wallet-history-line-seg wallet-history-line-seg--out');
        svg.appendChild(pl);
      }
    }
    coords.forEach(function (c) {
      var cir = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      cir.setAttribute('cx', c.x);
      cir.setAttribute('cy', c.y);
      cir.setAttribute('r', n > 24 ? 2.5 : 3.5);
      cir.setAttribute('class', c.sat >= 0 ? 'wallet-history-dot wallet-history-dot--in' : 'wallet-history-dot wallet-history-dot--out');
      svg.appendChild(cir);
    });
    host.appendChild(svg);
  }

  function renderHistoryUi(d) {
    var sumEl = document.getElementById('wallet-history-summary');
    var chart = document.getElementById('wallet-history-chart');
    var tb = document.getElementById('wallet-history-body');
    var s = d.summary || {};
    if (sumEl) {
      sumEl.innerHTML =
        '<div class="wallet-history-stat"><span class="wallet-history-stat__lab">' +
        escapeHtml(i18n('historySummaryTx')) +
        '</span><span class="wallet-history-stat__val">' +
        (s.tx_count != null ? s.tx_count : 0) +
        '</span></div>' +
        '<div class="wallet-history-stat"><span class="wallet-history-stat__lab">' +
        escapeHtml(i18n('historySummaryIn')) +
        '</span><span class="wallet-history-stat__val mono">' +
        escapeHtml(String(s.total_recv_tan || '0')) +
        '</span></div>' +
        '<div class="wallet-history-stat"><span class="wallet-history-stat__lab">' +
        escapeHtml(i18n('historySummaryOut')) +
        '</span><span class="wallet-history-stat__val mono">' +
        escapeHtml(String(s.total_sent_tan || '0')) +
        '</span></div>' +
        '<div class="wallet-history-stat"><span class="wallet-history-stat__lab">' +
        escapeHtml(i18n('historySummaryNet')) +
        '</span><span class="wallet-history-stat__val mono">' +
        escapeHtml(String(s.net_tan || '0')) +
        '</span></div>';
    }
    chart.innerHTML = '';
    renderHistoryLineChart(chart, d.line_points || []);
    tb.innerHTML = '';
    var rows = d.rows || [];
    if (!rows.length) {
      var tr0 = document.createElement('tr');
      var td0 = document.createElement('td');
      td0.colSpan = 7;
      td0.textContent = i18n('historyEmpty');
      tr0.appendChild(td0);
      tb.appendChild(tr0);
      return;
    }
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      var tdT = document.createElement('td');
      tdT.className = 'mono';
      var ts = Number(r.timestamp);
      var ms = ts > 1e12 ? ts : ts * 1000;
      tdT.textContent = new Date(ms).toISOString().replace('T', ' ').slice(0, 19);
      var tdTx = document.createElement('td');
      var a = document.createElement('a');
      a.className = 'mono-link mono';
      a.href = '/tx/' + encodeURIComponent(r.txid) + '/';
      a.textContent = r.txid_short || r.txid;
      tdTx.appendChild(a);
      var tdH = document.createElement('td');
      var ab = document.createElement('a');
      ab.className = 'mono';
      ab.href = '/block/' + encodeURIComponent(r.block_hash) + '/';
      ab.textContent = String(r.height);
      tdH.appendChild(ab);
      var tdR = document.createElement('td');
      tdR.className = 'mono';
      tdR.textContent = r.recv_tan != null ? String(r.recv_tan) : '—';
      var tdS = document.createElement('td');
      tdS.className = 'mono';
      tdS.textContent = r.sent_tan != null ? String(r.sent_tan) : '—';
      var tdN = document.createElement('td');
      tdN.className = 'mono';
      tdN.textContent = r.net_tan != null ? String(r.net_tan) : '—';
      var tdF = document.createElement('td');
      tdF.className = 'mono';
      tdF.textContent = r.fee_tan != null ? String(r.fee_tan) : '—';
      tr.appendChild(tdT);
      tr.appendChild(tdTx);
      tr.appendChild(tdH);
      tr.appendChild(tdR);
      tr.appendChild(tdS);
      tr.appendChild(tdN);
      tr.appendChild(tdF);
      tb.appendChild(tr);
    });
  }

  function initTabs() {
    document.querySelectorAll('.wallet-sidebar__nav [data-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(btn.getAttribute('data-tab'));
      });
    });
    document.querySelectorAll('[data-go-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-go-tab');
        activateTab(id);
        var t = document.querySelector('.wallet-sidebar__nav [data-tab="' + id + '"]');
        if (t) t.focus();
      });
    });
  }

  /* --- Onboarding --- */
  function setOnboardStep(n) {
    document.querySelectorAll('.wallet-onboard-step').forEach(function (el) {
      var s = parseInt(el.getAttribute('data-onboard-step'), 10);
      el.hidden = s !== n;
    });
  }

  function openOnboarding(step) {
    var o = document.getElementById('wallet-onboarding');
    if (!o) return;
    o.hidden = false;
    setOnboardStep(step || 1);
    var ib = document.getElementById('wallet-onboard-import-box');
    var ch = document.getElementById('wallet-onboard-create-hint');
    var dc = document.getElementById('wallet-onboard-do-create');
    if (ib) ib.hidden = true;
    if (ch) ch.hidden = true;
    if (dc) dc.hidden = true;
  }

  function closeOnboarding() {
    var o = document.getElementById('wallet-onboarding');
    if (o) o.hidden = true;
  }

  /* --- Privacy scan (local only) --- */
  function scanJpegExif(buf) {
    var u = new Uint8Array(buf);
    if (u.length < 4 || u[0] !== 0xff || u[1] !== 0xd8) return false;
    var max = Math.min(u.length, 65536);
    for (var i = 2; i < max - 1; i++) {
      if (u[i] === 0xff && u[i + 1] === 0xe1) return true;
    }
    return false;
  }

  function analyzeImageFile(file) {
    var notes = [];
    notes.push(i18n('privLocal'));
    if (file.size > 2 * 1024 * 1024) notes.push(i18n('privLarge'));
    notes.push(i18n('privFace'));
    return new Promise(function (resolve) {
      var fr = new FileReader();
      fr.onload = function () {
        if (scanJpegExif(fr.result)) notes.push(i18n('privExif'));
        resolve(notes);
      };
      fr.onerror = function () {
        resolve(notes);
      };
      fr.readAsArrayBuffer(file.slice(0, Math.min(file.size, 65536)));
    });
  }

  function resizeImageToDataUrl(file, maxPx, quality, cb) {
    var img = new Image();
    var url = URL.createObjectURL(file);
    img.onload = function () {
      URL.revokeObjectURL(url);
      var w = img.naturalWidth;
      var h = img.naturalHeight;
      var scale = Math.min(1, maxPx / Math.max(w, h));
      var cw = Math.round(w * scale);
      var ch = Math.round(h * scale);
      var c = document.createElement('canvas');
      c.width = cw;
      c.height = ch;
      var ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, cw, ch);
      try {
        cb(c.toDataURL('image/jpeg', quality));
      } catch (e) {
        cb(null);
      }
    };
    img.onerror = function () {
      URL.revokeObjectURL(url);
      cb(null);
    };
    img.src = url;
  }

  function renderPrivacyList(items) {
    var box = document.getElementById('wallet-privacy-scan');
    var ul = document.getElementById('wallet-privacy-list');
    if (!box || !ul) return;
    ul.innerHTML = '';
    items.forEach(function (t) {
      var li = document.createElement('li');
      li.textContent = t;
      ul.appendChild(li);
    });
    box.hidden = items.length === 0;
  }

  function renderAvatar(kr) {
    var prev = document.getElementById('wallet-avatar-preview');
    var ph = document.getElementById('wallet-avatar-placeholder');
    if (!prev || !ph) return;
    if (kr.avatarDataUrl) {
      prev.src = kr.avatarDataUrl;
      prev.hidden = false;
      ph.hidden = true;
    } else {
      prev.removeAttribute('src');
      prev.hidden = true;
      ph.hidden = false;
    }
  }

  /* --- Key material UI --- */
  function hideWifUi() {
    var mask = document.getElementById('wallet-wif-mask');
    var rev = document.getElementById('wallet-wif-reveal');
    var btn = document.getElementById('wallet-toggle-wif');
    if (mask) mask.hidden = false;
    if (rev) {
      rev.hidden = true;
      rev.textContent = '';
    }
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = i18n('show');
    }
  }

  function showWifUi() {
    var mask = document.getElementById('wallet-wif-mask');
    var rev = document.getElementById('wallet-wif-reveal');
    var btn = document.getElementById('wallet-toggle-wif');
    var p = getPrimary();
    if (rev && p) rev.textContent = p.wif;
    if (mask) mask.hidden = true;
    if (rev) rev.hidden = false;
    if (btn) {
      btn.setAttribute('aria-expanded', 'true');
      btn.textContent = i18n('hide');
    }
  }

  async function ensurePubkey(key) {
    if (key.pubkey_hex) return key;
    if (!window.WALLET_URLS.keyInfo) return key;
    var d = await postWallet(window.WALLET_URLS.keyInfo, { wif: key.wif }, { silent: true });
    if (d.ok && d.pubkey_hex) key.pubkey_hex = d.pubkey_hex;
    return key;
  }

  async function refreshPrimaryBalance() {
    var p = getPrimary();
    var tanEl = document.getElementById('wallet-dash-tan');
    var satEl = document.getElementById('wallet-dash-sat');
    var utxoEl = document.getElementById('wallet-dash-utxo');
    var pubEl = document.getElementById('wallet-super-pubkey');
    if (!p || !window.WALLET_URLS.balance) return;
    await ensurePubkey(p);
    var kr = loadKeyring();
    saveKeyring(kr);
    if (pubEl) {
      var hex = p.pubkey_hex || '—';
      pubEl.textContent = hex;
      pubEl.title = hex;
    }
    var d = await postWallet(window.WALLET_URLS.balance, { address: p.address }, { silent: true });
    if (!d.ok) return;
    if (tanEl) tanEl.textContent = d.tan != null ? String(d.tan) : '0';
    if (satEl) satEl.textContent = d.satoshis != null ? String(d.satoshis) + ' sat' : '—';
    if (utxoEl) utxoEl.textContent = (d.utxo_count != null ? d.utxo_count : 0) + ' ' + i18n('utxoLabel');
  }

  function syncSendWifFromKeySelect() {
    var sel = document.getElementById('wallet-send-keyselect');
    var ta = document.getElementById('wallet-send-wif');
    if (!sel || !ta) return;
    var kid = sel.value;
    if (!kid) {
      ta.value = '';
      return;
    }
    var kr = loadKeyring();
    var k = kr.keys.find(function (x) {
      return x.id === kid;
    });
    ta.value = k && k.wif ? k.wif : '';
  }

  function clearSendKeyUi() {
    var sel = document.getElementById('wallet-send-keyselect');
    var ta = document.getElementById('wallet-send-wif');
    if (sel) sel.innerHTML = '';
    if (ta) ta.value = '';
  }

  function populateSendSelect(kr) {
    var sel = document.getElementById('wallet-send-keyselect');
    if (!sel) return;
    sel.innerHTML = '';
    if (!kr.keys.length) {
      syncSendWifFromKeySelect();
      return;
    }
    var anySelected = false;
    kr.keys.forEach(function (k) {
      var opt = document.createElement('option');
      opt.value = k.id;
      opt.textContent = k.label + ' — ' + k.address.slice(0, 10) + '…';
      if (kr.primaryId && k.id === kr.primaryId) {
        opt.selected = true;
        anySelected = true;
      }
      sel.appendChild(opt);
    });
    if (!anySelected && sel.options.length) sel.options[0].selected = true;
    syncSendWifFromKeySelect();
  }

  function populateMineSelect(kr) {
    var sel = document.getElementById('wallet-mine-keyselect');
    if (!sel) return;
    sel.innerHTML = '';
    if (!kr.keys.length) return;
    var anySelected = false;
    kr.keys.forEach(function (k) {
      var opt = document.createElement('option');
      opt.value = k.id;
      opt.textContent = k.label + ' — ' + k.address.slice(0, 10) + '…';
      if (kr.primaryId && k.id === kr.primaryId) {
        opt.selected = true;
        anySelected = true;
      }
      sel.appendChild(opt);
    });
    if (!anySelected && sel.options.length) sel.options[0].selected = true;
  }

  async function loadMinerPanel() {
    if (!window.WALLET_URLS || !window.WALLET_URLS.chainStatus) return;
    var hEl = document.getElementById('wallet-miner-height');
    var mcEl = document.getElementById('wallet-miner-mempool-count');
    var dEl = document.getElementById('wallet-miner-diff');
    var tb = document.getElementById('wallet-miner-mempool-body');
    try {
      var st = await fetch(window.WALLET_URLS.chainStatus, { credentials: 'same-origin', cache: 'no-store' }).then(
        function (r) {
          return r.json();
        }
      );
      if (st.ok && st.chain) {
        var ch = st.chain;
        if (hEl) hEl.textContent = ch.height != null ? String(ch.height) : '—';
        if (mcEl) mcEl.textContent = ch.mempool_count != null ? String(ch.mempool_count) : '—';
        if (dEl) dEl.textContent = ch.initial_difficulty_bits != null ? String(ch.initial_difficulty_bits) : '—';
      }
    } catch (e) {}
    if (!tb) return;
    tb.innerHTML = '';
    try {
      var mp = await fetch(window.WALLET_URLS.chainMempool, { credentials: 'same-origin', cache: 'no-store' }).then(
        function (r) {
          return r.json();
        }
      );
      if (!mp.ok || !mp.transactions || !mp.transactions.length) {
        var tr0 = document.createElement('tr');
        var td0 = document.createElement('td');
        td0.colSpan = 3;
        td0.textContent = i18n('minerNoPending');
        tr0.appendChild(td0);
        tb.appendChild(tr0);
        return;
      }
      mp.transactions.forEach(function (tx) {
        var tr = document.createElement('tr');
        var tid = tx.txid || '';
        var tdId = document.createElement('td');
        var a = document.createElement('a');
        a.className = 'mono-link mono';
        a.href = '/tx/' + encodeURIComponent(tid) + '/';
        a.textContent = tid.length > 22 ? tid.slice(0, 14) + '…' + tid.slice(-8) : tid;
        tdId.appendChild(a);
        var tdIn = document.createElement('td');
        tdIn.textContent = String((tx.inputs && tx.inputs.length) || 0);
        var tdOut = document.createElement('td');
        tdOut.textContent = String((tx.outputs && tx.outputs.length) || 0);
        tr.appendChild(tdId);
        tr.appendChild(tdIn);
        tr.appendChild(tdOut);
        tb.appendChild(tr);
      });
    } catch (e) {
      var trE = document.createElement('tr');
      var tdE = document.createElement('td');
      tdE.colSpan = 3;
      tdE.textContent = '—';
      trE.appendChild(tdE);
      tb.appendChild(trE);
    }
  }

  function formatCardNumber(addr) {
    var s = String(addr || '').replace(/\s/g, '');
    var parts = [];
    for (var i = 0; i < s.length; i += 4) parts.push(s.slice(i, i + 4));
    return parts.join(' ');
  }

  function pubkeyFingerprint(hex) {
    if (!hex || hex.length < 20) return hex || '—';
    return hex.slice(0, 14) + '…' + hex.slice(-12);
  }

  function formatMemberSince(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      return isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
    } catch (e) {
      return '—';
    }
  }

  function loadQrForCard(card, address) {
    if (!window.WALLET_URLS.qrPng || card.dataset.qrLoaded === '1') return;
    card.dataset.qrLoaded = '1';
    postWallet(window.WALLET_URLS.qrPng, { text: address }, { silent: true }).then(function (d) {
      var im = card.querySelector('.wallet-id-card__qr');
      if (im && d.ok && d.png_base64) im.src = 'data:image/png;base64,' + d.png_base64;
    });
  }

  function attachIdentityCardFlip(card, k) {
    function flip() {
      var open = card.classList.toggle('is-flipped');
      card.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) loadQrForCard(card, k.address);
    }
    card.addEventListener('click', function (ev) {
      if (ev.target.closest('.wallet-id-card__noflip')) return;
      flip();
    });
    card.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') {
        if (ev.target.closest('.wallet-id-card__noflip')) return;
        ev.preventDefault();
        flip();
      }
    });
  }

  async function renderIdentityCards(kr) {
    var deck = document.getElementById('wallet-iddeck');
    var host = document.getElementById('wallet-id-cards');
    if (!deck || !host) return;
    if (!kr.keys.length) {
      deck.hidden = true;
      return;
    }
    deck.hidden = false;
    host.innerHTML = '';
    for (var i = 0; i < kr.keys.length; i++) {
      await ensurePubkey(kr.keys[i]);
    }
    saveKeyring(kr);
    var disp = (kr.displayName || '').trim();
    kr.keys.forEach(function (k) {
      var isPrimary = k.id === kr.primaryId;
      var card = document.createElement('div');
      card.className = 'wallet-id-card' + (isPrimary ? ' wallet-id-card--primary' : '');
      card.setAttribute('role', 'listitem');
      card.setAttribute('tabindex', '0');
      card.setAttribute('data-key-id', k.id);
      card.setAttribute('aria-expanded', 'false');
      card.setAttribute(
        'aria-label',
        (isPrimary ? i18n('primaryCard') : i18n('identityCard')) + ': ' + (disp || k.label)
      );
      var inner = document.createElement('div');
      inner.className = 'wallet-id-card__inner';
      var front = document.createElement('div');
      front.className = 'wallet-id-card__face wallet-id-card__face--front';
      var chip = document.createElement('div');
      chip.className = 'wallet-id-card__chip';
      chip.textContent = 'TAN';
      var brand = document.createElement('div');
      brand.className = 'wallet-id-card__brand';
      brand.textContent = 'TANCOIN';
      var photoWrap = document.createElement('div');
      photoWrap.className = 'wallet-id-card__photoWrap';
      if (kr.avatarDataUrl) {
        var img = document.createElement('img');
        img.className = 'wallet-id-card__photo';
        img.alt = '';
        img.width = 56;
        img.height = 56;
        img.src = kr.avatarDataUrl;
        photoWrap.appendChild(img);
      } else {
        var ph = document.createElement('div');
        ph.className = 'wallet-id-card__photo wallet-id-card__photo--ph';
        ph.setAttribute('aria-hidden', 'true');
        photoWrap.appendChild(ph);
      }
      var who = document.createElement('div');
      who.className = 'wallet-id-card__name';
      who.textContent = (disp || k.label || '').trim() || '—';
      var num = document.createElement('div');
      num.className = 'wallet-id-card__number';
      num.textContent = formatCardNumber(k.address);
      var pub = document.createElement('div');
      pub.className = 'wallet-id-card__pub';
      var pubLbl = document.createElement('span');
      pubLbl.className = 'wallet-id-card__pub-lbl';
      pubLbl.textContent = i18n('publicKey');
      var code = document.createElement('code');
      code.textContent = pubkeyFingerprint(k.pubkey_hex || '');
      pub.appendChild(pubLbl);
      pub.appendChild(document.createTextNode(' '));
      pub.appendChild(code);
      var meta = document.createElement('div');
      meta.className = 'wallet-id-card__meta';
      meta.textContent = i18n('memberSince') + ' ' + formatMemberSince(k.createdAt);
      if (isPrimary) {
        var badge = document.createElement('span');
        badge.className = 'wallet-id-card__badge';
        badge.textContent = i18n('primary');
        front.appendChild(badge);
      }
      front.appendChild(chip);
      front.appendChild(brand);
      front.appendChild(photoWrap);
      front.appendChild(who);
      front.appendChild(num);
      front.appendChild(pub);
      front.appendChild(meta);
      var hint = document.createElement('div');
      hint.className = 'wallet-id-card__flip-hint';
      hint.textContent = '↻';
      front.appendChild(hint);
      var back = document.createElement('div');
      back.className = 'wallet-id-card__face wallet-id-card__face--back';
      var qr = document.createElement('img');
      qr.className = 'wallet-id-card__qr';
      qr.width = 140;
      qr.height = 140;
      qr.alt = '';
      var addrLbl = document.createElement('p');
      addrLbl.className = 'wallet-id-card__back-lbl';
      addrLbl.textContent = i18n('addressLbl');
      var addrPre = document.createElement('pre');
      addrPre.className = 'wallet-id-card__addr';
      addrPre.textContent = k.address;
      var copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'wallet-btn wallet-btn--sm wallet-id-card__noflip';
      copyBtn.textContent = i18n('copyPubAddr');
      copyBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (window.tancoinCopy) window.tancoinCopy(k.address);
      });
      back.appendChild(qr);
      back.appendChild(addrLbl);
      back.appendChild(addrPre);
      back.appendChild(copyBtn);
      inner.appendChild(front);
      inner.appendChild(back);
      card.appendChild(inner);
      attachIdentityCardFlip(card, k);
      host.appendChild(card);
    });
  }

  async function renderKeyringTable(kr) {
    var tb = document.getElementById('wallet-keyring-body');
    if (!tb) return;
    tb.innerHTML = '';
    for (var i = 0; i < kr.keys.length; i++) {
      await ensurePubkey(kr.keys[i]);
    }
    saveKeyring(kr);
    kr.keys.forEach(function (k) {
      var tr = document.createElement('tr');
      var bal = '…';
      tr.innerHTML =
        '<td>' +
        escapeHtml(k.label) +
        '</td><td><code class="wallet-mono">' +
        escapeHtml(k.address) +
        '</code></td><td class="wallet-td-bal" data-kid="' +
        escapeHtml(k.id) +
        '">' +
        bal +
        '</td><td></td><td></td>';
      var tdPri = tr.children[3];
      var tdAct = tr.children[4];
      if (k.id === kr.primaryId) {
        tdPri.innerHTML = '<span class="wallet-badge-inline">' + escapeHtml(i18n('primary')) + '</span>';
      } else {
        var bSet = document.createElement('button');
        bSet.type = 'button';
        bSet.className = 'wallet-btn wallet-btn--sm wallet-btn--ghost';
        bSet.textContent = i18n('setPrimary');
        bSet.addEventListener('click', function () {
          kr.primaryId = k.id;
          saveKeyring(kr);
          renderAll().catch(function () {});
        });
        tdPri.appendChild(bSet);
      }
      var wrap = document.createElement('div');
      wrap.className = 'wallet-row-actions';
      var bca = document.createElement('button');
      bca.type = 'button';
      bca.className = 'wallet-btn wallet-btn--sm wallet-btn--ghost';
      bca.textContent = i18n('copyAddr');
      bca.addEventListener('click', function () {
        if (window.tancoinCopy) window.tancoinCopy(k.address);
      });
      var bcp = document.createElement('button');
      bcp.type = 'button';
      bcp.className = 'wallet-btn wallet-btn--sm wallet-btn--ghost';
      bcp.textContent = i18n('copyPub');
      bcp.addEventListener('click', function () {
        if (k.pubkey_hex && window.tancoinCopy) window.tancoinCopy(k.pubkey_hex);
      });
      var brm = document.createElement('button');
      brm.type = 'button';
      brm.className = 'wallet-btn wallet-btn--sm wallet-btn--danger';
      brm.textContent = i18n('remove');
      brm.addEventListener('click', function () {
        if (!window.confirm(i18n('removeOne'))) return;
        kr.keys = kr.keys.filter(function (x) {
          return x.id !== k.id;
        });
        if (kr.primaryId === k.id) kr.primaryId = kr.keys.length ? kr.keys[0].id : null;
        saveKeyring(kr);
        renderAll().catch(function () {});
      });
      wrap.appendChild(bca);
      wrap.appendChild(bcp);
      wrap.appendChild(brm);
      tdAct.appendChild(wrap);
      tb.appendChild(tr);
      postWallet(window.WALLET_URLS.balance, { address: k.address }, { silent: true }).then(function (d) {
        var cell = tb.querySelector('.wallet-td-bal[data-kid="' + k.id + '"]');
        if (cell && d.ok) cell.textContent = d.tan != null ? String(d.tan) : '0';
      });
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderAll() {
    return (async function () {
      var kr = loadKeyring();
      var empty = document.getElementById('wallet-dash-empty');
      var loaded = document.getElementById('wallet-dash-loaded');
      var wizBtn = document.getElementById('wallet-open-setup-wizard');
      if (kr.keys.length === 0) {
        if (empty) empty.hidden = false;
        if (loaded) loaded.hidden = true;
        if (wizBtn) wizBtn.hidden = true;
        clearSendKeyUi();
        renderAvatar(kr);
        dashAccountPick = '';
        try {
          sessionStorage.removeItem(dashPickStorageKey());
        } catch (e) {}
        setFundAddressOverride(null);
      } else {
        if (empty) empty.hidden = true;
        if (loaded) loaded.hidden = false;
        if (wizBtn) wizBtn.hidden = false;
        hideWifUi();
        populateSendSelect(kr);
        populateMineSelect(kr);
        renderAvatar(kr);
        var dn = document.getElementById('wallet-display-name');
        if (dn) dn.value = kr.displayName || '';
        await renderKeyringTable(kr);
        syncAccountPicker(kr);
        await renderIdentityCards(kr);
        await refreshPrimaryBalance();
      }
      syncSendHint();
      syncFaucetPrefill(kr);
      syncFundAddressDisplay();
    })();
  }

  function syncSendHint() {
    var hint = document.getElementById('wallet-send-hint');
    if (hint) hint.textContent = i18n('sendHintKeys');
  }

  function syncFaucetPrefill(kr) {
    var fa = document.getElementById('wallet-faucet-address');
    var p = getPrimary(kr);
    if (fa && p && !fa.value.trim()) fa.value = p.address;
  }

  function addKey(wif, address, pubkey_hex, label) {
    if (!keyringStorageKey()) {
      toast(i18n('signInRequired'), false);
      return;
    }
    var kr = loadKeyring();
    var id = rid();
    kr.keys.push({
      id: id,
      label: label || 'Wallet ' + (kr.keys.length + 1),
      wif: wif,
      address: address,
      pubkey_hex: pubkey_hex || '',
      createdAt: new Date().toISOString(),
    });
    if (!kr.primaryId) kr.primaryId = id;
    saveKeyring(kr);
    renderAll().catch(function () {});
  }

  function wire() {
    initTabs();
    renderAll().catch(function () {});

    document.getElementById('wallet-history-refresh') &&
      document.getElementById('wallet-history-refresh').addEventListener('click', function () {
        loadHistory().catch(function () {});
      });

    document.getElementById('wallet-miner-refresh') &&
      document.getElementById('wallet-miner-refresh').addEventListener('click', function () {
        loadMinerPanel().catch(function () {});
      });

    document.getElementById('wallet-mine-btn') &&
      document.getElementById('wallet-mine-btn').addEventListener('click', async function () {
        var kr = loadKeyring();
        var sel = document.getElementById('wallet-mine-keyselect');
        var kid = sel && sel.value;
        var wif = '';
        if (kid) {
          var k = kr.keys.find(function (x) {
            return x.id === kid;
          });
          if (k) wif = k.wif;
        }
        if (!wif) {
          toast(i18n('wifRequired'), false);
          return;
        }
        var btn = document.getElementById('wallet-mine-btn');
        var out = document.getElementById('wallet-mine-out');
        btn.disabled = true;
        var d = await postWallet(window.WALLET_URLS.mine, { from_wif: wif });
        btn.disabled = false;
        if (out) setOut(out, d, d.ok);
        if (d.ok) {
          loadMinerPanel().catch(function () {});
          renderAll().catch(function () {});
          loadHistory().catch(function () {});
        }
      });

    (function () {
      var accSel = document.getElementById('wallet-account-picker');
      if (!accSel) return;
      accSel.addEventListener('change', function () {
        dashAccountPick = accSel.value || '';
        try {
          if (dashAccountPick) sessionStorage.setItem(dashPickStorageKey(), dashAccountPick);
          else sessionStorage.removeItem(dashPickStorageKey());
        } catch (e) {}
        applyDashboardAccountView();
      });
    })();

    document.getElementById('wallet-key-page-copy-addr') &&
      document.getElementById('wallet-key-page-copy-addr').addEventListener('click', function () {
        var addr = (document.getElementById('wallet-key-page-addr') || {}).textContent;
        if (addr && window.tancoinCopy) window.tancoinCopy(addr);
      });

    document.getElementById('wallet-key-page-send') &&
      document.getElementById('wallet-key-page-send').addEventListener('click', function () {
        var id = dashAccountPick;
        if (!id) return;
        var s = document.getElementById('wallet-send-keyselect');
        if (s) s.value = id;
        syncSendWifFromKeySelect();
        activateTab('send');
      });

    document.getElementById('wallet-key-page-receive') &&
      document.getElementById('wallet-key-page-receive').addEventListener('click', function () {
        var kr = loadKeyring();
        var k = kr.keys.find(function (x) {
          return x.id === dashAccountPick;
        });
        if (!k) return;
        setFundAddressOverride(k.address);
        fundOpenPreserveOverride = true;
        activateTab('fund');
      });

    document.getElementById('wallet-fund-copy-address') &&
      document.getElementById('wallet-fund-copy-address').addEventListener('click', function () {
        var inp = document.getElementById('wallet-fund-address-display');
        var addr = inp && inp.value.trim();
        if (!addr) {
          toast(i18n('fundCopyNoKey'), false);
          return;
        }
        if (window.tancoinCopy) window.tancoinCopy(addr);
      });

    document.getElementById('wallet-refresh-balance') &&
      document.getElementById('wallet-refresh-balance').addEventListener('click', async function (ev) {
        ev.target.disabled = true;
        await refreshPrimaryBalance();
        var kr = loadKeyring();
        await renderKeyringTable(kr);
        await renderIdentityCards(kr);
        if (dashAccountPick) await renderKeyAccountPage(dashAccountPick);
        ev.target.disabled = false;
      });

    document.getElementById('wallet-toggle-wif') &&
      document.getElementById('wallet-toggle-wif').addEventListener('click', function () {
        var btn = document.getElementById('wallet-toggle-wif');
        if (btn.getAttribute('aria-expanded') === 'true') hideWifUi();
        else showWifUi();
      });

    document.getElementById('wallet-copy-wif') &&
      document.getElementById('wallet-copy-wif').addEventListener('click', function () {
        var p = getPrimary();
        if (p && window.tancoinCopy) window.tancoinCopy(p.wif);
      });

    document.getElementById('wallet-copy-super-pub') &&
      document.getElementById('wallet-copy-super-pub').addEventListener('click', async function () {
        var p = getPrimary();
        if (!p) return;
        await ensurePubkey(p);
        if (p.pubkey_hex && window.tancoinCopy) window.tancoinCopy(p.pubkey_hex);
      });

    document.getElementById('wallet-forget-btn') &&
      document.getElementById('wallet-forget-btn').addEventListener('click', function () {
        if (!window.confirm(i18n('forgetConfirm'))) return;
        var kk = keyringStorageKey();
        dashAccountPick = '';
        try {
          sessionStorage.removeItem(dashPickStorageKey());
        } catch (e) {}
        setFundAddressOverride(null);
        if (kk) sessionStorage.removeItem(kk);
        sessionStorage.removeItem(LEGACY_KEYRING_KEY);
        sessionStorage.removeItem(OLD_KEY);
        hideWifUi();
        renderPrivacyList([]);
        document.getElementById('wallet-privacy-scan') && (document.getElementById('wallet-privacy-scan').hidden = true);
        closeOnboarding();
        renderAll().catch(function () {});
        activateTab('dashboard');
      });

    document.getElementById('wallet-create-btn') &&
      document.getElementById('wallet-create-btn').addEventListener('click', async function () {
        var btn = document.getElementById('wallet-create-btn');
        var out = document.getElementById('wallet-create-out');
        btn.disabled = true;
        var d = await postWallet(window.WALLET_URLS.create, {});
        btn.disabled = false;
        if (d.ok && d.wif && d.address) {
          addKey(d.wif, d.address, d.pubkey_hex || '', '');
          if (out) out.hidden = true;
          activateTab('dashboard');
        } else if (out) setOut(out, d, false);
      });

    document.getElementById('wallet-import-btn') &&
      document.getElementById('wallet-import-btn').addEventListener('click', async function () {
        var wif = (document.getElementById('wallet-import-wif') || {}).value.trim();
        var out = document.getElementById('wallet-import-out');
        if (!wif) {
          toast(i18n('wifRequired'), false);
          return;
        }
        var d = await postWallet(window.WALLET_URLS.importKey, { wif: wif });
        if (d.ok && d.address) {
          addKey(wif, d.address, d.pubkey_hex || '', '');
          document.getElementById('wallet-import-wif').value = '';
          if (out) out.hidden = true;
          activateTab('dashboard');
        } else if (out) setOut(out, d, false);
      });

    (function () {
      var sendSel = document.getElementById('wallet-send-keyselect');
      if (!sendSel) return;
      sendSel.addEventListener('change', syncSendWifFromKeySelect);
      sendSel.addEventListener('input', syncSendWifFromKeySelect);
    })();

    document.getElementById('wallet-send-btn') &&
      document.getElementById('wallet-send-btn').addEventListener('click', async function () {
        var kr = loadKeyring();
        var sel = document.getElementById('wallet-send-keyselect');
        var ta = document.getElementById('wallet-send-wif');
        var kid = sel && sel.value;
        var wif = '';
        if (ta && ta.value.trim()) {
          wif = ta.value.trim();
        } else if (kid) {
          var k = kr.keys.find(function (x) {
            return x.id === kid;
          });
          if (k) wif = k.wif;
        }
        if (!wif) {
          toast(i18n('wifRequired'), false);
          return;
        }
        var btn = document.getElementById('wallet-send-btn');
        btn.disabled = true;
        var d = await postWallet(window.WALLET_URLS.send, {
          from_wif: wif,
          to_address: (document.getElementById('wallet-send-to') || {}).value.trim(),
          amount_tan: (document.getElementById('wallet-send-amount') || {}).value.trim(),
          fee_tan: ((document.getElementById('wallet-send-fee') || {}).value || '').trim() || '0.0005',
          mine: (document.getElementById('wallet-send-mine') || {}).checked,
        });
        btn.disabled = false;
        var so = document.getElementById('wallet-send-out');
        if (so) setOut(so, d, d.ok);
        if (d.ok) {
          await refreshPrimaryBalance();
          await renderKeyringTable(loadKeyring());
          if (dashAccountPick) await renderKeyAccountPage(dashAccountPick);
          loadHistory().catch(function () {});
        }
      });

    var faucetBtn = document.getElementById('wallet-faucet-btn');
    if (faucetBtn && window.WALLET_URLS.faucet) {
      faucetBtn.addEventListener('click', async function () {
        faucetBtn.disabled = true;
        var d = await postWallet(window.WALLET_URLS.faucet, {
          address: (document.getElementById('wallet-faucet-address') || {}).value.trim(),
          amount_tan: (document.getElementById('wallet-faucet-amount') || {}).value.trim() || '2',
        });
        faucetBtn.disabled = false;
        var fo = document.getElementById('wallet-faucet-out');
        if (fo) setOut(fo, d, d.ok);
        if (d.ok) {
          renderAll().catch(function () {});
          loadHistory().catch(function () {});
        }
      });
    }

    /* Avatar */
    var avIn = document.getElementById('wallet-avatar-input');
    if (avIn) {
      avIn.addEventListener('change', function () {
        var f = avIn.files && avIn.files[0];
        if (!f) return;
        analyzeImageFile(f).then(function (notes) {
          renderPrivacyList(notes);
        });
        resizeImageToDataUrl(f, 128, 0.82, function (dataUrl) {
          var kr = loadKeyring();
          kr.avatarDataUrl = dataUrl;
          saveKeyring(kr);
          renderAvatar(kr);
          renderIdentityCards(kr).catch(function () {});
        });
      });
    }
    document.getElementById('wallet-avatar-clear') &&
      document.getElementById('wallet-avatar-clear').addEventListener('click', function () {
        var kr = loadKeyring();
        kr.avatarDataUrl = null;
        saveKeyring(kr);
        renderAvatar(kr);
        renderPrivacyList([]);
        var ps = document.getElementById('wallet-privacy-scan');
        if (ps) ps.hidden = true;
        var avIn2 = document.getElementById('wallet-avatar-input');
        if (avIn2) avIn2.value = '';
        renderIdentityCards(loadKeyring()).catch(function () {});
      });

    var dnField = document.getElementById('wallet-display-name');
    if (dnField) {
      dnField.addEventListener('change', function () {
        var kr = loadKeyring();
        kr.displayName = dnField.value.trim().slice(0, 48);
        saveKeyring(kr);
        renderIdentityCards(kr).catch(function () {});
      });
    }

    /* Wizard */
    document.getElementById('wallet-start-wizard') &&
      document.getElementById('wallet-start-wizard').addEventListener('click', function () {
        openOnboarding(1);
      });
    document.getElementById('wallet-open-setup-wizard') &&
      document.getElementById('wallet-open-setup-wizard').addEventListener('click', function () {
        openOnboarding(1);
      });
    document.getElementById('wallet-onboard-close') &&
      document.getElementById('wallet-onboard-close').addEventListener('click', closeOnboarding);
    document.getElementById('wallet-onboard-to-2') &&
      document.getElementById('wallet-onboard-to-2').addEventListener('click', function () {
        setOnboardStep(2);
      });
    document.getElementById('wallet-onboard-back-1') &&
      document.getElementById('wallet-onboard-back-1').addEventListener('click', function () {
        setOnboardStep(1);
      });
    document.getElementById('wallet-onboard-to-3') &&
      document.getElementById('wallet-onboard-to-3').addEventListener('click', function () {
        setOnboardStep(3);
      });
    document.getElementById('wallet-onboard-back-2') &&
      document.getElementById('wallet-onboard-back-2').addEventListener('click', function () {
        setOnboardStep(2);
      });
    document.getElementById('wallet-onboard-create') &&
      document.getElementById('wallet-onboard-create').addEventListener('click', function () {
        document.getElementById('wallet-onboard-import-box').hidden = true;
        document.getElementById('wallet-onboard-create-hint').hidden = false;
        document.getElementById('wallet-onboard-do-create').hidden = false;
      });
    document.getElementById('wallet-onboard-import-focus') &&
      document.getElementById('wallet-onboard-import-focus').addEventListener('click', function () {
        document.getElementById('wallet-onboard-import-box').hidden = false;
        document.getElementById('wallet-onboard-create-hint').hidden = true;
        document.getElementById('wallet-onboard-do-create').hidden = true;
      });
    document.getElementById('wallet-onboard-do-create') &&
      document.getElementById('wallet-onboard-do-create').addEventListener('click', async function () {
        var btn = document.getElementById('wallet-onboard-do-create');
        btn.disabled = true;
        var d = await postWallet(window.WALLET_URLS.create, {});
        btn.disabled = false;
        if (d.ok && d.wif && d.address) {
          addKey(d.wif, d.address, d.pubkey_hex || '', '');
          setOnboardStep(4);
        }
      });
    document.getElementById('wallet-onboard-import-save') &&
      document.getElementById('wallet-onboard-import-save').addEventListener('click', async function () {
        var wif = (document.getElementById('wallet-onboard-wif') || {}).value.trim();
        if (!wif) {
          toast(i18n('wifRequired'), false);
          return;
        }
        var d = await postWallet(window.WALLET_URLS.importKey, { wif: wif });
        if (d.ok && d.address) {
          addKey(wif, d.address, d.pubkey_hex || '', '');
          document.getElementById('wallet-onboard-wif').value = '';
          setOnboardStep(4);
        }
      });
    document.getElementById('wallet-onboard-finish') &&
      document.getElementById('wallet-onboard-finish').addEventListener('click', function () {
        closeOnboarding();
        activateTab('dashboard');
        renderAll().catch(function () {});
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
