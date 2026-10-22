import { baseLayout, PLOT_CONFIG, SERIES, mw } from '../utils/plot-theme.js';

export const forecasting = {
    // Store the uploaded file
    uploadedFile: null,

    // Store the latest forecast data
    latestForecast: null,

    // Per-model result caches — keyed by model value (e.g. "Model 1")
    predictionCache: {},

    // Helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,
    
    // Initialize the module
    setup(helpers) {
        if (!helpers) {
            console.error('No helpers provided to Forecasting module');
            return;
        }
        
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;
        
        // Set up event listeners
        this.setupEventListeners();
        // 
    },
    
    setupEventListeners() {
        // The upload area is a <label for="forecast_file_input">, so the browser opens the
        // picker itself; only the file choice and drag-and-drop need handling here.
        const uploadArea = document.getElementById('forecast_upload_area');
        const fileInput = document.getElementById('forecast_file_input');

        fileInput?.addEventListener('change', () => {
            if (fileInput.files.length) this.handleFileUpload(fileInput.files[0]);
            // Clearing lets the same file be chosen again after "Change file"
            fileInput.value = '';
        });

        if (uploadArea) {
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('drag-over');
            });
            uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('drag-over');
                if (e.dataTransfer.files.length) this.handleFileUpload(e.dataTransfer.files[0]);
            });
        }

        document.getElementById('forecast_remove_file')?.addEventListener('click', () => this.removeUploadedFile());
        document.getElementById('load_recent_data')?.addEventListener('click', () => this.loadRecentData());
        document.getElementById('run_forecast')?.addEventListener('click', () => this.runForecast());
        document.getElementById('download_forecast')?.addEventListener('click', () => this.downloadForecast());

        // Show/hide lagged_hour selector based on selected model
        const forecastModelSelect   = document.getElementById('forecast_model');
        const lagLabel  = document.getElementById('lagged_hour_label');
        const lagSelect = document.getElementById('lagged_hour_selection');

        const updateLagVisibility = (model) => {
            const show = model === 'Model 2';
            lagLabel?.classList.toggle('d-none', !show);
            lagSelect?.classList.toggle('d-none', !show);
        };
        updateLagVisibility(forecastModelSelect?.value || 'Model 1');

        if (forecastModelSelect) {
            forecastModelSelect.addEventListener('change', () => {
                const m = forecastModelSelect.value;
                updateLagVisibility(m);
                if (this.predictionCache[m]) {
                    this.renderPredictionResult(this.predictionCache[m]);
                    this.displayMessage('Showing cached result for this model', 'info');
                }
            });
        }
    },
    
    async handleFileUpload(file) {
        if (!file.name.match(/\.(xls|xlsx)$/i)) {
            this.displayMessage('Upload the report as an Excel file (.xls or .xlsx).', 'warning');
            return;
        }
        // Matches MAX_CONTENT_LENGTH in factory.py; larger uploads are rejected by the server
        if (file.size > 1024 * 1024) {
            this.displayMessage('The file is larger than 1 MB. Upload the daily report as exported, without extra sheets.', 'warning');
            return;
        }

        // Read into memory immediately — avoids ERR_UPLOAD_FILE_CHANGED if the file
        // is re-downloaded or modified on disk after selection.
        try {
            const buffer = await file.arrayBuffer();
            this.uploadedBlob     = new Blob([buffer], { type: file.type || 'application/octet-stream' });
            this.uploadedFileName = file.name;
            this.uploadedFile     = file; // keep for size/name checks only
        } catch (e) {
            this.displayMessage('Could not read file. Please try again.', 'danger');
            return;
        }

        const fileInfo  = document.getElementById('forecast_file_info');
        const filename  = document.getElementById('forecast_filename');
        const uploadArea = document.getElementById('forecast_upload_area');
        if (fileInfo && filename) {
            filename.textContent = file.name;
            fileInfo.classList.remove('d-none');
            uploadArea.classList.add('d-none');
        }
        this.displayMessage(`${file.name} is ready. Load the recent direction or run a forecast.`, 'success');
    },

    removeUploadedFile() {
        this.uploadedFile     = null;
        this.uploadedBlob     = null;
        this.uploadedFileName = null;
        
        // Update UI
        document.getElementById('forecast_file_info')?.classList.add('d-none');
        document.getElementById('forecast_upload_area')?.classList.remove('d-none');
    },
    
    async loadRecentData() {
        if (!this.uploadedBlob) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }
        
        const hours = document.getElementById('recent_hours').value;
        const button = document.getElementById('load_recent_data');
        
        try {
            this.toggleButtonLoading(button, true);
            
            const formData = new FormData();
            formData.append('file', this.uploadedBlob, this.uploadedFileName);
            formData.append('hours', hours);
            
            // Send request
            const response = await fetch('/api/forecasting/recent-data', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                // Handle HTTP errors
                if (response.status === 500) {
                    const errorText = await response.text();
                    if (errorText.includes("max clients reached")) {
                        throw new Error("Database connection limit reached. Please try again in a few moments.");
                    } else {
                        throw new Error("Server error. Please try again later.");
                    }
                }
                throw new Error(`HTTP error ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.displayRecentDataChart(result.data);
                this.displayMessage('Recent data loaded successfully', 'success');
            } else {
                throw new Error(result.error || 'Failed to load recent data');
            }
        } catch (error) {
            console.error('Error loading recent data:', error);
            this.displayMessage(`Error: ${error.message}`, 'danger');
        } finally {
            this.toggleButtonLoading(button, false);
        }
    },
    
    displayRecentDataChart(data) {
        const x = data.map((item) => item.date);
        const y = data.map((item) => item.system_direction);

        // Bars coloured by sign read faster than a line when the question is "which way, and how much"
        const trace = {
            name: 'System direction',
            type: 'bar',
            x, y,
            marker: { color: y.map((v) => (v < 0 ? SERIES.gapDown : SERIES.gapUp)) },
            hovertemplate: '%{x|%d %b %H:%M}<br>%{y:,.0f} MW<extra></extra>',
        };
        const layout = baseLayout({
            height: 420,
            bargap: 0.15,
            showlegend: false,
            hovermode: 'closest',
            yaxis: { ...baseLayout().yaxis, title: { text: 'MW' }, zeroline: true, zerolinewidth: 1.5 },
        });
        Plotly.react('recent_data_chart', [trace], layout, PLOT_CONFIG);

        const tableContainer = document.getElementById('recent_data_table_container');
        if (!tableContainer) return;

        const maxAbs = Math.max(1, ...y.map((v) => Math.abs(v)));
        const fmtTime = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
        const cell = (v) => `<td class="num">${v != null ? mw.format(v) : '–'}</td>`;
        const rows = data.slice().reverse().map((item) => {
            const v = item.system_direction;
            // Tint strength follows the size of the value; the hue follows its sign
            const alpha = (0.12 + 0.5 * Math.abs(v) / maxAbs).toFixed(2);
            const tint = v < 0 ? `rgba(180, 83, 42, ${alpha})` : `rgba(44, 122, 91, ${alpha})`;
            return `<tr>
                <td>${fmtTime.format(new Date(item.date))}</td>
                <td class="num" style="background:${tint}">${mw.format(v)}</td>
                ${cell(item.wind)}${cell(item.hydro)}${cell(item.solar)}
            </tr>`;
        }).join('');

        tableContainer.innerHTML = `
            <div class="table-scroll mt-4">
                <table class="table table-sm table-hover mb-0">
                    <thead><tr>
                        <th>Hour</th><th class="num">System direction, MW</th>
                        <th class="num">Wind, MW</th><th class="num">Hydro, MW</th><th class="num">Solar, MW</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    },

    async runForecast() {
        if (!this.uploadedBlob) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }

        const model  = document.getElementById('forecast_model').value;
        const button = document.getElementById('run_forecast');

        try {
            this.toggleButtonLoading(button, true);

            const laggedHour = document.getElementById('lagged_hour_selection')?.value || '1';
            const formData = new FormData();
            formData.append('file', this.uploadedBlob, this.uploadedFileName);
            formData.append('model', model);
            formData.append('lagged_hour_selection', laggedHour);

            const predictResponse = await fetch('/api/forecasting/predict', {
                method: 'POST',
                body: formData
            });

            if (!predictResponse.ok) {
                const errorText = await predictResponse.text();
                if (errorText.includes('max clients reached')) {
                    throw new Error('Database connection limit reached. Please try again in a few moments.');
                }
                throw new Error(`Server error ${predictResponse.status}`);
            }

            const result = await predictResponse.json();
            if (!result.success) throw new Error(result.error || 'Failed to generate forecast');

            // Update forecast period badge
            const badge = document.getElementById('forecast_period_badge');
            if (badge) badge.textContent = `Forecast: ${result.known_price_length}h`;

            document.getElementById('download_forecast').disabled = false;
            this.latestForecast = { model, data: result };

            // Cache so switching model dropdown is instant
            this.predictionCache[model] = result;

            this.renderPredictionResult(result);
            this.displayMessage('Forecast generated successfully', 'success');

        } catch (error) {
            console.error('Error running forecast:', error);
            this.displayMessage(`Error: ${error.message}`, 'danger');
            Plotly.purge('forecast_chart');
        } finally {
            this.toggleButtonLoading(button, false);
        }
    },

    // Render a prediction result (used by runForecast and model-switch cache restore)
    renderPredictionResult(result) {
        this.displayForecastChart(result);
        const cmContainer = document.getElementById('forecast_confusion_matrix_container');
        if (result.confusion_matrix) {
            this.displayConfusionMatrix(result.confusion_matrix, 'forecast_confusion_matrix_chart');
            if (cmContainer) cmContainer.classList.remove('d-none');
        } else {
            if (cmContainer) cmContainer.classList.add('d-none');
            Plotly.purge('forecast_confusion_matrix_chart');
        }
    },

    // Render a prediction result (used by runForecast and model-switch cache restore)

    displayForecastChart(result) {
        // result = { model_name, mae, r2, known_price_length, validation: {x, actual, predicted}, forecast: {x, median, lower, upper}, ... }
        const validation = result.validation || {};
        const forecast = result.forecast || {};

        if (!validation.x || !forecast.x || !forecast.median) {
            console.error('Invalid chart data:', result);
            this.displayMessage('The forecast came back without chart data. Run it again, or try the other model.', 'warning');
            return;
        }

        const hover = '%{y:,.0f} MW';
        const traces = [
            { name: 'Actual', x: validation.x, y: validation.actual, type: 'scatter', mode: 'lines',
              line: { color: SERIES.capacity, width: 1.8 }, hovertemplate: hover },
            { name: 'Model on past hours', x: validation.x, y: validation.predicted, type: 'scatter', mode: 'lines',
              line: { color: SERIES.plan, width: 1.6, dash: 'dot' }, hovertemplate: hover },
            // Lower bound first so the upper bound can fill down to it
            { name: 'Lower bound', x: forecast.x, y: forecast.lower, type: 'scatter', mode: 'lines',
              line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
            { name: 'Forecast range', x: forecast.x, y: forecast.upper, type: 'scatter', mode: 'lines',
              fill: 'tonexty', fillcolor: 'rgba(194, 112, 46, 0.18)', line: { width: 0 }, hoverinfo: 'skip' },
            { name: 'Forecast (median)', x: forecast.x, y: forecast.median, type: 'scatter', mode: 'lines',
              line: { color: SERIES.actual, width: 2.2 }, hovertemplate: hover },
        ];

        // Open on the last 72 hours of history plus the whole forecast; the slider reaches the rest
        const start = new Date(forecast.x[0]);
        const zoomStart = new Date(start.getTime() - 72 * 3600 * 1000);
        const zoomEnd = forecast.x[forecast.x.length - 1];

        const base = baseLayout();
        const layout = baseLayout({
            height: 520,
            margin: { t: 40, r: 16, b: 40, l: 64 },
            xaxis: { ...base.xaxis, range: [zoomStart, zoomEnd], rangeslider: { visible: true, thickness: 0.08 } },
            yaxis: { ...base.yaxis, title: { text: 'MW' }, zeroline: true, zerolinewidth: 1.5 },
            // Marks where history ends and the forecast begins
            shapes: [{ type: 'line', xref: 'x', yref: 'paper', x0: forecast.x[0], x1: forecast.x[0], y0: 0, y1: 1,
                       line: { color: '#8A96A3', width: 1, dash: 'dash' } }],
            annotations: [{ xref: 'x', yref: 'paper', x: forecast.x[0], y: 1, yanchor: 'bottom', xanchor: 'left',
                            text: 'Forecast', showarrow: false, font: { size: 11, color: '#5B6773' } }],
        });

        const stats = document.getElementById('forecast_stats');
        if (stats) {
            stats.innerHTML = `
                <div><dt>Mean absolute error on past hours, MW</dt><dd>${result.mae != null ? mw.format(result.mae) : '–'}</dd></div>
                <div><dt>R² on past hours</dt><dd>${result.r2 ?? '–'}</dd></div>
                <div><dt>Hours forecast</dt><dd>${result.known_price_length ?? '–'}</dd></div>`;
            stats.hidden = false;
        }

        try {
            Plotly.react('forecast_chart', traces, layout, PLOT_CONFIG);
        } catch (error) {
            console.error('Chart rendering error:', error);
            this.displayMessage('The forecast chart could not be drawn. Reload the page and run it again.', 'danger');
        }
    },

    displayConfusionMatrix(confusionData, chartDivId = 'confusion_matrix_chart') {
        if (!confusionData || !confusionData.z) {
            console.warn('No confusion matrix data available');
            return;
        }
        const { z, x_labels: xLabels, y_labels: yLabels } = confusionData;

        // Shares, not raw counts: each column (one predicted direction) adds up to 100%.
        // Empty cells stay blank so the pattern along the diagonal stands out.
        const text = z.map((row) => row.map((v) => (v > 0 ? `${Math.round(v * 100)}%` : '')));
        const trace = {
            type: 'heatmap',
            z, x: xLabels, y: yLabels, text,
            texttemplate: '%{text}',
            colorscale: [[0, '#FFFFFF'], [1, '#1F5F99']],
            zmin: 0,
            zmax: 1,
            showscale: false,
            xgap: 2,
            ygap: 2,
            hoverongaps: false,
            hovertemplate: 'Predicted %{x}<br>Actual %{y}<br>%{z:.0%} of these predictions<extra></extra>',
        };

        // Outline the cells where the prediction matched what happened
        const shapes = xLabels.map((label, i) => yLabels.includes(label) ? {
            type: 'rect', xref: 'x', yref: 'y',
            x0: i - 0.5, x1: i + 0.5, y0: yLabels.indexOf(label) - 0.5, y1: yLabels.indexOf(label) + 0.5,
            line: { color: '#C2702E', width: 2 },
        } : null).filter(Boolean);

        const layout = {
            font: { family: "'RWE Sans Web', -apple-system, 'Segoe UI', sans-serif", size: 12, color: '#1F2933' },
            height: 520,
            xaxis: { title: { text: 'Predicted' }, side: 'bottom', tickangle: -30, tickfont: { size: 11 } },
            yaxis: { title: { text: 'Actual' }, autorange: 'reversed', tickfont: { size: 11 } },
            margin: { l: 150, r: 16, t: 16, b: 130 },
            shapes,
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
        };

        Plotly.react(chartDivId, [trace], layout, { responsive: true, displayModeBar: false });
    },

    async downloadForecast() {
        if (!this.uploadedBlob) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }

        const button = document.getElementById('download_forecast');

        try {
            this.toggleButtonLoading(button, true);

            if (!this.latestForecast) {
                this.displayMessage('Please run forecast first before downloading', 'warning');
                return;
            }

            const formData = new FormData();
            formData.append('file', this.uploadedBlob, this.uploadedFileName);
            formData.append('model', this.latestForecast.model);
            formData.append('reuse_results', 'true');
            
            // Send the forecast ID if available
            if (this.latestForecast.data.forecast_id) {
                formData.append('forecast_id', this.latestForecast.data.forecast_id);
                console.log('Using cached forecast with ID:', this.latestForecast.data.forecast_id);
            } else {
                console.warn('No forecast ID available, results may differ');
            }
            
            // Send request
            const response = await fetch('/api/forecasting/download-forecast', {
                method: 'POST',
                body: formData,
                cache: 'no-cache',
                redirect: 'follow',
                referrerPolicy: 'no-referrer'
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Convert base64 to blob
                const byteCharacters = atob(result.excel_data);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
                
                // Create download link
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = result.filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                this.displayMessage('Forecast downloaded successfully', 'success');
            } else {
                throw new Error(result.error || 'Failed to download forecast');
            }
        } catch (error) {
            console.error('Error downloading forecast:', error);
            this.displayMessage(`Error: ${error.message}`, 'danger');
        } finally {
            this.toggleButtonLoading(button, false);
        }
    },
    
    displayShapPlot(shapImageBase64) {
        const container = document.getElementById('shap_plot_container');
        const img = document.getElementById('shap_plot_image');
        
        if (!container || !img) return;
        
        if (shapImageBase64) {
            img.src = `data:image/png;base64,${shapImageBase64}`;
            container.classList.remove('d-none');
        } else {
            container.classList.add('d-none');
            img.src = '';
        }
    },
    
    // Listeners are bound once in setup(); nothing to do when the tab opens
    init() {}
}; 