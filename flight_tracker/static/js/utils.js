let canRetrain = false;
let updateTimeout = null;

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function appendLog(message) {
    const log = document.getElementById('log');
    log.innerText = message + '\n' + log.innerText;
    log.scrollTop = 0;
}

function debounceUpdateFlightPaths() {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(updateFlightPaths, 500);
}

function getSelectedClasses() {
    return Array.from(document.querySelectorAll('.path-checkboxes input[type="checkbox"]:checked'))
        .map(cb => cb.id.replace('show-', ''));
}

function updateFlightPaths() {
    fetch('/flight_paths')
        .then(response => response.json())
        .then(data => {
            console.log('Fetched flight paths:', data);
            const activeFlightIds = new Set(data.map(f => f.flight_id));
            Object.keys(flightLines).forEach(id => {
                if (!activeFlightIds.has(id)) {
                    if (flightLines[id].line) flightLayer.removeLayer(flightLines[id].line);
                    if (flightLines[id].marker) flightLayer.removeLayer(flightLines[id].marker);
                    delete flightLines[id];
                }
            });
            data.forEach(flight => debouncedRenderFlightPath(flight));
            updateFlightList();
            updateStats();
            fetch('/flight_paths').then(r => r.json()).then(data => {
                const classCounts = data.reduce((acc, f) => {
                    acc[f.classification] = (acc[f.classification] || 0) + 1;
                    return acc;
                }, {});
                canRetrain = Object.keys(classCounts).length > 1 && data.length >= 10;
                document.getElementById('retrain-btn').disabled = !canRetrain;
            });
            document.querySelectorAll('.path-checkboxes input[type="checkbox"]').forEach(cb => {
                Cookies.set(cb.id, cb.checked, { expires: 365 });
            });
        })
        .catch(error => console.error('Error fetching paths:', error));
}

