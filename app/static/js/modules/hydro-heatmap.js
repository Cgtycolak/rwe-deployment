export const hydroHeatmap = {
    // Helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    setup(helpers) {
        if (!helpers) {
            console.error('No helpers provided to Hydro Heatmap module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;

        // Set default date to today
        const dateInput = document.getElementById('hydro_date');
        if (dateInput) {
            dateInput.valueAsDate = new Date();
        }

        // Add event listener for the load button
        const loadButton = document.getElementById('load_hydro_heatmap');
        if (loadButton) {
            loadButton.addEventListener('click', () => {
                const dateInput = document.getElementById('hydro_date');
                this.loadHeatmapData(dateInput.value);
            });
        }
    },

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_hydro_heatmap');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const heatmapContainer = document.getElementById('hydro_heatmap_container');
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';
            
            const selectedDate = date || new Date().toISOString().split('T')[0];

            // Fetch both versions of the data
            const [firstVersionResponse, currentVersionResponse] = await Promise.all([
                fetch("/hydro_heatmap_data", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ 
                        date: selectedDate,
                        version: 'first'
                    })
                }),
                fetch("/hydro_heatmap_data", {
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
            console.error('Error loading heatmap data:', error);
            this.displayMessage("Error loading heatmap data", "danger");
            heatmapContainer.style.display = 'none';
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Load Heatmap';
        }
    },

    processAndDisplayHeatmap(data, date, version) {
        const elementId = version === 'first' ? 'hydro_heatmap_first_version' : 
                         version === 'current' ? 'hydro_heatmap_current' : 
                         'hydro_heatmap_difference';
        const element = document.getElementById(elementId);

        const values = data.values;
        const hours = data.hours;
        const plants = data.plants;

        // Find min and max for color scaling
        const allValues = values.flat();
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
            `Hourly Generation Difference MWh - ${date} (Final - First)` :
            `Hourly Generation MWh - ${date} (${version === 'first' ? 'First Version' : 'Final Version'})`;

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
    }
}; 