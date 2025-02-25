export const importCoalHeatmap = {
    // Helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    setup(helpers) {
        if (!helpers) {
            console.error('No helpers provided to Import Coal Heatmap module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;
    },

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_import_coal_heatmap');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const heatmapContainer = document.getElementById('import_coal_heatmap_container');
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';
            
            const selectedDate = date || new Date().toISOString().split('T')[0];
            
            // Fetch KGUP versions
            const [firstVersionResponse, currentVersionResponse] = await Promise.all([
                fetch("/import_coal_heatmap_data", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        date: selectedDate,
                        version: 'first'
                    })
                }),
                fetch("/import_coal_heatmap_data", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        date: selectedDate,
                        version: 'current'
                    })
                })
            ]);

            const firstVersionResult = await firstVersionResponse.json();
            const currentVersionResult = await currentVersionResponse.json();

            if (firstVersionResult.code === 200 && currentVersionResult.code === 200) {
                heatmapContainer.style.display = 'block';
                
                // Display KGUP versions
                this.processAndDisplayHeatmap(firstVersionResult.data, selectedDate, 'first');
                this.processAndDisplayHeatmap(currentVersionResult.data, selectedDate, 'current');
                
                // Calculate and display differences
                const differenceData = {
                    hours: firstVersionResult.data.hours,
                    plants: firstVersionResult.data.plants,
                    values: firstVersionResult.data.values.map((row, i) => 
                        row.map((val, j) => 
                            currentVersionResult.data.values[i][j] - val
                        )
                    )
                };
                this.processAndDisplayHeatmap(differenceData, selectedDate, 'difference');
            }

        } catch (error) {
            console.error('Error loading import coal heatmap data:', error);
            this.displayMessage("Error loading import coal heatmap data", "danger");
            heatmapContainer.style.display = 'none';
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Load Heatmap';
        }
    },

    processAndDisplayHeatmap(data, date, version) {
        try {
            if (!data.values || !data.hours || !data.plants) {
                console.error("Data is missing required fields");
                this.displayMessage("Error: Missing required data fields", "danger");
                return;
            }

            const elementId = version === 'first' ? 'import_coal_heatmap_first_version' : 
                            version === 'current' ? 'import_coal_heatmap_current' : 
                            'import_coal_heatmap_difference';
            
            const element = document.getElementById(elementId);

            // Find min and max for color scaling
            const allValues = data.values.flat();
            const maxValue = Math.max(...allValues);
            const minValue = Math.min(...allValues);

            // Function to determine text color based on background value
            const getTextColor = (value) => {
                const threshold = 0.3;
                const normalizedValue = (value - minValue) / (maxValue - minValue);
                return normalizedValue > threshold ? 'black' : 'white';
            };

            const colorscale = version === 'difference' ? [
                [0, 'blue'],      // Negative values
                [0.5, 'white'],   // Zero
                [1, 'red']        // Positive values
            ] : 'RdBu';

            const title = version === 'difference' ? 
                `Import Coal Hourly Generation Difference MWh - ${date} (Final - First)` :
                `Import Coal Hourly Generation MWh - ${date} (${version === 'first' ? 'First Version' : 'Final Version'})`;

            const layout = {
                title: {
                    text: title,
                    font: { size: 18 }
                },
                xaxis: {
                    title: '',
                    tickangle: -90,
                    ticktext: data.plants,
                    tickvals: Array.from({ length: data.plants.length }, (_, i) => i),
                    tickfont: { size: 14 },
                    tickmode: 'array',
                    side: 'bottom'
                },
                yaxis: {
                    title: 'Hour',
                    ticktext: data.hours,
                    tickvals: Array.from({ length: 24 }, (_, i) => i),
                    autorange: 'reversed',
                    tickfont: { size: 14 }
                },
                margin: { l: 80, r: 50, b: 400, t: 50, pad: 4 },
                width: 1400,
                height: 1200,
                plot_bgcolor: 'white',
                paper_bgcolor: 'white',
                annotations: data.values.map((row, i) => 
                    row.map((val, j) => ({
                        text: Math.round(val).toString(),
                        x: j,
                        y: i,
                        xref: 'x',
                        yref: 'y',
                        showarrow: false,
                        font: {
                            size: 14,
                            color: getTextColor(val)
                        }
                    }))
                ).flat()
            };

            const heatmapTrace = {
                z: data.values,
                x: data.plants,
                y: data.hours,
                type: 'heatmap',
                colorscale: colorscale,
                showscale: true,
                colorbar: {
                    title: 'MWh',
                    titleside: 'right',
                    thickness: 30,
                    len: 1.029
                },
                zmid: version === 'difference' ? 0 : undefined,
                hoverongaps: false,
                xgap: 1,
                ygap: 1
            };

            if (version === 'difference') {
                heatmapTrace.hovertemplate = 
                    'Hour: %{y}<br>' +
                    'Plant: %{x}<br>' +
                    'Difference: %{z:+.0f} MWh<extra></extra>';
            }

            Plotly.newPlot(element, [heatmapTrace], layout, {
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            });

        } catch (error) {
            console.error('Error processing data:', error);
            this.displayMessage("Error processing data", "danger");
        }
    },

    init() {
        try {
            // Set default date to today
            const dateInput = document.getElementById('import_coal_date');
            if (dateInput) {
                dateInput.valueAsDate = new Date();
            }

            // Add event listener
            const loadButton = document.getElementById('load_import_coal_heatmap');
            if (loadButton) {
                loadButton.addEventListener('click', () => {
                    const date = document.getElementById('import_coal_date').value;
                    this.loadHeatmapData(date);
                });
            }
        } catch (error) {
            console.error('Error initializing Import Coal Heatmap:', error);
            if (this.displayMessage) {
                this.displayMessage('Error initializing Import Coal Heatmap', 'danger');
            }
        }
    }
}; 