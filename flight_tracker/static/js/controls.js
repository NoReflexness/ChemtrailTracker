// flight_tracker/static/js/controls.js
let selectedAreaId = null;
let classifications = []; // Store database classifications

function toggleMonitoring() {
    if (!selectedArea) return;
    const url = selectedArea.isMonitoring ? '/stop_monitoring' : '/start_monitoring_existing';
    const body = { area_id: selectedArea.id };
    if (!selectedArea.isMonitoring) {
        body.frequency = document.getElementById('frequency').value;
    }

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
                    selectedArea.frequency = body.frequency;
                    appendLog(`Monitoring started for area ${data.area_id}`);
                }
                updateAreaStyle(selectedArea);
                updateStats();
                updateMonitorButton();
                updateAreaList();
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
                    selectedArea.isMonitoring = false;
                } else {
                    console.warn(`Stop monitoring failed: ${data.error}`);
                }
            })
            .catch(error => console.error('Error stopping monitoring:', error))
        : Promise.resolve();

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
                    selectedAreaId = null;
                    updateStats();
                    updateMonitorButton();
                    updateAreaList();
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
                updateMLStats();
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

function loadClassifications() {
    fetch('/classifications')
        .then(response => response.json())
        .then(data => {
            classifications = data;
            updateClassificationUI();
        })
        .catch(error => console.error('Error loading classifications:', error));
}

function updateClassificationUI() {
    const checkboxes = document.getElementById('path-checkboxes');
    const filter = document.getElementById('class-filter');
    const legend = document.getElementById('map-legend');
    checkboxes.innerHTML = '';
    filter.innerHTML = '<option value="">All Classifications</option>';
    legend.innerHTML = `
        <div><span style="color: #808080;">⋯</span> Disabled Area</div>
        <div><span style="color: #006400;">⋯</span> Monitored Area</div>
    `;

    classifications.forEach(cls => {
        const checkbox = document.createElement('label');
        checkbox.innerHTML = `<input type="checkbox" id="show-${cls.name}" onchange="updatePathsAndList()"> <span style="color: ${cls.color}">${cls.name}</span>`;
        checkboxes.appendChild(checkbox);
        if (Cookies.get(`show-${cls.name}`) === 'true') {
            document.getElementById(`show-${cls.name}`).checked = true;
        }

        const option = document.createElement('option');
        option.value = cls.name;
        option.textContent = cls.name;
        filter.appendChild(option);

        const legendItem = document.createElement('div');
        legendItem.innerHTML = `<span style="color: ${cls.color}">■</span> ${cls.name}`;
        legend.appendChild(legendItem);
    });
}

function addClassification() {
    const input = document.getElementById('new-class');
    const colorInput = document.getElementById('new-class-color');
    const name = input.value.trim();
    const color = colorInput.value;
    if (name && !classifications.some(c => c.name === name)) {
        fetch('/add_classification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, color })
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    classifications.push({ name, color });
                    updateClassificationUI();
                    input.value = '';
                    colorInput.value = '#808080';
                    appendLog(`Added classification ${name}`);
                }
            })
            .catch(error => console.error('Error adding classification:', error));
    }
}

function updatePathsAndList() {
    updateFlightPaths();
    filterFlights();
    document.querySelectorAll('.path-checkboxes input[type="checkbox"]').forEach(cb => {
        Cookies.set(cb.id, cb.checked, { expires: 365 });
    });
    socket.emit('update_classifications', { classifications: getSelectedClasses() });
    updateAreaPieChart();
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.style.display = 'none');
    document.getElementById(`tab-${tabId}`).classList.add('active');
    document.getElementById(`content-${tabId}`).style.display = 'block';
    if (tabId === 'area') updateAreaList();
    if (tabId === 'ml') updateMLStats();
}

