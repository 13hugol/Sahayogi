document.addEventListener("DOMContentLoaded", function () {
    const detectBtn = document.getElementById("use-my-location-btn");
    const locationInput = document.getElementById("location-input");
    const latInput = document.getElementById("loc-lat");
    const lngInput = document.getElementById("loc-lng");
    const labelInput = document.getElementById("loc-label");
    const statusText = document.getElementById("location-status");
    const applyBtn = document.getElementById("apply-location-filter-btn");

    if (!detectBtn || !locationInput) return;

    function setStatus(msg, isError = false) {
        statusText.textContent = msg;
        statusText.className = isError ? "form-text mt-1 text-danger" : "form-text mt-1 text-success";
    }

    locationInput.addEventListener("input", () => {
        latInput.value = "";
        lngInput.value = "";
        labelInput.value = locationInput.value;
        applyBtn.disabled = locationInput.value.trim().length === 0;
        statusText.textContent = "";
    });

    detectBtn.addEventListener("click", () => {
        if (!navigator.geolocation) {
            setStatus("Geolocation is not supported by your browser.", true);
            return;
        }

        detectBtn.disabled = true;
        detectBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        setStatus("Locating...");

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;

                latInput.value = lat.toFixed(6);
                lngInput.value = lng.toFixed(6);

                try {
                    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10`);
                    if (!res.ok) throw new Error("Geocoding failed");
                    const data = await res.json();
                    
                    const label = data.address.city || data.address.town || data.address.county || "Detected Location";
                    locationInput.value = label;
                    labelInput.value = label;

                    setStatus(`Found: ${label} (${lat.toFixed(2)}, ${lng.toFixed(2)})`);
                    applyBtn.disabled = false;

                    await fetch('/profile/update-location', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        },
                        body: JSON.stringify({ lat, lng, label })
                    });
                } catch (err) {
                    console.error(err);
                    locationInput.value = `Lat: ${lat.toFixed(2)}, Lng: ${lng.toFixed(2)}`;
                    labelInput.value = "Current Location";
                    setStatus("Location found (label resolution failed).", false);
                    applyBtn.disabled = false;
                } finally {
                    detectBtn.disabled = false;
                    detectBtn.innerHTML = '<i class="bi bi-crosshair"></i> Detect';
                }
            },
            (error) => {
                let msg = "Location error.";
                if (error.code === error.PERMISSION_DENIED) msg = "Location permission denied.";
                setStatus(msg, true);
                detectBtn.disabled = false;
                detectBtn.innerHTML = '<i class="bi bi-crosshair"></i> Detect';
            },
            { timeout: 10000 }
        );
    });

    const form = document.getElementById("searchForm");
    form.addEventListener("submit", async (e) => {
        if (latInput.value && lngInput.value) return;
        
        const q = locationInput.value.trim();
        if (!q) {
            return; // let it submit if empty location to clear filter
        }

        e.preventDefault();
        applyBtn.disabled = true;
        setStatus("Looking up coordinates...");

        try {
            const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=1`);
            if (!res.ok) throw new Error("Search failed");
            const data = await res.json();

            if (data.length === 0) {
                setStatus("Location not found. Please try a different city.", true);
                applyBtn.disabled = false;
                return;
            }

            latInput.value = parseFloat(data[0].lat).toFixed(6);
            lngInput.value = parseFloat(data[0].lon).toFixed(6);
            labelInput.value = data[0].display_name.split(',')[0];
            
            form.submit();
        } catch (err) {
            setStatus("Error looking up location. Please try again.", true);
            applyBtn.disabled = false;
        }
    });

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }
});
