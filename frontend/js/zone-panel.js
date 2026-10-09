/* FloodSense — Zone explainer: index gauge, factor breakdown with provenance badges,
   water-level toggle (true drop, no renormalisation), quality flags, profile. */
(function () {
  const FS = window.FS;
  const el = () => document.getElementById('zone-panel');

  function factorRow(key, r, z) {
    const raw = r.factor_raws[key], w = r.weights_used[key], contrib = r.contributions[key];
    const label = r.data_labels[key];
    const pct = Math.min(100, raw * 100);
    const isTop = key === r.top_driver;
    const isSim = key === 'water_level';
    const dim = isSim && !FS.state.showWaterLevel;
    const sub = {
      rainfall: `${FS.fmt1(z.observations.precip_1h_mm)} mm/h ÷ safe limit ${z.profile.max_safe_rain_1h} mm/h`,
      forecast: `${FS.fmt1(z.observations.forecast_6h_total_mm)} mm over 6h ÷ safe limit ${z.profile.max_safe_rain_6h} mm`,
      water_level: `${FS.fmt1(z.observations.water_level_cm)} cm ÷ flood mark ${z.profile.flood_water_level_cm} cm · synthetic sensor, no real device`,
      drainage: `1 − effective capacity (${z.profile.drainage_capacity_0_1})`,
      terrain: `terrain risk ${z.profile.terrain_risk_0_1} (SRTM / OpenTopoData derived)`,
      history: `historical flood frequency ${z.profile.historical_flood_freq_0_1}`,
    }[key];
    return `<div class="factor ${isTop ? 'top' : ''}" style="${dim ? 'opacity:.35' : ''}" title="raw ${raw} × weight ${w} = ${contrib}">
      <div class="factor-name">${FS.FACTOR_LABELS[key]} ${FS.badge(label)}</div>
      <div class="factor-bar ${isSim ? 'is-sim' : ''}"><i style="width:${pct}%"></i></div>
      <div class="factor-val">${raw.toFixed(2)} × ${w.toFixed(2)}</div>
      <div class="factor-sub">${sub} → contribution <b>${contrib.toFixed(3)}</b></div>
    </div>`;
  }

  function render(id) {
    const z = FS.state.zonesById[id];
    if (!z) return;
    const r = z.risk, v = z.water_level_views || {};
    const shown = FS.state.showWaterLevel ? r.index : v.without_water_level;
    const lvl = FS.state.showWaterLevel ? r.risk_level : classify(v.without_water_level);
    const c = FS.levelColor(lvl);
    const flags = Object.entries(z.quality_flags || {});
    const w = (FS.state.data || {}).weather || {};

    el().innerHTML = `
      <div class="zp-head">
        <div class="zp-title">
          <h2>${FS.esc(z.name)}</h2>
          <div class="zp-notes">${FS.esc(z.notes)} · ${z.lat.toFixed(4)}, ${z.lon.toFixed(4)}</div>
        </div>
        <div class="gauge">
          <div class="gauge-ring" style="--pct:${Math.min(100, shown)};--ring-color:${c}"><span class="gauge-val" style="color:${c}">${FS.fmt1(shown)}</span></div>
          <div class="gauge-meta">
            <span class="gauge-label">Relative Flood Risk Index (0–100)</span>
            <span class="lvl lvl-${lvl}">${lvl}</span>
            <span class="hint">rank #${z.rank || '—'} of ${(FS.state.data || { zones: [] }).zones.length}</span>
          </div>
        </div>
      </div>

      <div class="factors">${Object.keys(r.weights_used).map(k => factorRow(k, r, z)).join('')}</div>

      <div class="wl-toggle">
        <div class="row">
          <div><strong>Water level</strong> ${FS.badge('SIMULATED')} <span class="hint">synthetic sensor · toggle to see its true contribution</span></div>
          <label class="switch"><input type="checkbox" id="toggle-wl" ${FS.state.showWaterLevel ? 'checked' : ''}><span>Include</span></label>
        </div>
        <div class="wl-compare">
          <div><b>${FS.fmt1(v.with_water_level)}</b><div class="sub">with water level</div></div>
          <div><b>${FS.fmt1(v.without_water_level)}</b><div class="sub">without (factor dropped, no renormalisation)</div></div>
          <div><b>${FS.fmt1((v.with_water_level || 0) - (v.without_water_level || 0))}</b><div class="sub">true contribution to index</div></div>
        </div>
      </div>

      ${flags.length ? `<div class="flags">${flags.map(([k, msg]) => `<div class="flag">⚠ ${FS.FACTOR_LABELS[k] || k}: ${FS.esc(msg)}</div>`).join('')}</div>` : ''}
      ${w.stale ? `<div class="flags"><div class="flag">⚠ Rainfall inputs are ${w.source === 'offline-fallback' ? 'an offline fallback sample' : 'stale'} — see banner.</div></div>` : ''}

      <div class="kv" style="margin-top:14px">
        <div><span>Weighted sum Σ(raw × w)</span><span>${r.weighted_sum}</span></div>
        <div><span>Soft-scale k</span><span>${r.k_used}</span></div>
        <div><span>Top dynamic driver</span><span>${FS.FACTOR_LABELS[r.top_dynamic]}</span></div>
        <div><span>Top static driver</span><span>${FS.FACTOR_LABELS[r.top_static]}</span></div>
        <div><span>Forecast 6h ${FS.badge('FORECAST')}</span><span>${(z.observations.forecast_6h_mm || []).map(x => FS.fmt1(x)).join(' · ')} mm</span></div>
        <div><span>Observation time</span><span>${FS.esc(w.observation_time || '—')}</span></div>
      </div>`;

    document.getElementById('toggle-wl').addEventListener('change', e => { FS.state.showWaterLevel = e.target.checked; render(id); });
  }

  function classify(i) {
    const t = ((FS.state.data || {}).model || {}).thresholds || { MODERATE: 30, HIGH: 55, CRITICAL: 75 };
    if (i == null) return 'LOW';
    return i < t.MODERATE ? 'LOW' : i < t.HIGH ? 'MODERATE' : i < t.CRITICAL ? 'HIGH' : 'CRITICAL';
  }

  FS.bus.on('zone:select', render);
  FS.bus.on('data', () => FS.state.selectedZone && render(FS.state.selectedZone));
})();
