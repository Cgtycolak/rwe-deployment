import { postData, toggleLoading, displayMessage, isInvalidDuration } from '../utils/helpers.js';
import { getEndpoints } from '../config/endpoints.js';
import { THead } from '../classes/THead.js';
import { TBody } from '../classes/TBody.js';

export const realtime = {
    installed: false,
    _powerplants: null,
    _columns: null,
    _rows: null,
    optionsDisplayed: false,
    plotlyChart: null,
    orderedFuels: [
        "NG",
        "WIND",
        "LIGNITE",
        "HARDCOAL",
        "IMPORTCOAL",
        "FUELOIL",
        "HEPP",
        "ROR",
        "NAPHTHA",
        "BIO",
        "GEOTHERMAL"
    ],
    fuelMapping: {
        "NG": "dogalgaz",
        "WIND": "ruzgar",
        "LIGNITE": "linyit",
        "HARDCOAL": "tasKomur",
        "IMPORTCOAL": "ithalKomur",
        "FUELOIL": "fuelOil",
        "HEPP": "barajli",
        "ROR": "akarsu",
        "NAPHTHA": "nafta",
        "BIO": "biokutle",
        "GEOTHERMAL": "jeotermal"
    },

    set powerplants(reqAndRes) {
        this._powerplants = reqAndRes ? reqAndRes.data : null;
        if (this._powerplants) {
            const powerplantSelect = $("#powerplant_select");
            let optionsHtml = "";
            this._powerplants.forEach((plant) => {
                optionsHtml += `<option value="${plant.id}" title="${plant.name}">${plant.shortName || plant.name
                    }</option>`;
            });
            powerplantSelect.html(optionsHtml);

            if (!this.installed) {
                $("#realtime_args_content").show();
                this.installed = true;
            }
        }
    },

    get powerplants() {
        return this._powerplants;
    },

    set columns(cols) {
        if (cols) {
            // Always include these columns in this order
            const orderedColumns = ["PowerPlant", "DATE", "HOUR", "TOTAL"];
            const fuelOrder = [
                "NG",
                "HEPP",
                "LIGNITE",
                "ROR",
                "IMPORTCOAL",
                "WIND",
                "FUELOIL",
                "GEOTHERMAL",
                "HARDCOAL",
                "BIO",
                "NAPHTHA"
            ];

            // Add fuels in specified order
            const orderedFuelColumns = fuelOrder.filter(fuel => cols.includes(fuel));

            // Add any remaining columns except the ones we've already positioned
            const remainingColumns = cols.filter(col =>
                !orderedColumns.includes(col) &&
                !orderedFuelColumns.includes(col) &&
                !['date', 'DATE'].includes(col)
            );

            // Combine all columns in desired order
            this._columns = [...orderedColumns, ...orderedFuelColumns, ...remainingColumns];

            // Create table header
            const thead = $("#realtime_table thead");
            thead.empty();
            const headerRow = $("<tr>");

            // Add columns in the new order
            this._columns.forEach((col) => {
                headerRow.append($(`<th title="${col}">${col}</th>`));
            });
            thead.append(headerRow);
        } else {
            this._columns = null;
        }
    },

    get columns() {
        return this._columns;
    },

    set rows(data) {
        if (data && Array.isArray(data)) {
            // Process the rows to add DATE and ensure empty cells are 0.00
            this._rows = data.map(row => {
                // Create new row object
                const newRow = {};

                // First set all columns to their default values
                this._columns.forEach(col => {
                    if (col === 'PowerPlant') {
                        newRow[col] = row.PowerPlant || '';
                    } else if (col === 'HOUR') {
                        newRow[col] = row.HOUR || '';
                    } else if (col === 'DATE') {
                        // Extract date from the timestamp and ensure it's not empty
                        const timestamp = row.date || row.timestamp;
                        newRow[col] = timestamp ? timestamp.split('T')[0] : row.DATE; // Use current date as fallback
                    } else {
                        // All numeric columns default to '0.00'
                        newRow[col] = '0.00';
                    }
                });

                // Override with actual values where they exist
                Object.entries(row).forEach(([key, value]) => {
                    if (this._columns.includes(key)) {
                        if (key !== 'PowerPlant' && key !== 'HOUR' && key !== 'DATE') {
                            if (value !== null && value !== undefined && value !== '') {
                                newRow[key] = parseFloat(value).toFixed(2);
                            } else {
                                newRow[key] = '0.00';
                            }
                        }
                    }
                });

                return newRow;
            });

            // Create table body
            const tbody = $("#realtime_table tbody");
            tbody.empty();

            this._rows.forEach((row) => {
                const tr = $("<tr>");

                // Add cells in the correct order
                this._columns.forEach((col) => {
                    const val = row[col] || (col !== 'PowerPlant' && col !== 'HOUR' ? '0.00' : '');
                    tr.append($(`<td title="${val}">${val}</td>`));
                });

                tbody.append(tr);
            });
        } else {
            this._rows = null;
        }
    },

    get rows() {
        return this._rows;
    },

    displayChart: function (data, columns) {
        // First, reorder the columns
        const orderedColumns = ["HOUR", "TOTAL"];
        const fuelOrder = [
            "NG",
            "WIND",
            "LIGNITE",
            "HARDCOAL",
            "IMPORTCOAL",
            "FUELOIL",
            "HEPP",
            "ROR",
            "NAPHTHA",
            "BIO",
            "GEOTHERMAL"
        ];

        // Add fuels in specified order
        const orderedFuelColumns = fuelOrder.filter(fuel => columns.includes(fuel));

        // Add any remaining columns (like PowerPlant, Organization, etc)
        const remainingColumns = columns.filter(col =>
            !orderedFuelColumns.includes(col) &&
            !["HOUR", "TOTAL", "DATE", "PowerPlant"].includes(col)
        );

        // Combine all columns in desired order
        const finalColumns = [...orderedColumns, ...orderedFuelColumns, ...remainingColumns];

        // Filter out non-numeric and special columns for the chart
        const numericColumns = finalColumns.filter(
            (col) =>
                !["DATE", "date", "HOUR", "PowerPlant", "Organization", "UEVCB"].includes(col) &&
                data.some((row) => !isNaN(parseFloat(row[col])))
        );

        const traces = numericColumns.map((col) => ({
            type: "scatter",
            mode: "lines+markers",
            x: data.map((row) => row["HOUR"]),
            y: data.map((row) => parseFloat(row[col]) || 0),
            name: col,
        }));

        const layout = {
            title: "Power Generation by Type",
            xaxis: {
                title: "Hour",
                tickangle: -45,
            },
            yaxis: {
                title: "Generation (MW)",
            },
            showlegend: true,
            legend: {
                x: 1,
                xanchor: "right",
                y: 1,
            },
        };

        Plotly.newPlot("realtime_plotly_chart", traces, layout, {
            responsive: true,
        });
    },

    displaySummaryTable: function (data, columns) {
        // Get all available fuel types (excluding non-fuel columns)
        const availableFuelTypes = columns.filter(
            (col) => !["date", "HOUR", "PowerPlant", "Organization", "UEVCB", "TOTAL"].includes(col)
        );

        // Create fuel type buttons container with similar styling
        const buttonContainer = $("#realtime_fuel_buttons");
        buttonContainer.empty();
        buttonContainer.addClass("d-flex flex-wrap justify-content-start align-items-center p-2 mx-2 shadow");

        // Filter and sort fuels based on orderedFuels
        const displayFuels = this.orderedFuels.filter(fuel => availableFuelTypes.includes(fuel));

        // Create buttons for each fuel type
        displayFuels.forEach((fuel, index) => {
            const btnClass = index === 0 ? "btn-dark" : "btn-outline-dark";
            const button = $(`
                <button 
                    class="btn ${btnClass} btn-sm fuels_btns" 
                    data-fuel="${fuel}" 
                    data-selector=".fuels_btns" 
                    title="Click to display ordered Table For Fuel:${fuel}"
                >
                    ${fuel}
                </button>
            `);

            button.click((e) => {
                // Update button states
                $(".fuels_btns")
                    .removeClass("btn-dark")
                    .addClass("btn-outline-dark");
                $(e.target)
                    .removeClass("btn-outline-dark")
                    .addClass("btn-dark");

                // Display data for selected fuel
                this.displayFuelTypeData(data, fuel);
            });

            buttonContainer.append(button);
        });

        // Display initial fuel type data
        if (displayFuels.length > 0) {
            this.displayFuelTypeData(data, displayFuels[0]);
        }
    },

    displayFuelTypeData: function (data, fuelType) {
        const summaryTable = $("#realtime_fuel_types_table");
        summaryTable.empty();

        // Get unique dates and hours
        const dates = [...new Set(data.map((row) => row.DATE))].sort();
        const hours = [...new Set(data.map((row) => row.HOUR))].sort();

        // Create headers with tooltips
        const thead = $("<thead>").addClass("table-dark");
        const headerRow = $("<tr>");
        headerRow.append($("<th title='Power Plant'>Power Plant</th>"));
        headerRow.append($("<th title='Date'>Date</th>")); // Add date column
        headerRow.append($("<th title='Total'>Total</th>"));

        // Add hour columns
        hours.forEach((hour) => {
            headerRow.append($(`<th title='Hour ${hour}'>${hour}</th>`));
        });

        thead.append(headerRow);
        summaryTable.append(thead);

        // Group data by PowerPlant and Date
        const groupedData = {};
        data.forEach((row) => {
            const key = `${row.PowerPlant}_${row.DATE}`;
            if (!groupedData[key]) {
                groupedData[key] = {
                    PowerPlant: row.PowerPlant,
                    Date: row.DATE,
                    hours: {},
                    total: 0
                };
            }
            const value = parseFloat(row[fuelType]) || 0;
            groupedData[key].hours[row.HOUR] = value;
            groupedData[key].total += value;
        });

        // Create body with tooltips
        const tbody = $("<tbody>");
        Object.values(groupedData)
            .sort((a, b) => a.Date.localeCompare(b.Date))
            .forEach((group) => {
                const tr = $("<tr>");
                tr.append($(`<td class="org-name" title="${group.PowerPlant}">${group.PowerPlant}</td>`));
                tr.append($(`<td title="${group.Date}">${group.Date}</td>`));
                tr.append($(`<td title="${group.total.toFixed(2)}">${group.total.toFixed(2)}</td>`));

                // Get all values for this plant/date to determine min/max
                const hourValues = Object.values(group.hours).map(v => parseFloat(v) || 0);
                const minMax = this.getMaxAndMin(hourValues);

                hours.forEach((hour) => {
                    const value = group.hours[hour] || 0;
                    const background = this.getTableNumColor(value, minMax);
                    const style = background ? ` style="background:${background};"` : '';
                    tr.append($(`<td title="${value.toFixed(2)}"${style}>${value.toFixed(2)}</td>`));
                });

                tbody.append(tr);
            });

        summaryTable.append(tbody);
    },

    async loadPowerPlants(app) {
        try {
            this.powerplants = null;
            // toggleLoading(true);
            displayMessage();

            const endpoints = getEndpoints();
            const res = await $.ajax({
                url: endpoints.getPowerPlants,
                type: 'GET',
                dataType: 'json',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (res && res.code === 200 && Array.isArray(res.data)) {
                this.powerplants = res;

                // Update select with power plants
                const powerplantSelect = $("#powerplant_select");
                let optionsHtml = "";
                res.data.forEach((plant) => {
                    optionsHtml += `<option value="${plant.id}" title="${plant.name}">${plant.shortName || plant.name}</option>`;
                });
                powerplantSelect.html(optionsHtml);

                if (!this.installed) {
                    $("#realtime_args_content").show();
                    this.installed = true;
                }
            } else {
                displayMessage(res.message || "Unable to load power plants", "danger");
            }
            // toggleLoading(false);
        } catch (error) {
            console.error("loadPowerPlants Error", error);
            displayMessage("System error while loading power plants.", "danger");
            // toggleLoading(false);
        }
    },

    async getRealtimeData(app) {
        try {
            const powerplantSelect = $("#powerplant_select");
            const selectedPlants = powerplantSelect.val();

            if (!selectedPlants || selectedPlants.length === 0) {
                displayMessage("Please select at least one power plant", "warning");
                return;
            }

            // Check if we have valid dates
            const durationError = isInvalidDuration(app.global.start, app.global.end);
            if (durationError) {
                displayMessage(durationError, "warning");
                return;
            }

            // Check if end date is today or in the future
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const endDate = new Date(app.global.end);
            if (endDate >= today) {
                displayMessage("Only data up to one day before the current date can be viewed for realtime data.", "warning");
                return;
            }

            // toggleLoading(true);
            displayMessage();

            const reqData = {
                powerPlantId: selectedPlants[0].toString(),
                start: app.global.start,
                end: app.global.end,
            };

            // Get endpoints here
            const endpoints = getEndpoints();
            const res = await postData(endpoints.getRealtimeData, reqData);

            if (res.code === 200 && res.data) {
                // Store data in app state
                this.columns = res.columns;
                this.rows = res.data;

                // Hide all views first
                $(".switch_arg[data-group='realtime_nested']").hide();

                // Show summary view by default
                $(".switch_arg[data-switch='realtime_fuel_types']").show();

                // Display all views
                this.displayChart(res.data, res.columns);
                this.displaySummaryTable(res.data, res.columns);

                // If DPP data is available, show the difference chart
                if (app.dpp && app.dpp._rows) {
                    this.displayDifferenceChart(app.dpp._rows, res.data);
                }

                // Display main table
                new THead(res.columns, "#realtime_table");
                new TBody(res.data, "#realtime_table", res.columns);

                // Show options and container first time
                if (!this.optionsDisplayed) {
                    $(".realtime_options").show();
                    this.optionsDisplayed = true;
                }

                // Remove any existing click handlers first
                $(".btn[data-switch]").off('click');

                // Add click handlers for the view switches
                $(".btn[data-switch]").on('click', function () {
                    const targetView = $(this).data('switch');
                    const targetGroup = $(this).data('group');

                    // Only affect buttons and views in the same group
                    if (targetGroup) {
                        // Hide all views in this group
                        $(`.switch_arg[data-group='${targetGroup}']`).hide();

                        // Show selected view
                        $(`.switch_arg[data-switch='${targetView}']`).show();

                        // Update button states within the same group
                        $(`.btn[data-group='${targetGroup}']`)
                            .removeClass('btn-primary')
                            .addClass('btn-outline-primary');

                        $(this)
                            .removeClass('btn-outline-primary')
                            .addClass('btn-primary');
                    }
                });

            } else {
                displayMessage(res.message || "Unable to load realtime data", "danger");
            }
            // toggleLoading(false);
        } catch (error) {
            console.error("getRealtimeData Error", error);
            displayMessage("System error while loading realtime data.", "danger");
            // toggleLoading(false);
        }
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
            /* small */
            return "#ffcdcd";
        } else if (num !== 0 && num === minAndMax.max && num !== minAndMax.min) {
            /* large */
            return "#b9ffb9";
        } else if (num > 0 && num > minAndMax.min && num < minAndMax.max) {
            /* between */
            return "#a5fff4";
        } else {
            return "";
        }
    },

    displayDifferenceChart: function (dppData, realtimeData) {
        // Prepare data for the difference chart
        const differences = [];
        
        // Get unique dates from both datasets
        const dates = [...new Set([
            ...dppData.map(d => d.DATE),
            ...realtimeData.map(d => d.DATE)
        ])].sort();

        // For each date and hour combination
        dates.forEach(date => {
            // Create 24 hours for each date
            [...Array(24).keys()].forEach(h => {
                const hour = `${h.toString().padStart(2, '0')}:00`;
                
                // Find matching records for this date and hour
                const dppRecord = dppData.find(d => d.DATE === date && d.HOUR === hour);
                const realtimeRecord = realtimeData.find(d => d.DATE === date && d.HOUR === hour);
                
                const dppValue = dppRecord ? parseFloat(dppRecord.TOTAL) || 0 : 0;
                const realtimeValue = realtimeRecord ? parseFloat(realtimeRecord.TOTAL) || 0 : 0;
                
                differences.push({
                    datetime: `${date} ${hour}`,
                    date: date,
                    hour: hour,
                    difference: realtimeValue - dppValue,
                    dppValue: dppValue,
                    realtimeValue: realtimeValue
                });
            });
        });

        // Create the bar chart using Plotly
        const trace = {
            x: differences.map(d => d.datetime),
            y: differences.map(d => d.difference),
            type: 'bar',
            name: 'Realtime - DPP Difference',
            hovertemplate: 
                '<b>Date:</b> %{customdata.date}<br>' +
                '<b>Hour:</b> %{customdata.hour}<br>' +
                '<b>Difference:</b> %{y:.2f} MW<br>' +
                '<b>Realtime:</b> %{customdata.realtime:.2f} MW<br>' +
                '<b>DPP:</b> %{customdata.dpp:.2f} MW<br>' +
                '<extra></extra>',
            customdata: differences.map(d => ({
                date: d.date,
                hour: d.hour,
                realtime: d.realtimeValue,
                dpp: d.dppValue
            })),
            marker: {
                color: differences.map(d => d.difference > 0 ? 'rgba(0, 128, 0, 0.7)' : 'rgba(200, 20, 50, 0.7)')
            }
        };

        const layout = {
            title: {
                text: 'Difference between Realtime and Planned Generation',
                font: {
                    size: 24
                },
                y: 0.97,
                x: 0.5,
                xanchor: 'center',
                yanchor: 'top'
            },
            xaxis: {
                title: 'Date and Hour',
                tickangle: -45,
                tickformat: '%Y-%m-%d %H:%M',
                tickmode: 'auto',
                nticks: 24,
                rangeslider: {
                    visible: true,
                    thickness: 0.1
                },
                domain: [0, 1],
                automargin: true,
                fixedrange: false
            },
            yaxis: {
                title: 'Difference (MW)',
                zeroline: true,
                zerolinecolor: 'gray',
                zerolinewidth: 1,
                automargin: true,
                fixedrange: false
            },
            barmode: 'relative',
            showlegend: true,
            legend: {
                x: 1.0,
                y: 1.0,
                xanchor: 'right',
                yanchor: 'top',
                bgcolor: 'rgba(255, 255, 255, 0.8)',
                bordercolor: 'lightgray',
                borderwidth: 1
            },
            margin: {
                l: 80,
                r: 30,
                t: 100,
                b: 80,
                pad: 0
            },
            updatemenus: [{
                type: 'buttons',
                showactive: true,
                x: 0,
                y: 1.12,
                xanchor: 'left',
                yanchor: 'top',
                bgcolor: 'white',
                bordercolor: '#c7c7c7',
                borderwidth: 1,
                buttons: [{
                    label: '1 Day',
                    method: 'relayout',
                    args: ['xaxis.range', [
                        differences[0].datetime,
                        differences[23].datetime
                    ]]
                }, {
                    label: 'All Days',
                    method: 'relayout',
                    args: ['xaxis.range', [
                        differences[0].datetime,
                        differences[differences.length - 1].datetime
                    ]]
                }]
            }],
            annotations: [{
                text: 'Green: Realtime > Planned | Red: Realtime < Planned',
                showarrow: false,
                x: 0,
                y: 1.05,
                xref: 'paper',
                yref: 'paper',
                font: {
                    size: 12,
                    color: 'gray'
                }
            }],
            autosize: true
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtons: [[
                'zoom2d',
                'pan2d',
                'resetScale2d',
                'toImage'
            ]],
            displaylogo: false,
            toImageButtonOptions: {
                format: 'png',
                filename: 'difference_chart',
                height: 800,
                width: 1200,
                scale: 2
            },
            fillContainer: true
        };

        // Update trace for better visibility
        trace.marker.line = {
            width: 1,
            color: 'rgba(0,0,0,0.3)'
        };

        // Create the plot
        Plotly.newPlot('difference_chart', [trace], layout, config);

        // Function to properly size the chart
        const resizeChart = () => {
            const container = document.querySelector('.difference-chart-container');
            if (container) {
                const width = container.clientWidth;
                const height = container.clientHeight;
                
                Plotly.relayout('difference_chart', {
                    width: width,
                    height: height
                });
            }
        };

        // Remove any existing resize listener
        window.removeEventListener('resize', resizeChart);
        
        // Add resize listener
        window.addEventListener('resize', resizeChart);
        
        // Initial resize with a delay to ensure container is ready
        setTimeout(resizeChart, 50);
    }
};
