export const generationComparison = {
    currentRange: 'daily',
    chart: null,
    plotlyColorScale: "RdBu",
    plotlyConfig: { responsive: true },

    setup(helpers) {
        console.log('Setting up generation comparison module with helpers');
        this.helpers = helpers;
    },

    init() {
        console.log('Initializing generation comparison module');
        this.cleanup(); // Clean up before initializing
        try {
            this.setupEventListeners();
            this.setupDefaultDates();
            
            // Ensure correct initial view is shown
            const activeButton = document.querySelector('[data-group="comparison_view"].active');
            if (activeButton) {
                const targetView = activeButton.dataset.switch;
                // Hide all views
                document.querySelectorAll('.switch_arg[data-group="comparison_view"]').forEach(view => {
                    view.style.display = 'none';
                });
                // Show active view
                const activeView = document.querySelector(`.switch_arg[data-switch="${targetView}"]`);
                if (activeView) {
                    activeView.style.display = 'block';
                }
            }
        } catch (error) {
            console.error('Error during initialization:', error);
        }
    },

    setupDefaultDates() {
        console.log('Setting up default dates');
        const startInput = document.getElementById('comparison_start_date');
        const endInput = document.getElementById('comparison_end_date');
        
        if (!startInput || !endInput) {
            console.error('Date inputs not found. Skipping default date setup.');
            return;
        }

        // Set default date range (last 7 days)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7);

        // Format dates for input fields
        const formatDate = (date) => {
            return date.toISOString().split('T')[0];
        };

        startInput.value = formatDate(startDate);
        endInput.value = formatDate(endDate);

        // Load initial data only if table exists
        if (document.getElementById('comparison_fuel_types_table')) {
            this.loadData(formatDate(startDate), formatDate(endDate));
        }
    },

    setupEventListeners() {
        console.log('Setting up event listeners');
        try {
            // Range button clicks
            const rangeButtons = document.querySelectorAll('.comparison-range-btn');
            console.log('Found range buttons:', rangeButtons.length);
            
            // Date inputs
            const startDateInput = document.getElementById('comparison_start_date');
            const endDateInput = document.getElementById('comparison_end_date');
            
            // Add date validation
            if (startDateInput && endDateInput) {
                startDateInput.addEventListener('change', () => this.validateDates());
                endDateInput.addEventListener('change', () => this.validateDates());
            }
            
            rangeButtons.forEach(button => {
                button.addEventListener('click', (e) => {
                    console.log('Range button clicked:', e.target.dataset.range);
                    // Update buttons
                    document.querySelectorAll('.comparison-range-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    e.target.classList.add('active');
                    
                    // Update current range and validate dates
                    this.currentRange = e.target.dataset.range;
                    this.validateDates();
                    
                    // Reload data if dates are valid
                    const startDate = startDateInput.value;
                    const endDate = endDateInput.value;
                    if (startDate && endDate && this.validateDates()) {
                        this.loadData(startDate, endDate);
                    }
                });
            });

            // Load data button
            const loadButton = document.getElementById('load_comparison_data');
            if (loadButton) {
                console.log('Found load data button');
                loadButton.addEventListener('click', () => {
                    if (!this.validateDates()) {
                        return;
                    }
                    
                    const startDate = startDateInput.value;
                    const endDate = endDateInput.value;
                    
                    // Show loading state
                    const loadingIndicator = document.getElementById('comparison_loading');
                    if (loadingIndicator) loadingIndicator.style.display = 'block';
                    
                    this.loadData(startDate, endDate);
                });
            }

            // View switcher events
            document.querySelectorAll('[data-group="comparison_view"]').forEach(button => {
                button.addEventListener('click', (e) => {
                    const targetView = e.target.closest('button').dataset.switch;
                    
                    // Update active button
                    document.querySelectorAll('[data-group="comparison_view"]').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    e.target.closest('button').classList.add('active');

                    // Show/hide views
                    document.querySelectorAll('.switch_arg[data-group="comparison_view"]').forEach(view => {
                        view.style.display = 'none';
                    });
                    const targetElement = document.querySelector(`.switch_arg[data-switch="${targetView}"]`);
                    if (targetElement) {
                        targetElement.style.display = 'block';
                    }

                    // Update view with existing data if available
                    if (this.lastData) {
                        switch (targetView) {
                            case 'comparison_chart':
                                this.updateChart(this.lastData);
                                break;
                            case 'comparison_fuel_types':
                                this.updateDPPTable(this.lastData.dpp.items);
                                this.updateRealtimeTable(this.lastData.realtime.items);
                                break;
                            case 'comparison_differences':
                                this.updateDifferencesTable(this.lastData.differences.items);
                                break;
                        }
                    }
                });
            });

            // Show initial view
            const initialView = document.querySelector('.switch_arg[data-group="comparison_view"]');
            if (initialView) {
                initialView.style.display = 'block';
            }

            // Add export button listener
            const exportButton = document.getElementById('download_comparison_excel');
            if (exportButton) {
                exportButton.addEventListener('click', () => this.downloadExcel());
            }

        } catch (error) {
            console.error('Error setting up event listeners:', error);
        }
    },

    async loadData(startDate, endDate) {
        const loadingIndicator = document.getElementById('comparison_loading');
        const loadButton = document.getElementById('load_comparison_data');
        const normalState = loadButton?.querySelector('.normal-state');
        const loadingState = loadButton?.querySelector('.loading-state');
        
        try {
            // Show loading states
            if (loadingIndicator) loadingIndicator.style.display = 'block';
            if (loadButton) {
                loadButton.disabled = true;
                normalState.style.display = 'none';
                loadingState.style.display = 'inline-block';
            }
            
            if (!this.validateDates()) {
                throw new Error('Invalid date range');
            }

            const start = new Date(startDate);
            const end = new Date(endDate);
            const diffInMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());

            // // For yearly view, proceed normally
            // if (this.currentRange === 'yearly') {
            //     const data = await this.fetchAndProcessData(startDate, endDate);
            //     this.updateViews(data);
            //     return;
            // }

            // For other ranges, check if date range exceeds 3 months
            if (diffInMonths > 3) {
                let currentStart = new Date(start);
                let allData = {
                    dpp: { items: [] },
                    realtime: { items: [] },
                    differences: { items: [] }
                };

                while (currentStart < end) {
                    // Calculate chunk end date (3 months from current start or final end date)
                    let chunkEnd = new Date(currentStart);
                    chunkEnd.setMonth(chunkEnd.getMonth() + 3);
                    if (chunkEnd > end) {
                        chunkEnd = end;
                    } else {
                        // Subtract one day to avoid overlap
                        chunkEnd.setDate(chunkEnd.getDate() - 1);
                    }

                    // Format dates for API
                    const chunkStartStr = currentStart.toISOString().split('T')[0];
                    const chunkEndStr = chunkEnd.toISOString().split('T')[0];

                    // Fetch data for this chunk
                    const chunkData = await this.fetchAndProcessData(chunkStartStr, chunkEndStr);
                    
                    // Combine the data
                    if (chunkData) {
                        allData.dpp.items = [...allData.dpp.items, ...chunkData.dpp.items];
                        allData.realtime.items = [...allData.realtime.items, ...chunkData.realtime.items];
                        allData.differences.items = [...allData.differences.items, ...chunkData.differences.items];
                    }

                    // Move to next chunk (start from the next day)
                    currentStart = new Date(chunkEnd);
                    currentStart.setDate(currentStart.getDate() + 1);
                }

                // Deduplicate data
                ['dpp', 'realtime', 'differences'].forEach(key => {
                    allData[key].items = this.deduplicateItems(allData[key].items);
                    
                    // Sort by date and hour
                    allData[key].items.sort((a, b) => {
                        const dateCompare = new Date(a.date) - new Date(b.date);
                        if (dateCompare === 0) {
                            return (a.hour || a.time).localeCompare(b.hour || b.time);
                        }
                        return dateCompare;
                    });
                });

                this.updateViews(allData);
            } else {
                // For ranges within 3 months, proceed normally
                const data = await this.fetchAndProcessData(startDate, endDate);
                this.updateViews(data);
            }

        } catch (error) {
            console.error('Error loading data:', error);
            this.helpers.displayMessage(`Error loading data: ${error.message}`, 'danger');
        } finally {
            // Reset loading states
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            if (loadButton) {
                loadButton.disabled = false;
                normalState.style.display = 'inline-block';
                loadingState.style.display = 'none';
            }
        }
    },

    async fetchAndProcessData(startDate, endDate) {
        console.log('Fetching data for:', { startDate, endDate, range: this.currentRange });
        
        try {
            // Add request details logging
            const requestBody = {
                start: startDate,
                end: endDate
            };
            console.log('Request body:', requestBody);

            const response = await fetch(`/api/generation-comparison?range=${this.currentRange}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            // Log response status and headers
            console.log('Response status:', response.status);
            console.log('Response headers:', Object.fromEntries(response.headers.entries()));

            if (!response.ok) {
                // Try to get error details from response
                let errorDetails = '';
                try {
                    const errorData = await response.json();
                    errorDetails = errorData.message || errorData.error || '';
                } catch (e) {
                    errorDetails = await response.text();
                }
                
                throw new Error(`Failed to fetch data: ${response.status}. Details: ${errorDetails}`);
            }

            const data = await response.json();
            console.log('Response data:', data);

            if (data.code !== 200) {
                throw new Error(data.message || 'Failed to load data');
            }

            return data.data;
        } catch (error) {
            console.error('Fetch error details:', {
                message: error.message,
                stack: error.stack,
                range: this.currentRange,
                startDate,
                endDate
            });
            throw error;
        }
    },

    updateChart(data) {
        if (!data || !data.differences || !data.differences.items) {
            console.error('Invalid data for chart');
            return;
        }

        const items = data.differences.items;
        
        // Define fuel types to show (in order)
        const fuelTypes = [
            'naturalGas',
            'wind',
            'lignite',
            'importCoal',
            'fueloil',
            'geothermal',
            'dammedHydro',
            'naphta',
            'biomass',
            'river'
        ];

        // Create traces for each fuel type
        const traces = fuelTypes.map(fuelType => ({
            type: 'scatter',
            mode: 'lines+markers',
            name: fuelType,
            x: items.map(item => `${item.date} ${item.hour}`),
            y: items.map(item => item[fuelType] || 0),
            hovertemplate: `%{x}<br>${fuelType}: %{y:.2f}<extra></extra>`
        }));

        // Add total difference trace
        traces.unshift({
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Total Difference',
            x: items.map(item => `${item.date} ${item.hour}`),
            y: items.map(item => item.total),
            line: { color: 'black', width: 2 },
            hovertemplate: 'Total: %{y:.2f}<extra></extra>'
        });

        const layout = {
            title: 'Generation Comparison by Fuel Type',
            height: 700,
            xaxis: {
                title: 'Date & Hour',
                tickangle: -45
            },
            yaxis: {
                title: 'Difference (MWh)'
            },
            showlegend: true,
            legend: {
                orientation: 'h',
                y: -0.2
            },
            hovermode: 'closest'
        };

        Plotly.newPlot('generation_comparison_chart', traces, layout, this.plotlyConfig);
    },

    getMaxAndMin(values) {
        const nonZeroValues = values.filter(val => val !== 0);
        return {
            min: nonZeroValues.length > 0 ? Math.min(...nonZeroValues) : 0,
            max: nonZeroValues.length > 0 ? Math.max(...nonZeroValues) : 0
        };
    },

    getTableNumColor(num, minAndMax) {
        if (num !== 0 && num === minAndMax.min && num !== minAndMax.max) {
            /* small - soft red */
            return "rgba(255, 99, 132, 0.3)";  // Red with 30% opacity
        } else if (num !== 0 && num === minAndMax.max && num !== minAndMax.min) {
            /* large - stronger green */
            return "rgba(40, 167, 69, 0.4)";   // Bootstrap success green with 40% opacity
        } else if (num > 0 && num > minAndMax.min && num < minAndMax.max) {
            /* between - soft blue */
            return "rgba(54, 162, 235, 0.25)";  // Blue with 25% opacity
        } else {
            return "";
        }
    },

    validateDates() {
        const startDateInput = document.getElementById('comparison_start_date');
        const endDateInput = document.getElementById('comparison_end_date');
        const loadButton = document.getElementById('load_comparison_data');
        
        if (!startDateInput || !endDateInput) return false;

        const start = new Date(startDateInput.value);
        const end = new Date(endDateInput.value);
        const today = new Date();
        
        // Clear previous validation styles
        startDateInput.classList.remove('is-invalid');
        endDateInput.classList.remove('is-invalid');
        
        let isValid = true;
        let errorMessage = '';

        // Basic validation
        if (!startDateInput.value || !endDateInput.value) {
            errorMessage = 'Please select both start and end dates';
            isValid = false;
        }
        // End date should not be in the future
        else if (end > today) {
            endDateInput.classList.add('is-invalid');
            errorMessage = 'End date cannot be in the future';
            isValid = false;
        }
        // Start date should be before end date
        else if (start > end) {
            startDateInput.classList.add('is-invalid');
            endDateInput.classList.add('is-invalid');
            errorMessage = 'Start date must be before end date';
            isValid = false;
        }
        // Range-specific validations
        else {
            const diffInMonths = (end.getFullYear() - start.getFullYear()) * 12 
                + (end.getMonth() - start.getMonth());
            
            // switch (this.currentRange) {
            //     case 'daily':
            //     case 'weekly':
            //     case 'monthly':
            //         // if (diffInMonths > 3) {
            //         //     // Don't set isValid to false as we'll handle this in loadData
            //         // }
            //         // break;
            //     case 'yearly':
            //         // if (diffInMonths < 12) {
            //         //     errorMessage = 'Yearly view requires at least 12 months of data';
            //         //     isValid = false;
            //         // }
            //         // break;
            // }
        }

        // Update UI
        if (errorMessage) {
            this.helpers.displayMessage(errorMessage, isValid ? 'info' : 'warning');
        }
        
        // Enable/disable load button
        if (loadButton) {
            loadButton.disabled = !isValid;
        }

        return isValid;
    },

    cleanup() {
        // Clear chart if it exists
        const chartElement = document.getElementById('generation_comparison_chart');
        if (chartElement) {
            Plotly.purge(chartElement);
        }
    },

    updateDPPTable(items) {
        const table = document.getElementById('dpp_data_table');
        if (!table) {
            console.error('DPP table element not found');
            return;
        }
        
        const tbody = table.querySelector('tbody');
        if (!tbody) {
            console.error('DPP table body not found');
            return;
        }

        tbody.innerHTML = '';
        
        if (!Array.isArray(items)) {
            console.error('Invalid DPP items data:', items);
            return;
        }

        // Get min and max values for each column
        const columns = ['toplam', 'dogalgaz', 'ruzgar', 'linyit', 'ithalKomur', 
                        'fuelOil', 'jeotermal', 'barajli', 'nafta', 'biokutle', 'akarsu'];
        const columnStats = {};
        
        columns.forEach(col => {
            const values = items.map(item => parseFloat(item[col] || 0));
            columnStats[col] = this.getMaxAndMin(values);
        });

        items.forEach(item => {
            if (!item) return;
            const formatted = this.formatDateTime(item.date, item.hour);
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatted.date}</td>
                <td>${formatted.hour}</td>
                <td style="background-color: ${this.getTableNumColor(item.toplam, columnStats.toplam)}; 
                           color: #000;
                           font-weight: 500;">${(item.toplam || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.dogalgaz, columnStats.dogalgaz)}; 
                           color: #000;
                           font-weight: 500;">${(item.dogalgaz || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.ruzgar, columnStats.ruzgar)}; 
                           color: #000;
                           font-weight: 500;">${(item.ruzgar || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.linyit, columnStats.linyit)}; 
                           color: #000;
                           font-weight: 500;">${(item.linyit || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.ithalKomur, columnStats.ithalKomur)}; 
                           color: #000;
                           font-weight: 500;">${(item.ithalKomur || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.fuelOil, columnStats.fuelOil)}; 
                           color: #000;
                           font-weight: 500;">${(item.fuelOil || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.jeotermal, columnStats.jeotermal)}; 
                           color: #000;
                           font-weight: 500;">${(item.jeotermal || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.barajli, columnStats.barajli)}; 
                           color: #000;
                           font-weight: 500;">${(item.barajli || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.nafta, columnStats.nafta)}; 
                           color: #000;
                           font-weight: 500;">${(item.nafta || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.biokutle, columnStats.biokutle)}; 
                           color: #000;
                           font-weight: 500;">${(item.biokutle || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.akarsu, columnStats.akarsu)}; 
                           color: #000;
                           font-weight: 500;">${(item.akarsu || 0).toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
    },

    updateRealtimeTable(items) {
        const table = document.getElementById('realtime_data_table');
        if (!table) {
            console.error('Realtime table element not found');
            return;
        }
        
        const tbody = table.querySelector('tbody');
        if (!tbody) {
            console.error('Realtime table body not found');
            return;
        }
        
        tbody.innerHTML = '';
        
        if (!Array.isArray(items)) {
            console.error('Invalid realtime items data:', items);
            return;
        }

        // Get min and max values for each column
        const columns = ['total', 'naturalGas', 'wind', 'lignite', 'importCoal', 
                        'fueloil', 'geothermal', 'dammedHydro', 'naphta', 'biomass', 'river'];
        const columnStats = {};
        
        columns.forEach(col => {
            const values = items.map(item => parseFloat(item[col] || 0));
            columnStats[col] = this.getMaxAndMin(values);
        });
        
        items.forEach(item => {
            if (!item) return;
            const formatted = this.formatDateTime(item.date, item.hour);
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatted.date}</td>
                <td>${formatted.hour}</td>
                <td style="background-color: ${this.getTableNumColor(item.total, columnStats.total)}; 
                           color: #000;
                           font-weight: 500;">${(item.total || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.naturalGas, columnStats.naturalGas)}; 
                           color: #000;
                           font-weight: 500;">${(item.naturalGas || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.wind, columnStats.wind)}; 
                           color: #000;
                           font-weight: 500;">${(item.wind || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.lignite, columnStats.lignite)}; 
                           color: #000;
                           font-weight: 500;">${(item.lignite || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.importCoal, columnStats.importCoal)}; 
                           color: #000;
                           font-weight: 500;">${(item.importCoal || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.fueloil, columnStats.fueloil)}; 
                           color: #000;
                           font-weight: 500;">${(item.fueloil || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.geothermal, columnStats.geothermal)}; 
                           color: #000;
                           font-weight: 500;">${(item.geothermal || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.dammedHydro, columnStats.dammedHydro)}; 
                           color: #000;
                           font-weight: 500;">${(item.dammedHydro || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.naphta, columnStats.naphta)}; 
                           color: #000;
                           font-weight: 500;">${(item.naphta || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.biomass, columnStats.biomass)}; 
                           color: #000;
                           font-weight: 500;">${(item.biomass || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.river, columnStats.river)}; 
                           color: #000;
                           font-weight: 500;">${(item.river || 0).toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
    },

    updateDifferencesTable(items) {
        const table = document.getElementById('comparison_differences_table');
        if (!table) {
            console.error('Differences table element not found');
            return;
        }
        
        const tbody = table.querySelector('tbody');
        if (!tbody) {
            console.error('Differences table body not found');
            return;
        }
        
        tbody.innerHTML = '';
        
        if (!Array.isArray(items)) {
            console.error('Invalid differences items data:', items);
            return;
        }
        
        // Get min and max values for each column
        const columns = ['total', 'naturalGas', 'wind', 'lignite', 'importCoal', 
                        'fueloil', 'geothermal', 'dammedHydro', 'naphta', 'biomass', 'river'];
        const columnStats = {};
        
        columns.forEach(col => {
            const values = items.map(item => parseFloat(item[col] || 0));
            columnStats[col] = this.getMaxAndMin(values);
        });

        items.forEach(item => {
            if (!item) return;
            
            const formatted = this.formatDateTime(item.date, item.hour);
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatted.date}</td>
                <td>${formatted.hour}</td>
                <td style="background-color: ${this.getTableNumColor(item.total, columnStats.total)}; 
                           color: #000;
                           font-weight: 500;">${(item.total || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.naturalGas, columnStats.naturalGas)}; 
                           color: #000;
                           font-weight: 500;">${(item.naturalGas || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.wind, columnStats.wind)}; 
                           color: #000;
                           font-weight: 500;">${(item.wind || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.lignite, columnStats.lignite)}; 
                           color: #000;
                           font-weight: 500;">${(item.lignite || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.importCoal, columnStats.importCoal)}; 
                           color: #000;
                           font-weight: 500;">${(item.importCoal || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.fueloil, columnStats.fueloil)}; 
                           color: #000;
                           font-weight: 500;">${(item.fueloil || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.geothermal, columnStats.geothermal)}; 
                           color: #000;
                           font-weight: 500;">${(item.geothermal || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.dammedHydro, columnStats.dammedHydro)}; 
                           color: #000;
                           font-weight: 500;">${(item.dammedHydro || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.naphta, columnStats.naphta)}; 
                           color: #000;
                           font-weight: 500;">${(item.naphta || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.biomass, columnStats.biomass)}; 
                           color: #000;
                           font-weight: 500;">${(item.biomass || 0).toFixed(2)}</td>
                <td style="background-color: ${this.getTableNumColor(item.river, columnStats.river)}; 
                           color: #000;
                           font-weight: 500;">${(item.river || 0).toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
    },

    // Helper method to update all views
    updateViews(data) {
        if (!data) return;
        
        if (data.dpp?.items) this.updateDPPTable(data.dpp.items);
        if (data.realtime?.items) this.updateRealtimeTable(data.realtime.items);
        if (data.differences?.items) this.updateDifferencesTable(data.differences.items);
        
        if (document.querySelector('.switch_arg[data-switch="comparison_chart"]').style.display !== 'none') {
            this.updateChart(data);
        }
        
        this.lastData = data;
    },

    formatDateTime(date, hour) {
        // Create a date object and adjust for timezone
        let dateObj;
        
        if (date.includes('T')) {
            // For ISO format with timezone (e.g., "2024-12-31T00:00:00+03:00")
            dateObj = new Date(date);
        } else {
            // For simple date format (e.g., "2024-12-31")
            dateObj = new Date(`${date}T00:00:00+03:00`);
        }
        
        // Format the hour
        let hourFormatted;
        if (hour) {
            // If hour is provided directly (e.g., "09:00" or "9")
            hourFormatted = hour.length <= 2 ? hour.padStart(2, '0') + ':00' : hour;
        } else if (date.includes('T')) {
            // Extract hour from ISO timestamp
            const timePart = date.split('T')[1];
            hourFormatted = timePart.substring(0, 5); // Gets "HH:mm"
        } else {
            // Default to "00:00" if no hour information is available
            hourFormatted = '00:00';
        }

        // Format the date (keeping the original date part)
        const formattedDate = date.includes('T') ? 
            date.split('T')[0] : 
            date;

        return {
            date: formattedDate,
            hour: hourFormatted
        };
    },

    deduplicateItems(items) {
        const seen = new Set();
        return items.filter(item => {
            const key = `${item.date}_${item.hour || item.time || '00:00'}`;
            if (seen.has(key)) {
                return false;
            }
            seen.add(key);
            return true;
        });
    },

    downloadExcel() {
        try {
            if (!this.lastData) {
                this.helpers.displayMessage("No data available to download", "warning");
                return;
            }

            // Create workbook
            const wb = XLSX.utils.book_new();

            // Add DPP Data sheet
            if (this.lastData.dpp?.items) {
                const dppWs = XLSX.utils.json_to_sheet(this.lastData.dpp.items.map(item => {
                    const formatted = this.formatDateTime(item.date, item.hour);
                    return {
                        Date: formatted.date,
                        Hour: formatted.hour,
                        Total: item.toplam || 0,
                        "Natural Gas": item.dogalgaz || 0,
                        Wind: item.ruzgar || 0,
                        Lignite: item.linyit || 0,
                        "Import Coal": item.ithalKomur || 0,
                        "Fuel Oil": item.fuelOil || 0,
                        Geothermal: item.jeotermal || 0,
                        "Dammed Hydro": item.barajli || 0,
                        Naphtha: item.nafta || 0,
                        Biomass: item.biokutle || 0,
                        River: item.akarsu || 0
                    };
                }));
                XLSX.utils.book_append_sheet(wb, dppWs, "DPP Data");
            }

            // Add Realtime Data sheet
            if (this.lastData.realtime?.items) {
                const realtimeWs = XLSX.utils.json_to_sheet(this.lastData.realtime.items.map(item => {
                    const formatted = this.formatDateTime(item.date, item.hour);
                    return {
                        Date: formatted.date,
                        Hour: formatted.hour,
                        Total: item.total || 0,
                        "Natural Gas": item.naturalGas || 0,
                        Wind: item.wind || 0,
                        Lignite: item.lignite || 0,
                        "Import Coal": item.importCoal || 0,
                        "Fuel Oil": item.fueloil || 0,
                        Geothermal: item.geothermal || 0,
                        "Dammed Hydro": item.dammedHydro || 0,
                        Naphtha: item.naphta || 0,
                        Biomass: item.biomass || 0,
                        River: item.river || 0
                    };
                }));
                XLSX.utils.book_append_sheet(wb, realtimeWs, "Realtime Data");
            }

            // Add Differences sheet
            if (this.lastData.differences?.items) {
                const differencesWs = XLSX.utils.json_to_sheet(this.lastData.differences.items.map(item => {
                    const formatted = this.formatDateTime(item.date, item.hour);
                    return {
                        Date: formatted.date,
                        Hour: formatted.hour,
                        Total: item.total || 0,
                        "Natural Gas": item.naturalGas || 0,
                        Wind: item.wind || 0,
                        Lignite: item.lignite || 0,
                        "Import Coal": item.importCoal || 0,
                        "Fuel Oil": item.fueloil || 0,
                        Geothermal: item.geothermal || 0,
                        "Dammed Hydro": item.dammedHydro || 0,
                        Naphtha: item.naphta || 0,
                        Biomass: item.biomass || 0,
                        River: item.river || 0
                    };
                }));
                XLSX.utils.book_append_sheet(wb, differencesWs, "Differences");
            }

            // Generate filename with current date and range
            const date = new Date().toISOString().split('T')[0];
            const filename = `generation_comparison_${this.currentRange}_${date}.xlsx`;

            // Save file
            XLSX.writeFile(wb, filename);
        } catch (error) {
            console.error("Error downloading Excel:", error);
            this.helpers.displayMessage("Error generating Excel file", "danger");
        }
    }
}; 