function updateAreaList() {
    const list = document.getElementById('area-list');
    list.innerHTML = '';
    areas.forEach(area => {
        const div = document.createElement('div');
        div.className = 'area-item' + (area.id === selectedAreaId ? ' selected' : '');
        div.innerHTML = `
            <span class="area-name" ondblclick="editAreaName(${area.id}, this)">${area.name || area.id}</span>
            <span class="area-status">${area.isMonitoring ? '<i class="fas fa-eye"></i>' : '<i class="fas fa-eye-slash"></i>'}</span>
        `;
        div.onclick = () => selectAreaById(area.id);
        list.appendChild(div);
    });
    updateAreaPieChart();
}

function editAreaName(areaId, element) {
    const currentName = element.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.onblur = () => saveAreaName(areaId, input.value);
    input.onkeypress = (e) => { if (e.key === 'Enter') saveAreaName(areaId, input.value); };
    element.innerHTML = '';
    element.appendChild(input);
    input.focus();
}

function saveAreaName(areaId, name) {
    fetch('/update_area_name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ area_id: areaId, name: name })
    })
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                const area = areas.find(a => a.id === areaId);
                if (area) area.name = name;
                updateAreaList();
                appendLog(`Area ${areaId} renamed to ${name}`);
            }
        })
        .catch(error => console.error('Error renaming area:', error));
}

function selectAreaById(areaId) {
    const area = areas.find(a => a.id === areaId);
    if (area) {
        selectedAreaId = areaId;
        selectedArea = area;
        updateAreaList();
        updateMonitorButton();
        map.fitBounds(area.bounds);
    }
}

function updateMLStats() {
    fetch('/ml_stats')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch ML stats');
            return response.json();
        })
        .then(data => {
            document.getElementById('ml-status').textContent = data.status || 'Not loaded';
            document.getElementById('ml-samples').textContent = data.samples || 0;
            document.getElementById('ml-classes').textContent = data.classes || 0;
            document.getElementById('ml-retrain').textContent = data.retrainRecommended ? 'Yes' : 'No';
        })
        .catch(error => console.error('Error fetching ML stats:', error));
}

let pieChart = null;
function updateAreaPieChart() {
    const areaId = selectedAreaId || 'all';
    fetch(`/area_classifications?area_id=${areaId}`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch area classifications');
            return response.json();
        })
        .then(data => {
            const ctx = document.getElementById('area-pie-chart');
            if (!ctx) {
                console.error('Canvas element #area-pie-chart not found');
                return;
            }
            const chartContext = ctx.getContext('2d');
            if (pieChart) pieChart.destroy();
            const labels = Object.keys(data);
            const colors = labels.map(label => {
                const cls = classifications.find(c => c.name === label);
                return cls ? cls.color : '#808080';
            });
            pieChart = new Chart(chartContext, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        data: Object.values(data),
                        backgroundColor: colors
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { color: '#e0e0e0' }
                        }
                    },
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const classification = Object.keys(data)[index];
                            selectClassification(classification);
                            const area = areas.find(a => a.id === selectedAreaId);
                            if (area) map.fitBounds(area.bounds);
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching area classifications:', error));
}

function selectClassification(classification) {
    document.querySelectorAll('.path-checkboxes input[type="checkbox"]').forEach(cb => {
        cb.checked = cb.id === `show-${classification}`;
    });
    updatePathsAndList();
}

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupSocketEvents(map);

    const frequency = Cookies.get('frequency') || '30s';
    document.getElementById('frequency').value = frequency;
    loadClassifications();
    fetchTotalFlights();
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
            selectedAreaId = null;
            selectedArea = null;
            updateAreaList();
            updateMonitorButton();
        }
    });

    document.getElementById('monitor-btn').addEventListener('click', toggleMonitoring);
    document.getElementById('delete-btn').addEventListener('click', deleteArea);
    document.getElementById('retrain-btn').addEventListener('click', retrainModel);
    document.getElementById('add-class-btn').addEventListener('click', addClassification);
    document.querySelectorAll('.path-checkboxes input').forEach(cb => {
        cb.addEventListener('change', updatePathsAndList);
    });
    document.getElementById('tab-classification').addEventListener('click', () => switchTab('classification'));
    document.getElementById('tab-ml').addEventListener('click', () => switchTab('ml'));
    document.getElementById('tab-area').addEventListener('click', () => switchTab('area'));
});