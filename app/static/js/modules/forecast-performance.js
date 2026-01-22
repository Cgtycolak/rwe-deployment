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
        
        if (periodSelect) {
            periodSelect.addEventListener('change', (e) => {
                this.handlePeriodChange(e.target.value);
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
            if (chartContainer) {
                chartContainer.innerHTML = '';
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
                
                // Enable download button
                const downloadButton = document.getElementById('download_performance_chart');
                if (downloadButton) {
                    downloadButton.disabled = false;
                }
                
                this.helpers.displayMessage('Forecast performance data loaded successfully!', 'success');
            } else {
                throw new Error(result.error || 'Failed to load data');
            }
            
        } catch (error) {
            console.error('Error loading forecast performance data:', error);
            this.helpers.displayMessage(`Error: ${error.message}`, 'error');
            
            if (chartContainer) {
                chartContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i>
                        Failed to load forecast performance data: ${error.message}
                    </div>
                `;
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
        
        // Define smoother, more professional colors
        const colors = {
            actual: '#2E8B57',      // Sea Green - for actual data
            min: '#4A90E2',         // Soft Blue
            avg: '#50C878',         // Emerald Green  
            max: '#FF6B6B',         // Soft Red
            model: '#9B59B6',       // Purple
            cemre: '#F39C12'        // Orange - for Cemre forecast
        };
        
        const traces = [];
        
        // Actual Price (always show with distinct style)
        traces.push({
            x: data.dates,
            y: data.actual_price,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Realized Price',
            line: { 
                color: colors.actual,
                width: 3,
                dash: 'solid'
            },
            marker: {
                size: 4,
                color: colors.actual
            },
            hovertemplate: '<b>Realized Price</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
        });
        
        // Meteologica forecasts
        if (data.meteologica_min && data.meteologica_min.some(v => v > 0)) {
            traces.push({
                x: data.dates,
                y: data.meteologica_min,
                type: 'scatter',
                mode: 'lines',
                name: 'Meteologica Min',
                line: { 
                    color: colors.min,
                    width: 2,
                    dash: 'dot'
                },
                hovertemplate: '<b>Meteologica Min</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
            });
        }
        
        if (data.meteologica_avg && data.meteologica_avg.some(v => v > 0)) {
            traces.push({
                x: data.dates,
                y: data.meteologica_avg,
                type: 'scatter',
                mode: 'lines',
                name: 'Meteologica Avg',
                line: { 
                    color: colors.avg,
                    width: 2,
                    dash: 'solid'
                },
                hovertemplate: '<b>Meteologica Avg</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
            });
        }
        
        if (data.meteologica_max && data.meteologica_max.some(v => v > 0)) {
            traces.push({
                x: data.dates,
                y: data.meteologica_max,
                type: 'scatter',
                mode: 'lines',
                name: 'Meteologica Max',
                line: { 
                    color: colors.max,
                    width: 2,
                    dash: 'dash'
                },
                hovertemplate: '<b>Meteologica Max</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
            });
        }
        
        // Model forecast
        if (data.model_forecast && data.model_forecast.some(v => v > 0)) {
            traces.push({
                x: data.dates,
                y: data.model_forecast,
                type: 'scatter',
                mode: 'lines',
                name: 'Model Forecast',
                line: { 
                    color: colors.model,
                    width: 2,
                    dash: 'dashdot'
                },
                hovertemplate: '<b>Model Forecast</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
            });
        }
        
        // Cemre forecast
        if (data.cemre_forecast && data.cemre_forecast.some(v => v > 0)) {
            traces.push({
                x: data.dates,
                y: data.cemre_forecast,
                type: 'scatter',
                mode: 'lines',
                name: 'Cemre Forecast',
                line: { 
                    color: colors.cemre,
                    width: 2,
                    dash: 'dot'
                },
                hovertemplate: '<b>Cemre Forecast</b><br>%{x}<br>%{y:.2f} TL<extra></extra>'
            });
        }
        
        const horizonLabel = data.forecast_horizon ? ` (${data.forecast_horizon.toUpperCase()})` : '';
        const layout = {
            title: {
                text: `Forecast Performance Analysis ${data.period_info || ''}${horizonLabel}`,
                font: { size: 18, color: '#2c3e50' }
            },
            xaxis: {
                title: 'Date',
                type: 'date',
                gridcolor: '#ecf0f1',
                showgrid: true
            },
            yaxis: {
                title: 'Price (TL/MWh)',
                gridcolor: '#ecf0f1',
                showgrid: true
            },
            hovermode: 'x unified',
            legend: {
                orientation: 'h',
                y: -0.1,
                x: 0.5,
                xanchor: 'center'
            },
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            font: {
                family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                size: 12,
                color: '#2c3e50'
            },
            margin: { t: 60, b: 80, l: 60, r: 40 }
        };
        
        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'select2d', 'lasso2d', 'autoScale2d'],
            displaylogo: false
        };
        
        Plotly.newPlot(chartContainer, traces, layout, config);
    },
    
    updateMetrics(metrics) {
        const metricMappings = {
            'Meteologica Min': 'meteologica_min',
            'Meteologica Avg': 'meteologica_avg', 
            'Meteologica Max': 'meteologica_max',
            'Model Forecast': 'model_forecast',
            'Cemre Forecast': 'cemre_forecast'
        };
        
        Object.entries(metricMappings).forEach(([displayName, key]) => {
            if (metrics[displayName]) {
                const wmapeElement = document.getElementById(`${key}_wmape`);
                const rmseElement = document.getElementById(`${key}_rmse`);
                const r2Element = document.getElementById(`${key}_r2`);
                
                if (wmapeElement) wmapeElement.textContent = `${metrics[displayName].wmape}%`;
                if (rmseElement) rmseElement.textContent = `${metrics[displayName].rmse} TL`;
                if (r2Element) r2Element.textContent = metrics[displayName].r2;
            }
        });
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
    }
}; 