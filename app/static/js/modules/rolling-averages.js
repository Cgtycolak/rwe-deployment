// CAO charts tab: rolling production averages, demand and solar charts.
// Moved from an inline script in index.html.
import { getEndpoints } from '../config/endpoints.js';

// Add this debounce function at the top of your script
// Downloaded PNGs cannot use the page's web font, so they need a sans-serif fallback
const CHART_FONT = "'RWE Sans Web', Arial, Helvetica, sans-serif";

// Legends sit in one row between the title and the plot. Inside the plot they covered the
// current-year line once it reached the right-hand side late in the year.
const TOP_LEGEND = {
    orientation: 'h',
    x: 0,
    xanchor: 'left',
    y: 1.02,
    yanchor: 'bottom',
    bgcolor: 'rgba(0,0,0,0)',
    font: { family: CHART_FONT, size: 12, color: '#333333' },
    traceorder: 'reversed'
};

// "2026-10-22T13:00" (Istanbul) -> "22 Oct 13:00"
function formatHour(iso) {
    const [day, time] = iso.split('T');
    const [y, m, d] = day.split('-').map(Number);
    const month = new Date(y, m - 1, d).toLocaleDateString('en-GB', { month: 'short' });
    return `${d} ${month} ${time.slice(0, 5)}`;
}

function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Add a flag to track if charts are already loaded
let chartsLoaded = false;
// Add a flag to track if we're currently fetching last update info
let fetchingLastUpdate = false;

// Debounced version of fetchLastUpdateInfo to prevent multiple calls
const debouncedFetchLastUpdateInfo = debounce(function() {
    // Check if already fetching
    if (fetchingLastUpdate) {
        console.log("Already fetching last update info, skipping");
        return;
    }
    
    console.log("Fetching last update info");
    fetchingLastUpdate = true;
    
    fetch(getEndpoints().rollingLastUpdate)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // The scheduler keeps these current; showing each dataset's latest hour
            // makes a stalled sync visible without a manual fetch button
            const parts = [['Generation', data.production], ['demand', data.demand], ['solar', data.solar]]
                .filter(([, hour]) => hour)
                .map(([label, hour]) => `${label} ${formatHour(hour)}`);
            document.getElementById('last-update-info').textContent =
                parts.length ? `Data up to: ${parts.join(', ')}` : '';
            fetchingLastUpdate = false;
        })
        .catch(error => {
            console.error('Error fetching last update info:', error);
            fetchingLastUpdate = false;
        });
}, 500); // Increase debounce time to 500ms

// Track if controls are already set up
let controlsSetup = false;

function setupRollingAveragesControls() {
    // Skip if already set up
    if (controlsSetup) {
        console.log("Controls already set up, skipping");
        return;
    }
    
    // Load charts button
    const loadChartsBtn = document.getElementById('load-rolling-charts');
    if (loadChartsBtn) {
        // Clear any existing listeners by cloning and replacing
        const newLoadBtn = loadChartsBtn.cloneNode(true);
        loadChartsBtn.parentNode.replaceChild(newLoadBtn, loadChartsBtn);
        
        // Add new event listener
        newLoadBtn.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent event bubbling
            // renderCharts appends, so clear the old charts before drawing again
            const container = document.getElementById('charts-container');
            container.querySelectorAll('.js-plotly-plot').forEach((chart) => Plotly.purge(chart));
            container.innerHTML = '';
            chartsLoaded = false;
            loadRollingCharts();
        });
    }
    
    // Toggle modebar for all charts
    const toggleBtn = document.getElementById('toggle-modebar-all');
    if (toggleBtn) {
        // Clear any existing listeners by cloning and replacing
        const newToggleBtn = toggleBtn.cloneNode(true);
        toggleBtn.parentNode.replaceChild(newToggleBtn, toggleBtn);
        
        // Add new event listener
        newToggleBtn.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent event bubbling
            const container = document.getElementById('charts-container');
            if (container.classList.contains('hide-modebar')) {
                container.classList.remove('hide-modebar');
                this.textContent = 'Hide All Chart Controls';
            } else {
                container.classList.add('hide-modebar');
                this.textContent = 'Show All Chart Controls';
            }
        });
    }
    
    // Mark controls as set up
    controlsSetup = true;
}


// Define the handler function separately so we can remove it if needed
function sectionActivatedHandler(e) {
    if (e.detail.section !== 'rolling-averages') return;

    controlsSetup = false;
    debouncedFetchLastUpdateInfo();
    setupRollingAveragesControls();

    // Load on the first visit; later visits only resize the charts drawn while hidden
    if (!chartsLoaded) {
        loadRollingCharts();
    } else {
        document.querySelectorAll('#charts-container .js-plotly-plot').forEach((chart) => Plotly.Plots.resize(chart));
    }
}


