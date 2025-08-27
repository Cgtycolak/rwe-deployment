export const ligniteHeatmap = {
    // Helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    setup(helpers) {
        if (!helpers) {
            console.error('No helpers provided to Lignite Heatmap module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;

        // Set default date to today
        const dateInput = document.getElementById('lignite_date');
        if (dateInput) {
            dateInput.valueAsDate = new Date();
        }

        // Add event listeners
        const loadButton = document.getElementById('load_lignite_heatmap');
        const toggleButton = document.getElementById('toggle_lignite_realtime');
        
        if (loadButton) {
            loadButton.addEventListener('click', () => {
                const dateInput = document.getElementById('lignite_date');
                this.loadHeatmapData(dateInput.value);
            });
        }

        if (toggleButton) {
            toggleButton.addEventListener('click', () => {
                this.toggleRealtime();
            });
        }

        // NEW: Add event listener for date comparison
        const comparisonButton = document.getElementById('load_lignite_comparison');
        if (comparisonButton) {
            comparisonButton.addEventListener('click', () => {
                this.loadDateComparison();
            });
        }
    },

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_lignite_heatmap');
        const toggleButton = document.getElementById('toggle_lignite_realtime');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const heatmapContainer = document.getElementById('lignite_heatmap_container');
        
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
            if (toggleButton) {
                toggleButton.textContent = 'Show Realtime';
                toggleButton.disabled = isToday; // Disable for today's date
            }
            this.realtimeVisible = false;
            this.selectedDate = selectedDate;  // Store date for later use
            
            // Hide realtime sections and comparison
            const realtimeSection = document.getElementById('lignite_heatmap_realtime').parentElement;
            const realtimeDiffSection = document.getElementById('lignite_heatmap_realtime_difference').parentElement;
            const comparisonContainer = document.getElementById('lignite_comparison_container');
            realtimeSection.style.display = 'none';
            realtimeDiffSection.style.display = 'none';
            comparisonContainer.style.display = 'none';
            
            // Fetch lignite versions
            const [firstVersionResponse, currentVersionResponse] = await Promise.all([
                fetch("/lignite_heatmap_data", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        date: selectedDate,
                        version: 'first'
                    })
                }),
                fetch("/lignite_heatmap_data", {
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
                
                // Store data for later use
                this.currentVersionData = currentVersionResult.data;
                this.firstVersionData = firstVersionResult.data;
                
                // Display lignite versions
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
            } else {
                console.error('Failed to load lignite data. First version code:', firstVersionResult.code, 'Current version code:', currentVersionResult.code);
                this.displayMessage(`Failed to load lignite heatmap data. First: ${firstVersionResult.code}, Current: ${currentVersionResult.code}`, "danger");
                heatmapContainer.style.display = 'none';
                if (toggleButton) toggleButton.disabled = true;
            }

        } catch (error) {
            console.error('Error loading lignite heatmap data:', error);
            this.displayMessage("Error loading lignite heatmap data", "danger");
            heatmapContainer.style.display = 'none';
            if (toggleButton) toggleButton.disabled = true;
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Load Heatmap';
        }
    },

    async toggleRealtime() {
        const realtimeSection = document.getElementById('lignite_heatmap_realtime').parentElement;
        const realtimeDiffSection = document.getElementById('lignite_heatmap_realtime_difference').parentElement;
        const toggleButton = document.getElementById('toggle_lignite_realtime');

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
            const realtimeResponse = await fetch("/lignite_realtime_heatmap_data", {
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

    async loadDateComparison() {
        const button = document.getElementById('load_lignite_comparison');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const comparisonContainer = document.getElementById('lignite_comparison_container');
        const comparisonDate = document.getElementById('lignite_comparison_date').value;
        
        if (!comparisonDate) {
            this.displayMessage("Please select a comparison date", "warning");
            return;
        }
        
        if (!this.selectedDate) {
            this.displayMessage("Please load the main heatmap first", "warning");
            return;
        }
        
        if (comparisonDate === this.selectedDate) {
            this.displayMessage("Comparison date must be different from the main date", "warning");
            return;
        }
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';
            
            // Fetch first version data for comparison date
            const comparisonResponse = await fetch("/lignite_heatmap_data", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    date: comparisonDate,
                    version: 'first'
                })
            });
            
            const comparisonResult = await comparisonResponse.json();
            
            if (comparisonResult.code === 200) {
                // Calculate difference (Selected Date - Comparison Date)
                const dateComparisonData = {
                    hours: this.firstVersionData.hours,
                    plants: this.firstVersionData.plants,
                    values: this.firstVersionData.values.map((row, i) => 
                        row.map((val, j) => 
                            val - comparisonResult.data.values[i][j]
                        )
                    )
                };
                
                // Show comparison container and display heatmap
                comparisonContainer.style.display = 'block';
                this.processAndDisplayHeatmap(
                    dateComparisonData, 
                    `${this.selectedDate} vs ${comparisonDate}`, 
                    'date_comparison'
                );
                
            } else {
                this.displayMessage("Failed to load comparison data", "danger");
            }
            
        } catch (error) {
            console.error('Error loading comparison data:', error);
            this.displayMessage("Error loading comparison data", "danger");
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Compare Dates';
        }
    },

    processAndDisplayHeatmap(data, date, version) {
        try {
            if (!data.values || !data.hours || !data.plants) {
                console.error("Data is missing required fields");
                this.displayMessage("Error: Missing required data fields", "danger");
                return;
            }

            const elementId = version === 'first' ? 'lignite_heatmap_first_version' : 
                            version === 'current' ? 'lignite_heatmap_current' : 
                            version === 'realtime' ? 'lignite_heatmap_realtime' :
                            version === 'realtime_difference' ? 'lignite_heatmap_realtime_difference' :
                            version === 'date_comparison' ? 'lignite_heatmap_date_comparison' :
                            'lignite_heatmap_difference';
            
            const element = document.getElementById(elementId);

            // Find min and max for color scaling
            const allValues = data.values.flat();
            const maxValue = Math.max(...allValues);
            const minValue = Math.min(...allValues);

            // Function to determine text color based on background value
            const getTextColor = (value) => {
                if ((version === 'difference' || version === 'realtime_difference' || version === 'date_comparison') && value === 0) return 'black';
                const threshold = 0.3;
                const normalizedValue = (value - minValue) / (maxValue - minValue);
                return normalizedValue > threshold ? 'black' : 'white';
            };

            const colorscale = (version === 'difference' || version === 'realtime_difference' || version === 'date_comparison') ? [
                [0, 'blue'],      // Negative values
                [0.5, 'white'],   // Zero
                [1, 'red']        // Positive values
            ] : 'RdBu';

            const title = version === 'difference' ? 
                `Lignite Hourly Generation Difference MWh - ${date} (Final - First)` :
                version === 'realtime_difference' ?
                `Lignite Hourly Generation Difference MWh - ${date} (Realtime - Final)` :
                version === 'date_comparison' ?
                `Lignite Hourly Generation Difference MWh - ${date} (First Version)` :
                `Lignite Hourly Generation MWh - ${date} (${version === 'first' ? 'First Version' : version === 'current' ? 'Final Version' : 'Realtime'})`;

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
                zmid: (version === 'difference' || version === 'realtime_difference' || version === 'date_comparison') ? 0 : undefined,
                hoverongaps: false,
                xgap: 1,
                ygap: 1
            };

            if (version === 'difference' || version === 'realtime_difference' || version === 'date_comparison') {
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
        // Initialize state
        this.realtimeVisible = false;
        this.realtimeData = null;
        this.currentVersionData = null;
        this.firstVersionData = null; // NEW: Store first version data
        this.selectedDate = null; // NEW: Store selected date
    }
};