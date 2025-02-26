const socket = io();

function setupSocketEvents() {
    socket.on('log', (data) => {
        appendLog(data.message);
    });

    socket.on('flight_update', (flight) => {
        console.log('Received flight_update:', flight);
        window.debouncedRenderFlightPath(flight); // Raw function
        updateFlightList();
        updateStats();
    });

    socket.on('flight_batch_update', (data) => {
        console.log('Received flight_batch_update:', data);
        let allCoords = [];
        data.flights.forEach(flight => {
            console.log('Processing flight:', flight);
            window.debouncedRenderFlightPath(flight); // Raw function
            allCoords = allCoords.concat(flight.points.map(p => [p[0], p[1]]));
        });
        if (allCoords.length > 0 && !hasZoomed) {
            map.fitBounds(allCoords);
            hasZoomed = true;
        }
        updateFlightList();
        updateStats();
    });
}