const socket = io();

function setupSocketEvents(map) {
    if (!map) {
        console.error('Map not initialized for socket events');
        return;
    }

    socket.on('log', (data) => {
        appendLog(data.message);
    });

    socket.on('flight_batch_update', (data) => {
        let allCoords = [];
        data.flights.forEach(flight => {
            flightLines.add(flight.flight_id);
            window.debouncedRenderFlightPath(flight);
            allCoords = allCoords.concat(flight.points.map(p => [p[0], p[1]]));
        });
        if (map.fitBounds != undefined && allCoords.length > 0 && !hasZoomed) {
            map.fitBounds(allCoords);
            hasZoomed = true;
        }
        updateFlightList();
        updateStats();
    });

    socket.on('connect', () => {
        console.log('Connected to server');
        fetch('/get_flight_paths')
            .then(response => response.json())
            .then(data => {
                console.log('Fetched flight paths:', data);
                data.forEach(flight => flightLines.add(flight.flight_id));
                updateFlightList();
            })
            .catch(err => console.error('Error fetching flight paths:', err));
    });

    socket.on('flight_cleanup', (data) => {
        data.flight_ids.forEach(id => flightLines.delete(id));
        console.log('Cleaned up flights, new flightLines:', Array.from(flightLines));
        updateFlightList();
    });

    socket.on('disconnect', () => console.log('Disconnected from server'));
    socket.on('error', (err) => console.error('WebSocket error:', err));
}