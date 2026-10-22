// AIC tab: available installed capacity vs planned (DPP) and realtime generation, from
// /get_aic_data?range=week|month|year|5year. Loads the last 7 days on first visit.
import { SERIES, baseLayout, PLOT_CONFIG, lineTrace, mw, pct } from '../utils/plot-theme.js';

const RANGE_LABELS = {
    week: 'the last 7 days',
    month: 'the last 30 days',
    year: 'the last 12 months',
    '5year': 'the last 5 years',
};

// "2026-10-15T00:00:00+03:00" + "05:00" -> "2026-10-15 05:00" (Istanbul wall time, no TZ shift)
function hourKey(date, hour) {
    return `${date.slice(0, 10)} ${hour}`;
}

function average(values) {
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export const aic = {
    range: null,
    requestId: 0,
    bound: false,

    setup(helpers) {
        this.helpers = helpers;
    },

    // Runs every time the tab opens
    init() {
        if (!this.bound) {
            document.querySelectorAll('.aic-range-btn').forEach((button) => {
                button.addEventListener('click', () => this.loadAICData(button.dataset.range));
            });
            this.bound = true;
        }
        if (!this.range) {
            this.loadAICData('week');
        } else {
            const chart = document.getElementById('aic_realtime_chart');
            if (chart && !chart.hidden) Plotly.Plots.resize(chart);
        }
    },

    setStatus(text, isError = false) {
        const status = document.getElementById('aic_status');
        if (!status) return;
        status.hidden = !text;
        status.classList.toggle('is-error', isError);
        status.innerHTML = text ? `<p>${text}</p>` : '';
    },

    async loadAICData(range = 'week') {
        this.range = range;
        const id = ++this.requestId;
        document.querySelectorAll('.aic-range-btn').forEach((b) => {
            b.setAttribute('aria-pressed', String(b.dataset.range === range));
        });

        const chart = document.getElementById('aic_realtime_chart');
        const stats = document.getElementById('aic_stats');
        chart.hidden = true;
        stats.hidden = true;
        this.setStatus(`Loading ${RANGE_LABELS[range]}. Longer periods can take up to a minute.`);

        try {
            const response = await fetch(`/get_aic_data?range=${encodeURIComponent(range)}`);
            if (!response.ok) throw new Error(`the server answered ${response.status}`);
            const result = await response.json();
            if (id !== this.requestId) return; // a newer range was picked meanwhile

            const data = result.data;
            if (result.code !== 200 || !data?.aic || !data?.realtime || !data?.dpp) {
                this.setStatus(`There is no AIC data for ${RANGE_LABELS[range]}. Try a shorter period.`);
                return;
            }

            const series = this.buildSeries(data);
            if (!series.x.length) {
                this.setStatus(`There is no AIC data for ${RANGE_LABELS[range]}. Try a shorter period.`);
                return;
            }

            this.setStatus('');
            chart.hidden = false;
            this.renderStats(series);
            this.renderChart(series);
        } catch (error) {
            if (id !== this.requestId) return;
            console.error('AIC load failed:', error);
            this.setStatus(`AIC data for ${RANGE_LABELS[range]} did not load: ${error.message}. Pick the period again to retry.`, true);
        }
    },

    buildSeries(data) {
        const aicByHour = new Map(data.aic.map((d) => [hourKey(d.date, d.time), d.toplam]));
        const dppByHour = new Map(data.dpp.map((d) => [hourKey(d.date, d.time), d.toplam]));
        const rtByHour = new Map(data.realtime.map((d) => [hourKey(d.date, d.hour), d.total]));
        const x = [...new Set([...aicByHour.keys(), ...dppByHour.keys(), ...rtByHour.keys()])].sort();
        const pick = (map) => x.map((k) => (map.has(k) ? map.get(k) : null));
        return { x, aic: pick(aicByHour), dpp: pick(dppByHour), realtime: pick(rtByHour) };
    },

    renderStats({ x, aic, realtime }) {
        const both = (a, b) => a.map((v, i) => [v, b[i]]).filter(([p, q]) => p != null && q != null);
        const rtVsAic = both(realtime, aic);
        const headroom = x.map((t, i) => [t, aic[i] != null && realtime[i] != null ? aic[i] - realtime[i] : null])
            .filter(([, h]) => h != null)
            .sort((a, b) => a[1] - b[1])[0];
        const avgAic = average(aic.filter((v) => v != null));
        const avgRt = average(realtime.filter((v) => v != null));
        const usage = rtVsAic.length ? average(rtVsAic.map(([r]) => r)) / average(rtVsAic.map(([, c]) => c)) : null;

        const stats = document.getElementById('aic_stats');
        stats.innerHTML = `
            <div><dt>Average available capacity, MW</dt><dd>${avgAic != null ? mw.format(avgAic) : 'No data'}</dd></div>
            <div><dt>Average realtime generation, MW</dt><dd>${avgRt != null ? mw.format(avgRt) : 'No data'}</dd></div>
            <div><dt>Realtime as a share of capacity</dt><dd>${usage != null ? pct.format(usage) : 'No data'}</dd></div>
            <div><dt>${headroom ? `Smallest headroom, MW, at ${headroom[0]}` : 'Smallest headroom, MW'}</dt><dd>${headroom ? mw.format(headroom[1]) : 'No data'}</dd></div>`;
        stats.hidden = false;
    },

    renderChart({ x, aic, dpp, realtime }) {
        const traces = [
            lineTrace('Available capacity (AIC)', x, aic, SERIES.capacity),
            lineTrace('Planned (DPP)', x, dpp, SERIES.plan),
            lineTrace('Realtime', x, realtime, SERIES.actual),
        ];
        const layout = baseLayout({ height: 460, yaxis: { ...baseLayout().yaxis, title: { text: 'MW' }, rangemode: 'tozero' } });
        Plotly.react('aic_realtime_chart', traces, layout, PLOT_CONFIG);
    },
};
