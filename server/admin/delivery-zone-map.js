(() => {
  const NEEMUCH_CENTER = [24.4764, 74.8624];
  let map = null;
  let polygon = null;
  let markers = [];
  let points = [];

  const round = value => Number(value).toFixed(6);
  const textForPoints = rows => rows.map(([lat, lng]) => `${round(lat)}, ${round(lng)}`).join('\n');

  function readPoints() {
    const textarea = byId('delivery-zone-boundary');
    if (!textarea || !textarea.value.trim()) return [];
    try {
      const ring = parseDeliveryZoneBoundary(textarea.value);
      return ring.slice(0, -1).map(([lng, lat]) => [lat, lng]);
    } catch {
      return [];
    }
  }

  function markUnsaved() {
    const activate = document.querySelector('[data-action="activate-delivery-zone"]');
    if (activate) activate.disabled = true;
    const state = byId('delivery-zone-map-save-state');
    if (state) state.textContent = 'Unsaved boundary changes — save draft before activation.';
  }
  function syncTextarea(markDirty = true) {
    const textarea = byId('delivery-zone-boundary');
    if (textarea) textarea.value = textForPoints(points);
    if (markDirty) markUnsaved();
  }
  function markerIcon(index) {
    return L.divIcon({
      className: 'delivery-zone-map-marker-wrap',
      html: `<span class="delivery-zone-map-marker">${index + 1}</span>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
  }

  function rebuildLayers() {
    if (!map) return;
    if (polygon) map.removeLayer(polygon);
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    polygon = points.length >= 3 ? L.polygon(points, {weight: 3, fillOpacity: 0.18}).addTo(map) : null;
    points.forEach((point, index) => {
      const marker = L.marker(point, {draggable: true, icon: markerIcon(index)}).addTo(map);
      marker.on('drag', event => {
        const latlng = event.target.getLatLng();
        points[index] = [latlng.lat, latlng.lng];
        if (polygon) polygon.setLatLngs(points);
        syncTextarea();
      });
      marker.on('dragend', syncTextarea);
      markers.push(marker);
    });
    const count = byId('delivery-zone-map-count');
    if (count) count.textContent = `${points.length} point${points.length === 1 ? '' : 's'}`;
  }
  function fitBoundary() {
    if (!map) return;
    if (points.length) map.fitBounds(L.latLngBounds(points), {padding: [30, 30], maxZoom: 16});
    else map.setView(NEEMUCH_CENTER, 13);
  }

  function renderControls(host) {
    const toolbar = document.createElement('div');
    toolbar.className = 'delivery-zone-map-toolbar';
    toolbar.innerHTML = '<div><strong>Draw delivery area on map</strong><small>Click around the boundary in order. Drag numbered points to adjust.</small></div>' +
      '<div class="actions"><button type="button" id="delivery-zone-map-undo" class="secondary">Undo point</button>' +
      '<button type="button" id="delivery-zone-map-clear" class="secondary">Clear map</button>' +
      '<button type="button" id="delivery-zone-map-fit" class="secondary">Fit boundary</button></div>';
    host.appendChild(toolbar);
    const mapNode = document.createElement('div');
    mapNode.id = 'delivery-zone-map';
    mapNode.setAttribute('aria-label', 'Neemuch delivery boundary map editor');
    host.appendChild(mapNode);
    const footer = document.createElement('div');
    footer.className = 'delivery-zone-map-footer';
    footer.innerHTML = '<span id="delivery-zone-map-count">0 points</span><span id="delivery-zone-map-save-state">Saved boundary draft</span><span>Map data © OpenStreetMap contributors</span>';
    host.appendChild(footer);
  }
  function initializeMap() {
    const boundaryLabel = document.querySelector('.delivery-zone-boundary');
    if (!boundaryLabel || typeof L === 'undefined') return;
    map?.remove();
    map = null;
    polygon = null;
    markers = [];
    points = readPoints();

    const host = document.createElement('section');
    host.className = 'delivery-zone-map-editor';
    boundaryLabel.parentNode.insertBefore(host, boundaryLabel);
    renderControls(host);

    map = L.map('delivery-zone-map', {scrollWheelZoom: true}).setView(NEEMUCH_CENTER, 13);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    map.on('click', event => {
      points.push([event.latlng.lat, event.latlng.lng]);
      syncTextarea();
      rebuildLayers();
    });
    rebuildLayers();
    fitBoundary();
  }
  function bindEditorControls() {
    byId('delivery-zone-map-undo')?.addEventListener('click', () => {
      points.pop();
      syncTextarea();
      rebuildLayers();
    });
    byId('delivery-zone-map-clear')?.addEventListener('click', () => {
      points = [];
      syncTextarea();
      rebuildLayers();
      fitBoundary();
    });
    byId('delivery-zone-map-fit')?.addEventListener('click', fitBoundary);
    const textarea = byId('delivery-zone-boundary');
    if (textarea) {
      const updateFromTextarea = () => {
        markUnsaved();
        try {
          const ring = parseDeliveryZoneBoundary(textarea.value);
          points = ring.slice(0, -1).map(([lng, lat]) => [lat, lng]);
          rebuildLayers();
          fitBoundary();
        } catch {
          // Keep the current map while coordinates are incomplete or being edited.
        }
      };
      textarea.addEventListener('input', markUnsaved);
      textarea.addEventListener('change', updateFromTextarea);
    }
  }
  const baseRenderDeliveryZone = renderDeliveryZone;
  renderDeliveryZone = function renderDeliveryZoneWithMap(configuration) {
    if (map) {
      map.remove();
      map = null;
    }
    baseRenderDeliveryZone(configuration);
    initializeMap();
    bindEditorControls();
  };
})();
