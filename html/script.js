document.getElementById('queryForm').addEventListener('submit', function(event) {
    event.preventDefault();

    const query = document.getElementById('query').value;
    const responseField = document.getElementById('response');

    query.value=""

    // Clear previous response
    responseField.value = "Thinking...";

    fetch('http://127.0.0.1:5000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `query=${encodeURIComponent(query)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.result) {
            responseField.value = data.result;
        } else {
            responseField.value = "Error: No response from AI.";
        }
    })
    .catch(error => {
        responseField.value = `Error: ${error.message}`;
    });
});

document.getElementById('chartForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const chartType = document.getElementById('chartType').value;
    const aiResponse = document.getElementById('response').value;

    // Fetch the energy data using a GET request
    const response = await fetch('http://127.0.0.1:5000/energy_data');

    if (!response.ok) {
        console.error("Failed to fetch energy data.");
        return;
    }

    const energyData = await response.json();

    // Clear the existing chart container
    document.getElementById('chartContainer').innerHTML = '';

    // Plot the charts based on the fetched data and user input
    generateCharts(energyData, chartType);
});

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    if (sidebar.style.width === "250px") {
        sidebar.style.width = "0";
    } else {
        sidebar.style.width = "250px";
    }
}



function generateCharts(energyData, chartType) {
    // List of devices (this should match the columns in your data)
    const devices = ['washing_machine1_energy_W', 'washing_machine2_energy_W', 'fridge1_energy_W', 'fridge2_energy_W', 'AC_energy_W'];

    devices.forEach(device => {
        const canvas = document.createElement('canvas');
        canvas.id = `${device}_chart`;
        document.getElementById('chartContainer').appendChild(canvas);

        const context = document.getElementById(`${device}_chart`).getContext('2d');
        plotLineChart(energyData, device, context, chartType);
    });
}

function plotLineChart(data, device, context, chartType) {
    const labels = data.map(entry => entry.timestamp);
    const values = data.map(entry => entry[device]);

    new Chart(context, {
        type: chartType,  // Use the selected chart type
        data: {
            labels: labels,
            datasets: [{
                label: `${device} Consumption (W)`,
                data: values,
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                fill: false,
                tension: 0.1
            }]
        },
        options: {
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour'
                    },
                    title: {
                        display: true,
                        text: 'Timestamp'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Energy Consumption (W)'
                    }
                }
            }
        }
    });
}

function toggleDarkMode() {
    document.body.classList.toggle("dark-mode");
}

const form = document.getElementById('newsletterForm');
const emailInput = document.getElementById('emailInput');
const successBanner = document.getElementById('successBanner');
const confettiCanvas = document.getElementById('confettiCanvas');
let ctx = confettiCanvas.getContext('2d');
let particles = [];

form.addEventListener('submit', function(event) {
    event.preventDefault();
    if (emailInput.value) {
        successBanner.style.display = 'block';
        startConfetti();
        setTimeout(() => {
            stopConfetti();
            successBanner.style.display = 'none';
            emailInput.value = '';
        }, 5000);
    }
});

// Confetti setup
function startConfetti() {
    confettiCanvas.style.display = 'block';
    confettiCanvas.width = window.innerWidth;
    confettiCanvas.height = window.innerHeight;

    particles = Array.from({ length: 100 }, () => ({
        x: Math.random() * confettiCanvas.width,
        y: Math.random() * confettiCanvas.height - confettiCanvas.height,
        w: 10 + Math.random() * 10,
        h: 10 + Math.random() * 10,
        color: `hsl(${Math.random() * 360}, 100%, 50%)`,
        velocityY: Math.random() * 3 + 2
    }));

    confettiInterval = setInterval(updateConfetti, 16);
}

function stopConfetti() {
    clearInterval(confettiInterval);
    confettiCanvas.style.display = 'none';
}

function updateConfetti() {
    ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
    particles.forEach((p) => {
        p.y += p.velocityY;
        if (p.y > confettiCanvas.height) {
            p.y = -p.h;
            p.x = Math.random() * confettiCanvas.width;
        }
        ctx.fillStyle = p.color;
        ctx.fillRect(p.x, p.y, p.w, p.h);
    });
}

window.addEventListener('resize', () => {
    confettiCanvas.width = window.innerWidth;
    confettiCanvas.height = window.innerHeight;
});
