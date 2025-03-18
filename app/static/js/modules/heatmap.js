export const heatmap = {
    // Helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    // Initialize with helper functions
    setup(helpers) {
        console.log('Setting up Heatmap module with helpers:', helpers);
        if (!helpers) {
            console.error('No helpers provided to Heatmap module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;
    },

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_heatmap');
        const toggleButton = document.getElementById('toggle_realtime');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const heatmapContainer = document.getElementById('heatmap_container');
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';
            
            const selectedDate = date || new Date().toISOString().split('T')[0];
            
            // Check if selected date is today
            const today = new Date().toISOString().split('T')[0];
            const isToday = selectedDate === today;

            // Reset toggle button and realtime state
            toggleButton.textContent = 'Show Realtime';
            this.realtimeVisible = false;
            this.selectedDate = selectedDate;  // Store date for later use
            
            // Hide realtime sections
            const realtimeSection = document.getElementById('generation_heatmap_realtime').parentElement;
            const realtimeDiffSection = document.getElementById('generation_heatmap_realtime_difference').parentElement;
            realtimeSection.style.display = 'none';
            realtimeDiffSection.style.display = 'none';

            // Fetch KGUP versions only
            const [firstVersionResponse, currentVersionResponse] = await Promise.all([
                fetch("/heatmap_data", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        date: selectedDate,
                        version: 'first'
                    })
                }),
                fetch("/heatmap_data", {
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
                
                // Store current version for difference calculation later
                this.currentVersionData = currentVersionResult.data;
                
                // Display KGUP versions
                this.processAndDisplayHeatmap(firstVersionResult.data, selectedDate, 'first');
                this.processAndDisplayHeatmap(currentVersionResult.data, selectedDate, 'current');
                
                // Calculate and display KGUP differences (Final - First)
                const kgupDifferenceData = {
                    hours: firstVersionResult.data.hours,
                    plants: firstVersionResult.data.plants,
                    values: firstVersionResult.data.values.map((row, i) => 
                        row.map((val, j) => 
                            currentVersionResult.data.values[i][j] - val
                        )
                    )
                };
                this.processAndDisplayHeatmap(kgupDifferenceData, selectedDate, 'difference');

                // Enable toggle button only if not today
                toggleButton.disabled = isToday;
            }

        } catch (error) {
            console.error('Error loading heatmap data:', error);
            this.displayMessage("Error loading heatmap data", "danger");
            heatmapContainer.style.display = 'none';
            toggleButton.disabled = true;
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

            const processedData = {
                values: data.values,
                hours: data.hours,
                plants: data.plants
            };

            this.displayHeatmap(processedData, date, version);
        } catch (error) {
            console.error('Error processing data:', error);
            this.displayMessage("Error processing data", "danger");
        }
    },

    displayHeatmap(data, date, version) {
        const elementId = version === 'first' ? 'generation_heatmap_first_version' : 
                         version === 'current' ? 'generation_heatmap_current' :
                         version === 'realtime' ? 'generation_heatmap_realtime' :
                         version === 'realtime_difference' ? 'generation_heatmap_realtime_difference' :
                         'generation_heatmap_difference';
        const element = document.getElementById(elementId);

        // Extract values from data
        const values = data.values;
        const hours = data.hours;
        const plants = data.plants;

        // Find min and max for color scaling
        const allValues = values.flat();
        const maxValue = Math.max(...allValues);
        const minValue = Math.min(...allValues);

        // Function to determine text color based on background value
        const getTextColor = (value) => {
            if (version === 'difference' || version === 'realtime_difference') {
                if (value === 0) return 'black';
            }
            const threshold = 0.3;
            const normalizedValue = (value - minValue) / (maxValue - minValue);
            return normalizedValue > threshold ? 'black' : 'white';
        };

        // Different color scale for difference heatmap
        const colorscale = version === 'difference' ? [
            [0, 'blue'],      // Negative values
            [0.5, 'white'],   // Zero
            [1, 'red']        // Positive values
        ] : 'RdBu';

        const title = version === 'difference' ? 
            `Hourly Generation Difference MWh - ${date} (Final - First)` :
            version === 'realtime_difference' ?
            `Hourly Generation Difference MWh - ${date} (Realtime - Final)` :
            `Hourly Generation MWh - ${date} (${version === 'first' ? 'First Version' : version === 'current' ? 'Final Version' : 'Realtime'})`;

        const layout = {
            title: {
                text: title,
                font: { size: 18 }
            },
            xaxis: {
                title: '',
                tickangle: -90,
                ticktext: plants,
                tickvals: Array.from({ length: plants.length }, (_, i) => i),
                tickfont: { size: 14 },
                tickmode: 'array',
                side: 'bottom'
            },
            yaxis: {
                title: 'Hour',
                ticktext: hours,
                tickvals: Array.from({ length: 24 }, (_, i) => i),
                autorange: 'reversed',
                tickfont: { size: 14 }
            },
            margin: { l: 80, r: 50, b: 300, t: 50, pad: 4 },
            width: 1400,
            height: 1000,
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            annotations: values.map((row, i) => 
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
            z: values,
            x: plants,
            y: hours,
            type: 'heatmap',
            colorscale: colorscale,
            showscale: true,
            colorbar: {
                title: 'MWh',
                titleside: 'right',
                thickness: 30,
                len: 1.029
            },
            // For difference heatmap, center the color scale at zero
            zmid: version === 'difference' ? 0 : undefined,
            hoverongaps: false,
            xgap: 1,
            ygap: 1
        };

        // Add hover template to show the difference values
        if (version === 'difference' || version === 'realtime_difference') {
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
    },

    async toggleRealtime() {
        const realtimeSection = document.getElementById('generation_heatmap_realtime').parentElement;
        const realtimeDiffSection = document.getElementById('generation_heatmap_realtime_difference').parentElement;
        const toggleButton = document.getElementById('toggle_realtime');

        if (this.realtimeVisible) {
            // Just hide the sections if they're already visible
            realtimeSection.style.display = 'none';
            realtimeDiffSection.style.display = 'none';
            toggleButton.textContent = 'Show Realtime';
            this.realtimeVisible = false;
            return;
        }

        try {
            // Show loading state
            toggleButton.disabled = true;
            toggleButton.textContent = 'Loading...';

            // Fetch realtime data
            const realtimeResponse = await fetch("/realtime_heatmap_data", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ date: this.selectedDate })
            });
            const realtimeResult = await realtimeResponse.json();

            if (realtimeResult.code === 200) {
                // Show the sections
                realtimeSection.style.display = 'block';
                realtimeDiffSection.style.display = 'block';
                
                // Display realtime data
                this.processAndDisplayHeatmap(realtimeResult.data, this.selectedDate, 'realtime');
                
                // Calculate and display differences
                const realtimeDifferenceData = {
                    hours: realtimeResult.data.hours,
                    plants: realtimeResult.data.plants,
                    values: realtimeResult.data.values.map((row, i) => 
                        row.map((val, j) => 
                            val - this.currentVersionData.values[i][j]
                        )
                    )
                };
                this.processAndDisplayHeatmap(realtimeDifferenceData, this.selectedDate, 'realtime_difference');
                
                toggleButton.textContent = 'Hide Realtime';
                this.realtimeVisible = true;
            } else {
                this.displayMessage("Failed to load realtime data", "danger");
            }
        } catch (error) {
            console.error('Error loading realtime data:', error);
            this.displayMessage("Error loading realtime data", "danger");
        } finally {
            toggleButton.disabled = false;
        }
    },

    init() {
        // Set default date to today
        const dateInput = document.getElementById('heatmap_date');
        if (dateInput) {
            dateInput.valueAsDate = new Date();
        }

        // Add event listeners
        document.getElementById('load_heatmap').addEventListener('click', () => {
            const date = document.getElementById('heatmap_date').value;
            this.loadHeatmapData(date);
        });

        document.getElementById('toggle_realtime').addEventListener('click', () => {
            this.toggleRealtime();
        });

        // Initialize state
        this.realtimeVisible = false;
        this.realtimeData = null;
        this.realtimeDifferenceData = null;
    }
};