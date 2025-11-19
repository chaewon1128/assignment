<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PM10 and Public Transit Data Analysis</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
    <!-- Chart.js Adapter Luxon for time series (optional but good practice for time data) -->
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@2.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/papaparse@5.3.2/min/papaparse.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .chart-container {
            background-color: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        }
        .hidden {
            display: none;
        }
        /* Custom scrollbar for better appearance */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }
        .data-message {
            padding: 2rem;
            text-align: center;
            font-weight: 600;
            color: #ef4444; /* Red color for error/not found */
            border: 2px dashed #fca5a5;
            border-radius: 8px;
            margin: 20px 0;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 300px;
        }
        #timeSeriesChart {
            height: 400px; /* Ensure time series chart has enough height for readability */
        }
    </style>
</head>
<body class="p-4 md:p-8">
    <header class="mb-8 text-center">
        <h1 class="text-3xl font-bold text-gray-800">PM10 and Public Transit Analysis in Seoul</h1>
        <p class="text-gray-500">Comparing fine dust concentration and public transportation usage across districts and time.</p>
    </header>

    <main class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        <!-- Chart 1: Average PM10 Concentration by District (with Year Selector) -->
        <section class="lg:col-span-2 chart-container">
            <h2 id="chart-title-district" class="text-xl font-semibold mb-4 text-gray-700">Average PM10 Concentration by District (2012 Data)</h2>
            <div class="mb-4 flex flex-wrap items-center space-x-4">
                <label for="year-selector" class="text-gray-600 font-medium">Select Data Year:</label>
                <!-- Available years for ppl_data are 2012 and 2014 -->
                <select id="year-selector" class="border border-gray-300 rounded-md p-2 shadow-sm focus:ring-blue-500 focus:border-blue-500">
                    <option value="2012">2012</option>
                    <option value="2014">2014</option>
                    <option value="2013">2013 (No Data)</option>
                    <option value="2015">2015 (No Data)</option>
                </select>
            </div>
            <div id="pm10-district-chart-wrapper" class="relative">
                <canvas id="pm10DistrictChart" class="h-96"></canvas>
            </div>
            <!-- Data Not Found Message for Chart 1 -->
            <div id="data-not-found-message-district" class="data-message hidden">
                No PM10 data or corresponding transit data found for the selected year. Please choose 2012 or 2014.
            </div>
        </section>

        <!-- Chart 2: Time Series Comparison -->
        <section class="lg:col-span-3 chart-container">
            <h2 id="chart-title-timeseries" class="text-xl font-semibold mb-4 text-gray-700">Time Series Comparison of PM10 and Public Transit Usage (Daily Average)</h2>
            <canvas id="timeSeriesChart"></canvas>
        </section>

        <!-- Chart 3: Average Public Transit Usage by PM10 Status -->
        <section class="lg:col-span-1 chart-container">
            <h2 id="chart-title-status" class="text-xl font-semibold mb-4 text-gray-700">Average Public Transit Usage by PM10 Status</h2>
            <canvas id="pm10StatusChart"></canvas>
        </section>

    </main>

    <script type="module">
        // Global Chart instances
        let pm10DistrictChart = null;
        let timeSeriesChart = null;
        let pm10StatusChart = null;

        // Global data storage
        let dataPM10; // combined_pol.csv
        let dataTransit; // trans.csv
        let dataPPL_2012; // ppl_2012.csv
        let dataPPL_2014; // ppl_2014.csv

        // API Key (kept empty as per instructions)
        const apiKey = "";
        
        // --- Data Loading and Parsing Utilities ---

        /**
         * Fetches and parses a CSV file using PapaParse.
         * @param {string} filePath - The path/name of the CSV file.
         * @returns {Promise<Array<Object>>} - A promise that resolves with the parsed data array.
         */
        function fetchAndParseCsv(filePath) {
            return new Promise((resolve, reject) => {
                // Use the global fetch logic for Canvas environment
                fetch(filePath)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`Failed to load ${filePath}: ${response.statusText}`);
                        }
                        return response.text();
                    })
                    .then(csvText => {
                        Papa.parse(csvText, {
                            header: true,
                            // Use a custom worker to handle dynamic typing for potential number columns
                            dynamicTyping: (value, field) => {
                                // Explicitly check if it looks like a number
                                if (field.includes('PM10') || field.includes('승객') || field.includes('개수')) {
                                    const num = parseFloat(value);
                                    return isNaN(num) ? value : num;
                                }
                                return value;
                            },
                            skipEmptyLines: true,
                            complete: function(results) {
                                resolve(results.data);
                            },
                            error: function(error) {
                                reject(new Error(`PapaParse error for ${filePath}: ${error.message}`));
                            }
                        });
                    })
                    .catch(error => {
                        console.error("Fetch/Parse Error:", error);
                        reject(error);
                    });
            });
        }

        // --- Data Preparation Functions ---

        /**
         * Aggregates PM10 and public transit data by District for a specific year.
         * Filters PM10 data by the year and combines it with district-level transit/population proxy data.
         * @param {number} year - The year to filter the data for (expected: 2012 or 2014).
         * @returns {Array<Object>} - Aggregated data with district, avg_pm10, and passenger_count.
         */
        function getPM10TransitDataByDistrict(year) {
            let pplData;
            if (year === 2012) {
                pplData = dataPPL_2012;
            } else if (year === 2014) {
                pplData = dataPPL_2014;
            } else {
                // Return empty array for years without corresponding PPL data
                return []; 
            }

            const yearStr = String(year);

            // 1. Filter and Aggregate PM10 data for the given year
            // Filter by year and exclude '평균' (average) rows as we want district-specific data
            const pm10DataForYear = dataPM10.filter(d => 
                d.일시 && d.일시.startsWith(yearStr) && d['자치구'] !== '평균'
            );
            
            if (pm10DataForYear.length === 0) {
                 // If no PM10 data for the year exists
                 return [];
            }

            const pm10Aggregated = pm10DataForYear.reduce((acc, curr) => {
                const district = curr['자치구'];
                const pm10 = curr['미세먼지(PM10)'];

                if (district && typeof pm10 === 'number' && !isNaN(pm10)) {
                    if (!acc[district]) {
                        acc[district] = { sum_pm10: 0, count: 0 };
                    }
                    acc[district].sum_pm10 += pm10;
                    acc[district].count += 1;
                }
                return acc;
            }, {});

            // 2. Combine with Public Transit/Population data (pplData)
            const combinedData = [];
            
            // Map the aggregated PM10 data to the passenger data (pplData)
            pplData.forEach(d => {
                const district = d['거주지'];
                // Ensure the district has aggregated PM10 data
                if (district && pm10Aggregated[district]) {
                    const avg_pm10 = pm10Aggregated[district].sum_pm10 / pm10Aggregated[district].count;
                    combinedData.push({
                        district: district,
                        avg_pm10: avg_pm10,
                        passenger_count: d['개수'] // Proxy for passenger count / population
                    });
                }
            });

            // If the combined data is empty (e.g., no matching districts or missing data), return empty array
            if (combinedData.length === 0) {
                return [];
            }
            
            // Sort by PM10 (highest first) for better visualization
            return combinedData.sort((a, b) => b.avg_pm10 - a.avg_pm10);
        }

        /**
         * Aggregates data for time series chart (PM10 daily average vs. Transit daily average).
         * @returns {Array<Object>} - Aggregated daily data.
         */
        function getTimeSeriesData() {
            // 1. Aggregate daily PM10 average (from combined_pol.csv)
            const dailyPM10 = dataPM10.reduce((acc, curr) => {
                const date = curr['일시'];
                const pm10 = curr['미세먼지(PM10)'];

                // Only use '평균' (average) row for daily time series
                if (curr['자치구'] !== '평균' || !date || typeof pm10 !== 'number' || isNaN(pm10)) return acc;

                acc[date] = { pm10_avg: pm10 };
                return acc;
            }, {});

            // 2. Aggregate daily Transit average (from trans.csv) - Sum of passengers per day
            const dailyTransit = dataTransit.reduce((acc, curr) => {
                const date = curr['기준_날짜'];
                const passengers = curr['승객_수'];

                if (date && typeof passengers === 'number' && !isNaN(passengers)) {
                    if (!acc[date]) {
                        acc[date] = 0;
                    }
                    acc[date] += passengers;
                }
                return acc;
            }, {});

            // 3. Combine and sort
            const combined = [];
            Object.keys(dailyPM10).forEach(date => {
                const transit_total = dailyTransit[date] || 0;
                // Only include data where both PM10 and Transit data points exist
                if (transit_total > 0) {
                     combined.push({
                        date: date,
                        pm10_avg: dailyPM10[date].pm10_avg,
                        transit_total: transit_total
                    });
                }
            });
            
            // Sort by date
            return combined.sort((a, b) => new Date(a.date) - new Date(b.date));
        }

        /**
         * Calculates average transit usage based on PM10 status (Good, Normal, Bad).
         * @returns {Object<string, number>} - Object containing average transit usage by status.
         */
        function getPM10StatusTransitData() {
            // Define PM10 Status thresholds (Korea's standards for daily PM10)
            const THRESHOLDS = {
                GOOD: 30,    // <= 30 µg/m³
                NORMAL: 80,  // 31 ~ 80 µg/m³
                BAD: 150,    // 81 ~ 150 µg/m³
                VERY_BAD: 151
            };

            const getStatus = (pm10) => {
                if (pm10 <= THRESHOLDS.GOOD) return 'Good';
                if (pm10 <= THRESHOLDS.NORMAL) return 'Normal';
                if (pm10 <= THRESHOLDS.BAD) return 'Bad';
                return 'Very Bad';
            };

            // 1. Calculate daily PM10 average and status (from '평균' row)
            const dailyPM10Map = dataPM10.reduce((acc, curr) => {
                const date = curr['일시'];
                const pm10 = curr['미세먼지(PM10)'];
                
                // Only consider the overall average row ('자치구' is '평균')
                if (curr['자치구'] === '평균' && date && typeof pm10 === 'number' && !isNaN(pm10)) {
                    acc[date] = { pm10: pm10, status: getStatus(pm10) };
                }
                return acc;
            }, {});

            // 2. Aggregate daily Transit usage (from trans.csv)
            const dailyTransitTotal = dataTransit.reduce((acc, curr) => {
                const date = curr['기준_날짜'];
                const passengers = curr['승객_수'];

                if (date && typeof passengers === 'number' && !isNaN(passengers)) {
                    if (!acc[date]) {
                        acc[date] = 0;
                    }
                    acc[date] += passengers;
                }
                return acc;
            }, {});

            // 3. Combine by PM10 Status
            const statusAggregation = {
                'Good': { sum_transit: 0, count: 0 },
                'Normal': { sum_transit: 0, count: 0 },
                'Bad': { sum_transit: 0, count: 0 },
                'Very Bad': { sum_transit: 0, count: 0 }
            };

            // Iterate over dates that exist in both PM10 and Transit data (intersection)
            Object.keys(dailyPM10Map).forEach(date => {
                const transit_total = dailyTransitTotal[date];
                const pm10_status = dailyPM10Map[date].status;

                if (transit_total && pm10_status && statusAggregation[pm10_status]) {
                    statusAggregation[pm10_status].sum_transit += transit_total;
                    statusAggregation[pm10_status].count += 1;
                }
            });

            // 4. Calculate final averages
            const finalAverages = {};
            const statusOrder = ['Good', 'Normal', 'Bad', 'Very Bad']; // Define order for chart
            
            statusOrder.forEach(status => {
                const agg = statusAggregation[status];
                finalAverages[status] = agg.count > 0 ? agg.sum_transit / agg.count : 0;
            });
            
            return finalAverages;
        }

        // --- Chart Rendering Functions ---

        /**
         * Renders the Average PM10 Concentration by District chart.
         * @param {number} selectedYear - The year selected by the user.
         */
        function updatePM10ByDistrictChart(selectedYear) {
            const chartData = getPM10TransitDataByDistrict(selectedYear);
            
            const canvas = document.getElementById('pm10DistrictChart');
            const errorElement = document.getElementById('data-not-found-message-district');
            const titleElement = document.getElementById('chart-title-district');
            
            titleElement.textContent = `Average PM10 Concentration by District (${selectedYear} Data)`;

            if (chartData.length === 0) {
                // Handle missing data: hide canvas, show message
                canvas.classList.add('hidden');
                errorElement.classList.remove('hidden');
                errorElement.textContent = `No PM10 data or corresponding transit/population data found for the year: ${selectedYear}. Please choose 2012 or 2014.`;
                if (pm10DistrictChart) {
                    pm10DistrictChart.destroy();
                    pm10DistrictChart = null;
                }
                return; // Stop execution if data is missing
            }

            // Data found: hide message, show canvas
            canvas.classList.remove('hidden');
            errorElement.classList.add('hidden');

            const labels = chartData.map(d => d.district);
            const pm10Values = chartData.map(d => d.avg_pm10);
            const transitValues = chartData.map(d => d.passenger_count);

            if (pm10DistrictChart) {
                pm10DistrictChart.destroy();
            }

            const ctx = canvas.getContext('2d');
            pm10DistrictChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Avg PM10 (µg/m³)',
                            data: pm10Values,
                            backgroundColor: 'rgba(59, 130, 246, 0.7)', // Blue
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Total Transit Passengers (Proxy)',
                            data: transitValues,
                            backgroundColor: 'rgba(239, 68, 68, 0.8)', // Red
                            type: 'line',
                            yAxisID: 'y1',
                            tension: 0.3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: false, // Title is handled by H2 element
                        },
                        tooltip: {
                             callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        // Format large numbers with commas
                                        label += context.parsed.y.toLocaleString() + (context.dataset.yAxisID === 'y' ? ' µg/m³' : ' trips (proxy)');
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'District',
                                font: { weight: 'bold' }
                            },
                            ticks: {
                                autoSkip: false,
                                maxRotation: 45,
                                minRotation: 45
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Avg PM10 (µg/m³)',
                                font: { weight: 'bold' }
                            },
                            grid: {
                                drawOnChartArea: true,
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Total Transit Passengers (Proxy)',
                                font: { weight: 'bold' }
                            },
                            grid: {
                                drawOnChartArea: false, // Only draw grid lines for the left axis
                            },
                            // Add tick formatter for large numbers
                            ticks: {
                                callback: function(value, index, ticks) {
                                    return value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        }

        /**
         * Renders the Time Series Comparison chart.
         */
        function renderTimeSeriesChart() {
            const chartData = getTimeSeriesData();

            const labels = chartData.map(d => d.date);
            const pm10Values = chartData.map(d => d.pm10_avg);
            const transitValues = chartData.map(d => d.transit_total / 1000); // Scale down transit for readability (in thousands)

            if (timeSeriesChart) {
                timeSeriesChart.destroy();
            }

            const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            timeSeriesChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Avg PM10 (µg/m³)',
                            data: pm10Values,
                            borderColor: 'rgba(59, 130, 246, 1)', // Blue
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            fill: true,
                            yAxisID: 'y',
                            tension: 0.2,
                            pointRadius: 0
                        },
                        {
                            label: 'Total Transit (Thousands)',
                            data: transitValues,
                            borderColor: 'rgba(220, 38, 38, 1)', // Red
                            backgroundColor: 'rgba(220, 38, 38, 0.1)',
                            fill: false,
                            yAxisID: 'y1',
                            tension: 0.2,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        tooltip: {
                             callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.dataset.yAxisID === 'y1') {
                                        // Show actual total (unscaled) in tooltip
                                        label += (context.parsed.y * 1000).toLocaleString() + ' trips';
                                    } else {
                                        label += context.parsed.y.toFixed(2) + ' µg/m³';
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Date (Year-Month)',
                                font: { weight: 'bold' }
                            },
                            // Use 'time' type for dates
                            type: 'time',
                            time: {
                                unit: 'month',
                                tooltipFormat: 'yyyy-MM-dd',
                                displayFormats: {
                                    month: 'yyyy-MM'
                                }
                            },
                            ticks: {
                                autoSkip: true,
                                maxTicksLimit: 15
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Avg PM10 (µg/m³)',
                                font: { weight: 'bold' }
                            },
                            grid: {
                                drawOnChartArea: true,
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Total Transit (Thousands of trips)',
                                font: { weight: 'bold' }
                            },
                            grid: {
                                drawOnChartArea: false,
                            },
                            // Add tick formatter to show 'K' (thousands)
                             ticks: {
                                callback: function(value, index, ticks) {
                                    return value.toLocaleString() + 'K';
                                }
                            }
                        }
                    }
                }
            });
        }

        /**
         * Renders the Average Public Transit Usage by PM10 Status chart.
         */
        function renderPM10StatusChart() {
            const averages = getPM10StatusTransitData();

            const labels = Object.keys(averages);
            const dataValues = Object.values(averages);

            // Define colors based on PM10 status (Good to Very Bad)
            const colors = labels.map(label => {
                switch (label) {
                    case 'Good': return 'rgba(34, 197, 94, 0.7)'; // Green
                    case 'Normal': return 'rgba(251, 191, 36, 0.7)'; // Yellow
                    case 'Bad': return 'rgba(234, 88, 12, 0.7)'; // Orange
                    case 'Very Bad': return 'rgba(220, 38, 38, 0.7)'; // Red
                    default: return 'rgba(107, 114, 128, 0.7)';
                }
            });

            if (pm10StatusChart) {
                pm10StatusChart.destroy();
            }

            const ctx = document.getElementById('pm10StatusChart').getContext('2d');
            pm10StatusChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Avg Daily Transit Passengers',
                        data: dataValues,
                        backgroundColor: colors,
                        borderColor: colors.map(c => c.replace('0.7', '1')),
                        borderWidth: 1,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += Math.round(context.parsed.y).toLocaleString() + ' trips';
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'PM10 Status',
                                font: { weight: 'bold' }
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Avg Daily Transit Passengers (Trips)',
                                font: { weight: 'bold' }
                            },
                            beginAtZero: true,
                            ticks: {
                                callback: function(value, index, ticks) {
                                    return value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        }


        // --- Initialization ---

        async function init() {
            try {
                // Load all data files asynchronously
                const [pol, transit, ppl2012, ppl2014] = await Promise.all([
                    fetchAndParseCsv('combined_pol.csv'),
                    fetchAndParseCsv('trans.csv'),
                    fetchAndParseCsv('ppl_2012.csv'),
                    fetchAndParseCsv('ppl_2014.csv')
                ]);

                dataPM10 = pol;
                dataTransit = transit;
                dataPPL_2012 = ppl2012;
                dataPPL_2014 = ppl2014;

                // Set up event listener for the year selector
                const yearSelector = document.getElementById('year-selector');
                yearSelector.addEventListener('change', (e) => {
                    const selectedYear = parseInt(e.target.value);
                    updatePM10ByDistrictChart(selectedYear);
                });

                // Initial Chart rendering
                // Use the default selected year (2012)
                updatePM10ByDistrictChart(parseInt(yearSelector.value)); 
                renderTimeSeriesChart();
                renderPM10StatusChart();
                
            } catch (error) {
                console.error("Failed to initialize the application:", error);
                // Display a general error message if data loading fails
                const errorMessage = `<p class="text-red-600 font-semibold text-center text-lg mt-10">Error loading application data. Please ensure all CSV files are correctly loaded. Detail: ${error.message}</p>`;
                document.querySelector('main').innerHTML = errorMessage;
            }
        }

        // Start initialization after the window loads
        window.onload = init;
    </script>
</body>
</html>
