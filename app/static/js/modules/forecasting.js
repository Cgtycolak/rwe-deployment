export const forecasting = {
    // Store the uploaded file
    uploadedFile: null,
    
    // Store the latest forecast data
    latestForecast: null,
    
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
        
        document.getElementById('run_evaluation')?.addEventListener('click', () => {
            this.runEvaluation();
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
        
        // Set up evaluation button
        const evaluateBtn = document.getElementById('run_evaluation');
        if (evaluateBtn) {
            evaluateBtn.addEventListener('click', () => this.runEvaluation());
        }
    },
    
    handleFileUpload(file) {
        // Prevent duplicate uploads
        if (this.uploadedFile && this.uploadedFile.name === file.name && 
            this.uploadedFile.size === file.size && 
            this.uploadedFile.lastModified === file.lastModified) {
            console.log('File already uploaded, ignoring duplicate');
            return;
        }
        
        // Check file type
        if (!file.name.match(/\.(xls|xlsx)$/i)) {
            this.displayMessage('Please upload an Excel file (.xls or .xlsx)', 'warning');
            return;
        }
        
        // Check file size (200MB limit)
        if (file.size > 200 * 1024 * 1024) {
            this.displayMessage('File size exceeds 200MB limit', 'warning');
            return;
        }
        
        // Store the file
        this.uploadedFile = file;
        
        // Update UI
        const fileInfo = document.getElementById('forecast_file_info');
        const filename = document.getElementById('forecast_filename');
        const uploadArea = document.getElementById('forecast_upload_area');
        
        if (fileInfo && filename) {
            filename.textContent = file.name;
            fileInfo.classList.remove('d-none');
            uploadArea.classList.add('d-none');
        }
        
        this.displayMessage(`File "${file.name}" uploaded successfully`, 'success');
    },
    
    removeUploadedFile() {
        this.uploadedFile = null;
        
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
        if (!this.uploadedFile) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }
        
        const hours = document.getElementById('recent_hours').value;
        const button = document.getElementById('load_recent_data');
        
        try {
            this.toggleButtonLoading(button, true);
            
            // Create form data
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
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
    
    async runEvaluation() {
        if (!this.uploadedFile) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }
        
        const model = document.getElementById('eval_model').value;
        const forecastPeriod = document.getElementById('eval_forecast_period').value;
        const button = document.getElementById('run_evaluation');
        
        try {
            this.toggleButtonLoading(button, true);
            
            // Create form data
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
            formData.append('model', model);
            formData.append('forecast_period', forecastPeriod);
            
            // Send the evaluation request to the correct endpoint
            const response = await fetch('/api/forecasting/evaluate', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const evalResult = await response.json();
            
            if (evalResult.success) {
                const result = evalResult.result;
                
                // Update the evaluation metrics display
                document.getElementById('eval_model_name').textContent = result.model_name;
                document.getElementById('eval_mae').textContent = result.mae;
                document.getElementById('eval_r2').textContent = result.r2;
                
                // Show the results section
                document.getElementById('evaluation_results').classList.remove('d-none');
                
                // Create plot data for the chart
                const plotData = [
                    {
                        x: result.real_data.x,
                        y: result.real_data.y,
                        type: 'scatter',
                        mode: 'lines',
                        name: 'Real Values',
                        line: {
                            color: 'blue',
                            width: 2
                        }
                    },
                    {
                        x: result.forecast_data.x,
                        y: result.forecast_data.y,
                        type: 'scatter',
                        mode: 'lines',
                        name: 'Forecast',
                        line: {
                            color: 'red',
                            width: 2
                        }
                    }
                ];
                
                const layout = {
                    title: `${result.model_name} Evaluation (MAE: ${result.mae}, R²: ${result.r2})`,
                    xaxis: {
                        title: 'Date & Time',
                        tickformat: '%Y-%m-%d', // Format to show just the date
                        tickangle: -45,
                        nticks: 12, // Fewer ticks for dates only
                        gridcolor: 'rgba(200,200,200,0.2)'
                    },
                    yaxis: {
                        title: 'System Direction (MW)',
                        gridcolor: 'rgba(200,200,200,0.2)',
                        zerolinecolor: 'rgba(200,200,200,0.5)',
                        zerolinewidth: 1
                    },
                    legend: {
                        x: 0,
                        y: 1,
                        orientation: 'h'
                    },
                    margin: {
                        l: 60,
                        r: 30,
                        t: 60,
                        b: 80  // Slightly reduced since we have shorter labels
                    },
                    hovermode: 'closest',
                    plot_bgcolor: 'rgba(255,255,255,1)',
                    paper_bgcolor: 'rgba(255,255,255,1)',
                    grid: {
                        rows: 1,
                        columns: 1,
                        pattern: 'independent',
                        roworder: 'top to bottom'
                    }
                };
                
                // Create the plot
                Plotly.newPlot('evaluation_chart', plotData, layout, {responsive: true});
                
                this.displayMessage('Model evaluation completed successfully', 'success');
            } else {
                throw new Error(evalResult.error || 'Failed to evaluate model');
            }
        } catch (error) {
            console.error('Error evaluating model:', error);
            this.displayMessage(`Error: ${error.message}`, 'danger');
            // Clear any existing chart on error
            Plotly.purge('evaluation_chart');
            // Hide results section
            document.getElementById('evaluation_results').classList.add('d-none');
        } finally {
            this.toggleButtonLoading(button, false);
        }
    },
    
    async runForecast() {
        if (!this.uploadedFile) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }
        
        const model = document.getElementById('forecast_model').value;
        const forecastPeriod = document.getElementById('forecast_period').value;
        const button = document.getElementById('run_forecast');
        
        try {
            this.toggleButtonLoading(button, true);
            
            // Create form data
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
            formData.append('model', model);
            formData.append('forecast_period', forecastPeriod);
            
            // First, get the forecast data for visualization
            const predictResponse = await fetch('/api/forecasting/predict', {
                method: 'POST',
                body: formData
            });
            
            if (!predictResponse.ok) {
                if (predictResponse.status === 500) {
                    const errorText = await predictResponse.text();
                    if (errorText.includes("max clients reached")) {
                        throw new Error("Database connection limit reached. Please try again in a few moments.");
                    } else {
                        throw new Error("Server error. Please try again later.");
                    }
                }
                throw new Error(`HTTP error ${predictResponse.status}`);
            }
            
            const predictResult = await predictResponse.json();
            console.log("Forecast prediction response:", predictResult);
            
            if (predictResult.success) {
                // Enable download button
                document.getElementById('download_forecast').disabled = false;
                
                // Extract the forecast data from the nested structure
                const forecastData = predictResult.forecast_data || {};
                console.log("Extracted forecast data:", forecastData);
                
                // Check if we have forecast data in the expected format
                if (forecastData.median && Array.isArray(forecastData.median) && forecastData.median.length > 0) {
                    console.log("Forecast data found in response");
                    
                    // Create chart data object directly from the response
                    const chartData = {
                        x: forecastData.x || [],
                        median: forecastData.median || [],
                        lower: forecastData.lower || [],
                        upper: forecastData.upper || [],
                        model_name: forecastData.model_name || predictResult.model_name || model,
                        forecast_period: forecastData.forecast_period || forecastPeriod
                    };
                    
                    // Store the forecast result for later use
                    this.latestForecast = {
                        model: model,
                        period: forecastPeriod,
                        data: predictResult
                    };
                    
                    console.log("Chart data being passed to displayForecastChart:", chartData);
                    
                    // Display the chart
                    this.displayForecastChart(chartData);
                    this.displayMessage('Forecast generated successfully', 'success');
                } else {
                    console.warn("No forecast data available in the response");
                    this.displayMessage('Forecast generated but no data available for visualization', 'warning');
                    // Clear any existing chart
                    Plotly.purge('forecast_chart');
                }
            } else {
                throw new Error(predictResult.error || 'Failed to generate forecast');
            }
        } catch (error) {
            console.error('Error running forecast:', error);
            this.displayMessage(`Error: ${error.message}`, 'danger');
            // Clear any existing chart on error
            Plotly.purge('forecast_chart');
        } finally {
            this.toggleButtonLoading(button, false);
        }
    },
    
    displayForecastChart(data) {
        console.log("displayForecastChart called with data:", data);
        
        // Make sure we have valid data to display
        if (!data.x || !data.x.length || !data.median || !data.median.length) {
            console.error("Invalid chart data:", data);
            this.displayMessage("No forecast data available to display", "warning");
            return;
        }
        
        // Ensure dates are properly formatted
        const xValues = data.x.map(d => typeof d === 'string' ? new Date(d) : d);
        
        const medianTrace = {
            x: xValues,
            y: data.median,
            type: 'scatter',
            mode: 'lines',
            name: 'Median Forecast',
            line: {
                color: 'rgb(255, 0, 0)',
                width: 2
            }
        };
        
        console.log("Median trace:", medianTrace);
        
        // Only add confidence interval if we have upper and lower bounds
        let traces = [medianTrace];
        
        if (data.upper && data.upper.length && data.lower && data.lower.length) {
            // First define the lower trace (no fill)
            const lowerTrace = {
                x: xValues,
                y: data.lower,
                type: 'scatter',
                mode: 'lines',
                name: '95% Confidence Interval',
                line: {
                    color: 'rgba(0, 0, 0, 0)',
                    width: 0
                }
            };
            
            // Then define the upper trace (with fill to the trace below)
            const upperTrace = {
                x: xValues,
                y: data.upper,
                type: 'scatter',
                mode: 'lines',
                name: '95% Upper Bound',
                fill: 'tonexty',
                fillcolor: 'rgba(200, 200, 200, 0.3)',
                line: {
                    color: 'rgba(0, 0, 0, 0)',
                    width: 0
                },
                showlegend: false
            };
            
            // The order matters here - lowerTrace must come first
            traces = [lowerTrace, upperTrace, medianTrace];
        }
        
        const layout = {
            title: `${data.model_name || 'Model'} Forecast (${data.forecast_period || '24'} hours)`,
            xaxis: {
                type: 'date'
            },
            yaxis: {
                title: 'System Direction (MW)'
            },
            hovermode: 'closest',
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            legend: {
                orientation: 'h',
                y: -0.2
            }
        };
        
        console.log("About to call Plotly.newPlot with:", {
            chartDiv: 'forecast_chart',
            traces: traces,
            layout: layout
        });
        
        try {
            Plotly.newPlot('forecast_chart', traces, layout, {responsive: true});
            console.log("Chart successfully rendered");
        } catch (error) {
            console.error("Error rendering chart:", error);
            this.displayMessage("Error rendering chart: " + error.message, "danger");
        }
    },
    
    async downloadForecast() {
        if (!this.uploadedFile) {
            this.displayMessage('Please upload an Excel file first', 'warning');
            return;
        }
        
        const button = document.getElementById('download_forecast');
        
        try {
            this.toggleButtonLoading(button, true);
            
            // Check if we have the latest forecast result
            if (!this.latestForecast) {
                this.displayMessage('Please run forecast first before downloading', 'warning');
                return;
            }
            
            // Create form data
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
            formData.append('model', this.latestForecast.model);
            formData.append('forecast_period', this.latestForecast.period);
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