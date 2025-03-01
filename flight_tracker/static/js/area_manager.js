let areas = [];
let drawing = false;
let startLatLng = null;
let currentRectangle = null;
let selectedArea = null;

function onMouseDown(e) {
    if (e.originalEvent.shiftKey) {
        drawing = true;
        startLatLng = e.latlng;
        currentRectangle = L.rectangle([[startLatLng.lat, startLatLng.lng], [startLatLng.lat, startLatLng.lng]], {
            color: '#808080',
            weight: 2,
            dashArray: '5, 5',
            fillOpacity: 0
        }).addTo(map);
    }
}

function onMouseMove(e) {
    if (drawing && currentRectangle) {
        const bounds = L.latLngBounds(startLatLng, e.latlng);
        currentRectangle.setBounds(bounds);
    }
}

function onMouseUp(e) {
    if (drawing && currentRectangle) {
        drawing = false;
        const bounds = currentRectangle.getBounds();
        const frequency = document.getElementById('frequency').value;
        persistArea(bounds, false, frequency);
        map.removeLayer(currentRectangle);
        currentRectangle = null;
    }
}

function onMapClick(e) {
    const clickedOnArea = areas.some(area => area.rectangle.getBounds().contains(e.latlng));
    if (!clickedOnArea && !e.originalEvent.shiftKey) {
        console.log('Clicked outside, deselecting area');
        deselectArea();
        deselectFlight();
    }
}

function persistArea(bounds, isMonitoring, frequency) {
    fetch('/start_monitoring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            lamin: bounds.getSouth(),
            lamax: bounds.getNorth(),
            lomin: bounds.getWest(),
            lomax: bounds.getEast(),
            frequency: frequency
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
            } else {
                addArea(bounds, isMonitoring, data.area_id, frequency);
                appendLog(`Area created with ID ${data.area_id}`);
            }
        });
}

function addArea(bounds, isMonitoring, id, frequency) {
    const style = isMonitoring ?
        { color: '#006400', weight: 2, dashArray: '5, 5', fillOpacity: 0 } :
        { color: '#808080', weight: 2, dashArray: '5, 5', fillOpacity: 0 };
    const rectangle = L.rectangle(bounds, style).addTo(map);
    const area = { rectangle, bounds, isMonitoring, id, frequency };
    rectangle.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        console.log(`Area clicked, selecting: ${JSON.stringify(bounds)}`);
        selectArea(area);
    });
    areas.push(area);
    updateStats();
    updateMonitorButton();
}

function selectArea(area) {
    if (selectedArea && selectedArea !== area) {
        console.log(`Deselecting previous area: ${JSON.stringify(selectedArea.bounds)}`);
        updateAreaStyle(selectedArea);
    }
    selectedArea = area;
    console.log(`Selecting new area: ${JSON.stringify(area.bounds)}`);
    updateAreaStyle(area);
    updateMonitorButton();
    document.getElementById('delete-btn').disabled = false;
}

function deselectArea() {
    if (selectedArea) {
        console.log(`Deselecting area: ${JSON.stringify(selectedArea.bounds)}`);
        updateAreaStyle(selectedArea);
        selectedArea = null;
        updateMonitorButton();
        document.getElementById('delete-btn').disabled = true;
    }
}

function updateAreaStyle(area) {
    const fillOpacity = (area === selectedArea) ? 0.01 : 0;
    const fillColor = '#00ff00';
    console.log(`Updating style for area: ${JSON.stringify(area.bounds)}, selected: ${area === selectedArea}, fillOpacity: ${fillOpacity}`);
    area.rectangle.setStyle({
        color: area.is_monitoring ? '#006400' : '#808080',
        fillOpacity: fillOpacity,
        fillColor: fillColor
    });
}