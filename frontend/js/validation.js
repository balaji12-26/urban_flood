/* FloodSense — Validation panel: monotonicity, weight sensitivity, baseline comparison, historical replay.
   All checks run live against the engine via /api/validation/*. */
(function () {
  const FS = window.FS;
  const $ = id => document.getElementById(id);
  const charts = {};
  let ran = false;

  function chart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id).getContext('2d'), cfg);
  }
  const axis = extra => Object.assign({ ticks: { color: '#7c87a6', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,.06)' } }, extra || {});
  const legend = { labels: { color: '#a9b3cc', boxWidth: 10, font: { family: 'Inter', size: 11 } } };
  const stat = (v, label, ok) => `<div class="stat ${ok === true ? 'ok' : ok === false ? 'bad' : ''}"><b>${v}</b><span>${label}</span></div>`;
  const names = () => Object.fromEntries((FS.state.data ? FS.state.data.zones : []).map(z => [z.id, z.name]));
  const nm = id => names()[id] || id;

  // ───── 1. monotonicity ─────
  function renderMono(m) {
    $('val-mono-status').textContent = `${m.passed}/${m.total} checks pass`;
    $('val-monotone').innerHTML = `<div class="mono-grid">${m.checks.map(c => `
      <div class="mono-cell ${c.monotone ? 'ok' : 'bad'}" title="${c.lever}: ${c.values.join(', ')}">
        <span>${FS.esc(c.zone_name)}<br><small>${c.lever.replace(/_/g, ' ')}</small></span>
        <span class="spark">${c.indices.map(i => i.toFixed(0)).join('→')}</span>
      </div>`).join('')}</div>`;
    return m.all_passed;
  }

  // ───── 2. sensitivity ─────
  function renderSens(s) {
    $('val-sens-status').textContent = `min rank agreement ${s.min_rank_agreement} · top zone stable in ${s.top_zone_stable_in}/${s.total_sweeps} sweeps`;
    const ws = s.sweeps.filter(x => x.kind === 'weight');
    chart('chart-sens', {
      type: 'bar',
      data: {
        labels: ws.map(x => `${x.factor} ${x.delta > 0 ? '+' : ''}${x.delta.toFixed(2)}`),
        datasets: [
          { label: 'max |Δ index| across zones', data: ws.map(x => x.max_abs_change), backgroundColor: 'rgba(79,140,255,.55)', borderRadius: 4, yAxisID: 'y' },
          { label: 'rank agreement (Spearman)', data: ws.map(x => x.rank_agreement), type: 'line', borderColor: '#2ecc8f', pointBackgroundColor: '#2ecc8f', yAxisID: 'y2', tension: .3 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend },
        scales: { x: axis({ ticks: { color: '#7c87a6', font: { size: 9 }, maxRotation: 45 } }), y: axis({ min: 0, title: { display: true, text: 'index points', color: '#7c87a6', font: { size: 10 } } }),
          y2: axis({ position: 'right', min: 0, max: 1, grid: { drawOnChartArea: false } }) } },
    });
    const ks = s.sweeps.filter(x => x.kind === 'k');
    $('val-sensitivity').innerHTML = `<div class="kv">
      <div><span>Baseline ranking</span><span>${s.baseline_ranking.map(nm).join(' › ')}</span></div>
      <div><span>Mean rank agreement</span><span>${s.mean_rank_agreement}</span></div>
      ${ks.map(x => `<div><span>k = ${x.k}</span><span>max Δ ${x.max_abs_change} · agreement ${x.rank_agreement}</span></div>`).join('')}
    </div>`;
    return s.min_rank_agreement;
  }

  // ───── 3. baseline ─────
  function renderBase(b) {
    $('val-base-status').textContent = `full-model spread ${b.full_spread} pts`;
    const zones = b.full_ranking;
    const palette = { full_model: '#4f8cff', rainfall_only: '#2ecc8f', static_only: '#a9b3cc', equal_weights: '#f2c94c' };
    chart('chart-baseline', {
      type: 'bar',
      data: { labels: zones.map(nm),
        datasets: Object.entries(b.indices_by_model).map(([model, row]) => ({ label: model.replace(/_/g, ' '), data: zones.map(z => row[z]), backgroundColor: palette[model], borderRadius: 3 })) },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend }, scales: { x: axis(), y: axis({ min: 0, max: 100 }) } },
    });
    $('val-baseline').innerHTML = `<table class="table"><thead><tr><th>Baseline</th><th>Ranking</th><th>Agreement w/ full</th><th>Spread</th></tr></thead><tbody>
      ${b.comparisons.map(c => `<tr><td><b>${c.baseline.replace(/_/g, ' ')}</b></td><td class="hint">${c.ranking.map(nm).join(' › ')}</td><td>${c.rank_agreement_with_full}</td><td>${c.spread}</td></tr>`).join('')}
    </tbody></table>`;
  }

  // ───── 4. replay ─────
  function renderReplay(r) {
    const banner = $('replay-banner');
    banner.innerHTML = `<strong>⚠ ${FS.esc(r.banner)}</strong><br>
      <span class="small">Date ${r.date} · rainfall source: <b>${FS.esc(r.rainfall_provider || r.rainfall_source)}</b> · daily total ${r.daily_total_mm} mm · water level: ${FS.badge('SIMULATED')} reconstructed</span>
      ${r.rainfall_is_synthetic ? `<br><span class="small" style="color:#ffb3c0">Archive unreachable (${FS.esc(r.archive_error || '')}). Rainfall shown is a SYNTHETIC shape, not a historical record.</span>` : ''}`;
    const labels = r.hourly_times.map(t => (t || '').slice(11, 16) || '');
    const lineColors = ['#4f8cff', '#ff4d6d', '#f2c94c', '#2ecc8f', '#b57bff', '#ff8c42'];
    chart('chart-replay', {
      data: {
        labels,
        datasets: [
          { type: 'bar', label: 'rain mm/h (archive)', data: r.hourly_precip_mm, backgroundColor: 'rgba(79,195,247,.3)', yAxisID: 'y2', borderRadius: 2 },
          ...r.series.map((s, i) => ({ type: 'line', label: s.name, data: s.points.map(p => p.index), borderColor: lineColors[i % lineColors.length], pointRadius: 0, borderWidth: 2, tension: .3, yAxisID: 'y' })),
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend }, interaction: { mode: 'index', intersect: false },
        scales: { x: axis(), y: axis({ min: 0, max: 100, title: { display: true, text: 'Relative Flood Risk Index', color: '#7c87a6', font: { size: 10 } } }),
          y2: axis({ position: 'right', min: 0, grid: { drawOnChartArea: false }, title: { display: true, text: 'mm/h', color: '#4fc3f7', font: { size: 10 } } }) } },
    });
    $('val-replay').innerHTML = `<table class="table"><thead><tr><th>Zone</th><th>Peak index</th><th>Peak hour</th><th>Hours ≥ HIGH</th></tr></thead><tbody>
      ${r.series.map(s => `<tr><td><b>${FS.esc(s.name)}</b></td><td style="color:${FS.levelColor(s.peak_level)};font-weight:700">${FS.fmt1(s.peak_index)} <span class="lvl lvl-${s.peak_level}" style="font-size:9.5px">${s.peak_level}</span></td><td>${String(s.peak_hour).padStart(2, '0')}:00</td><td>${s.hours_at_or_above_high}</td></tr>`).join('')}
    </tbody></table>`;
  }

  async function runAll() {
    const btn = $('btn-validate'); btn.disabled = true; btn.textContent = 'Running…';
    $('validation-summary').innerHTML = '<span class="hint">running monotonicity, sensitivity, baseline and replay…</span>';
    try {
      const date = $('replay-date').value || '2015-12-01';
      const v = await FS.api.getValidation('all', { date, sensor_mode: FS.state.sensorMode });
      const monoOk = renderMono(v.monotone);
      const minAgree = renderSens(v.sensitivity);
      renderBase(v.baseline);
      renderReplay(v.replay);
      $('validation-summary').innerHTML =
        stat(`${v.monotone.passed}/${v.monotone.total}`, 'monotone checks', monoOk) +
        stat(minAgree, 'min rank agreement', minAgree >= 0.8) +
        stat(v.baseline.full_spread, 'index spread (full model)') +
        stat(v.replay.daily_total_mm + ' mm', `rain on ${v.replay.date}`) +
        stat(v.weather_stale ? 'STALE' : 'LIVE', `weather · sensor ${v.sensor_mode}`, !v.weather_stale);
      ran = true;
    } catch (e) {
      $('validation-summary').innerHTML = `<span class="flag">Validation needs the backend: ${FS.esc(e.message)}</span>`;
    } finally { btn.disabled = false; btn.textContent = 'Run checks'; }
  }

  async function runReplayOnly() {
    try { renderReplay(await FS.api.getValidation('replay', { date: $('replay-date').value })); }
    catch (e) { $('replay-banner').textContent = `Replay failed: ${e.message}`; }
  }

  FS.bus.on('boot', () => {
    $('btn-validate').addEventListener('click', runAll);
    $('btn-replay').addEventListener('click', runReplayOnly);
  });
  FS.bus.on('tab', t => { if (t === 'validation' && !ran) runAll(); });
})();
