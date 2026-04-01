// SafeLink - location.js

let map;
let pairedMarker = null;
let myMarker = null;

function setStatus(message) {
    const statusBox = document.getElementById("statusBox");
    if (statusBox) {
        statusBox.innerText = "Status: " + message;
    }
}

function initializeMap(lat = 17.3850, lng = 78.4867, zoom = 13) {
    const mapElement = document.getElementById("map");
    if (!mapElement) return;

    map = L.map("map").setView([lat, lng], zoom);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
}

function updateMyLocation() {
    if (!navigator.geolocation) {
        setStatus("Geolocation is not supported by this browser.");
        return;
    }

    setStatus("Fetching your current location...");

    navigator.geolocation.getCurrentPosition(
        function (position) {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            fetch("/update-location", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setStatus("Your location updated successfully.");

                    if (map) {
                        if (myMarker) {
                            myMarker.setLatLng([latitude, longitude]);
                        } else {
                            myMarker = L.marker([latitude, longitude]).addTo(map)
                                .bindPopup("My Current Location");
                        }
                    }
                } else {
                    setStatus(data.message || "Failed to update location.");
                }
            })
            .catch(error => {
                console.error(error);
                setStatus("Error while updating location.");
            });
        },
        function (error) {
            console.error(error);
            setStatus("Location access denied or unavailable.");
        }
    );
}

function refreshPairedLocation() {
    fetch("/get-paired-location")
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const lat = data.latitude;
                const lng = data.longitude;

                if (document.getElementById("latText")) {
                    document.getElementById("latText").innerText = lat;
                }
                if (document.getElementById("lngText")) {
                    document.getElementById("lngText").innerText = lng;
                }
                if (document.getElementById("timeText")) {
                    document.getElementById("timeText").innerText = data.updated_at;
                }

                if (map) {
                    if (pairedMarker) {
                        pairedMarker.setLatLng([lat, lng]);
                        pairedMarker.bindPopup(data.name + "'s Live Location");
                    } else {
                        pairedMarker = L.marker([lat, lng]).addTo(map)
                            .bindPopup(data.name + "'s Live Location");
                    }

                    map.setView([lat, lng], 14);
                }

                setStatus("Paired user location updated.");
            } else {
                setStatus(data.message || "No paired user location found.");
            }
        })
        .catch(error => {
            console.error(error);
            setStatus("Error fetching paired user location.");
        });
}

function sendSOS() {
    if (!navigator.geolocation) {
        setStatus("Geolocation is not supported by this browser.");
        return;
    }

    setStatus("Fetching location for SOS...");

    navigator.geolocation.getCurrentPosition(
        function (position) {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            fetch("/send-sos", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setStatus("SOS alert sent successfully.");
                    alert("SOS alert sent successfully!");
                } else {
                    setStatus(data.message || "Failed to send SOS.");
                }
            })
            .catch(error => {
                console.error(error);
                setStatus("Error sending SOS alert.");
            });
        },
        function (error) {
            console.error(error);
            setStatus("Unable to get location for SOS.");
        }
        
    );
}

function startAutoRefresh(interval = 5000) {
    setInterval(refreshPairedLocation, interval);
}
// ===== LIVE TRACKING ADDITION (DO NOT MODIFY EXISTING CODE) =====

let trackingInterval = null;

function startTracking() {
    if (trackingInterval !== null) {
        setStatus("Already sharing location.");
        return;
    }

    setStatus("Live location sharing started...");

    // send immediately
    updateMyLocation();

    // then repeat every 5 seconds
    trackingInterval = setInterval(() => {
        updateMyLocation();
    }, 5000);
}

function stopTracking() {
    if (trackingInterval === null) {
        setStatus("Tracking is not active.");
        return;
    }

    clearInterval(trackingInterval);
    trackingInterval = null;

    setStatus("Live location sharing stopped.");
}