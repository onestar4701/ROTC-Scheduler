document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('calendarGrid');
    const monthPicker = document.getElementById('monthPicker');

    if (!grid || !monthPicker) return; // Only run on pages with these elements

    let isDragging = false;
    let startCell = null;
    let currentMode = 'toggle'; // 'available' -> 'unavailable' -> 'preferred' -> 'available'

    // Load initial data
    loadMonthData();

    monthPicker.addEventListener('change', loadMonthData);

    function getDaysInMonth(year, month) {
        return new Date(year, month + 1, 0).getDate();
    }

    async function loadMonthData() {
        const [year, month] = monthPicker.value.split('-').map(Number);
        const daysInMonth = getDaysInMonth(year, month - 1);

        // Fetch existing availability
        const response = await fetch(`/api/availability/${PERSON_ID}`);
        const data = await response.json();
        const availabilityMap = {};
        data.forEach(item => availabilityMap[item.date] = item.status);

        grid.innerHTML = '';

        for (let i = 1; i <= daysInMonth; i++) {
            const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
            const dayOfWeek = new Date(year, month - 1, i).getDay(); // 0 = Sun, 6 = Sat
            const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

            const cell = document.createElement('div');
            cell.className = 'day-slot';
            cell.dataset.date = dateStr;
            cell.dataset.status = availabilityMap[dateStr] || 'available'; // Default available

            // Apply class based on status
            cell.classList.add(cell.dataset.status);

            cell.innerHTML = `
                <div style="font-size: 0.8rem; color: #64748b;">${dayNames[dayOfWeek]}</div>
                <div style="font-weight: bold; font-size: 1.1rem;">${i}</div>
            `;

            // Mouse Events
            cell.addEventListener('mousedown', (e) => {
                isDragging = true;
                startCell = cell;
                // Determine next status based on current status of start cell
                const statusCycle = {
                    'available': 'unavailable',
                    'unavailable': 'preferred',
                    'preferred': 'available'
                };
                currentMode = statusCycle[cell.dataset.status];
                updateCellStatus(cell, currentMode);
                e.preventDefault(); // Prevent text selection
            });

            cell.addEventListener('mouseenter', () => {
                if (isDragging) {
                    updateCellStatus(cell, currentMode);
                }
            });

            grid.appendChild(cell);
        }
    }

    document.addEventListener('mouseup', () => {
        isDragging = false;
        startCell = null;
    });

    function updateCellStatus(cell, status) {
        if (cell.dataset.status === status) return;

        // Remove old class
        cell.classList.remove('available', 'unavailable', 'preferred');

        // Update status
        cell.dataset.status = status;

        // Add new class
        cell.classList.add(status);

        // Save to backend
        saveAvailability(cell.dataset.date, status);
    }

    async function saveAvailability(date, status) {
        try {
            await fetch(`/api/availability/${PERSON_ID}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ date, status }),
            });
        } catch (error) {
            console.error('Failed to save availability', error);
        }
    }
});