function showStatusMessage(message, type) {
    const statusDiv = document.getElementById('status-message');
    statusDiv.className = `alert alert-${type}`;
    statusDiv.textContent = message;
    statusDiv.style.display = 'block';
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

function toggleButtonLoading(buttonId, isLoading) {
    const button = document.getElementById(buttonId);
    if (!button) return;
    
    const spinner = button.querySelector('.spinner-border');
    const content = button.querySelector('.button-content');
    
    if (isLoading) {
        button.disabled = true;
        if (spinner) spinner.classList.remove('d-none');
        if (content) content.style.opacity = '0.5';
    } else {
        button.disabled = false;
        if (spinner) spinner.classList.add('d-none');
        if (content) content.style.opacity = '1';
    }
}

function renderCharts() {
    const chartsContainer = document.getElementById('charts-container');
    
    // Add 7-Day Rolling Averages title first
    const rollingTitle = document.createElement('div');
    rollingTitle.className = 'row mt-4 mb-3';
    rollingTitle.innerHTML = `
        <div class="col-12">
            <h3 class="section-title">
                7-Day Rolling Averages
            </h3>
        </div>
    `;
    chartsContainer.appendChild(rollingTitle);

    const rollingData = window.rollingData;
    const currentYear = new Date().getFullYear();
    
    // Filter for specific fuel types and define their display order
    const fuelTypes = [
        'naturalgas',    // CCGT
        'lignite',       // Lignite
        'wind',          // Wind
        'solar_combined', // Combined Solar (existing + unlicensed)
        'importcoal',    // HardCoal
        'importexport',  // ImportExport
        'river',         // Run of River
        'dammedhydro',   // Dam
        'renewablesratio_monthly', // Renewables/Total Ratio (Monthly)
        'consumption',    // Demand
    ];
    
    // Map column names to display names
    const typeMapping = {
        'naturalgas': 'CCGT',
        'importcoal': 'HardCoal',
        'lignite': 'Lignite',
        'wind': 'Wind',
        'solar_combined': 'Solar (Combined)',  // Update this
        'importexport': 'ImportExport',
        'river': 'Run-of-River',
        'dammedhydro': 'Dam',
        'renewablesratio_monthly': 'Renewables/Total Generation Ratio',
        'consumption': 'Electricity Demand',
    };
    
    // Process each fuel type in the specified order
    let rowDiv; // Declare rowDiv outside the loop
    fuelTypes.forEach((type, index) => {
        if (!rollingData[type]) {
            console.warn(`No data found for ${type}`);
            return; // Skip if no data
        }
        
        // Create column for chart
        if (index % 2 === 0) {
            // Start a new row for every 2 charts
            rowDiv = document.createElement('div');
            rowDiv.className = 'row mb-4';
            chartsContainer.appendChild(rowDiv);
        }
        
        // Create column
        const colDiv = document.createElement('div');
        colDiv.className = 'col-md-6';
        rowDiv.appendChild(colDiv);
        
        // Create chart container
        const chartDiv = document.createElement('div');
        chartDiv.className = 'chart-container';
        chartDiv.id = `chart-${type}`;
        colDiv.appendChild(chartDiv);
        
        // Get data for this fuel type
        const data = rollingData[type];
        const traces = [];
        
        // Check for metadata FIRST, before using it
        let dateRange;
        
        // Special handling for solar_combined and renewables charts that use combined solar data
        if (type === 'solar_combined' || type === 'renewablesratio_monthly') {
            const solarMetadata = rollingData._solar_combined_metadata || {};
            dateRange = solarMetadata.date_range || '2020-2025';
        } else {
            // Use general metadata for all other charts
            const metadata = rollingData._metadata || { date_range: '2016-2025' };
            dateRange = metadata.date_range;
        }
        
        // Add historical range area
        if (data.historical_range) {
            const rangeData = data.historical_range;
            
            // Use different x values for monthly data
            let x;
            if (type === 'renewablesratio_monthly') {
                x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; // Month numbers
            } else {
                x = Array.from({length: rangeData.length}, (_, i) => i);
            }
            
            // Calculate min and max values for the legend
            const maxValue = Math.max(...rangeData.map(d => d ? d.max : 0).filter(v => v !== null));
            const minValue = Math.min(...rangeData.map(d => d ? d.min : 0).filter(v => v !== null));
            
            // Format the values based on chart type
            let rangeLabel;
            if (type === 'renewablesratio_monthly') {
                // Format as percentage for renewables ratio
                const minPercent = (minValue * 100).toFixed(0);
                const maxPercent = (maxValue * 100).toFixed(0);
                rangeLabel = `${minPercent}%-${maxPercent}%`;
            } else {
                // Format with thousands separator for other types
                const formatter = new Intl.NumberFormat('en-US');
                rangeLabel = `${formatter.format(Math.round(minValue))}-${formatter.format(Math.round(maxValue))} MWh`;
            }
            
            // Create the range area with dynamic date range
            traces.push({
                name: `${dateRange}`,
                x: x.concat(x.slice().reverse()),
                y: rangeData.map(d => d ? d.max : null).concat(rangeData.map(d => d ? d.min : null).reverse()),
                fill: 'toself',
                type: 'scatter',
                mode: 'none',
                fillcolor: 'rgba(135, 206, 250, 0.4)',
                line: {color: 'transparent', width: 0},
                showlegend: true,
                hoverinfo: 'skip',  // Skip hover information for the range area
                hoverlabel: {namelength: -1}  // Show full name in hover label
            });
        }
        
        // Add historical average
        if (data.historical_avg) {
            // Use different x values for monthly data
            let x;
            if (type === 'renewablesratio_monthly') {
                x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; // Month numbers
            } else {
                x = Array.from({length: data.historical_avg.length}, (_, i) => i);
            }
            
            traces.push({
                name: `${dateRange} avg.`,
                x: x,
                y: data.historical_avg,
                type: 'scatter',
                mode: 'lines',
                line: {
                    color: 'rgba(0, 0, 255, 0.8)',
                    width: 1.5,
                    dash: '3,3'
                }
            });
        }
        
        // Add 2025 (previous year - shown as solid black line)
        if (data[currentYear - 1]) {
            // Use different x values for monthly data
            let x;
            if (type === 'renewablesratio_monthly') {
                x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; // Month numbers
            } else {
                x = Array.from({length: data[currentYear - 1].length}, (_, i) => i);
            }
            
            traces.push({
                name: (currentYear - 1).toString(),
                x: x,
                y: data[currentYear - 1],
                type: 'scatter',
                mode: 'lines',
                line: {
                    color: 'black',
                    width: 2.5
                }
            });
        }
        
        // Add 2026 (current year - shown as solid red line)
        if (data[currentYear]) {
            // Use different x values for monthly data
            let x;
            if (type === 'renewablesratio_monthly') {
                x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; // Month numbers
            } else {
                x = Array.from({length: data[currentYear].length}, (_, i) => i);
            }
            
            traces.push({
                name: currentYear.toString(),
                x: x,
                y: data[currentYear],
                type: 'scatter',
                mode: 'lines',
                line: {
                    color: 'red',
                    width: 2.5
                }
            });
        }
        
        // Get display name for the fuel type
        let displayType = typeMapping[type] || type;
        
        // Special handling for renewables ratio
        let yaxisFormat = ',d';
        let yaxisTitle = 'MW';
        let chartTitle = `TR 7-Day Rolling ${displayType} Generation, MW`;
        let xaxisTicktext = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        let xaxisTickvals = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

        if (type === 'renewablesratio_monthly') {
            yaxisFormat = '.0%';  // Format as percentage
            yaxisTitle = '';  // Percentage label for renewables ratio
            chartTitle = `${displayType}`;  // No need for "Generation - MWh" suffix
            xaxisTickvals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; // Month numbers
        }
        
        const layout = {
            title: {
                text: chartTitle,
                font: {
                    family: CHART_FONT,
                    size: 22,
                    color: '#333333'
                },
                xref: 'paper', x: 0,
                y: 0.95,
                xanchor: 'left',
                yanchor: 'top'
            },
            xaxis: {
                ticktext: xaxisTicktext,
                tickvals: xaxisTickvals,
                showgrid: true,
                gridcolor: 'rgba(0,0,0,0.2)',
                tickfont: {
                    family: CHART_FONT,
                    size: 14,
                    color: '#333333'
                },
                linecolor: 'black',
                linewidth: 1,
                mirror: true,
                zeroline: true,
                zerolinecolor: 'rgba(0,0,0,0.2)',
                zerolinewidth: 1
            },
            yaxis: {
                showgrid: true,
                gridcolor: 'rgba(0,0,0,0.2)',
                tickfont: {
                    family: CHART_FONT,
                    size: 14,
                    color: '#333333'
                },
                exponentformat: 'none',
                separatethousands: true,
                rangemode: 'normal',
                autorange: true,
                tickformat: yaxisFormat,
                title: yaxisTitle,
                linecolor: 'black',
                linewidth: 1,
                mirror: true,
                zeroline: true,
                zerolinecolor: 'rgba(0,0,0,0.2)',
                zerolinewidth: 1
            },
            showlegend: true,
            legend: TOP_LEGEND,
            margin: {
                l: 70,
                r: 20,
                t: 96,
                b: 50
            },
            autosize: false,
            height: 480,
            hovermode: 'x unified',
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            font: {
                family: CHART_FONT
            },
            shapes: [{
                type: 'rect',
                xref: 'paper',
                yref: 'paper',
                x0: 0,
                y0: 0,
                x1: 1,
                y1: 1,
                line: {
                    color: 'black',
                    width: 1
                },
                layer: 'below'
            }]
        };
        
        // Add this to the layout object
        layout.hovermode = 'closest';
        layout.hoverlabel = {
            namelength: -1,  // Show full trace name
            font: {
                family: CHART_FONT,
                size: 12
            }
        };

        // Modify the range trace to use custom hover template
        traces[0].hovertemplate = '%{y:,.0f} MWh<extra></extra>';
        
        // Modify all traces to use custom hover templates with proper date formatting
        traces.forEach((trace, i) => {
            if (i === 0) {
                // For the range area, we already set hoverinfo: 'skip'
                return;
            }
            
            // For time series data, create a custom hover template with formatted dates
            if (type === 'renewablesratio_monthly') {
                // For monthly data, show month names
                const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                               'July', 'August', 'September', 'October', 'November', 'December'];
                trace.hovertemplate = 
                    '<b>%{data.name}</b><br>' +
                    '%{x|%B}: %{y:,.0f} MWh<extra></extra>';
            } else {
                // For daily data, format as proper dates
                trace.hovertemplate = 
                    '<b>%{data.name}</b><br>' +
                    '%{text}: %{y:,.0f} MWh<extra></extra>';
                
                // Add formatted dates as text array
                const dateTexts = [];
                for (let i = 0; i < trace.x.length; i++) {
                    const dayOfYear = trace.x[i];
                    const date = new Date(currentYear, 0, dayOfYear + 1); // +1 because day of year is 0-indexed
                    dateTexts.push(date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}));
                }
                trace.text = dateTexts;
            }
        });
        
        Plotly.newPlot(chartDiv, traces, layout, {
            displayModeBar: true,
            responsive: true,
            modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
            toImageButtonOptions: {
                format: 'png',
                filename: `TR_7Day_Rolling_${displayType}`,
                height: 600,
                width: 800,
                scale: 2,
                bgcolor: 'white',
                font: {
                    family: CHART_FONT
                }
            }
        });
        
        // IMPORTANT: Remove the individual resize handlers from each chart
        // Delete these lines from your existing code:
        // window.addEventListener('resize', function() {
        //     Plotly.Plots.resize(chartDiv);
        // });
    });
}



