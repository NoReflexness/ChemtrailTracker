const map = L.map('map', {
    zoomControl: false,
    renderer: L.canvas() // Use canvas renderer for the map
}).setView([56.0, 11.0], 6);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

const flightLayer = L.markerClusterGroup({
    maxClusterRadius: 50,
    disableClusteringAtZoom: 15,
    chunkedLoading: true // Improve loading performance for many markers
}).addTo(map);

let hasZoomed = false;

function initMap() {
    console.log('Initializing map and flightLayer');
    fetch('/areas')
        .then(response => response.json())
        .then(data => {
            data.forEach(area => {
                const bounds = L.latLngBounds([area.lamin, area.lomin], [area.lamax, area.lomax]);
                addArea(bounds, area.is_monitoring, area.id, area.frequency);
            });
        })
        .catch(error => console.error('Error loading areas:', error));

    map.on('mousedown', onMouseDown);
    map.on('mousemove', onMouseMove);
    map.on('mouseup', onMouseUp);
    map.on('click', onMapClick);
}