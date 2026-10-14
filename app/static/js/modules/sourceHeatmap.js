// Generation by Source heatmap: system-wide DPP first/final versions vs realtime,
// one column per source. Mirrors ligniteHeatmap.js, with three differences:
// - absolute views colour each column against its own min/max, since sources
//   range from ~0 MW (naphta) to ~12,000 MW (solar) and one scale would wash
//   the small ones out;
// - hours without data are null and render as blank, never as zero;
// - solar hours whose unlicensed part is Meteologica's forecast are marked "*".
const DIFF_VERSIONS = ['difference', 'realtime_difference', 'date_comparison'];
// Smallest MW range a column is coloured across in the absolute views
const MIN_SPAN_MW = 100;

const ELEMENT_IDS = {
    first: 'source_heatmap_first_version',
    current: 'source_heatmap_current',
    difference: 'source_heatmap_difference',
    realtime: 'source_heatmap_realtime',
    realtime_difference: 'source_heatmap_realtime_difference',
    date_comparison: 'source_heatmap_date_comparison',
};

const subtract = (a, b) => (a === null || a === undefined || b === null || b === undefined) ? null : a - b;

export const sourceHeatmap = {
    toggleLoading: null,
    displayMessage: null,
    toggleButtonLoading: null,

    setup(helpers) {
        if (!helpers) {
            console.error('No helpers provided to Source Heatmap module');
            return;
        }
        this.toggleLoading = helpers.toggleLoading;
        this.displayMessage = helpers.displayMessage;
        this.toggleButtonLoading = helpers.toggleButtonLoading;

        const dateInput = document.getElementById('source_date');
        if (dateInput) {
            dateInput.valueAsDate = new Date();
        }

        document.getElementById('load_source_heatmap')?.addEventListener('click', () => {
            this.loadHeatmapData(document.getElementById('source_date').value);
        });
        document.getElementById('toggle_source_realtime')?.addEventListener('click', () => {
            this.toggleRealtime();
        });
        document.getElementById('load_source_comparison')?.addEventListener('click', () => {
            this.loadDateComparison();
        });
    },

    async fetchPlan(date, version) {
        const response = await fetch('/source_heatmap_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, version })
        });
        return response.json();
    },

    diffData(base, a, b) {
        return {
            hours: base.hours,
            plants: base.plants,
            values: a.values.map((row, i) => row.map((val, j) => subtract(val, b.values[i][j])))
        };
    },

    async loadHeatmapData(date = null) {
        const button = document.getElementById('load_source_heatmap');
        const toggleButton = document.getElementById('toggle_source_realtime');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const heatmapContainer = document.getElementById('source_heatmap_container');

        try {
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';

            const selectedDate = date || new Date().toISOString().split('T')[0];
            const today = new Date().toISOString().split('T')[0];

            if (toggleButton) {
                toggleButton.textContent = 'Show Realtime';
                toggleButton.disabled = selectedDate >= today; // no realtime for today onwards
            }
            this.realtimeVisible = false;
            this.selectedDate = selectedDate;

            document.getElementById(ELEMENT_IDS.realtime).parentElement.style.display = 'none';
            document.getElementById(ELEMENT_IDS.realtime_difference).parentElement.style.display = 'none';
            document.getElementById('source_comparison_container').style.display = 'none';

            const [firstResult, currentResult] = await Promise.all([
                this.fetchPlan(selectedDate, 'first'),
                this.fetchPlan(selectedDate, 'current')
            ]);

            if (firstResult.code === 200 && currentResult.code === 200) {
                heatmapContainer.style.display = 'block';
                this.firstVersionData = firstResult.data;
                this.currentVersionData = currentResult.data;

                this.processAndDisplayHeatmap(firstResult.data, selectedDate, 'first');
                this.processAndDisplayHeatmap(currentResult.data, selectedDate, 'current');
                this.processAndDisplayHeatmap(
                    this.diffData(firstResult.data, currentResult.data, firstResult.data),
                    selectedDate, 'difference'
                );
            } else {
                const message = firstResult.message || currentResult.message || 'Failed to load source heatmap data';
                this.displayMessage(message, 'warning');
                heatmapContainer.style.display = 'none';
                if (toggleButton) toggleButton.disabled = true;
            }
        } catch (error) {
            console.error('Error loading source heatmap data:', error);
            this.displayMessage('Error loading source heatmap data', 'danger');
            heatmapContainer.style.display = 'none';
            if (toggleButton) toggleButton.disabled = true;
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Load Heatmap';
        }
    },

    async toggleRealtime() {
        const realtimeSection = document.getElementById(ELEMENT_IDS.realtime).parentElement;
        const realtimeDiffSection = document.getElementById(ELEMENT_IDS.realtime_difference).parentElement;
        const toggleButton = document.getElementById('toggle_source_realtime');

        if (this.realtimeVisible) {
            realtimeSection.style.display = 'none';
            realtimeDiffSection.style.display = 'none';
            toggleButton.textContent = 'Show Realtime';
            this.realtimeVisible = false;
            return;
        }

        try {
            toggleButton.disabled = true;
            toggleButton.textContent = 'Loading...';

            const response = await fetch('/source_realtime_heatmap_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: this.selectedDate })
            });
            const result = await response.json();

            if (result.code === 200) {
                realtimeSection.style.display = 'block';
                realtimeDiffSection.style.display = 'block';

                const estimated = result.data.solar_estimated || [];
                this.processAndDisplayHeatmap(result.data, this.selectedDate, 'realtime', estimated);
                this.processAndDisplayHeatmap(
                    this.diffData(result.data, result.data, this.currentVersionData),
                    this.selectedDate, 'realtime_difference', estimated
                );

                const note = document.getElementById('source_estimate_note');
                if (note) note.classList.toggle('d-none', !estimated.some(Boolean));

                toggleButton.textContent = 'Hide Realtime';
                this.realtimeVisible = true;
            } else {
                toggleButton.textContent = 'Show Realtime';
                this.displayMessage(result.message || 'Failed to load realtime data', 'warning');
            }
        } catch (error) {
            console.error('Error loading realtime data:', error);
            toggleButton.textContent = 'Show Realtime';
            this.displayMessage('Error loading realtime data', 'danger');
        } finally {
            toggleButton.disabled = false;
        }
    },

    async loadDateComparison() {
        const button = document.getElementById('load_source_comparison');
        const spinner = button.querySelector('.spinner-border');
        const buttonText = button.querySelector('.button-content');
        const comparisonContainer = document.getElementById('source_comparison_container');
        const comparisonDate = document.getElementById('source_comparison_date').value;

        if (!comparisonDate) {
            this.displayMessage('Please select a comparison date', 'warning');
            return;
        }
        if (!this.selectedDate) {
            this.displayMessage('Please load the main heatmap first', 'warning');
            return;
        }
        if (comparisonDate === this.selectedDate) {
            this.displayMessage('Comparison date must be different from the main date', 'warning');
            return;
        }

        try {
            button.disabled = true;
            spinner.classList.remove('d-none');
            buttonText.textContent = 'Loading...';

            const comparisonResult = await this.fetchPlan(comparisonDate, 'first');

            if (comparisonResult.code === 200) {
                comparisonContainer.style.display = 'block';
                this.processAndDisplayHeatmap(
                    this.diffData(this.firstVersionData, this.firstVersionData, comparisonResult.data),
                    `${this.selectedDate} vs ${comparisonDate}`, 'date_comparison'
                );
            } else {
                this.displayMessage(comparisonResult.message || 'Failed to load comparison data', 'warning');
            }
        } catch (error) {
            console.error('Error loading comparison data:', error);
            this.displayMessage('Error loading comparison data', 'danger');
        } finally {
            button.disabled = false;
            spinner.classList.add('d-none');
            buttonText.textContent = 'Compare Dates';
        }
    },

    processAndDisplayHeatmap(data, date, version, solarEstimated = []) {
        try {
            if (!data.values || !data.hours || !data.plants) {
                this.displayMessage('Error: Missing required data fields', 'danger');
                return;
            }

            const element = document.getElementById(ELEMENT_IDS[version]);
            const isDiff = DIFF_VERSIONS.includes(version);
            const nCols = data.plants.length;
            const totalIdx = nCols - 1;
            const solarIdx = data.plants.indexOf('Solar');
            const isNum = v => v !== null && v !== undefined;

            // Colour value per cell. Difference views share one scale centred on 0,
            // sized without Total so the sum does not flatten every source to white.
            // Absolute views normalise each column to 0..1 against its own range.
            let z;
            let zmin;
            let zmax;
            if (isDiff) {
                const sourceVals = data.values.flatMap(row => row.slice(0, totalIdx)).filter(isNum);
                const absMax = Math.max(...sourceVals.map(Math.abs), 1);
                z = data.values;
                zmin = -absMax;
                zmax = absMax;
            } else {
                const ranges = Array.from({ length: nCols }, (_, j) => {
                    const col = data.values.map(row => row[j]).filter(isNum);
                    return col.length ? { min: Math.min(...col), max: Math.max(...col) } : { min: 0, max: 0 };
                });
                // Centred on the column's midpoint over at least MIN_SPAN_MW, so a
                // near-constant column (fuel oil at 1-3 MW) stays pale instead of
                // being stretched across the whole colour range.
                z = data.values.map(row => row.map((v, j) => {
                    if (!isNum(v)) return null;
                    const { min, max } = ranges[j];
                    const span = Math.max(max - min, MIN_SPAN_MW);
                    return 0.5 + (v - (min + max) / 2) / span;
                }));
                zmin = 0;
                zmax = 1;
            }

            const textColor = (zv) => {
                if (!isNum(zv)) return 'black';
                if (isDiff) return Math.abs(zv) / zmax > 0.6 ? 'white' : 'black';
                // RdBu: both ends are dark
                return (zv < 0.2 || zv > 0.8) ? 'white' : 'black';
            };

            // Night hours are zero whatever the source, so marking them would be noise
            const estimatedCell = (i, j) => j === solarIdx && solarEstimated[i]
                && isNum(data.values[i][j]) && Math.round(data.values[i][j]) !== 0;
            const cellText = data.values.map((row, i) => row.map((v, j) => {
                if (!isNum(v)) return '';
                const n = Math.round(v);
                return `${isDiff && n > 0 ? '+' : ''}${n}${estimatedCell(i, j) ? '*' : ''}`;
            }));
            const hoverNote = data.values.map((row, i) => row.map((v, j) => {
                if (!isNum(v)) return 'No data yet';
                return estimatedCell(i, j) ? 'Unlicensed solar is a Meteologica estimate' : '';
            }));

            const viewName = {
                first: 'First Version', current: 'Final Version', realtime: 'Realtime',
                difference: 'Difference (Final - First)',
                realtime_difference: 'Difference (Realtime - Final)',
                date_comparison: 'Difference (First Version)',
            }[version];

            const layout = {
                title: { text: `Generation by Source MWh - ${date} (${viewName})`, font: { size: 18 } },
                xaxis: {
                    tickangle: -90,
                    ticktext: data.plants,
                    tickvals: data.plants.map((_, i) => i),
                    tickfont: { size: 13 },
                    tickmode: 'array',
                    side: 'bottom'
                },
                yaxis: {
                    title: 'Hour',
                    ticktext: data.hours,
                    tickvals: data.hours.map((_, i) => i),
                    autorange: 'reversed',
                    tickfont: { size: 14 }
                },
                margin: { l: 80, r: 50, b: 230, t: 50, pad: 4 },
                width: 1400,
                height: 1050,
                plot_bgcolor: '#f1f3f5',  // shows through blank (no data) cells
                paper_bgcolor: 'white',
                // Total is a sum, not a source: set it apart with a frame
                shapes: [{
                    type: 'rect', xref: 'x', yref: 'paper',
                    x0: totalIdx - 0.5, x1: totalIdx + 0.5, y0: 0, y1: 1,
                    line: { color: '#212529', width: 2 }, fillcolor: 'rgba(0,0,0,0)'
                }],
                annotations: data.values.flatMap((row, i) => row.map((_, j) => ({
                    text: cellText[i][j],
                    x: j, y: i, xref: 'x', yref: 'y',
                    showarrow: false,
                    font: { size: 13, color: textColor(z[i][j]) }
                })))
            };

            const trace = {
                z,
                x: data.plants.map((_, i) => i),
                y: data.hours.map((_, i) => i),
                customdata: data.values.map((row, i) => row.map((v, j) => [
                    data.plants[j], data.hours[i], isNum(v) ? Math.round(v) : '-', hoverNote[i][j]
                ])),
                hovertemplate: `%{customdata[0]}<br>Hour: %{customdata[1]}<br>${isDiff ? 'Difference' : 'Generation'}: %{customdata[2]} MWh<br>%{customdata[3]}<extra></extra>`,
                type: 'heatmap',
                colorscale: isDiff ? [[0, 'blue'], [0.5, 'white'], [1, 'red']] : 'RdBu',
                zmin, zmax,
                zmid: isDiff ? 0 : undefined,
                showscale: isDiff,
                colorbar: { title: 'MWh', titleside: 'right', thickness: 30 },
                hoverongaps: false,
                xgap: 1,
                ygap: 1
            };

            Plotly.newPlot(element, [trace], layout, {
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            });
        } catch (error) {
            console.error('Error processing source heatmap data:', error);
            this.displayMessage('Error processing data', 'danger');
        }
    },

    init() {
        this.realtimeVisible = false;
        this.currentVersionData = null;
        this.firstVersionData = null;
        this.selectedDate = null;
    }
};