function createDemandChartsRow() {
    const chartsContainer = document.getElementById('charts-container');
    if (!chartsContainer) {
        console.error('Charts container not found');
        return;
    }
    
    // Check if Demand title already exists
    const existingDemandTitle = Array.from(document.querySelectorAll('.section-title'))
        .find(el => el.textContent.trim() === 'Average Demand');
    
    if (!existingDemandTitle) {
        const sectionDivider = document.createElement('div');
        sectionDivider.className = 'row mt-4 mb-3';
        sectionDivider.innerHTML = `
            <div class="col-12">
                <h3 class="section-title">
                    Average Demand
                </h3>
            </div>
        `;
        chartsContainer.appendChild(sectionDivider);
    }
    
    // Create a dedicated row for demand charts
    const demandChartsRow = document.createElement('div');
    demandChartsRow.className = 'row mb-4';
    demandChartsRow.id = 'demand-charts-row';
    chartsContainer.appendChild(demandChartsRow);
}

function renderDemandChart() {
    // Create demand chart container if it doesn't exist
    let chartDiv = document.getElementById('demand-chart');
    if (!chartDiv) {
        const demandChartsRow = document.getElementById('demand-charts-row');
        if (!demandChartsRow) {
            console.error('Demand charts row not found');
            return;
        }
        
        const chartContainer = document.createElement('div');
        chartContainer.className = 'col-md-6';
        chartContainer.innerHTML = `
            <div class="chart-container" id="demand-chart"></div>
        `;
        
        demandChartsRow.appendChild(chartContainer);
        chartDiv = document.getElementById('demand-chart');
    }

    fetch(getEndpoints().demandData)
        .then(response => response.json())
        .then(data => {
            const currentYear = new Date().getFullYear();
            const previousYear = currentYear - 1;
            const traces = [];
            
            // Render MTD/YTD metrics panel
            try {
                const demandChartsRow = document.getElementById('demand-charts-row');
                if (demandChartsRow && data.metrics) {
                    let metricsCol = document.getElementById('demand-metrics-col');
                    if (!metricsCol) {
                        metricsCol = document.createElement('div');
                        metricsCol.className = 'col-12 mb-2';
                        metricsCol.id = 'demand-metrics-col';
                        // Insert metrics row before charts
                        demandChartsRow.parentNode.insertBefore(metricsCol, demandChartsRow);
                    }
                    const fmt = (n) => (n === null || n === undefined) ? '-' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
                    const fmtPct = (p) => (p === null || p === undefined) ? '-' : `${(p>0?'+':'')}${Number(p).toFixed(2)}%`;
                    const m = data.metrics;
                    const monthName = (m && m.mtd && m.mtd.month_name) ? m.mtd.month_name : '';
                    const mtd = m && m.mtd ? m.mtd : null;
                    const ytd = m && m.ytd ? m.ytd : null;
                    const block = (title, v) => `
                        <section class="demand-period">
                            <h4>${title}</h4>
                            <dl>
                                <div><dt>${previousYear}</dt><dd>${fmt(v ? v.previous_year : null)} MWh</dd></div>
                                <div><dt>${currentYear}</dt><dd>${fmt(v ? v.current_year : null)} MWh</dd></div>
                                <div><dt>Change</dt><dd class="${v && v.pct >= 0 ? 'up' : 'down'}">${fmt(v ? v.diff : null)} MWh (${fmtPct(v ? v.pct : null)})</dd></div>
                            </dl>
                        </section>`;
                    metricsCol.innerHTML = `<div class="demand-summary">${block(`Month to date (${monthName})`, mtd)}${block('Year to date', ytd)}</div>`;
                }
            } catch (e) {
                console.warn('Failed to render demand metrics panel', e);
            }

            // Get current date to limit the data range
            const now = new Date();
            const currentWeek = Math.ceil((now - new Date(now.getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24 * 7));
            
            // Create date array for x-axis with weekly points
            const dateArray = [];
            const startDate = new Date(currentYear, 0, 1);
            for (let i = 0; i < currentWeek; i++) {
                const date = new Date(startDate);
                date.setDate(date.getDate() + (i * 7));
                dateArray.push(date.toISOString().split('T')[0]);
            }

            // Create tick values and labels for first day of each month
            const tickVals = [];
            const tickText = [];
            let currentMonth = -1;
            dateArray.forEach(date => {
                const d = new Date(date);
                if (d.getMonth() !== currentMonth) {
                    currentMonth = d.getMonth();
                    const firstOfMonth = new Date(d.getFullYear(), d.getMonth(), 1);
                    tickVals.push(firstOfMonth.toISOString().split('T')[0]);
                    tickText.push(firstOfMonth.toLocaleString('en-US', { month: 'short' }));
                }
            });
            
            // Add previous year data (2024) - solid blue line
            if (data.consumption && data.consumption[previousYear]) {
                const y = data.consumption[previousYear].slice(0, currentWeek);
                
                // Create an array of formatted dates with week information
                const hoverTexts = dateArray.map(dateStr => {
                    const date = new Date(dateStr);
                    const month = date.toLocaleString('en-US', { month: 'short' });
                    const weekOfMonth = Math.ceil(date.getDate() / 7);
                    return `${month} Week ${weekOfMonth}`;
                });
                
                traces.push({
                    name: previousYear.toString(),
                    x: dateArray,
                    y: y,
                    type: 'scatter',
                    mode: 'lines',
                    line: {
                        color: 'blue',
                        width: 2
                    },
                    text: hoverTexts,
                    hovertemplate: '<b>%{data.name}</b><br>%{text}: %{y:,.0f} MWh<extra></extra>'
                });
            }
            
            // Add current year data (2025) - solid red line
            if (data.consumption && data.consumption[currentYear]) {
                const y = data.consumption[currentYear].slice(0, currentWeek);
                
                // Create an array of formatted dates with week information
                const hoverTexts = dateArray.map(dateStr => {
                    const date = new Date(dateStr);
                    const month = date.toLocaleString('en-US', { month: 'short' });
                    const weekOfMonth = Math.ceil(date.getDate() / 7);
                    return `${month} Week ${weekOfMonth}`;
                });
                
                traces.push({
                    name: currentYear.toString(),
                    x: dateArray,
                    y: y,
                    type: 'scatter',
                    mode: 'lines',
                    line: {
                        color: 'red',
                        width: 2
                    },
                    text: hoverTexts,
                    hovertemplate: '<b>%{data.name}</b><br>%{text}: %{y:,.0f} MWh<extra></extra>'
                });
            }
            
            const layout = {
                title: {
                    text: 'Avg. Demand',
                    font: {
                        family: CHART_FONT,
                        size: 22,
                        color: '#333333'
                    },
                    xref: 'paper', x: 0,
                    y: 0.95,
                    xanchor: 'left',
                    yanchor: 'top'
                },
                xaxis: {
                    showgrid: true,
                    gridcolor: 'rgba(0,0,0,0.2)',
                    zeroline: true,
                    zerolinecolor: 'rgba(0,0,0,0.2)',
                    zerolinewidth: 1,
                    linecolor: 'black',
                    linewidth: 1,
                    mirror: true,
                    type: 'date',
                    tickformat: '%b',
                    tickangle: 0,
                    tickmode: 'array',
                    ticktext: tickText,
                    tickvals: tickVals,
                    nticks: tickVals.length,
                    tickfont: {
                        family: CHART_FONT,
                        size: 14,
                        color: '#333333'
                    }
                },
                yaxis: {
                    title: 'MWh',
                    showgrid: true,
                    gridcolor: 'rgba(0,0,0,0.2)',
                    zeroline: true,
                    zerolinecolor: 'rgba(0,0,0,0.2)',
                    zerolinewidth: 1,
                    linecolor: 'black',
                    linewidth: 1,
                    mirror: true,
                    tickfont: {
                        family: CHART_FONT,
                        size: 14,
                        color: '#333333'
                    },
                    exponentformat: 'none',
                    separatethousands: true,
                    rangemode: 'normal',
                    autorange: true,
                    tickformat: ',d'
                },
                showlegend: true,
                legend: TOP_LEGEND,
                plot_bgcolor: 'white',
                paper_bgcolor: 'white',
                hovermode: 'x unified',
                font: {
                    family: CHART_FONT
                },
                shapes: [{
                    type: 'rect',
                    xref: 'paper',
                    yref: 'paper',
                    x0: 0,
                    y0: 0,
                    x1: 1,
                    y1: 1,
                    line: {
                        color: 'black',
                        width: 1
                    },
                    layer: 'below'
                }],
                margin: {
                    l: 70,
                    r: 20,
                    t: 96,
                    b: 50
                },
                autosize: false,
                height: 480
            };
            
            Plotly.newPlot(chartDiv, traces, layout, {
                displayModeBar: true,
                responsive: true,
                modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
                toImageButtonOptions: {
                    format: 'png',
                    filename: 'TR_Average_Demand',
                    height: 600,
                    width: 800,
                    scale: 2,
                    bgcolor: 'white',
                    font: {
                        family: CHART_FONT
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error fetching demand data:', error);
            chartDiv.innerHTML = `<div class="alert alert-danger">Error loading demand data: ${error.message}</div>`;
        });
}

function renderMonthlyDemandChart() {
    // Create monthly demand chart container if it doesn't exist
    let chartDiv = document.getElementById('monthly-demand-chart');
    if (!chartDiv) {
        const demandChartsRow = document.getElementById('demand-charts-row');
        if (!demandChartsRow) {
            console.error('Demand charts row not found');
            return;
        }
        
        const chartContainer = document.createElement('div');
        chartContainer.className = 'col-md-6';
        chartContainer.innerHTML = `
            <div class="chart-container" id="monthly-demand-chart"></div>
        `;
        
        demandChartsRow.appendChild(chartContainer);
        chartDiv = document.getElementById('monthly-demand-chart');
    }

    fetch(getEndpoints().monthlyDemandData)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            const currentYear = new Date().getFullYear();
            const previousYear = currentYear - 1;
            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const monthNumbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
            
            const traces = [];
            
            // Get current month to limit display
            const currentMonth = new Date().getMonth() + 1; // 1-based month
            const displayMonths = monthNumbers.slice(0, currentMonth);
            const displayMonthNames = monthNames.slice(0, currentMonth);
            
            // Get data for both years
            const currentYearData = data.monthly_consumption[currentYear] ? data.monthly_consumption[currentYear].slice(0, currentMonth) : [];
            const previousYearData = data.monthly_consumption[previousYear] ? data.monthly_consumption[previousYear].slice(0, currentMonth) : [];
            
            // Function to find intersection point between two line segments
            function findIntersection(x1, y1, x2, y2, x3, y3, x4, y4) {
                const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
                if (Math.abs(denom) < 1e-10) return null; // Lines are parallel
                
                const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
                if (t < 0 || t > 1) return null; // Intersection outside segment
                
                const x = x1 + t * (x2 - x1);
                const y = y1 + t * (y2 - y1);
                return { x, y };
            }
            
            // Function to interpolate between two points
            function interpolate(x1, y1, x2, y2, x) {
                if (Math.abs(x2 - x1) < 1e-10) return y1;
                const t = (x - x1) / (x2 - x1);
                return y1 + t * (y2 - y1);
            }
            
            // Create high-resolution fill areas with precise crossover detection
            let hasGreenLegend = false;
            let hasRedLegend = false;
            
            // For each monthly segment, create sub-segments with intersection detection
            for (let i = 0; i < currentYearData.length - 1; i++) {
                const x1 = displayMonths[i];
                const x2 = displayMonths[i + 1];
                const y1_current = currentYearData[i];     // 2025 start
                const y2_current = currentYearData[i + 1]; // 2025 end
                const y1_previous = previousYearData[i];    // 2024 start
                const y2_previous = previousYearData[i + 1]; // 2024 end
                
                // Find intersection point within this segment
                const intersection = findIntersection(x1, y1_current, x2, y2_current, x1, y1_previous, x2, y2_previous);
                
                if (intersection) {
                    // Lines cross within this segment - create two sub-segments
                    const intersectionX = intersection.x;
                    const intersectionY = intersection.y;
                    
                    // First sub-segment: from start to intersection
                    const isGreen1 = y1_current > y1_previous;
                    const fillColor1 = isGreen1 ? 
                        'rgba(34, 139, 34, 0.4)' : // Green
                        'rgba(255, 0, 0, 0.4)';    // Red
                    const traceName1 = isGreen1 ? 'Higher than 2025' : 'Lower than 2025';
                    
                    const showInLegend1 = (isGreen1 && !hasGreenLegend) || (!isGreen1 && !hasRedLegend);
                    if (isGreen1) hasGreenLegend = true;
                    if (!isGreen1) hasRedLegend = true;
                    
                    traces.push({
                        name: traceName1,
                        x: [x1, intersectionX, intersectionX, x1],
                        y: [y1_current, intersectionY, intersectionY, y1_previous],
                        fill: 'toself',
                        type: 'scatter',
                        mode: 'none',
                        fillcolor: fillColor1,
                        line: {color: 'transparent', width: 0},
                        showlegend: showInLegend1,
                        legendgroup: traceName1,
                        hoverinfo: 'skip'
                    });
                    
                    // Second sub-segment: from intersection to end
                    const isGreen2 = y2_current > y2_previous;
                    const fillColor2 = isGreen2 ? 
                        'rgba(34, 139, 34, 0.4)' : // Green
                        'rgba(255, 0, 0, 0.4)';    // Red
                    const traceName2 = isGreen2 ? 'Higher than 2025' : 'Lower than 2025';
                    
                    const showInLegend2 = (isGreen2 && !hasGreenLegend) || (!isGreen2 && !hasRedLegend);
                    if (isGreen2) hasGreenLegend = true;
                    if (!isGreen2) hasRedLegend = true;
                    
                    traces.push({
                        name: traceName2,
                        x: [intersectionX, x2, x2, intersectionX],
                        y: [intersectionY, y2_current, y2_previous, intersectionY],
                        fill: 'toself',
                        type: 'scatter',
                        mode: 'none',
                        fillcolor: fillColor2,
                        line: {color: 'transparent', width: 0},
                        showlegend: showInLegend2,
                        legendgroup: traceName2,
                        hoverinfo: 'skip'
                    });
                } else {
                    // Lines don't cross within this segment - single color for entire segment
                    const isGreen = y1_current > y1_previous; // Use start point to determine color
                    const fillColor = isGreen ? 
                        'rgba(34, 139, 34, 0.4)' : // Green
                        'rgba(255, 0, 0, 0.4)';    // Red
                    const traceName = isGreen ? 'Higher than 2025' : 'Lower than 2025';
                    
                    const showInLegend = (isGreen && !hasGreenLegend) || (!isGreen && !hasRedLegend);
                    if (isGreen) hasGreenLegend = true;
                    if (!isGreen) hasRedLegend = true;
                    
                    traces.push({
                        name: traceName,
                        x: [x1, x2, x2, x1],
                        y: [y1_current, y2_current, y2_previous, y1_previous],
                        fill: 'toself',
                        type: 'scatter',
                        mode: 'none',
                        fillcolor: fillColor,
                        line: {color: 'transparent', width: 0},
                        showlegend: showInLegend,
                        legendgroup: traceName,
                        hoverinfo: 'skip'
                    });
                }
            }
            
            // Add previous year line (2024) - blue
            if (previousYearData.length > 0) {
                traces.push({
                    name: previousYear.toString(),
                    x: displayMonths,
                    y: previousYearData,
                    type: 'scatter',
                    mode: 'lines',
                    line: {
                        color: 'blue',
                        width: 2
                    },
                    hovertemplate: '<b>%{data.name}</b><br>%{text}: %{y:,.0f} MWh<extra></extra>',
                    text: displayMonthNames
                });
            }
            
            // Add current year line (2025) - red
            if (currentYearData.length > 0) {
                traces.push({
                    name: currentYear.toString(),
                    x: displayMonths,
                    y: currentYearData,
                    type: 'scatter',
                    mode: 'lines',
                    line: {
                        color: 'red',
                        width: 2
                    },
                    hovertemplate: '<b>%{data.name}</b><br>%{text}: %{y:,.0f} MWh<extra></extra>',
                    text: displayMonthNames
                });
            }
            
            const layout = {
                title: {
                    text: 'Average Electricity Demand, Y-o-Y',
                    font: {
                        family: CHART_FONT,
                        size: 22,
                        color: '#333333'
                    },
                    xref: 'paper', x: 0,
                    y: 0.95,
                    xanchor: 'left',
                    yanchor: 'top'
                },
                xaxis: {
                    ticktext: displayMonthNames,
                    tickvals: displayMonths,
                    showgrid: true,
                    gridcolor: 'rgba(0,0,0,0.2)',
                    tickfont: {
                        family: CHART_FONT,
                        size: 14,
                        color: '#333333'
                    },
                    linecolor: 'black',
                    linewidth: 1,
                    mirror: true,
                    zeroline: true,
                    zerolinecolor: 'rgba(0,0,0,0.2)',
                    zerolinewidth: 1
                },
                yaxis: {
                    title: 'MWh',
                    showgrid: true,
                    gridcolor: 'rgba(0,0,0,0.2)',
                    tickfont: {
                        family: CHART_FONT,
                        size: 14,
                        color: '#333333'
                    },
                    exponentformat: 'none',
                    separatethousands: true,
                    rangemode: 'normal',
                    autorange: true,
                    tickformat: ',d',
                    linecolor: 'black',
                    linewidth: 1,
                    mirror: true,
                    zeroline: true,
                    zerolinecolor: 'rgba(0,0,0,0.2)',
                    zerolinewidth: 1
                },
                showlegend: true,
                legend: TOP_LEGEND,
                margin: {
                    l: 70,
                    r: 20,
                    t: 96,
                    b: 50
                },
                autosize: false,
                height: 480,
                hovermode: 'x unified',
                plot_bgcolor: 'white',
                paper_bgcolor: 'white',
                font: {
                    family: CHART_FONT
                },
                shapes: [{
                    type: 'rect',
                    xref: 'paper',
                    yref: 'paper',
                    x0: 0,
                    y0: 0,
                    x1: 1,
                    y1: 1,
                    line: {
                        color: 'black',
                        width: 1
                    },
                    layer: 'below'
                }]
            };
            
            Plotly.newPlot(chartDiv, traces, layout, {
                displayModeBar: true,
                responsive: true,
                modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
                toImageButtonOptions: {
                    format: 'png',
                    filename: 'TR_Average_Electricity_Demand_YoY',
                    height: 600,
                    width: 800,
                    scale: 2,
                    bgcolor: 'white',
                    font: {
                        family: CHART_FONT
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error fetching monthly demand data:', error);
            chartDiv.innerHTML = `<div class="alert alert-danger">Error loading monthly demand data: ${error.message}</div>`;
        });
}

function renderWeeklySolarChart() {
    const chartsContainer = document.getElementById('charts-container');

    // Section title
    const titleDiv = document.createElement('div');
    titleDiv.className = 'row mt-4 mb-3';
    titleDiv.innerHTML = `
        <div class="col-12">
            <h3 class="section-title">
                Solar Generation – Weekly Hourly View
            </h3>
        </div>`;
    chartsContainer.appendChild(titleDiv);

    const rowDiv = document.createElement('div');
    rowDiv.className = 'row mb-4';
    chartsContainer.appendChild(rowDiv);

    const colDiv = document.createElement('div');
    colDiv.className = 'col-12';
    rowDiv.appendChild(colDiv);

    const chartDiv = document.createElement('div');
    chartDiv.className = 'chart-container';
    chartDiv.id = 'chart-solar-weekly';
    chartDiv.style.width = '100%';
    colDiv.appendChild(chartDiv);

    fetch(getEndpoints().solarWeeklyData)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                chartDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                return;
            }

            const cur  = data.current_week;
            const prev = data.previous_week;
            const ly   = data.last_year;
            const hr   = data.historical_range;

            const xCur  = cur.values.map((_, i) => i);
            const xPrev = prev.values.map((_, i) => i);
            const xLy   = ly.values.map((_, i) => i);
            const xHr   = hr.min.map((_, i) => i);

            const traces = [];

            // Historical range fill (2020-2025)
            traces.push({
                name: hr.years,
                x: xHr.concat(xHr.slice().reverse()),
                y: hr.max.concat(hr.min.slice().reverse()),
                fill: 'toself',
                type: 'scatter', mode: 'none',
                fillcolor: 'rgba(135, 206, 250, 0.4)',
                line: { color: 'transparent', width: 0 },
                showlegend: true,
                hoverinfo: 'skip'
            });

            // Historical average (dashed blue)
            traces.push({
                name: `${hr.years} avg.`,
                x: xHr,
                y: hr.avg,
                type: 'scatter', mode: 'lines',
                line: { color: 'rgba(0,0,255,0.8)', width: 1.5, dash: '3,3' },
                hovertemplate: '<b>Historical avg</b><br>%{y:,.0f} MW<extra></extra>'
            });

            // Last year
            traces.push({
                name: `Last year (${ly.range})`,
                x: xLy, y: ly.values, text: ly.labels,
                type: 'scatter', mode: 'lines',
                line: { color: 'rgba(100,100,100,0.7)', width: 1.5, dash: 'dot' },
                hovertemplate: '<b>Last year</b><br>%{text}<br>%{y:,.0f} MW<extra></extra>'
            });

            // Previous week
            traces.push({
                name: `Previous week (${prev.range})`,
                x: xPrev, y: prev.values, text: prev.labels,
                type: 'scatter', mode: 'lines',
                line: { color: 'black', width: 2 },
                hovertemplate: '<b>Previous week</b><br>%{text}<br>%{y:,.0f} MW<extra></extra>'
            });

            // Current week
            traces.push({
                name: `Current week (${cur.range})`,
                x: xCur, y: cur.values, text: cur.labels,
                type: 'scatter', mode: 'lines',
                line: { color: 'red', width: 2.5 },
                hovertemplate: '<b>Current week</b><br>%{text}<br>%{y:,.0f} MW<extra></extra>'
            });

            // Build tick marks at midnight (hour 0) of each day — every 24 points
            const tickVals = [], tickText = [];
            cur.labels.forEach((lbl, i) => {
                if (lbl.includes('00:00')) { tickVals.push(i); tickText.push(lbl.split(' ').slice(0,3).join(' ')); }
            });

            const layout = {
                title: {
                    text: 'Solar (Combined) Generation – Hourly, Last 7 Days vs Previous Week vs Same Week Last Year',
                    font: { family: CHART_FONT, size: 22, color: '#333333' },
                    xref: 'paper', x: 0,
                    y: 0.95,
                    xanchor: 'left',
                    yanchor: 'top'
                },
                xaxis: {
                    tickmode: 'array', tickvals: tickVals, ticktext: tickText,
                    showgrid: true, gridcolor: 'rgba(0,0,0,0.2)',
                    linecolor: 'black', linewidth: 1, mirror: true,
                    zeroline: true, zerolinecolor: 'rgba(0,0,0,0.2)', zerolinewidth: 1,
                    tickfont: { family: CHART_FONT, size: 14, color: '#333333' }
                },
                yaxis: {
                    title: 'MW', tickformat: ',d',
                    showgrid: true, gridcolor: 'rgba(0,0,0,0.2)',
                    linecolor: 'black', linewidth: 1, mirror: true,
                    zeroline: true, zerolinecolor: 'rgba(0,0,0,0.2)', zerolinewidth: 1,
                    rangemode: 'tozero',
                    exponentformat: 'none', separatethousands: true,
                    tickfont: { family: CHART_FONT, size: 14, color: '#333333' }
                },
                showlegend: true,
                legend: TOP_LEGEND,
                hovermode: 'x unified',
                hoverlabel: { namelength: -1, font: { family: CHART_FONT, size: 12 } },
                plot_bgcolor: 'white', paper_bgcolor: 'white',
                font: { family: CHART_FONT },
                margin: { l: 70, r: 20, t: 96, b: 50 },
                autosize: true,
                height: 600,
                shapes: [{ type: 'rect', xref: 'paper', yref: 'paper',
                           x0: 0, y0: 0, x1: 1, y1: 1,
                           line: { color: 'black', width: 1 }, layer: 'below' }]
            };

            Plotly.newPlot(chartDiv, traces, layout, {
                displayModeBar: true,
                responsive: true,
                modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
                toImageButtonOptions: {
                    format: 'png', filename: 'Solar_Weekly_Hourly',
                    height: 600, width: 1400, scale: 2,
                    bgcolor: 'white', font: { family: CHART_FONT }
                }
            });
        })
        .catch(err => {
            chartDiv.innerHTML = `<div class="alert alert-danger">Error loading weekly solar data: ${err.message}</div>`;
        });
}

function loadRollingCharts() {
    // Prevent multiple loads
    if (chartsLoaded) {
        console.log("Charts already loaded, skipping");
        return;
    }
    
    // Show loading indicator
    const loadingDiv = document.getElementById('loading');
    loadingDiv.style.display = 'block';
    
    // Clear any existing charts
    const chartsContainer = document.getElementById('charts-container');
    chartsContainer.innerHTML = '';
    
    // Toggle button state
    toggleButtonLoading('load-rolling-charts', true);
    
    // Hide any previous status messages
    document.getElementById('status-message').style.display = 'none';
    
    // Get data and render charts
    fetch(getEndpoints().rollingData)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(rollingData => {
            if (rollingData.error) {
                throw new Error(rollingData.error);
            }
            
            // Store data globally for access
            window.rollingData = rollingData;
            
            // Render the charts
            renderCharts();
            
            // Create a dedicated row for the demand charts
            createDemandChartsRow();
            
            // Render both demand charts
            renderDemandChart();
            renderMonthlyDemandChart();

            // Render weekly solar hourly chart
            renderWeeklySolarChart();
            
            // Set the loaded flag
            chartsLoaded = true;
            
            // Hide loading indicator
            loadingDiv.style.display = 'none';
            
            // Reset button state
            toggleButtonLoading('load-rolling-charts', false);
            
            // Add resize handler if not already added
            if (!window.chartResizeHandlerAdded) {
                window.addEventListener('resize', debounce(function() {
                    const charts = document.querySelectorAll('.chart-container');
                    charts.forEach(chart => {
                        if (chart.id && window.Plotly) {
                            Plotly.Plots.resize(chart);
                        }
                    });
                }, 250));
                
                window.chartResizeHandlerAdded = true;
            }
        })
        .catch(error => {
            console.error('Error fetching rolling data:', error);
            showStatusMessage('Error loading charts: ' + error.message, 'danger');
            loadingDiv.style.display = 'none';
            toggleButtonLoading('load-rolling-charts', false);
            chartsLoaded = false;
        });
}

export const rollingAverages = {
    init() {
        document.addEventListener('section:activated', sectionActivatedHandler);
    }
};
