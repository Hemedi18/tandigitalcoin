/**
 * Explorer: raw JSON toggle + home dashboard live refresh.
 */
(function () {
  'use strict';

  document.querySelectorAll('[data-toggle-next]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const target = btn.nextElementSibling;
      if (target && target.classList.contains('toggle-panel')) {
        target.hidden = !target.hidden;
        btn.setAttribute('aria-expanded', String(!target.hidden));
      }
    });
  });

  function pct(value, max) {
    if (!max || max <= 0) return 4;
    const p = Math.round((Number(value) / Number(max)) * 100);
    return Math.min(100, Math.max(4, p));
  }

  /** Apply heights from data-bar-pct (SSR home charts; avoids Django in style="" for linters). */
  function paintBarsFromDataAttrs() {
    document.querySelectorAll('.block-chart__bar-wrap[data-bar-pct]').forEach(function (wrap) {
      const bar = wrap.querySelector('.block-chart__bar');
      if (!bar) return;
      const raw = wrap.getAttribute('data-bar-pct');
      const p = raw === null || raw === '' ? NaN : Number(raw);
      if (!Number.isFinite(p)) return;
      const hp = Math.min(100, Math.max(4, p));
      bar.style.height = hp + '%';
      wrap.setAttribute('data-bar-pct', String(hp));
    });
  }

  function rebuildBars(container, rows, valueKey, barClass) {
    if (!container || !rows || !rows.length) return;
    container.textContent = '';
    rows.forEach(function (row) {
      const wrap = document.createElement('div');
      wrap.className = 'block-chart__bar-wrap';
      const v = row[valueKey];
      const m = row.max_hint || 1;
      wrap.title = String(row.height) + ': ' + String(v);
      const bar = document.createElement('div');
      bar.className = 'block-chart__bar' + (barClass ? ' ' + barClass : '');
      const hp =
        row.bar_pct != null && row.bar_pct !== ''
          ? Math.min(100, Math.max(4, Number(row.bar_pct)))
          : pct(v, m);
      wrap.setAttribute('data-bar-pct', String(hp));
      bar.style.height = hp + '%';
      const lab = document.createElement('span');
      lab.className = 'block-chart__label';
      lab.textContent = String(row.height);
      wrap.appendChild(bar);
      wrap.appendChild(lab);
      container.appendChild(wrap);
    });
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function rebuildBlocksTable(tbody, rows, noMsg) {
    if (!tbody) return;
    tbody.textContent = '';
    if (!rows || !rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 4;
      td.textContent = noMsg;
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    rows.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdH = document.createElement('td');
      tdH.className = 'mono';
      tdH.textContent = String(r.height);
      const tdHash = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono-link mono';
      a.href = '/block/' + encodeURIComponent(r.hash) + '/';
      a.textContent = r.hash_short;
      tdHash.appendChild(a);
      const tdTx = document.createElement('td');
      tdTx.textContent = String(r.txs);
      const tdTs = document.createElement('td');
      tdTs.className = 'mono';
      tdTs.textContent = String(r.ts);
      tr.appendChild(tdH);
      tr.appendChild(tdHash);
      tr.appendChild(tdTx);
      tr.appendChild(tdTs);
      tbody.appendChild(tr);
    });
  }

  function rebuildTxsTable(tbody, rows, noMsg) {
    if (!tbody) return;
    tbody.textContent = '';
    if (!rows || !rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = noMsg;
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    const mempoolLbl = (window.TANCOIN_HOME_I18N && window.TANCOIN_HOME_I18N.mempool) || 'mempool';
    rows.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdId = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono-link mono';
      a.href = '/tx/' + encodeURIComponent(r.txid) + '/';
      a.textContent = r.txid_short;
      tdId.appendChild(a);
      const tdBl = document.createElement('td');
      if (r.mempool) {
        const sp = document.createElement('span');
        sp.className = 'badge badge-mempool';
        sp.textContent = mempoolLbl;
        tdBl.appendChild(sp);
      } else {
        tdBl.textContent = '#' + String(r.block_height);
      }
      const tdFee = document.createElement('td');
      tdFee.className = 'mono';
      tdFee.textContent = r.fee_tan != null ? String(r.fee_tan) : '—';
      tr.appendChild(tdId);
      tr.appendChild(tdBl);
      tr.appendChild(tdFee);
      tbody.appendChild(tr);
    });
  }

  function tickHome() {
    const url = window.TANCOIN_LIVE_URL;
    if (!url) return;
    fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        setText('live-stat-height', String(d.height));
        setText('live-stat-tip', d.tip_short || '');
        setText('live-stat-mempool', String(d.mempool));
        setText('live-stat-price', String(d.reference_price_usd));
        setText('live-stat-diff', String(d.initial_difficulty_bits));
        setText('live-side-mempool', String(d.mempool));
        rebuildBars(document.getElementById('live-chart-tx'), d.block_chart, 'tx_count', '');
        rebuildBars(
          document.getElementById('live-chart-interval'),
          d.interval_chart,
          'interval_s',
          'block-chart__bar--interval'
        );
        rebuildBars(
          document.getElementById('live-chart-outputs'),
          d.outputs_chart,
          'output_count',
          'block-chart__bar--outputs'
        );
        const i18n = window.TANCOIN_HOME_I18N || {};
        rebuildBlocksTable(document.getElementById('live-blocks-body'), d.recent_blocks, i18n.noBlocks || '');
        rebuildTxsTable(document.getElementById('live-txs-body'), d.recent_txs, i18n.noTx || '');
        const hint = document.getElementById('live-updated');
        if (hint) {
          const t = new Date();
          hint.textContent = (i18n.updated || 'Updated') + ' ' + t.toLocaleTimeString();
        }
        const pill = document.getElementById('live-pill');
        if (pill) {
          pill.classList.remove('live-pill--err');
        }
      })
      .catch(function () {
        const pill = document.getElementById('live-pill');
        if (pill) pill.classList.add('live-pill--err');
      });
  }

  function rebuildDonut(legendUl, ringEl, pie) {
    if (ringEl && pie && pie.conic) ringEl.style.background = pie.conic;
    if (!legendUl || !pie || !pie.legend) return;
    legendUl.textContent = '';
    pie.legend.forEach(function (item) {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chart-donut__seg';
      btn.setAttribute('data-pct', String(item.pct));
      btn.setAttribute('data-value', String(item.value));
      btn.setAttribute('data-label', String(item.label));
      btn.style.setProperty('--seg-color', item.color);
      const sw = document.createElement('span');
      sw.className = 'chart-donut__swatch';
      sw.setAttribute('aria-hidden', 'true');
      const tx = document.createElement('span');
      tx.className = 'chart-donut__seg-txt';
      tx.textContent = item.label + ' — ' + item.value + ' (' + item.pct + '%)';
      btn.appendChild(sw);
      btn.appendChild(tx);
      li.appendChild(btn);
      legendUl.appendChild(li);
    });
  }

  function wireDonutCardsOnce() {
    if (window.__tancoinDonutWired) return;
    window.__tancoinDonutWired = true;
    document.body.addEventListener('click', function (ev) {
      const btn = ev.target.closest('.chart-donut__seg');
      if (!btn) return;
      const card = btn.closest('.chart-donut-card');
      if (!card) return;
      card.querySelectorAll('.chart-donut__seg').forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      const det = card.querySelector('.chart-donut__detail');
      if (det) {
        det.textContent =
          (btn.getAttribute('data-label') || '') +
          ': ' +
          (btn.getAttribute('data-value') || '') +
          ' (' +
          (btn.getAttribute('data-pct') || '') +
          '%)';
      }
    });
  }

  function rebuildComparisonStrip(container, rows) {
    if (!container || !rows || !rows.length) return;
    container.textContent = '';
    rows.forEach(function (r) {
      const col = document.createElement('div');
      col.className = 'charts-comparison-col';
      col.title = 'Height ' + r.height;
      [
        ['tx', r.tx_bar],
        ['out', r.out_bar],
        ['fee', r.fee_bar],
      ].forEach(function (pair) {
        const kind = pair[0];
        const v = Math.max(1, Math.round(Number(pair[1]) || 1));
        const bar = document.createElement('div');
        bar.className =
          'charts-comparison-col__bar charts-comparison-col__bar--' + kind;
        bar.style.flexGrow = String(v);
        col.appendChild(bar);
      });
      const lab = document.createElement('span');
      lab.className = 'charts-comparison-col__lab mono';
      lab.textContent = String(r.height);
      col.appendChild(lab);
      container.appendChild(col);
    });
  }

  function rebuildChartsWindowTable(tbody, rows, i18n) {
    if (!tbody) return;
    tbody.textContent = '';
    const list = rows && rows.length ? rows.slice().reverse() : [];
    if (!list.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 9;
      td.textContent = i18n.noBlocks || '';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    list.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdH = document.createElement('td');
      tdH.className = 'mono';
      tdH.textContent = String(r.height);
      const tdTx = document.createElement('td');
      tdTx.textContent = String(r.tx_count);
      const tdOut = document.createElement('td');
      tdOut.textContent = String(r.output_count);
      const tdIn = document.createElement('td');
      tdIn.textContent = String(r.input_sum);
      const tdOv = document.createElement('td');
      tdOv.className = 'mono';
      tdOv.textContent = String(r.output_value_tan || '');
      const tdFee = document.createElement('td');
      tdFee.className = 'mono';
      tdFee.textContent = String(r.fee_tan || '');
      const tdGap = document.createElement('td');
      tdGap.textContent = String(r.interval_s);
      const tdMiner = document.createElement('td');
      tdMiner.className = 'mono';
      if (r.miner_address) {
        const am = document.createElement('a');
        am.className = 'mono-link';
        am.href = '/address/' + encodeURIComponent(r.miner_address) + '/';
        am.textContent = r.miner_short || '—';
        tdMiner.appendChild(am);
      } else {
        tdMiner.textContent = '—';
      }
      const tdBlk = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono';
      a.href = '/block/' + encodeURIComponent(r.hash) + '/';
      const hx = r.hash;
      a.textContent = hx.length > 16 ? hx.substring(0, 14) + '…' : hx;
      tdBlk.appendChild(a);
      tr.appendChild(tdH);
      tr.appendChild(tdTx);
      tr.appendChild(tdOut);
      tr.appendChild(tdIn);
      tr.appendChild(tdOv);
      tr.appendChild(tdFee);
      tr.appendChild(tdGap);
      tr.appendChild(tdMiner);
      tr.appendChild(tdBlk);
      tbody.appendChild(tr);
    });
  }

  function rebuildMinerLeaderboard(tbody, rows, noMsg) {
    if (!tbody) return;
    tbody.textContent = '';
    if (!rows || !rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = noMsg || '';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    rows.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdA = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono-link mono';
      a.href = '/address/' + encodeURIComponent(r.address) + '/';
      a.textContent = r.address_short || r.address;
      tdA.appendChild(a);
      const tdB = document.createElement('td');
      tdB.textContent = String(r.blocks);
      const tdP = document.createElement('td');
      tdP.className = 'mono';
      tdP.textContent = String(r.pct) + '%';
      tr.appendChild(tdA);
      tr.appendChild(tdB);
      tr.appendChild(tdP);
      tbody.appendChild(tr);
    });
  }

  function rebuildChartsTopTable(tbody, rows, i18n) {
    if (!tbody) return;
    tbody.textContent = '';
    if (!rows || !rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 3;
      td.textContent = i18n.noBlocks || '';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    rows.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdH = document.createElement('td');
      tdH.className = 'mono';
      tdH.textContent = String(r.height);
      const tdTx = document.createElement('td');
      tdTx.textContent = String(r.tx_count);
      const tdBlk = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono';
      a.href = '/block/' + encodeURIComponent(r.hash) + '/';
      const hx = r.hash;
      a.textContent = hx.length > 16 ? hx.substring(0, 14) + '…' : hx;
      tdBlk.appendChild(a);
      tr.appendChild(tdH);
      tr.appendChild(tdTx);
      tr.appendChild(tdBlk);
      tbody.appendChild(tr);
    });
  }

  function rebuildChartsRecentTxs(tbody, rows, noMsg) {
    if (!tbody) return;
    tbody.textContent = '';
    const i18n = window.TANCOIN_CHARTS_I18N || {};
    const ml = i18n.mempool || 'mempool';
    if (!rows || !rows.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 5;
      td.textContent = noMsg || i18n.noTx || '';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    rows.forEach(function (r) {
      const tr = document.createElement('tr');
      const tdId = document.createElement('td');
      const a = document.createElement('a');
      a.className = 'mono-link mono';
      a.href = '/tx/' + encodeURIComponent(r.txid) + '/';
      a.textContent = r.txid_short;
      tdId.appendChild(a);
      const tdBl = document.createElement('td');
      if (r.mempool) {
        const sp = document.createElement('span');
        sp.className = 'badge badge-mempool';
        sp.textContent = ml;
        tdBl.appendChild(sp);
      } else {
        tdBl.textContent = '#' + String(r.block_height);
      }
      const tdIn = document.createElement('td');
      tdIn.textContent = String(r.input_count);
      const tdOut = document.createElement('td');
      tdOut.textContent = String(r.output_count);
      const tdFee = document.createElement('td');
      tdFee.className = 'mono';
      tdFee.textContent = r.fee_tan != null ? String(r.fee_tan) : '—';
      tr.appendChild(tdId);
      tr.appendChild(tdBl);
      tr.appendChild(tdIn);
      tr.appendChild(tdOut);
      tr.appendChild(tdFee);
      tbody.appendChild(tr);
    });
  }

  function applyDonutsFromPayload(d) {
    var pairs = [
      ['chart-ring-tx-role', 'chart-legend-tx-role', d.pie_tx_role],
      ['chart-ring-tx-hist', 'chart-legend-tx-hist', d.pie_tx_histogram],
      ['chart-ring-out-kind', 'chart-legend-out-kind', d.pie_output_kinds],
      ['chart-ring-fee-bucket', 'chart-legend-fee-bucket', d.pie_fee_blocks],
    ];
    if (d.pie_miners) {
      pairs.push(['chart-ring-miners', 'chart-legend-miners', d.pie_miners]);
    }
    pairs.forEach(function (row) {
      rebuildDonut(document.getElementById(row[1]), document.getElementById(row[0]), row[2]);
    });
  }

  function tickCharts() {
    var url = window.TANCOIN_CHARTS_LIVE_URL;
    if (!url) return;
    fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        var i18n = window.TANCOIN_CHARTS_I18N || {};
        if (d.stats) {
          document.querySelectorAll('.charts-live-stat[data-stat]').forEach(function (el) {
            var k = el.getAttribute('data-stat');
            if (k && d.stats[k] !== undefined) el.textContent = d.stats[k];
          });
        }
        if (d.interval_stats) {
          document.querySelectorAll('.charts-live-interval[data-interval]').forEach(function (el) {
            var k = el.getAttribute('data-interval');
            if (k && d.interval_stats[k] !== undefined) el.textContent = String(d.interval_stats[k]);
          });
        }
        var tipEl = document.getElementById('charts-live-tip');
        if (tipEl && d.tip_short) tipEl.textContent = d.tip_short;
        rebuildBars(document.getElementById('charts-live-tx'), d.block_chart, 'tx_count', '');
        rebuildBars(
          document.getElementById('charts-live-interval'),
          d.interval_chart,
          'interval_s',
          'block-chart__bar--interval'
        );
        rebuildBars(
          document.getElementById('charts-live-outputs'),
          d.outputs_chart,
          'output_count',
          'block-chart__bar--outputs'
        );
        rebuildBars(document.getElementById('charts-live-fee'), d.fee_chart, 'fee_sat', 'block-chart__bar--fee');
        rebuildBars(
          document.getElementById('charts-live-value'),
          d.output_value_bars,
          'value_sat',
          'block-chart__bar--value'
        );
        applyDonutsFromPayload(d);
        rebuildComparisonStrip(document.getElementById('charts-comparison-strip'), d.comparison_strip);
        rebuildChartsWindowTable(document.getElementById('charts-window-body'), d.window_rows, i18n);
        rebuildMinerLeaderboard(
          document.getElementById('charts-miners-body'),
          d.miner_leaderboard,
          i18n.noBlocks || ''
        );
        rebuildChartsTopTable(document.getElementById('charts-top-blocks-body'), d.top_blocks_by_tx, i18n);
        rebuildChartsRecentTxs(document.getElementById('charts-recent-tx-body'), d.recent_txs, i18n.noTx || '');
        var hint = document.getElementById('charts-live-updated');
        if (hint) {
          var t = new Date();
          hint.textContent = (i18n.updated || 'Updated') + ' ' + t.toLocaleTimeString();
        }
        var pill = document.getElementById('charts-live-pill');
        if (pill) pill.classList.remove('live-pill--err');
      })
      .catch(function () {
        var pill = document.getElementById('charts-live-pill');
        if (pill) pill.classList.add('live-pill--err');
      });
  }

  paintBarsFromDataAttrs();

  if (document.body.classList.contains('explorer-dash-charts')) {
    wireDonutCardsOnce();
  }

  if (document.body.classList.contains('explorer-dash-home')) {
    tickHome();
    setInterval(tickHome, 12000);
  }

  if (document.body.classList.contains('explorer-dash-charts')) {
    tickCharts();
    setInterval(tickCharts, 10000);
  }
})();
