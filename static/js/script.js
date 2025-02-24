document.addEventListener('DOMContentLoaded', () => {
    const analyzeForm = document.getElementById('analyze-form');
    const resultDiv = document.getElementById('result');
    const flightReviewDiv = document.getElementById('flight-review');
    const retrainBtn = document.getElementById('retrain-btn');
    const logOutput = document.getElementById('log-output');
    const authMessage = document.getElementById('auth-message');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const stopBtn = document.getElementById('stop-btn');
    const creditsInfo = document.getElementById('credits-info');
    const timer = document.getElementById('timer');
    const areaInfo = document.getElementById('area-info');
    const refreshRateSelect = document.getElementById('refresh-rate');
    let currentFormData = null;
    let selectedRectangle = null;
    let isMonitoring = false;
    let flightPaths = {};  // Store path layers
    let airplaneMarkers = {};  // Store airplane markers

    const socket = io.connect('http://' + document.domain + ':' + location.port);

    socket.on('log_message', (data) => {
        logOutput.textContent += data.message + '\n';
        logOutput.scrollTop = logOutput.scrollHeight;
    });

    socket.on('credit_update', (data) => {
        creditsInfo.textContent = `Credits Used: ${data.credits_used} | Remaining: ${data.remaining_credits}`;
    });

    socket.on('refresh_timer', (data) => {
        timer.textContent = `Next Refresh: ${Math.ceil(data.next_refresh)} seconds`;
    });

    socket.on('update_paths', (data) => {
        updateFlightPaths(data.paths);
    });

    const map = L.map('mapid', {
        center: [0, 0],
        zoom: 2,
        layers: [L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: 'OpenSky Flight Analyzer Map © OpenStreetMap contributors'
        })]
    });
    console.log('Leaflet map initialized:', map);

    if (savedBounds) {
        selectedRectangle = L.rectangle([[savedBounds.lamin, savedBounds.lomin], [savedBounds.lamax, savedBounds.lomax]], { color: "#ff7800", weight: 2 });
        selectedRectangle.addTo(map);
        const { areaSqKm, creditCost } = calculateAreaAndCost(selectedRectangle.getBounds());
        areaInfo.textContent = `Area: ${areaSqKm} km² | Credit Cost: ${creditCost} per refresh`;
        playPauseBtn.disabled = false;
        stopBtn.disabled = false;
        playPauseBtn.textContent = 'Play';
        refreshRateSelect.value = savedBounds.refresh_rate.toString();
        logOutput.textContent += `Loaded last monitored area: ${areaSqKm} km², Credit Cost: ${creditCost}\n`;
        console.log('Restored rectangle from server:', savedBounds);
        fetchFlightPaths();  // Load initial flight paths
    }

    map.on('mousedown', function (e) {
        if (e.originalEvent.shiftKey) {
            console.log('Shift + mousedown detected at:', e.latlng);
            if (selectedRectangle) {
                console.log('Removing previous rectangle');
                map.removeLayer(selectedRectangle);
                selectedRectangle = null;
            }
            const startLatLng = e.latlng;
            selectedRectangle = L.rectangle([startLatLng, startLatLng], { color: "#ff7800", weight: 2 });
            selectedRectangle.addTo(map);

            map.on('mousemove', function (e) {
                if (selectedRectangle) {
                    console.log('Dragging to:', e.latlng);
                    selectedRectangle.setBounds([startLatLng, e.latlng]);
                }
            });

            map.on('mouseup', function (e) {
                if (selectedRectangle) {
                    console.log('Mouseup detected, rectangle bounds set');
                    const bounds = selectedRectangle.getBounds();
                    const { areaSqKm, creditCost } = calculateAreaAndCost(bounds);
                    areaInfo.textContent = `Area: ${areaSqKm} km² | Credit Cost: ${creditCost} per refresh`;
                    playPauseBtn.disabled = false;
                    stopBtn.disabled = false;
                    playPauseBtn.textContent = 'Play';
                    logOutput.textContent += `Area selected: ${areaSqKm} km², Credit Cost: ${creditCost}\n`;
                    map.off('mousemove');
                    map.off('mouseup');
                }
            });
        }
    });

    function calculateAreaAndCost(bounds) {
        const lamin = bounds.getSouthWest().lat;
        const lamax = bounds.getNorthEast().lat;
        const lomin = bounds.getSouthWest().lng;
        const lomax = bounds.getNorthEast().lng;
        const latRange = lamax - lamin;
        const lonRange = lomax - lomin;
        const areaSqDeg = latRange * lonRange;
        const avgLat = (lamin + lamax) / 2;
        const kmPerLonDeg = 111 * Math.cos(avgLat * Math.PI / 180);
        const areaSqKm = latRange * 111 * lonRange * kmPerLonDeg;
        const creditCost = areaSqDeg <= 25 ? 1 : areaSqDeg <= 100 ? 2 : areaSqDeg <= 400 ? 3 : 4;
        return { areaSqKm: areaSqKm.toFixed(2), creditCost };
    }

    function fetchFlightPaths() {
        fetch('/get_flight_paths')
            .then(response => response.json())
            .then(data => updateFlightPaths(data.paths))
            .catch(error => console.error('Error fetching flight paths:', error));
    }

    function updateFlightPaths(paths) {
        // Clear existing paths and markers
        Object.values(flightPaths).forEach(path => map.removeLayer(path));
        Object.values(airplaneMarkers).forEach(marker => map.removeLayer(marker));
        flightPaths = {};
        airplaneMarkers = {};

        paths.forEach(path => {
            // Draw polyline for the flight path
            const polyline = L.polyline(path.coords, { color: 'blue', weight: 2 }).addTo(map);
            flightPaths[path.icao24] = polyline;

            // Add airplane marker at latest position with rotation
            if (path.latest) {
                const icon = L.divIcon({
                    html: airplaneIconSvg,
                    className: 'airplane-icon',
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                const marker = L.marker([path.latest.lat, path.latest.lon], {
                    icon: icon,
                    rotationAngle: path.latest.true_track || 0,  // Rotate based on true_track
                    rotationOrigin: 'center center'
                }).addTo(map);
                airplaneMarkers[path.icao24] = marker;
            }
        });
    }

    playPauseBtn.addEventListener('click', () => {
        if (!selectedRectangle) {
            alert('Please hold Shift and drag on the map to define an area.');
            return;
        }
        if (playPauseBtn.textContent === 'Play') {
            playPauseBtn.textContent = 'Pause';
            isMonitoring = true;
            const bounds = selectedRectangle.getBounds();
            const data = {
                lamin: bounds.getSouthWest().lat,
                lamax: bounds.getNorthEast().lat,
                lomin: bounds.getSouthWest().lng,
                lomax: bounds.getNorthEast().lng,
                refresh_rate: refreshRateSelect.value
            };
            fetch('/begin_monitoring', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        authMessage.style.display = 'block';
                        authMessage.textContent = data.error;
                    } else {
                        authMessage.style.display = 'block';
                        authMessage.textContent = data.message;
                    }
                })
                .catch(error => console.error('Error:', error));
        } else {
            playPauseBtn.textContent = 'Play';
            isMonitoring = false;
            fetch('/pause_monitoring', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        authMessage.style.display = 'block';
                        authMessage.textContent = data.error;
                    } else {
                        authMessage.style.display = 'block';
                        authMessage.textContent = data.message;
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });

    stopBtn.addEventListener('click', () => {
        if (!selectedRectangle) {
            alert('No monitoring to stop.');
            return;
        }
        playPauseBtn.textContent = 'Play';
        isMonitoring = false;
        fetch('/stop_monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    authMessage.style.display = 'block';
                    authMessage.textContent = data.error;
                } else {
                    authMessage.style.display = 'block';
                    authMessage.textContent = data.message;
                }
            })
            .catch(error => console.error('Error:', error));
    });

    analyzeForm.addEventListener('submit', (e) => {
        e.preventDefault();
        fetchData('/analyze', new FormData());
    });

    retrainBtn.addEventListener('click', () => {
        fetch('/retrain', {
            method: 'POST'
        })
            .then(response => response.json())
            .then(data => alert(data.status))
            .catch(error => console.error('Error:', error));
    });

    function fetchData(url, formData) {
        fetch(url, {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    authMessage.style.display = 'block';
                    authMessage.textContent = data.error;
                    return;
                }

                authMessage.style.display = 'none';
                flightReviewDiv.innerHTML = '';
                data.report.forEach(row => {
                    const div = document.createElement('div');
                    div.className = 'flight-entry';
                    div.innerHTML = `
                    <img src="${row.svg_path}" alt="Flight Path for ${row.icao24}" style="max-width: 400px;">
                    <div>
                        <p>ICAO24: ${row.icao24}</p>
                        <label for="pattern-${row.icao24}">Pattern Type:</label>
                        <select id="pattern-${row.icao24}" data-icao="${row.icao24}" data-coords='${JSON.stringify(row.coords)}'>
                            <option value="Commercial" ${row.pattern_type === 'Commercial' ? 'selected' : ''}>Commercial</option>
                            <option value="Survey" ${row.pattern_type === 'Survey' ? 'selected' : ''}>Survey</option>
                            <option value="Agricultural" ${row.pattern_type === 'Agricultural' ? 'selected' : ''}>Agricultural</option>
                            <option value="Firefighting" ${row.pattern_type === 'Firefighting' ? 'selected' : ''}>Firefighting</option>
                            <option value="Chemtrail" ${row.pattern_type === 'Chemtrail' ? 'selected' : ''}>Chemtrail</option>
                        </select>
                    </div>
                `;
                    flightReviewDiv.appendChild(div);

                    const select = div.querySelector('select');
                    select.addEventListener('change', (e) => {
                        const formData = new FormData();
                        formData.append('icao24', e.target.dataset.icao);
                        formData.append('pattern_type', e.target.value);
                        formData.append('coords', e.target.dataset.coords);
                        fetch('/update_pattern', {
                            method: 'POST',
                            body: formData
                        })
                            .then(response => response.json())
                            .then(data => console.log(data.status))
                            .catch(error => console.error('Error:', error));
                    });
                });

                resultDiv.style.display = 'block';
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred during analysis.');
            });
    }
});