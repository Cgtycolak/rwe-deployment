import { baseLayout, PLOT_CONFIG, SERIES } from '../utils/plot-theme.js';

export const forecastPerformance = {
    helpers: null,
    currentData: null,
    
    setup(helpers) {
        this.helpers = helpers;
    },
    
    init() {
        // Initialize event listeners
        this.setupEventListeners();
        this.setupDateDefaults();
    },
    
    setupEventListeners() {
        const loadButton = document.getElementById('load_forecast_performance');
        const downloadButton = document.getElementById('download_performance_chart');
        const downloadExcelButton = document.getElementById('download_performance_excel');
        const periodSelect = document.getElementById('performance_period');
        
        if (loadButton) {
            loadButton.addEventListener('click', () => {
                this.loadPerformanceData();
            });
        }
        
        if (downloadButton) {
            downloadButton.addEventListener('click', () => {
                this.downloadChart();
            });
        }
        
        if (downloadExcelButton) {
            downloadExcelButton.addEventListener('click', () => {
                this.downloadExcel();
            });
        }
        
        if (periodSelect) {
            periodSelect.addEventListener('change', (e) => {
                this.handlePeriodChange(e.target.value);
                // Preset periods reload at once; custom dates wait for Show performance
                if (e.target.value !== 'custom' && this.currentData) this.loadPerformanceData();
            });
        }
        
        const horizonSelect = document.getElementById('forecast_horizon');
        if (horizonSelect) {
            horizonSelect.addEventListener('change', () => {
                // Reload data when horizon changes
                if (this.currentData) {
                    this.loadPerformanceData();
                }
            });
        }
    },
    
    setupDateDefaults() {
        // Set default dates for custom range
        const today = new Date();
        const thirtyDaysAgo = new Date(today.getTime() - (30 * 24 * 60 * 60 * 1000));
        
        const startDateInput = document.getElementById('performance_start_date');
        const endDateInput = document.getElementById('performance_end_date');
        
        if (startDateInput) {
            startDateInput.value = thirtyDaysAgo.toISOString().split('T')[0];
        }
        if (endDateInput) {
            endDateInput.value = today.toISOString().split('T')[0];
        }
    },
    
    handlePeriodChange(value) {
        const customRangeStart = document.getElementById('custom_date_range');
        const customRangeEnd = document.getElementById('custom_date_range_end');
        
        if (value === 'custom') {
            // Show custom date range inputs
            if (customRangeStart) customRangeStart.style.display = 'block';
            if (customRangeEnd) customRangeEnd.style.display = 'block';
        } else {
            // Hide custom date range inputs
            if (customRangeStart) customRangeStart.style.display = 'none';
            if (customRangeEnd) customRangeEnd.style.display = 'none';
        }
        
        // Update period info display
        this.updatePeriodInfo(value);
    },
    
    updatePeriodInfo(period) {
        const periodInfo = document.getElementById('chart_period_info');
        if (periodInfo) {
            if (period === 'custom') {
                periodInfo.textContent = '(Custom Range)';
            } else {
                periodInfo.textContent = `(Last ${period} Days)`;
            }
        }
    },
    
    async loadPerformanceData() {
        const loadButton = document.getElementById('load_forecast_performance');
        const chartContainer = document.getElementById('forecast_performance_chart');
        const loadingIndicator = document.getElementById('performance_loading');
        const metricsSection = document.getElementById('performance_metrics');
        
        try {
            // Show loading state
            if (loadButton) {
                this.helpers.toggleButtonLoading(loadButton, true);
            }
            if (loadingIndicator) {
                loadingIndicator.style.display = 'block';
            }
            
            // Get parameters
            const params = this.getRequestParams();
            const queryString = new URLSearchParams(params).toString();
            
            // Make API request
            const response = await fetch(`/forecast-performance-data?${queryString}`);
            const result = await response.json();
            
            if (result.code === 200) {
                this.currentData = result.data;
                this.renderChart(result.data);
                this.updateMetrics(result.data.metrics || {});
                
                // Always show metrics
                if (metricsSection) {
                    metricsSection.style.display = 'block';
                }
                
                // Enable download buttons
                const downloadButton = document.getElementById('download_performance_chart');
                if (downloadButton) {
                    downloadButton.disabled = false;
                }
                const downloadExcelButton = document.getElementById('download_performance_excel');
                if (downloadExcelButton) {
                    downloadExcelButton.disabled = false;
                }
                
            } else {
                throw new Error(result.error || 'Failed to load data');
            }
            
        } catch (error) {
            console.error('Error loading forecast performance data:', error);
            if (chartContainer) {
                Plotly.purge(chartContainer);
                chartContainer.innerHTML = '<div class="placeholder-note is-error"><p>The forecasts could not be loaded. Press Show performance to try again.</p></div>';
            }
        } finally {
            // Hide loading state
            if (loadButton) {
                this.helpers.toggleButtonLoading(loadButton, false);
            }
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        }
    },
    
    getRequestParams() {
        const periodSelect = document.getElementById('performance_period');
        const startDateInput = document.getElementById('performance_start_date');
        const endDateInput = document.getElementById('performance_end_date');
        const horizonSelect = document.getElementById('forecast_horizon');
        
        const params = {};
        
        // Add forecast horizon
        if (horizonSelect && horizonSelect.value) {
            params.horizon = horizonSelect.value;
        }
        
        if (periodSelect && periodSelect.value === 'custom') {
            if (startDateInput && startDateInput.value) {
                params.start_date = startDateInput.value;
            }
            if (endDateInput && endDateInput.value) {
                params.end_date = endDateInput.value;
            }
        } else if (periodSelect && periodSelect.value) {
            params.period = periodSelect.value;
        }
        
        return params;
    },
    
    renderChart(data) {
        const chartContainer = document.getElementById('forecast_performance_chart');
        if (!chartContainer || !data.dates) return;

        const x = data.dates;
        const has = (series) => Array.isArray(series) && series.some((v) => v > 0);
        const price = (name) => `<b>${name}</b> %{y:,.0f} TL/MWh<extra></extra>`;
        const traces = [];

        // Meteologica's min and max read as one range, so they are drawn as a band, not two lines
        if (has(data.meteologica_min) && has(data.meteologica_max)) {
            traces.push(
                { name: 'Meteologica min', x, y: data.meteologica_min, type: 'scatter', mode: 'lines',
                  line: { width: 0 }, showlegend: false, hovertemplate: price('Meteologica min') },
                { name: 'Meteologica range', x, y: data.meteologica_max, type: 'scatter', mode: 'lines',
                  fill: 'tonexty', fillcolor: 'rgba(31, 95, 153, 0.12)', line: { width: 0 },
                  hovertemplate: price('Meteologica max') },
            );
        }
        if (has(data.meteologica_avg)) {
            traces.push({ name: 'Meteologica average', x, y: data.meteologica_avg, type: 'scatter', mode: 'lines',
                          line: { color: SERIES.plan, width: 1.6, dash: 'dot' }, hovertemplate: price('Meteologica average') });
        }
        if (has(data.model_forecast)) {
            traces.push({ name: 'Our model', x, y: data.model_forecast, type: 'scatter', mode: 'lines',
                          line: { color: SERIES.actual, width: 1.8 }, hovertemplate: price('Our model') });
        }
        if (has(data.cemre_forecast)) {
            traces.push({ name: 'Cemre', x, y: data.cemre_forecast, type: 'scatter', mode: 'lines',
                          line: { color: '#5E8C3A', width: 1.6, dash: 'dash' }, hovertemplate: price('Cemre') });
        }
        // Realised price last, so it is drawn on top of everything it is judged against
        traces.push({ name: 'Realised price', x, y: data.actual_price, type: 'scatter', mode: 'lines',
                      line: { color: SERIES.capacity, width: 2.4 }, hovertemplate: price('Realised price') });

        const base = baseLayout();
        const layout = baseLayout({
            height: 520,
            margin: { t: 40, r: 16, b: 40, l: 64 },
            yaxis: { ...base.yaxis, title: { text: 'TL/MWh' }, rangemode: 'tozero' },
            legend: { ...base.legend, traceorder: 'reversed' },
        });

        // Clear an earlier error note before drawing into the same element
        if (!chartContainer.classList.contains('js-plotly-plot')) chartContainer.innerHTML = '';
        Plotly.react(chartContainer, traces, layout, PLOT_CONFIG);
    },

    updateMetrics(metrics) {
        const table = document.getElementById('performance_metrics_table');
        if (!table) return;

        const names = ['Model Forecast', 'Cemre Forecast', 'Meteologica Avg', 'Meteologica Min', 'Meteologica Max'];
        const labels = { 'Model Forecast': 'Our model', 'Cemre Forecast': 'Cemre', 'Meteologica Avg': 'Meteologica average',
                         'Meteologica Min': 'Meteologica min', 'Meteologica Max': 'Meteologica max' };
        const rows = names.filter((n) => metrics[n]).map((n) => ({ name: labels[n], ...metrics[n] }));
        if (!rows.length) {
            table.innerHTML = '<p class="text-muted">No forecasts overlap the realised prices in this period.</p>';
            return;
        }

        const num = (v) => (v == null || v === '' || isNaN(Number(v)) ? null : Number(v));
        const best = (key, lowerIsBetter) => {
            const values = rows.map((r) => num(r[key])).filter((v) => v != null);
            if (!values.length) return null;
            return lowerIsBetter ? Math.min(...values) : Math.max(...values);
        };
        const bestWmape = best('wmape', true);
        const bestRmse = best('rmse', true);
        const bestR2 = best('r2', false);
        const fmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 });
        const cell = (value, bestValue, suffix = '') => {
            const v = num(value);
            if (v == null) return '<td class="num">–</td>';
            const isBest = v === bestValue;
            return `<td class="num${isBest ? ' is-best' : ''}">${fmt.format(v)}${suffix}${isBest ? '<span class="visually-hidden"> (best)</span>' : ''}</td>`;
        };

        table.innerHTML = `
            <table class="table table-sm">
                <thead><tr><th>Forecast</th><th class="num">WMAPE</th><th class="num">RMSE, TL/MWh</th><th class="num">R²</th></tr></thead>
                <tbody>${rows.map((r) => `<tr>
                    <td>${r.name}</td>${cell(r.wmape, bestWmape, '%')}${cell(r.rmse, bestRmse)}${cell(r.r2, bestR2)}
                </tr>`).join('')}</tbody>
            </table>`;
    },

    downloadChart() {
        const chartContainer = document.getElementById('forecast_performance_chart');
        if (chartContainer && this.currentData) {
            const filename = `forecast_performance_${new Date().toISOString().split('T')[0]}.png`;
            Plotly.downloadImage(chartContainer, {
                format: 'png',
                width: 1200,
                height: 800,
                filename: filename
            });
        }
    },
    
    downloadExcel() {
        if (!this.currentData) {
            this.helpers.displayMessage('Please load data first before downloading', 'warning');
            return;
        }
        
        try {
            // Get current parameters
            const params = this.getRequestParams();
            const queryString = new URLSearchParams(params).toString();
            
            // Create download URL
            const downloadUrl = `/download-forecast-performance-excel?${queryString}`;
            
            // Show loading message
            this.helpers.displayMessage('Preparing Excel file for download...', 'info');
            
            // Use window.location for download (simpler and more reliable)
            window.location.href = downloadUrl;
            
            // Show success message after a short delay
            setTimeout(() => {
                this.helpers.displayMessage('Excel file download started!', 'success');
            }, 500);
            
        } catch (error) {
            console.error('Error downloading Excel file:', error);
            this.helpers.displayMessage(`Error: ${error.message}`, 'error');
        }
    }
}; 