let flightLines = new Set();
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
    if (!flight || !flight.flight_id) {
        console.warn('Invalid flight data, skipping render');
        return;
    }

    //console.log('Rendering flight:', flight);
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
    flightData.classification = flight.classification;
    flightData.classification_source = flight.classification_source;
    flightData.avg_altitude = flight.avg_altitude;
    flightData.avg_velocity = flight.avg_velocity;
    flightData.duration = flight.duration;

    const color = flight.classification === 'commercial' ? '#00ff00' :
        flight.classification === 'survey' ? '#ff0000' :
            flight.classification === 'agriculture' ? '#FFA500' :
                flight.classification === 'cloud seeding' ? '#0000FF' :
                    flight.classification === 'crop dusting' ? '#FF00FF' :
                        flight.classification === 'rescue' ? '#FFFF00' :
                            flight.classification === 'chemtrail' ? '#800080' : '#808080';
    const opacity = isSelected ? 1 : (selectedFlightId ? 0.1 : 0.6);
    let rotation = 0;

    // Pattern detection for visualization
    let patternStyle = { dashArray: null };
    if (flight.classification === 'cloud seeding' && isSelected) {
        patternStyle.dashArray = '10, 5'; // Grid-like
    } else if (flight.classification === 'crop dusting' && isSelected) {
        patternStyle.dashArray = '5, 10, 5'; // Zig-zag
    } else if (flight.classification === 'rescue' && isSelected) {
        patternStyle.dashArray = '15, 5'; // Circular
    }

    if (coords.length >= 1) {
        const lastPoint = sortedPoints[sortedPoints.length - 1];
        const altitude = lastPoint[3] === -1 ? 'N/A' : `${lastPoint[3]} m`;
        const velocity = lastPoint[4] === -1 ? 'N/A' : `${lastPoint[4]} m/s`;
        const avgAltitude = flight.avg_altitude === -1 ? 'N/A' : `${Math.round(flight.avg_altitude)} m`;
        const avgVelocity = flight.avg_velocity === -1 ? 'N/A' : `${Math.round(flight.avg_velocity)} m/s`;
        const duration = flight.duration === 0 ? 'N/A' : `${Math.round(flight.duration / 60)} min`;
        const popupContent = `Flight: ${flight.flight_id}<br>Class: ${flight.classification || 'N/A'} (${flight.classification_source || 'N/A'})<br>Altitude: ${altitude}<br>Velocity: ${velocity}<br>Avg Altitude: ${avgAltitude}<br>Avg Velocity: ${avgVelocity}<br>Duration: ${duration}`;

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

            if (shouldRenderPath(flight)) {
                if (validCoords.length > 1) {
                    try {
                        if (flightData.line) {
                            flightData.line.setLatLngs(validCoords);
                        } else {
                            flightData.line = L.polyline(validCoords, {
                                color: color,
                                weight: 4,
                                opacity: opacity,
                                dashArray: patternStyle.dashArray
                            });
                            flightData.line.addTo(flightLayer);
                            flightData.line.on('dblclick', () => selectFlight(flight.flight_id));
                        }
                        flightData.line.bindPopup(popupContent);
                        flightData.line.setStyle({ opacity: opacity, dashArray: patternStyle.dashArray });
                    } catch (e) {
                        console.error(`Failed to render polyline for ${flight.flight_id}:`, e);
                        delete flightData.line;
                    }
                } else {
                    console.warn(`Insufficient valid coordinates for polyline in ${flight.flight_id}:`, validCoords);
                    if (flightData.line) {
                        flightLayer.removeLayer(flightData.line);
                        delete flightData.line;
                    }
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
            flightData.marker = L.marker(coords[coords.length - 1], { icon: airplaneIcon })
                .bindPopup(popupContent)
                .addTo(flightLayer);
            flightData.marker.on('dblclick', () => selectFlight(flight.flight_id));
            flightData.marker.setOpacity(opacity);
        }
    } else {
        console.warn(`No valid coordinates for flight ${flight.flight_id}`);
    }
}

const debouncedRenderFlightPath = debounce(renderFlightPath, 100);
window.debouncedRenderFlightPath = renderFlightPath;


function selectFlight(flightId) {
    if (!flightId || !flightLines[flightId]) {
        console.warn(`Cannot select flight ${flightId}: not found in flightLines`);
        return;
    }

    selectedFlightId = flightId;
    const selectedFlightData = flightLines[flightId];

    // Immediately render the selected flight’s path with full points
    renderFlightPath(selectedFlightData);

    // Update opacity for all other flights
    Object.keys(flightLines).forEach(id => {
        if (id !== flightId) {
            const flightData = flightLines[id];
            const opacity = 0.1; // Dim unselected flights
            if (flightData.line) {
                if (shouldRenderPath(flightData) && id !== selectedFlightId) {
                    flightData.line.setStyle({ opacity: opacity });
                } else if (!shouldRenderPath(flightData)) {
                    flightLayer.removeLayer(flightData.line);
                    delete flightData.line;
                }
            }
            if (flightData.marker) {
                flightData.marker.setOpacity(opacity);
            }
        }
    });

    // Zoom to the selected flight without forcing a cluster redraw
    if (selectedFlightData.line) {
        map.fitBounds(selectedFlightData.line.getBounds(), { maxZoom: 15 });
    } else if (selectedFlightData.marker) {
        map.setView(selectedFlightData.marker.getLatLng(), Math.min(map.getZoom(), 15));
    }

    updateFlightList(); // Update list without fetch
}

function deselectFlight() {
    selectedFlightId = null;

    // Update all flights immediately
    Object.keys(flightLines).forEach(id => {
        const flightData = flightLines[id];
        const opacity = 0.6; // All shown mode
        const shouldRender = document.getElementById(`show-${flightData.classification || 'N/A'}`)?.checked;
        if (flightData.line) {
            if (shouldRender) {
                flightData.line.setStyle({ opacity: opacity });
            } else {
                flightLayer.removeLayer(flightData.line);
                delete flightData.line;
            }
        } else if (shouldRender) {
            renderFlightPath(flightData); // Draw path if it should be visible
        }
        if (flightData.marker) {
            flightData.marker.setOpacity(opacity);
        }
    });

    updateFlightList(); // Update list without fetch
}