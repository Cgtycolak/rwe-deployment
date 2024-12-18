export const aic = {
    // Add properties to store helper functions
    toggleLoading: null,
    displayMessage: null,

    // Initialize with helper functions
    setup(helpers) {
        console.log('Setting up AIC module with helpers');
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
    },

    async loadAICData(range = 'week') {
        try {
            console.log('Loading AIC data for range:', range);
            // this.toggleLoading(true);
            const response = await fetch(`/get_aic_data?range=${range}`);
            const result = await response.json();
            console.log('AIC data received:', result);
            
            if (result.code === 200 && result.data && result.data.length > 0) {
                console.log('Processing AIC data:', result.data[0]); // Log sample data
                this.displayAICChart(result.data);
                this.updateButtonState(range);
            } else {
                console.error('Failed to load AIC data:', result.message || 'No data received');
                this.displayMessage("No data available for the selected period", "warning");
            }
            // this.toggleLoading(false);
        } catch (error) {
            console.error('Error loading AIC data:', error);
            this.displayMessage("Error loading AIC data", "danger");
            // this.toggleLoading(false);
        }
    },

    updateButtonState(range) {
        // Remove active state from all buttons
        document.querySelectorAll('.aic-range-btn').forEach(btn => {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        // Add active state to selected button
        const activeBtn = document.querySelector(`.aic-range-btn[data-range="${range}"]`);
        if (activeBtn) {
            activeBtn.classList.remove('btn-outline-primary');
            activeBtn.classList.add('btn-primary');
        }
    },

    displayAICChart(data) {
        console.log('Displaying AIC chart with data:', data.length, 'records');
        
        // Process data for plotting
        const dates = [...new Set(data.map(item => item.date.split('T')[0]))].sort();
        console.log('Unique dates:', dates);
        
        const hours = [...new Set(data.map(item => item.time))].sort();
        console.log('Unique hours:', hours);
        
        // Create x-axis labels combining date and hour
        const xLabels = [];
        const aicValues = [];
        const realtimeValues = [];
        
        dates.forEach(date => {
            hours.forEach(hour => {
                const dataPoint = data.find(d => 
                    d.date.startsWith(date) && d.time === hour
                );
                if (dataPoint) {
                    xLabels.push(`${date} ${hour}`);
                    // Sum up all generation types for total generation
                    const totalGeneration = [
                        dataPoint.akarsu || 0,
                        dataPoint.barajli || 0,
                        dataPoint.biokutle || 0,
                        dataPoint.dogalgaz || 0,
                        dataPoint.fuelOil || 0,
                        dataPoint.ithalKomur || 0,
                        dataPoint.jeotermal || 0,
                        dataPoint.linyit || 0,
                        dataPoint.nafta || 0,
                        dataPoint.ruzgar || 0,
                        dataPoint.tasKomur || 0,
                        dataPoint.diger || 0
                    ].reduce((a, b) => a + b, 0);

                    aicValues.push(totalGeneration);
                    realtimeValues.push(dataPoint.toplam || 0);
                }
            });
        });

        console.log('Sample values - AIC:', aicValues.slice(0, 5));
        console.log('Sample values - Realtime:', realtimeValues.slice(0, 5));

        const traces = [
            {
                name: 'Total Generation',
                x: xLabels,
                y: aicValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: {
                    color: '#1f77b4',
                    width: 2
                },
                marker: {
                    size: 4
                }
            },
            {
                name: 'Realtime Total',
                x: xLabels,
                y: realtimeValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: {
                    color: '#ff7f0e',
                    width: 2
                },
                marker: {
                    size: 4
                }
            }
        ];

        const layout = {
            title: 'Total Generation vs Realtime Total',
            xaxis: {
                title: 'Date & Hour',
                tickangle: -45,
                tickfont: {
                    size: 10
                },
                nticks: 24 // Show fewer ticks for better readability
            },
            yaxis: {
                title: 'Generation (MW)',
                rangemode: 'tozero' // Start y-axis from 0
            },
            showlegend: true,
            legend: {
                x: 1,
                xanchor: 'right',
                y: 1
            },
            margin: {
                b: 100, // Increase bottom margin for rotated labels
                l: 80,  // Left margin for y-axis labels
                r: 50,  // Right margin for legend
                t: 50   // Top margin for title
            },
            hovermode: 'closest',
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff',
            width: null,  // Allow responsive width
            height: 700
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        };

        try {
            console.log('Creating Plotly chart...');
            Plotly.newPlot('aic_realtime_chart', traces, layout, config);
            console.log('Chart created successfully');
        } catch (error) {
            console.error('Error creating chart:', error);
            this.displayMessage("Error displaying chart", "danger");
        }
    },

    init() {
        console.log('Initializing AIC module');
        // Add click handlers for range buttons
        document.querySelectorAll('.aic-range-btn').forEach(button => {
            button.addEventListener('click', () => {
                const range = button.dataset.range;
                console.log('Range button clicked:', range);
                this.loadAICData(range);
            });
        });
    }
};