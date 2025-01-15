export const aic = {
    // Add properties to store helper functions
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    // Initialize with helper functions
    setup(helpers) {
        console.log('Setting up AIC module with helpers:', helpers);
        if (!helpers) {
            console.error('No helpers provided to AIC module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;

        // Verify helpers are properly set
        if (!this.toggleButtonLoading) {
            console.error('toggleButtonLoading helper not properly set');
        }
    },

    async loadAICData(range = 'week') {
        const button = document.querySelector(`.aic-range-btn[data-range="${range}"]`);
        try {
            if (!this.toggleButtonLoading) {
                console.error('toggleButtonLoading helper not available');
                return;
            }

            console.log('Loading AIC data for range:', range);
            this.toggleButtonLoading(button, true);

            const response = await fetch(`/get_aic_data?range=${range}`);
            const result = await response.json();
            console.log('AIC data received:', result);

            if (result.code === 200 && result.data &&
                result.data.aic && result.data.realtime && result.data.dpp) {
                console.log('Processing generation data:', {
                    aic: result.data.aic.length,
                    realtime: result.data.realtime.length,
                    dpp: result.data.dpp.length
                });
                this.displayAICChart(result.data);
                this.updateButtonState(range);
            } else {
                console.error('Failed to load generation data:', result.message || 'No data received');
                this.displayMessage("No data available for the selected period", "warning");
            }
        } catch (error) {
            console.error('Error loading generation data:', error);
            this.displayMessage("Error loading generation data", "danger");
        } finally {
            this.toggleButtonLoading(button, false);
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
        console.log('Displaying generation chart with data');

        // Process data for plotting
        const dates = [...new Set([
            ...data.aic.map(item => item.date.split('T')[0]),
            ...data.realtime.map(item => item.date.split('T')[0]),
            ...data.dpp.map(item => item.date.split('T')[0])
        ])].sort();

        const hours = [...new Set([
            ...data.aic.map(item => item.time),
            ...data.realtime.map(item => item.hour),
            ...data.dpp.map(item => item.time)
        ])].sort();

        // Create x-axis labels combining date and hour
        const xLabels = [];
        const aicValues = [];
        const realtimeValues = [];
        const dppValues = [];

        dates.forEach(date => {
            hours.forEach(hour => {
                const aicPoint = data.aic.find(d =>
                    d.date.startsWith(date) && d.time === hour
                );
                const realtimePoint = data.realtime.find(d =>
                    d.date.startsWith(date) && d.hour === hour
                );
                const dppPoint = data.dpp.find(d =>
                    d.date.startsWith(date) && d.time === hour
                );

                if (aicPoint || realtimePoint || dppPoint) {
                    xLabels.push(`${date} ${hour}`);
                    aicValues.push(aicPoint ? aicPoint.toplam || 0 : null);
                    realtimeValues.push(realtimePoint ? realtimePoint.total || 0 : null);
                    dppValues.push(dppPoint ? dppPoint.toplam || 0 : null);
                }
            });
        });

        const traces = [
            {
                name: 'AIC Total',
                x: xLabels,
                y: aicValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#1f77b4', width: 2 },
                marker: { size: 4 }
            },
            {
                name: 'Realtime Total',
                x: xLabels,
                y: realtimeValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#ff7f0e', width: 2 },
                marker: { size: 4 }
            },
            {
                name: 'KGÜP Total',
                x: xLabels,
                y: dppValues,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#2ca02c', width: 2 },
                marker: { size: 4 }
            }
        ];

        const layout = {
            title: 'Generation Comparison (AIC vs Realtime vs KGÜP)',
            xaxis: {
                title: 'Date & Hour',
                tickangle: -45,
                tickfont: { size: 10 },
                nticks: 24
            },
            yaxis: {
                title: 'Generation (MW)',
                rangemode: 'tozero'
            },
            showlegend: true,
            legend: {
                x: 1,
                xanchor: 'right',
                y: 1
            },
            margin: {
                b: 100,
                l: 80,
                r: 50,
                t: 50
            },
            hovermode: 'closest',
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff',
            width: null,
            height: 700
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        };

        try {
            Plotly.newPlot('aic_realtime_chart', traces, layout, config);
        } catch (error) {
            console.error('Error creating chart:', error);
            this.displayMessage("Error displaying chart", "danger");
        }
    },

    cleanup() {
        // Clear chart if it exists
        const chartElement = document.getElementById('aic_realtime_chart');
        if (chartElement) {
            Plotly.purge(chartElement);
        }
    },

    init() {
        console.log('Initializing AIC module');
        this.cleanup(); // Clean up before initializing
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