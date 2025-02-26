function toggleMonitoring() {
    if (!selectedArea) return;
    const frequency = document.getElementById('frequency').value;
    const bounds = selectedArea.bounds;
    if (selectedArea.isMonitoring) {
        console.log(`Stopping monitoring for area_id: ${selectedArea.id}`);
        fetch('/stop_monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ area_id: selectedArea.id })
        })
            .then(response => {
                console.log(`Stop monitoring response status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    console.error(`Error stopping monitoring: ${data.error}`);
                    appendLog(`Error: ${data.error}`);
                } else {
                    selectedArea.isMonitoring = false;
                    updateAreaStyle(selectedArea);
                    appendLog(`Monitoring stopped for area ${data.area_id}`);
                    console.log(`Monitoring stopped successfully for area_id: ${data.area_id}`);
                    updateStats();
                    updateMonitorButton();
                }
            })
            .catch(error => console.error('Fetch error:', error));
    } else {
        console.log(`Starting monitoring for area: ${JSON.stringify(bounds)}`);
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
                    selectedArea.isMonitoring = true;
                    selectedArea.id = data.area_id;
                    selectedArea.frequency = frequency;
                    updateAreaStyle(selectedArea);
                    appendLog(`Monitoring started for area ${data.area_id}`);
                    console.log(`Monitoring started successfully for area_id: ${data.area_id}`);
                    updateStats();
                    updateMonitorButton();
                }
            });
    }
}

function deleteArea() {
    if (!selectedArea) return;
    if (selectedArea.isMonitoring) {
        console.log(`Deleting area, stopping monitoring for area_id: ${selectedArea.id}`);
        fetch('/stop_monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ area_id: selectedArea.id })
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    appendLog(`Monitoring stopped for area ${data.area_id}`);
                    console.log(`Monitoring stopped during delete for area_id: ${data.area_id}`);
                }
            });
    }
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

function filterFlights() {
    const filter = document.getElementById('flight-filter').value.toLowerCase();
    const list = document.getElementById('flight-list-content');
    Array.from(list.children).forEach(div => {
        const text = div.textContent.toLowerCase();
        div.style.display = text.includes(filter) ? '' : 'none';
    });
}