function updateFlightList() {
    const list = document.getElementById('flight-list-content');
    list.innerHTML = '';
    console.log('Updating flight list with flightLines:', Object.keys(flightLines));
    const selectedClasses = getSelectedClasses();

    Object.keys(flightLines).forEach(id => {
        const flight = flightLines[id];
        const popupContent = flight.line?.getPopup()?.getContent() || flight.marker?.getPopup()?.getContent() || '';
        const currentClass = popupContent.match(/Class: (.*?)(?:\s\(|$)/)?.[1] || 'N/A';
        const source = popupContent.match(/\((.*?)\)/)?.[1] || 'N/A';
        const lastPoint = flight.points[flight.points.length - 1];
        const altitude = lastPoint[3] === -1 ? 'N/A' : `${lastPoint[3]} m`;
        const velocity = lastPoint[4] === -1 ? 'N/A' : `${lastPoint[4]} m/s`;
        const avgAltitude = flight.avg_altitude === -1 ? 'N/A' : `${Math.round(flight.avg_altitude)} m`;
        const avgVelocity = flight.avg_velocity === -1 ? 'N/A' : `${Math.round(flight.avg_velocity)} m/s`;
        const duration = flight.duration === 0 ? 'N/A' : `${Math.round(flight.duration / 60)} min`;
        const heading = flight.line ? (flight.line.getLatLngs().length > 1 ? flight.lastRotation || 'N/A' : 'N/A') : 'N/A';

        // Show flight if its class is selected, no classes are selected, or it’s the selected flight
        const shouldShow = selectedClasses.length === 0 || selectedClasses.includes(currentClass) || id === selectedFlightId;
        if (shouldShow) {
            const div = document.createElement('div');
            if (id === selectedFlightId) {
                div.className = 'flight-item detailed';
                div.innerHTML = `
                    <div class="flight-header">
                        <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2">
                            <path d="M20.5 3.5L3.5 12L9.5 14.5L15.5 9.5L10.5 15.5L13 20.5L20.5 3.5Z"/>
                        </svg>
                        <span>${id}</span>
                    </div>
                    <div class="flight-data">
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M12 2v20m10-10H2"/></svg><span>Alt: ${altitude}</span></div>
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M22 11h-8l-2-9L2 12l10 10 2-9h8z"/></svg><span>Vel: ${velocity}</span></div>
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M12 2v10l8 4-8-14zm0 20v-6"/></svg><span>Heading: ${heading === 'N/A' ? 'N/A' : `${Math.round(heading)}°`}</span></div>
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M12 2v20m10-10H2"/></svg><span>Avg Alt: ${avgAltitude}</span></div>
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M22 11h-8l-2-9L2 12l10 10 2-9h8z"/></svg><span>Avg Vel: ${avgVelocity}</span></div>
                        <div><svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2"><path d="M12 2v6m0 10v6m-6-12h12"/></svg><span>Duration: ${duration}</span></div>
                    </div>
                    <select onchange="updateClassification('${id}', this.value)">
                        ${Array.from(document.getElementById('class-filter').options).map(opt =>
                    `<option value="${opt.value}" ${currentClass === opt.value ? 'selected' : ''}>${opt.value || 'N/A'}</option>`
                ).join('')}
                    </select>
                    <span class="source">(${source})</span>
                `;
            } else {
                div.className = 'flight-item compact';
                div.innerHTML = `
                    <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e0e0e0" stroke-width="2">
                        <path d="M20.5 3.5L3.5 12L9.5 14.5L15.5 9.5L10.5 15.5L13 20.5L20.5 3.5Z"/>
                    </svg>
                    <span>${id} - ${currentClass}</span>
                `;
            }
            div.dataset.classification = currentClass;
            div.style.backgroundColor = id === selectedFlightId ? '#3c3c3c' : '';
            div.onclick = () => selectFlight(id);
            div.tabIndex = 0;
            list.appendChild(div);
        }
    });
    filterFlights();

    list.addEventListener('keydown', (e) => {
        const items = Array.from(list.children).filter(item => item.style.display !== 'none');
        if (!items.length) return;
        const focused = document.activeElement;
        const index = items.indexOf(focused);

        if (e.key === 'ArrowDown' && index < items.length - 1) {
            e.preventDefault();
            items[index + 1].focus();
            selectFlight(items[index + 1].querySelector('span').textContent.split(' - ')[0]);
        } else if (e.key === 'ArrowUp' && index > 0) {
            e.preventDefault();
            items[index - 1].focus();
            selectFlight(items[index - 1].querySelector('span').textContent.split(' - ')[0]);
        }
    });
}

function updateStats() {
    document.getElementById('flight-count').innerText = Object.keys(flightLines).length;
    document.getElementById('area-count').innerText = areas.filter(a => a.is_monitoring).length;
    console.log('Total flights tracked:', flightLines.size);
}

function updateClassification(flightId, classification) {
    fetch('/update_classification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flight_id: flightId, classification: classification })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
            } else {
                appendLog(data.message);
                debounceUpdateFlightPaths();
            }
        })
        .catch(error => console.error('Error:', error));
}

function filterFlights() {
    const textFilter = document.getElementById('flight-filter').value.toLowerCase();
    const classFilter = document.getElementById('class-filter').value;
    const selectedClasses = getSelectedClasses();
    const list = document.getElementById('flight-list-content');
    Array.from(list.children).forEach(div => {
        const text = div.textContent.toLowerCase();
        const classification = div.dataset.classification || 'N/A';
        const flightId = div.querySelector('span').textContent.split(' - ')[0];
        const matchesText = text.includes(textFilter);
        const matchesClass = !classFilter || classification === classFilter;
        const matchesPathSelection = selectedClasses.length === 0 || selectedClasses.includes(classification) || flightId === selectedFlightId;
        div.style.display = matchesText && matchesClass && matchesPathSelection ? '' : 'none';
    });
}