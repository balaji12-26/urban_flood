/* FloodSense — Scenario simulator: sliders → POST /api/scenario (local per-zone overrides),
   before/after table, and the 6-hour projection curve (Chart.js). */
(function () {
  const FS = window.FS;
  let curveChart = null, timer = null, inflight = 0;

  const $ = id => document.getElementById(id);
  const sliders = () => ({ rain: $('sl-rain'), drain: $('sl-drain'), wl: $('sl-wl') });

  function readScenario() {
    const s = sliders();
    return {
      rainfall_multiplier: parseFloat(s.rain.value),
      drainage_blockage: parseFloat(s.drain.value),
      water_level_rise_cm: parseFloat(s.wl.value),
    };
  }
  function isIdentity(sc) { return sc.rainfall_multiplier === 1 && sc.drainage_blockage === 0 && sc.water_level_rise_cm === 0; }

  function paintOutputs(sc) {
    $('out-rain').textContent = `${sc.rainfall_multiplier.toFixed(1)}×`;
    $('out-drain').textContent = `${Math.round(sc.drainage_blockage * 100)}%`;
    $('out-wl').textContent = `+${Math.round(sc.water_level_rise_cm)} cm`;
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(run, 120);
  }

  async function run() {
    const sc = readScenario();
    FS.state.scenario = sc;
    paintOutputs(sc);
    const w = (FS.state.data || {}).weather || {};
    const dry = (w.precip_1h_mm || 0) === 0 && ((w.forecast_6h_mm || []).reduce((a, b) => a + b, 0)) === 0;
    $('sim-dry-hint').classList.toggle('hidden', !dry);
    const body = {};
    if (!isIdentity(sc)) {
      if (FS.state.scope === 'all') body.global = sc;
      else body.zone_scenarios = { [FS.state.selectedZone]: sc };
    }
    const my = ++inflight;
    $('sim-status').textContent = 'scoring…';
    try {
      const [res, curve] = await Promise.all([
        FS.api.postScenario(body),
        FS.api.getForecastCurve(FS.state.selectedZone, isIdentity(sc) ? {} : sc),
      ]);
      if (my !== inflight) return; // stale response
      renderTable(res);
      renderCurve(curve);
      $('sim-status').textContent = isIdentity(sc) ? 'no overrides' :
        (FS.state.scope === 'all' ? 'applied to all zones' : `applied to ${FS.state.zonesById[FS.state.selectedZone].name} only`);
    } catch (e) {
      $('sim-status').textContent = FS.state.usingMock ? 'simulator needs the backend (mock mode)' : `error: ${e.message}`;
    }
  }

  function renderTable(res) {
    const tb = $('sim-table').querySelector('tbody');
    tb.innerHTML = res.zones.map(z => {
      const d = z.delta, cls = d > 0 ? 'pos' : d < 0 ? 'neg' : 'zero';
      const touched = Object.keys(z.scenario_applied || {}).length > 0;
      return `<tr class="${touched ? 'changed' : ''}">
        <td><b>${FS.esc(z.name)}</b>${touched ? ' <span class="hint">· override</span>' : ''}</td>
        <td>${FS.fmt1(z.baseline_index)} <span class="lvl lvl-${z.baseline_level}" style="font-size:9.5px">${z.baseline_level}</span></td>
        <td style="color:${FS.levelColor(z.risk.risk_level)};font-weight:700">${FS.fmt1(z.risk.index)}</td>
        <td class="${cls}">${d > 0 ? '+' : ''}${FS.fmt1(d)}</td>
        <td><span class="lvl lvl-${z.risk.risk_level}">${z.risk.risk_level}</span>${z.level_changed ? ' <span class="hint">↑ changed</span>' : ''}</td>
      </tr>`;
    }).join('');
  }

  function renderCurve(curve) {
    const c = (curve.curves || [])[0];
    if (!c) return;
    const labels = c.points.map(p => p.label);
    const idx = c.points.map(p => p.index);
    const rain = c.points.map(p => p.precip_mm);
    const colors = c.points.map(p => FS.levelColor(p.risk_level));
    const ctx = $('chart-curve').getContext('2d');
    if (curveChart) curveChart.destroy();
    curveChart = new Chart(ctx, {
      data: {
        labels,
        datasets: [
          { type: 'line', label: `${c.name} · index`, data: idx, borderColor: '#4f8cff', backgroundColor: 'rgba(79,140,255,.15)', fill: true,
            tension: .35, pointBackgroundColor: colors, pointBorderColor: colors, pointRadius: 5, yAxisID: 'y' },
          { type: 'bar', label: 'rain mm/h (forecast)', data: rain, backgroundColor: 'rgba(79,195,247,.35)', borderRadius: 4, yAxisID: 'y2' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
        plugins: { legend: { labels: { color: '#a9b3cc', boxWidth: 10, font: { family: 'Inter', size: 11 } } },
          tooltip: { callbacks: { afterBody: items => { const p = c.points[items[0].dataIndex]; return [`level: ${p.risk_level}`, `water level (SIMULATED): ${p.water_level_cm} cm`, `6h window: ${p.forecast_window_mm} mm`]; } } } },
        scales: {
          x: { ticks: { color: '#7c87a6' }, grid: { color: 'rgba(255,255,255,.05)' } },
          y: { min: 0, max: 100, ticks: { color: '#7c87a6' }, grid: { color: 'rgba(255,255,255,.06)' }, title: { display: true, text: 'Relative Flood Risk Index', color: '#7c87a6', font: { size: 10 } } },
          y2: { position: 'right', min: 0, ticks: { color: '#4fc3f7' }, grid: { drawOnChartArea: false }, title: { display: true, text: 'mm/h', color: '#4fc3f7', font: { size: 10 } } },
        },
      },
    });
  }

  function reset() {
    const s = sliders();
    s.rain.value = 1; s.drain.value = 0; s.wl.value = 0;
    schedule();
  }
  const PRESETS = {
    cloudburst: { rain: 2.5, drain: 0, wl: 0 },
    blocked: { rain: 1, drain: 0.7, wl: 0 },
    lake: { rain: 1, drain: 0, wl: 60 },
  };

  function init() {
    const s = sliders();
    Object.values(s).forEach(el => el.addEventListener('input', schedule));
    $('btn-sim-reset').addEventListener('click', reset);
    document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => {
      const p = PRESETS[b.dataset.preset]; s.rain.value = p.rain; s.drain.value = p.drain; s.wl.value = p.wl; schedule();
    }));
    document.querySelectorAll('#sim-scope .seg-btn').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('#sim-scope .seg-btn').forEach(x => x.classList.toggle('active', x === b));
      FS.state.scope = b.dataset.scope; schedule();
    }));
    paintOutputs(readScenario());
  }

  FS.bus.on('boot', init);
  FS.bus.on('data', schedule);
  FS.bus.on('zone:select', schedule);
  FS.bus.on('tab', t => { if (t === 'simulator') schedule(); });
})();
