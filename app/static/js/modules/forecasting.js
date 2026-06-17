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
        // File upload handling
        const uploadArea = document.getElementById('forecast_upload_area');
        const fileInput = document.getElementById('forecast_file_input');
        const removeFileBtn = document.getElementById('forecast_remove_file');
        
        // Create a dedicated button for file selection
        if (uploadArea && fileInput) {
            // First, remove any existing click event listeners
            const newUploadArea = uploadArea.cloneNode(true);
            uploadArea.parentNode.replaceChild(newUploadArea, uploadArea);
            
            // Function to handle file selection without duplicate dialogs
            const selectFile = (e) => {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                
                // Create a new file input each time to avoid browser caching issues
                const oldInput = document.getElementById('forecast_file_input');
                const newInput = document.createElement('input');
                newInput.type = 'file';
                newInput.id = 'forecast_file_input';
                newInput.className = 'd-none';
                newInput.accept = '.xls,.xlsx';
                
                // Set up the change event before adding to DOM
                newInput.addEventListener('change', (event) => {
                    if (event.target.files.length) {
                        this.handleFileUpload(event.target.files[0]);
                    }
                });
                
                // Replace the old input with the new one
                if (oldInput && oldInput.parentNode) {
                    oldInput.parentNode.replaceChild(newInput, oldInput);
                } else {
                    // If for some reason the old input doesn't exist, append to upload area
                    document.body.appendChild(newInput);
                }
                
                // Trigger click on the new input
                setTimeout(() => {
                    newInput.click();
                }, 0);
            };
            
            // Set up drag and drop
            newUploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                newUploadArea.classList.add('drag-over');
            });
            
            newUploadArea.addEventListener('dragleave', () => {
                newUploadArea.classList.remove('drag-over');
            });
            
            newUploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                newUploadArea.classList.remove('drag-over');
                
                if (e.dataTransfer.files.length) {
                    this.handleFileUpload(e.dataTransfer.files[0]);
                }
            });
            
            // Use a single click handler for the upload area
            newUploadArea.addEventListener('click', selectFile);
        }
        
        if (removeFileBtn) {
            removeFileBtn.addEventListener('click', () => {
                this.removeUploadedFile();
            });
        }
        
        // Button click handlers
        document.getElementById('load_recent_data')?.addEventListener('click', () => {
            this.loadRecentData();
        });
        
        
        document.getElementById('run_forecast')?.addEventListener('click', () => {
            this.runForecast();
        });
        
        document.getElementById('download_forecast')?.addEventListener('click', () => {
            this.downloadForecast();
        });
        
        // Tab handling
        const tabs = document.querySelectorAll('#forecastingTabs .nav-link');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                // Remove active class from all tabs
                tabs.forEach(t => t.classList.remove('active'));
                
                // Add active class to clicked tab
                e.target.classList.add('active');
                
                // Show the corresponding tab content
                const tabId = e.target.getAttribute('data-bs-target');
                document.querySelectorAll('.tab-pane').forEach(pane => {
                    pane.classList.remove('show', 'active');
                });
                document.querySelector(tabId).classList.add('show', 'active');
            });
        });
        
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
            this.displayMessage('Please upload an Excel file (.xls or .xlsx)', 'warning');
            return;
        }
        if (file.size > 200 * 1024 * 1024) {
            this.displayMessage('File size exceeds 200MB limit', 'warning');
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
        this.displayMessage(`File "${file.name}" uploaded successfully`, 'success');
    },

    removeUploadedFile() {
        this.uploadedFile     = null;
        this.uploadedBlob     = null;
        this.uploadedFileName = null;
        
        // Update UI
        const fileInfo = document.getElementById('forecast_file_info');
        const uploadArea = document.getElementById('forecast_upload_area');
        const fileInput = document.getElementById('forecast_file_input');
        
        if (fileInfo && uploadArea && fileInput) {
            fileInfo.classList.add('d-none');
            uploadArea.classList.remove('d-none');
            fileInput.value = ''; // Clear the file input
        }
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
        const dates = data.map(item => item.date);
        const values = data.map(item => item.system_direction);
        
        const trace = {
            x: dates,
            y: values,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'System Direction',
            line: {
                color: 'rgb(255, 0, 0)',
                width: 2
            },
            marker: {
                size: 6,
                color: 'rgb(255, 0, 0)'
            }
        };
        
        const layout = {
            title: 'Recent System Direction',
            yaxis: {
                title: 'System Direction (MW)'
            },
            hovermode: 'closest',
            plot_bgcolor: 'white',
            paper_bgcolor: 'white'
        };
        
        Plotly.newPlot('recent_data_chart', [trace], layout, {responsive: true});
        
        // Add table display with heatmap coloring
        const tableContainer = document.getElementById('recent_data_table_container');
        if (tableContainer) {
            // Find min and max values for system direction to create color scale
            const systemDirectionValues = data.map(item => item.system_direction);
            const minValue = Math.min(...systemDirectionValues);
            const maxValue = Math.max(...systemDirectionValues);
            
            let tableHtml = `
                <div class="table-responsive mt-4">
                    <table class="table table-striped table-hover">
                        <thead class="table-dark">
                            <tr>
                                <th>DATE & TIME</th>
                                <th>SYSTEM DIRECTION (MW)</th>
                                <th>WIND (MW)</th>
                                <th>HYDRO (MW)</th>
                                <th>SOLAR (MW)</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            data.forEach(item => {
                // Format date for display
                const date = new Date(item.date);
                const formattedDate = date.toLocaleString();
                
                // Calculate color for system direction (red for negative, green for positive)
                let backgroundColor, textColor;
                
                if (item.system_direction < 0) {
                    // Red gradient for negative values - more intense
                    const intensity = Math.min(Math.abs(item.system_direction) / Math.abs(minValue), 1);
                    backgroundColor = `rgba(255, 0, 0, ${0.3 + intensity * 0.6})`;
                    textColor = 'black';
                } else {
                    // Green gradient for positive values - more intense
                    const intensity = Math.min(item.system_direction / maxValue, 1);
                    backgroundColor = `rgba(0, 180, 0, ${0.3 + intensity * 0.6})`;
                    textColor = 'black';
                }
                
                tableHtml += `
                    <tr>
                        <td>${formattedDate}</td>
                        <td style="background-color: ${backgroundColor}; color: ${textColor}; text-align: right;">
                            ${item.system_direction.toFixed(2)}
                        </td>
                        <td style="text-align: right;">${item.wind ? item.wind.toFixed(2) : '0.00'}</td>
                        <td style="text-align: right;">${item.hydro ? item.hydro.toFixed(2) : '0.00'}</td>
                        <td style="text-align: right;">${item.solar ? item.solar.toFixed(2) : '0.00'}</td>
                    </tr>
                `;
            });
            
            tableHtml += `
                        </tbody>
                    </table>
                </div>
            `;
            
            tableContainer.innerHTML = tableHtml;
        }
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
            this.displayMessage('No forecast data available', 'warning');
            return;
        }

        const traces = [
            // Validation section: actual values (blue solid)
            {
                x: validation.x,
                y: validation.actual,
                type: 'scatter',
                mode: 'lines',
                name: 'Actual Values',
                line: { color: 'rgb(0, 0, 255)', width: 2 }
            },
            // Validation section: predicted values (green dashed)
            {
                x: validation.x,
                y: validation.predicted,
                type: 'scatter',
                mode: 'lines',
                name: 'Model Prediction (Validation)',
                line: { color: 'rgb(0, 128, 0)', width: 2, dash: 'dash' }
            },
            // Forecast section: lower bound (gray, no visibility)
            {
                x: forecast.x,
                y: forecast.lower,
                type: 'scatter',
                mode: 'lines',
                name: 'Confidence Band',
                line: { color: 'rgba(128, 128, 128, 0)', width: 0 },
                showlegend: true
            },
            // Forecast section: upper bound (gray, fill to lower)
            {
                x: forecast.x,
                y: forecast.upper,
                type: 'scatter',
                mode: 'lines',
                name: 'Upper Confidence Bound',
                fill: 'tonexty',
                fillcolor: 'rgba(128, 128, 128, 0.3)',
                line: { color: 'rgba(128, 128, 128, 0)', width: 0 },
                showlegend: false
            },
            // Forecast section: median (red solid)
            {
                x: forecast.x,
                y: forecast.median,
                type: 'scatter',
                mode: 'lines',
                name: 'Median Forecast',
                line: { color: 'rgb(255, 0, 0)', width: 2 }
            }
        ];

        // Default view: last 48h of validation + full forecast, range slider for full history
        const forecastStart = forecast.x.length ? new Date(forecast.x[0]) : null;
        const forecastEnd   = forecast.x.length ? new Date(forecast.x[forecast.x.length - 1]) : null;
        const zoomStart     = forecastStart
            ? new Date(forecastStart.getTime() - 48 * 60 * 60 * 1000)
            : undefined;

        const layout = {
            title: `${result.model_name} | MAE: ${result.mae} | R²: ${result.r2} | Best Q: ${result.best_quantile ?? '-'} | Forecast: ${result.known_price_length}h`,
            xaxis: {
                type: 'date',
                title: 'Date & Time',
                tickangle: -45,
                range: zoomStart && forecastEnd
                    ? [zoomStart.toISOString(), forecastEnd.toISOString()]
                    : undefined,
                rangeslider: { visible: true, thickness: 0.08 },
            },
            yaxis: {
                title: 'System Direction (MW)',
                zerolinecolor: 'rgba(0,0,0,0.2)',
                zerolinewidth: 1
            },
            hovermode: 'closest',
            plot_bgcolor: 'rgba(255,255,255,1)',
            paper_bgcolor: 'rgba(255,255,255,1)',
            legend: { x: 0, y: 1, orientation: 'h' },
            margin: { l: 60, r: 30, t: 80, b: 60 }
        };

        try {
            Plotly.newPlot('forecast_chart', traces, layout, { responsive: true });
        } catch (error) {
            console.error('Chart rendering error:', error);
            this.displayMessage('Error rendering chart: ' + error.message, 'danger');
        }
    },
    
    displayConfusionMatrix(confusionData, chartDivId = 'confusion_matrix_chart') {
        if (!confusionData || !confusionData.z) {
            console.warn('No confusion matrix data available');
            return;
        }
        
        // Format text annotations for the heatmap cells
        const textAnnotations = confusionData.z.map(row => 
            row.map(v => v.toFixed(2))
        );
        
        const heatmapTrace = {
            z: confusionData.z,
            x: confusionData.x_labels,
            y: confusionData.y_labels,
            type: 'heatmap',
            colorscale: 'Reds',
            text: textAnnotations,
            texttemplate: '%{text}',
            showscale: true,
            hoverongaps: false
        };
        
        const layout = {
            title: '<b>YAL-YAT Prediction Heatmap</b>',
            autosize: true,
            xaxis: {
                title: '<b>Predicted</b>',
                tickfont: { size: 12 },
                side: 'bottom',
                tickangle: -35
            },
            yaxis: {
                title: '<b>Actual</b>',
                tickfont: { size: 12 },
                autorange: 'reversed'
            },
            margin: {
                l: 180,
                r: 80,
                t: 80,
                b: 180
            },
            plot_bgcolor: 'white',
            paper_bgcolor: 'white'
        };

        Plotly.newPlot(chartDivId, [heatmapTrace], layout, {responsive: true, displayModeBar: false});
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
    
    init() {
        console.log('Initializing forecasting module');
        
        // Add CSS for the upload area
        const style = document.createElement('style');
        style.textContent = `
            .upload-area {
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 30px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
            }
            
            .upload-area:hover, .upload-area.drag-over {
                border-color: #007bff;
                background-color: rgba(0, 123, 255, 0.05);
            }
            
            .upload-prompt {
                color: #6c757d;
            }
        `;
        document.head.appendChild(style);
        
        // Set up event listeners
        this.setupEventListeners();
    }
}; 