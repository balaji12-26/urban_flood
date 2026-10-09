/* FloodSense — Leaflet map with GeoJSON zone polygons coloured by risk level, plus the ranking list. */
(function () {
  const FS = window.FS;
  let map, layer, geo;
  const polys = {};

  function style(zone) {
    const lvl = zone ? zone.risk.risk_level : 'LOW';
    const c = FS.levelColor(lvl);
    const sel = zone && zone.id === FS.state.selectedZone;
    return { color: sel ? '#ffffff' : c, weight: sel ? 3 : 1.5, fillColor: c, fillOpacity: sel ? 0.55 : 0.38 };
  }

  function popup(z) {
    const r = z.risk;
    return `<div style="min-width:180px">
      <div style="font-weight:700;font-size:14px">${FS.esc(z.name)}</div>
      <div style="margin:4px 0"><span style="font-size:22px;font-weight:800;color:${FS.levelColor(r.risk_level)}">${FS.fmt1(r.index)}</span>
        <span class="lvl lvl-${r.risk_level}" style="margin-left:6px">${r.risk_level}</span></div>
      <div style="font-size:11.5px;color:#a9b3cc">Relative Flood Risk Index (0–100)</div>
      <div style="font-size:11.5px;margin-top:4px">Top driver: <b>${FS.FACTOR_LABELS[r.top_driver]}</b> ${FS.badge(r.data_labels[r.top_driver])}</div>
      <div style="font-size:11px;color:#7c87a6;margin-top:4px">Approximate demonstration polygon</div>
    </div>`;
  }

  async function init() {
    map = L.map('map', { zoomControl: true, attributionControl: true }).setView([12.975, 80.20], 11);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18, className: 'dark-tiles',
    }).addTo(map);
    geo = await FS.api.getGeoJSON();
    if (!geo) return;
    layer = L.geoJSON(geo, {
      style: f => style(FS.state.zonesById[f.properties.id]),
      onEachFeature: (f, l) => {
        polys[f.properties.id] = l;
        l.on('click', () => FS.bus.emit('zone:select', f.properties.id));
        l.on('mouseover', () => l.setStyle({ fillOpacity: 0.65 }));
        l.on('mouseout', () => l.setStyle(style(FS.state.zonesById[f.properties.id])));
      },
    }).addTo(map);
    const fit = () => { map.invalidateSize(); try { map.fitBounds(layer.getBounds().pad(0.08)); } catch (_) { /* ignore */ } };
    fit();
    setTimeout(fit, 250);            // layout may still be settling (fonts, sticky column)
    window.addEventListener('resize', () => map.invalidateSize());
    if (FS.state.data) update(FS.state.data);
  }

  function update(d) {
    if (!layer) return;
    d.zones.forEach(z => {
      const l = polys[z.id];
      if (!l) return;
      l.setStyle(style(z));
      l.bindPopup(popup(z));
      l.bindTooltip(`${z.name} · ${FS.fmt1(z.risk.index)}`, { direction: 'center', permanent: false, className: 'zone-tip' });
    });
    renderList(d);
  }

  function renderList(d) {
    const ol = document.getElementById('zone-list');
    ol.innerHTML = d.zones.map(z => {
      const r = z.risk, c = FS.levelColor(r.risk_level);
      return `<li class="zone-row ${z.id === FS.state.selectedZone ? 'selected' : ''}" data-id="${z.id}">
        <span class="zone-rank">${z.rank || ''}</span>
        <span><span class="zone-name">${FS.esc(z.name)}</span><br><span class="zone-driver">${FS.FACTOR_LABELS[r.top_driver]} ${FS.badge(r.data_labels[r.top_driver])}</span></span>
        <span class="zone-bar"><i style="width:${Math.min(100, r.index)}%;background:${c}"></i></span>
        <span class="zone-idx" style="color:${c}">${FS.fmt1(r.index)}</span>
      </li>`;
    }).join('');
    ol.querySelectorAll('.zone-row').forEach(li => li.addEventListener('click', () => FS.bus.emit('zone:select', li.dataset.id)));
  }

  function select(id) {
    FS.state.selectedZone = id;
    document.querySelectorAll('.zone-row').forEach(li => li.classList.toggle('selected', li.dataset.id === id));
    Object.entries(polys).forEach(([zid, l]) => l.setStyle(style(FS.state.zonesById[zid])));
    const l = polys[id];
    if (l && map) { l.bringToFront(); }
  }

  FS.bus.on('boot', init);
  FS.bus.on('data', update);
  FS.bus.on('zone:select', select);
  FS.map = { invalidate: () => map && map.invalidateSize() };
})();
