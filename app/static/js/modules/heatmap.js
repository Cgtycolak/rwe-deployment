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

    // Configuration
    plantIds: [3197267, 3205710, 134405, 3205527, 3204758, 3204759, 1740316, 3205381, 3205524, 3205525, 3206732, 3206733, 3195727, 2543, 301420, 472111, 924, 928, 923, 979, 980, 937, 3204400, 3204399, 24604, 3194367, 945, 983],
    orgIds: [10372, 166, 396, 11816, 294, 294, 1964, 11810, 11811, 11811, 11997, 11997, 9488, 181, 3625, 6839, 195, 195, 195, 195, 195, 195, 195, 195, 282, 282, 378, 378],
    plantNames: ['ACWA', 'AKENRJ ERZIN', 'AKSA ANT', 'BAYMINA', 'BILGIN1', 'BILGIN2', 'CENGIZ', 'ENKA ADP',
        'ENKA GBZ1', 'ENKA GBZ2', 'ENKA IZM1', 'ENKA IZM2', 'GAMA ICAN', 'HABAS', 'RWE', 'YENI', 'BURSA BLOK1',
        'BURSA BLOK2', 'İST A-(A)', 'İST A-(B)', 'İST A-(C)', 'İST B (Blok40+ Blok50)', 'TEKİRA', 'TEKİRB',
        'BAN1', 'BAN2', 'HAM-10', 'HAM-20'],

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_heatmap');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';
            
            const selectedDate = date || new Date().toISOString().split('T')[0];
            
            // Fetch both versions
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
                // Display both versions
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
            `Hourly Generation Difference MWh - ${date}` :
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
            // For difference heatmap, center the color scale at zero
            zmid: version === 'difference' ? 0 : undefined,
            hoverongaps: false,
            xgap: 1,
            ygap: 1
        };

        // Add hover template to show the difference values
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
    }
};