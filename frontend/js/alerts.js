/* FloodSense — pre-authored action card for the selected zone. Always carries the prototype disclaimer. */
(function () {
  const FS = window.FS;

  function render(id) {
    const z = FS.state.zonesById[id];
    const box = document.getElementById('alert-panel');
    if (!z || !z.action) { box.innerHTML = ''; return; }
    const a = z.action, r = z.risk, c = FS.levelColor(r.risk_level);
    box.className = 'card alert-card';
    box.style.borderLeftColor = c;
    box.innerHTML = `
      <div class="card-head">
        <h2>Suggested action</h2>
        <span><span class="lvl lvl-${r.risk_level}">${r.risk_level}</span> <span class="hint">· driven by ${FS.FACTOR_LABELS[a.based_on.top_dynamic]} ${FS.badge(r.data_labels[a.based_on.top_dynamic])}</span></span>
      </div>
      <div class="alert-text">${FS.esc(a.text)}</div>
      <div class="alert-basis">Pre-authored template <code>${FS.esc(a.based_on.template_key)}</code> selected by (risk level, top dynamic factor). No generated text.</div>
      <div class="alert-disc">${FS.esc(a.disclaimer)}</div>`;
  }

  FS.bus.on('zone:select', render);
  FS.bus.on('data', () => FS.state.selectedZone && render(FS.state.selectedZone));
})();
