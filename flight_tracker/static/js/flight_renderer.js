// flight_tracker/static/js/flight_renderer.js
let flightLines = {};
let selectedFlightId = null;

const airplaneSvg = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20.5 3.5L3.5 12L9.5 14.5L15.5 9.5L10.5 15.5L13 20.5L20.5 3.5Z" fill="#333" stroke="#333" stroke-width="2"/>
    </svg>
`;

function calculateBearing(lat1, lon1, lat2, lon2) {
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
    const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
        Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
    const bearing = Math.atan2(y, x);
    return (bearing * 180 / Math.PI + 360) % 360;
}

function shouldRenderPath(flight) {
    const checkbox = document.getElementById(`show-${flight.classification || 'N/A'}`);
    return flight.flight_id === selectedFlightId || (checkbox && checkbox.checked);
}

function renderFlightPath(flight) {
    if (!flight || !flight.flight_id || !flight.points) {
        console.warn('Invalid flight data, skipping render:', flight);
        return;
    }

    console.log(`Rendering flight ${flight.flight_id}: points=${flight.points.length}, classification=${flight.classification || 'N/A'}`);
    const sortedPoints = flight.points.slice().sort((a, b) => a[2] - b[2]);
    let coords;
    const isSelected = flight.flight_id === selectedFlightId;
    const totalPaths = Object.keys(flightLines).length;
    const useFullPoints = isSelected || totalPaths < 200;

    if (typeof simplify !== 'undefined' && !useFullPoints) {
        const simplifiedPoints = simplify(sortedPoints.map(p => ({ x: p[1], y: p[0], t: p[2], alt: p[3], vel: p[4] })), 0.1, true);
        coords = simplifiedPoints.map(p => [p.y, p.x]);
    } else {
        coords = sortedPoints.map(p => [p[0], p[1]]);
    }

    const flightData = flightLines[flight.flight_id] || {};
    flightLines[flight.flight_id] = flightData;
    flightData.points = sortedPoints;
    flightData.classification = flight.classification || 'N/A';
    flightData.classification_source = flight.classification_source;
    flightData.avg_altitude = flight.avg_altitude;
    flightData.avg_velocity = flight.avg_velocity;
    flightData.duration = flight.duration;

    const willRender = shouldRenderPath(flight);
    console.log(`Flight ${flight.flight_id}: shouldRender=${willRender}, coords=${coords.length}`);

    if (!willRender) {
        if (flightData.line) flightLayer.removeLayer(flightData.line);
        if (flightData.marker) flightLayer.removeLayer(flightData.marker);
        delete flightData.line;
        delete flightData.marker;
        return;
    }

    const color = {
        'commercial': '#00ff00',
        'survey': '#ff0000',
        'agriculture': '#FFA500',
        'cloud seeding': '#0000FF',
        'crop dusting': '#FF00FF',
        'rescue': '#FFFF00',
        'chemtrail': '#800080',
        'N/A': '#808080'
    }[flightData.classification] || '#808080';
    const opacity = isSelected ? 1 : (selectedFlightId ? 0.1 : 0.6);

    let patternStyle = { dashArray: null };
    if (isSelected) {
        if (flightData.classification === 'cloud seeding') patternStyle.dashArray = '10, 5';
        else if (flightData.classification === 'crop dusting') patternStyle.dashArray = '5, 10, 5';
        else if (flightData.classification === 'rescue') patternStyle.dashArray = '15, 5';
    }

    if (coords.length >= 1) {
        const lastPoint = sortedPoints[sortedPoints.length - 1];
        const popupContent = `Flight: ${flight.flight_id}<br>Class: ${flightData.classification}<br>Altitude: ${lastPoint[3] === -1 ? 'N/A' : `${lastPoint[3]} m`}<br>Velocity: ${lastPoint[4] === -1 ? 'N/A' : `${lastPoint[4]} m/s`}<br>Avg Altitude: ${flight.avg_altitude === -1 ? 'N/A' : `${Math.round(flight.avg_altitude)} m`}<br>Avg Velocity: ${flight.avg_velocity === -1 ? 'N/A' : `${Math.round(flight.avg_velocity)} m/s`}<br>Duration: ${flight.duration === 0 ? 'N/A' : `${Math.round(flight.duration / 60)} min`}`;

        let rotation = 0;
        if (coords.length > 1) {
            const validCoords = coords.filter(([lat, lon]) => lat !== null && lon !== null && !isNaN(lat) && !isNaN(lon));
            const lastPoints = validCoords.slice(-3);
            if (lastPoints.length >= 2) {
                const [lat2, lon2] = lastPoints[lastPoints.length - 1];
                const [lat1, lon1] = lastPoints[lastPoints.length - 2];
                rotation = calculateBearing(lat1, lon1, lat2, lon2) - 45;
                flightData.lastRotation = rotation;
            } else {
                rotation = flightData.lastRotation || 0;
            }

            if (validCoords.length > 1) {
                try {
                    if (flightData.line) {
                        flightData.line.setLatLngs(validCoords);
                        flightData.line.setStyle({ color, opacity, dashArray: patternStyle.dashArray });
                    } else {
                        flightData.line = L.polyline(validCoords, { color, weight: 4, opacity, dashArray: patternStyle.dashArray })
                            .addTo(flightLayer)
                            .on('dblclick', () => selectFlight(flight.flight_id));
                    }
                    flightData.line.bindPopup(popupContent);
                    console.log(`Flight ${flight.flight_id}: polyline rendered`);
                } catch (e) {
                    console.error(`Failed to render polyline for ${flight.flight_id}:`, e);
                    delete flightData.line;
                }
            } else if (flightData.line) {
                flightLayer.removeLayer(flightData.line);
                delete flightData.line;
            }
        }

        const airplaneIcon = L.divIcon({
            html: `<div style="transform: rotate(${rotation}deg);">${airplaneSvg}</div>`,
            className: 'airplane-icon',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });

        if (flightData.marker) {
            flightData.marker.setLatLng(coords[coords.length - 1]);
            flightData.marker.setIcon(airplaneIcon);
            flightData.marker.setOpacity(opacity);
        } else {
            try {
                flightData.marker = L.marker(coords[coords.length - 1], { icon: airplaneIcon })
                    .bindPopup(popupContent)
                    .addTo(flightLayer)
                    .on('dblclick', () => selectFlight(flight.flight_id));
                flightData.marker.setOpacity(opacity);
                console.log(`Flight ${flight.flight_id}: marker rendered`);
            } catch (e) {
                console.error(`Failed to render marker for ${flight.flight_id}:`, e);
                delete flightData.marker;
            }
        }
    }
}

// Remove debounce for immediate rendering
function renderFlightPathImmediate(flight) {
    renderFlightPath(flight);
}
window.debouncedRenderFlightPath = renderFlightPathImmediate; // Expose globally

function selectFlight(flightId) {
    if (!flightId) return;

    fetch(`/flight_path/${flightId}`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.error) {
                console.error(data.error);
                return;
            }
            selectedFlightId = flightId;
            renderFlightPath(data);

            Object.keys(flightLines).forEach(id => {
                if (id !== flightId) {
                    const flightData = flightLines[id];
                    const opacity = 0.1;
                    if (flightData.line) flightData.line.setStyle({ opacity });
                    if (flightData.marker) flightData.marker.setOpacity(opacity);
                }
            });

            if (flightLines[flightId].line) {
                map.fitBounds(flightLines[flightId].line.getBounds(), { maxZoom: 15 });
            } else if (flightLines[flightId].marker) {
                map.setView(flightLines[flightId].marker.getLatLng(), Math.min(map.getZoom(), 15));
            }

            updateFlightList();
        })
        .catch(error => console.error('Error fetching flight:', error));
}

function deselectFlight() {
    selectedFlightId = null;
    Object.keys(flightLines).forEach(id => {
        const flightData = flightLines[id];
        const opacity = 0.6;
        const shouldRender = shouldRenderPath(flightData);
        if (flightData.line) {
            if (shouldRender) flightData.line.setStyle({ opacity });
            else {
                flightLayer.removeLayer(flightData.line);
                delete flightData.line;
            }
        } else if (shouldRender) {
            renderFlightPath(flightData);
        }
        if (flightData.marker) flightData.marker.setOpacity(opacity);
    });
    updateFlightList();
}

function updateFlightPathsFromData(data) {
    const activeFlightIds = new Set(data.map(f => f.flight_id));
    Object.keys(flightLines).forEach(id => {
        if (!activeFlightIds.has(id)) {
            if (flightLines[id].line) flightLayer.removeLayer(flightLines[id].line);
            if (flightLines[id].marker) flightLayer.removeLayer(flightLines[id].marker);
            delete flightLines[id];
        }
    });
    console.log(`Processing ${data.length} flights for rendering`);
    data.forEach(flight => window.debouncedRenderFlightPath(flight));
    updateFlightList();
    updateStats();
}