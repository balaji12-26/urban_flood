/* FloodSense — Methods & Limitations panel: canonical text from the backend, provenance grid, engine constants. */
(function () {
  const FS = window.FS;
  const $ = id => document.getElementById(id);

  const FALLBACK_TEXT = `FloodSense — Methods & Limitations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Relative Flood Risk Index (0–100).
Not a probability. Not a validated prediction.
For scenario exploration and zone comparison only.

FORMULA: index = 100 × (1 − exp(−Σ(factor × weight) / 0.7))
Weights: rainfall 0.30 · forecast 0.20 · water_level 0.20
         drainage 0.15 · terrain 0.10 · history 0.05

DATA SOURCES:
  LIVE        Current rainfall       Open-Meteo API
  FORECAST    Next 6h rainfall       Open-Meteo API
  SIMULATED   Water level            Synthetic sensor (no real device)
  DERIVED     Terrain risk           SRTM elevation, OpenTopoData
  PROFILE     Drainage, history      Zone characteristics

ZONE BOUNDARIES: Approximate demonstration polygons.
Not administrative wards or hydrological catchments.

CANNOT DO: Predict exact flood onset · Replace IMD/NDMA ·
Account for real-time drainage state or upstream inflow.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

  const PROV = [
    ['LIVE', 'Current rainfall', 'Open-Meteo API (city centroid, hourly, no key)'],
    ['FORECAST', 'Next 6h rainfall', 'Open-Meteo API hourly forecast'],
    ['SIMULATED', 'Water level', 'Synthetic sensor — deterministic 30 s noise, no real device'],
    ['DERIVED', 'Terrain risk', 'SRTM elevation via OpenTopoData, normalised 0–1'],
    ['PROFILE', 'Drainage, history', 'Hand-authored zone characteristics'],
  ];

  function renderConstants(m) {
    const w = m.weights || {}, t = m.thresholds || {};
    $('methods-constants').innerHTML =
      Object.entries(w).map(([k, v]) => `<div><span>weight · ${FS.FACTOR_LABELS[k] || k} ${FS.badge((m.data_labels || {})[k] || '')}</span><span>${v.toFixed(2)}</span></div>`).join('') +
      `<div><span>Σ weights</span><span>${Object.values(w).reduce((a, b) => a + b, 0).toFixed(2)}</span></div>` +
      `<div><span>k (soft-saturation)</span><span>${m.k}</span></div>` +
      Object.entries(t).map(([k, v]) => `<div><span>threshold · ${k}</span><span>≥ ${v}</span></div>`).join('') +
      `<div><span>formula</span><span style="font-family:monospace;font-size:11px">${FS.esc(m.formula || '')}</span></div>`;
  }

  async function load() {
    $('prov-grid').innerHTML = `<div class="ph">Label</div><div class="ph">Input</div><div class="ph c3">Source</div>` +
      PROV.map(([l, i, s]) => `<div>${FS.badge(l)}</div><div>${i}</div><div class="c3 muted">${s}</div>`).join('');
    try {
      const m = await FS.api.getMethods();
      $('methods-text').textContent = m.text || FALLBACK_TEXT;
      renderConstants(m);
    } catch (_) {
      $('methods-text').textContent = FALLBACK_TEXT;
      const d = FS.state.data;
      if (d && d.model) renderConstants(Object.assign({ formula: 'index = 100 * (1 - exp(-sum(factor_raw * weight) / k))' }, d.model));
      else $('methods-constants').innerHTML = '<span class="hint">backend unavailable</span>';
    }
  }

  FS.bus.on('boot', load);
})();
