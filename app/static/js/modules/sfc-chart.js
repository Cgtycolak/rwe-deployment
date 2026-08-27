// SFC (Secondary Frequency Capacity) price — line chart + hour×date heatmap.
// Data source: /get_sfc_chart_data (EPİAS transparency API). Replaces the
// embedded Databricks SFCP dashboard with native Plotly visuals.
export const sfcChart = {
    displayMessage: null,
    _loaded: false,

    setup(helpers) {
        this.displayMessage = (helpers && helpers.displayMessage) || (() => {});

        const loadBtn = document.getElementById('load_sfc_chart');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadData());
        }

        // Default range: last 14 days (matches the Databricks heatmap default)
        const startInput = document.getElementById('sfc_start_date');
        const endInput = document.getElementById('sfc_end_date');
        if (startInput && endInput) {
            const today = new Date();
            const start = new Date();
            start.setDate(today.getDate() - 13);
            endInput.valueAsDate = today;
            startInput.valueAsDate = start;
        }
    },

    init() {
        // Lazy-load the first time the SFC section is opened
        document.addEventListener('section:activated', (e) => {
            if (e.detail.section === 'sfc-price' && !this._loaded) {
                this._loaded = true;
                this.loadData();
            }
        });
    },

    async loadData() {
        const btn = document.getElementById('load_sfc_chart');
        const spinner = btn ? btn.querySelector('.spinner-border') : null;
        const startInput = document.getElementById('sfc_start_date');
        const endInput = document.getElementById('sfc_end_date');

        try {
            if (btn) btn.disabled = true;
            if (spinner) spinner.classList.remove('d-none');

            const body = {};
            if (startInput && startInput.value && endInput && endInput.value) {
                body.start_date = startInput.value;
                body.end_date = endInput.value;
            } else {
                body.days = 14;
            }

            const resp = await fetch('/get_sfc_chart_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const result = await resp.json();

            if (result.code !== 200) {
                this.displayMessage('Failed to load SFC price data', 'danger');
                return;
            }

            this.renderLine(result.data.mcp_series);
            this.renderHeatmap(result.data.heatmap);
        } catch (err) {
            console.error('Error loading SFC data:', err);
            this.displayMessage('Error loading SFC price data', 'danger');
        } finally {
            if (btn) btn.disabled = false;
            if (spinner) spinner.classList.add('d-none');
        }
    },

    renderLine(series) {
        const el = document.getElementById('sfc_line_chart');
        if (!el || !series) return;

        const trace = {
            x: series.map(p => p.datetime),
            y: series.map(p => p.value),
            type: 'scatter',
            mode: 'lines',
            line: { color: '#29b6f6', width: 2, shape: 'linear' },
            hovertemplate: '%{x}<br>%{y:,.0f} TL/MWh<extra></extra>'
        };

        const layout = {
            title: { text: 'Market Clearing Price (MCP)', font: { size: 16 } },
            xaxis: { title: 'date' },
            yaxis: { title: 'price' },
            margin: { l: 70, r: 20, t: 50, b: 60 },
            height: 400,
            plot_bgcolor: 'white',
            paper_bgcolor: 'white'
        };

        Plotly.newPlot(el, [trace], layout, {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        });
    },

    renderHeatmap(hm) {
        const el = document.getElementById('sfc_heatmap');
        if (!el || !hm) return;

        const { hours, dates, values } = hm;

        const trace = {
            z: values,
            x: dates,
            y: hours,
            type: 'heatmap',
            colorscale: 'Reds',
            hoverongaps: false,
            xgap: 1,
            ygap: 1,
            colorbar: { title: 'price' },
            hovertemplate: 'Date: %{x}<br>Hour: %{y}<br>Price: %{z:,.0f}<extra></extra>'
        };

        // Cell value labels — only when the grid is small enough to stay legible
        const annotations = [];
        if (dates.length <= 21) {
            for (let i = 0; i < hours.length; i++) {
                for (let j = 0; j < dates.length; j++) {
                    const v = values[i][j];
                    if (v === null || v === undefined) continue;
                    annotations.push({
                        x: dates[j],
                        y: hours[i],
                        text: Math.round(v).toLocaleString(),
                        showarrow: false,
                        font: { size: 9, color: '#222' }
                    });
                }
            }
        }

        const layout = {
            title: { text: 'SFC Price — Hourly Heatmap', font: { size: 16 } },
            xaxis: { title: 'date', side: 'bottom', tickangle: -30 },
            yaxis: { title: 'hour', autorange: 'reversed' },
            margin: { l: 60, r: 20, t: 50, b: 90 },
            height: 760,
            annotations: annotations,
            plot_bgcolor: 'white',
            paper_bgcolor: 'white'
        };

        Plotly.newPlot(el, [trace], layout, {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        });
    }
};
