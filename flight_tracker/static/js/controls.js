// flight_tracker/static/js/controls.js
function toggleMonitoring() {
    if (!selectedArea) return;
    const frequency = document.getElementById('frequency').value;
    const bounds = selectedArea.bounds;
    const url = selectedArea.isMonitoring ? '/stop_monitoring' : '/start_monitoring';
    const body = selectedArea.isMonitoring
        ? { area_id: selectedArea.id }
        : {
            lamin: bounds.getSouth(),
            lamax: bounds.getNorth(),
            lomin: bounds.getWest(),
            lomax: bounds.getEast(),
            frequency: frequency
        };

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
                appendLog(`Error: ${data.error}`);
            } else {
                selectedArea.isMonitoring = !selectedArea.isMonitoring;
                if (!selectedArea.isMonitoring) {
                    appendLog(`Monitoring stopped for area ${data.area_id}`);
                } else {
                    selectedArea.id = data.area_id;
                    selectedArea.frequency = frequency;
                    appendLog(`Monitoring started for area ${data.area_id}`);
                }
                updateAreaStyle(selectedArea);
                updateStats();
                updateMonitorButton();
            }
        })
        .catch(error => console.error('Fetch error:', error));
}

function deleteArea() {
    if (!selectedArea) return;

    const stopMonitoring = selectedArea.isMonitoring
        ? fetch('/stop_monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ area_id: selectedArea.id })
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    appendLog(`Monitoring stopped for area ${data.area_id}`);
                    selectedArea.isMonitoring = false; // Update local state
                } else {
                    console.warn(`Stop monitoring failed: ${data.error}, proceeding with deletion`);
                }
            })
            .catch(error => {
                console.error('Error stopping monitoring:', error);
                appendLog(`Error stopping monitoring for area ${selectedArea.id}: ${error}`);
            })
        : Promise.resolve(); // Skip if not monitoring

    stopMonitoring.then(() => {
        fetch('/delete_area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ area_id: selectedArea.id })
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    map.removeLayer(selectedArea.rectangle);
                    areas = areas.filter(a => a !== selectedArea);
                    selectedArea = null;
                    updateStats();
                    updateMonitorButton();
                    appendLog(`Area ${data.area_id} deleted`);
                }
            })
            .catch(error => console.error('Error deleting area:', error));
    });
}

function retrainModel() {
    if (!canRetrain) return;
    fetch('/retrain_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
                appendLog(`Error: ${data.error}`);
            } else {
                appendLog(data.message);
            }
        })
        .catch(error => console.error('Error:', error));
}

function updateMonitorButton() {
    const monitorBtn = document.getElementById('monitor-btn');
    if (selectedArea) {
        monitorBtn.textContent = selectedArea.isMonitoring ? 'Stop Monitoring' : 'Start Monitoring';
        monitorBtn.disabled = false;
    } else {
        monitorBtn.textContent = 'Start Monitoring';
        monitorBtn.disabled = true;
        document.getElementById('delete-btn').disabled = true;
    }
}

function addClassification() {
    const input = document.getElementById('new-class');
    const newClass = input.value.trim();
    if (newClass && !Array.from(document.querySelectorAll('.path-checkboxes input')).some(cb => cb.id === `show-${newClass}`)) {
        const checkbox = document.createElement('label');
        checkbox.innerHTML = `<input type="checkbox" id="show-${newClass}" onchange="updatePathsAndList()"> ${newClass}`;
        document.querySelector('.path-checkboxes').appendChild(checkbox);
        document.getElementById('class-filter').add(new Option(newClass, newClass));
        Cookies.set(`show-${newClass}`, 'false');
        input.value = '';
        updatePathsAndList();
    }
}

function updatePathsAndList() {
    updateFlightPaths();
    filterFlights();
    document.querySelectorAll('.path-checkboxes input[type="checkbox"]').forEach(cb => {
        Cookies.set(cb.id, cb.checked, { expires: 365 });
    });
    socket.emit('update_classifications', { classifications: getSelectedClasses() });
}

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupSocketEvents(map);

    const frequency = Cookies.get('frequency') || '30s';
    document.getElementById('frequency').value = frequency;
    ['commercial', 'survey', 'agriculture', 'cloud-seeding', 'crop-dusting', 'rescue', 'chemtrail', 'N/A'].forEach(cls => {
        const checkbox = document.getElementById(`show-${cls}`);
        if (checkbox) checkbox.checked = Cookies.get(`show-${cls}`) === 'true';
    });
    fetchTotalFlights(); // Fetch total flights on load
    updatePathsAndList();
    setInterval(updateFlightPaths, 10000);

    document.getElementById('frequency').addEventListener('change', (e) => {
        Cookies.set('frequency', e.target.value, { expires: 365 });
    });

    map.on('click', (e) => {
        const clickedOnFlight = Object.values(flightLines).some(fd =>
            (fd.marker && fd.marker.getLatLng().equals(e.latlng)) ||
            (fd.line && fd.line.getBounds().contains(e.latlng))
        );
        if (!clickedOnFlight && !areas.some(a => a.rectangle.getBounds().contains(e.latlng))) {
            deselectFlight();
        }
    });

    document.getElementById('monitor-btn').addEventListener('click', toggleMonitoring);
    document.getElementById('delete-btn').addEventListener('click', deleteArea);
    document.getElementById('retrain-btn').addEventListener('click', retrainModel);
    document.getElementById('add-class-btn').addEventListener('click', addClassification);
    document.querySelectorAll('.path-checkboxes input').forEach(cb => {
        cb.addEventListener('change', updatePathsAndList);
    });
});