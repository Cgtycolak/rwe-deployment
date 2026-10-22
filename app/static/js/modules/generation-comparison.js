// Generation comparison tab: planned (DPP) vs realtime generation by fuel, and the gap.
// Always fetches hourly rows from /api/generation-comparison (in chunks, EPIAS caps a request
// at about 90 days) and averages by week, month or year here, so a period that spans two
// chunks is averaged once over all of its hours.
import { loadXLSX } from '../utils/helpers.js';
import { SERIES, baseLayout, PLOT_CONFIG, lineTrace, mw, signed } from '../utils/plot-theme.js';

// [key, label, DPP field, realtime field, compared in the gap]
const FUELS = [
    ['total', 'Total', 'toplam', 'total', true],
    ['naturalGas', 'Natural gas', 'dogalgaz', 'naturalGas', true],
    ['wind', 'Wind', 'ruzgar', 'wind', true],
    ['solar', 'Solar', 'gunes', 'sun', false],
    ['lignite', 'Lignite', 'linyit', 'lignite', true],
    ['importCoal', 'Import coal', 'ithalKomur', 'importCoal', true],
    ['hardCoal', 'Hard coal', 'tasKomur', 'blackCoal', false],
    ['dammedHydro', 'Dammed hydro', 'barajli', 'dammedHydro', true],
    ['river', 'Run-of-river', 'akarsu', 'river', true],
    ['geothermal', 'Geothermal', 'jeotermal', 'geothermal', true],
    ['biomass', 'Biomass', 'biokutle', 'biomass', true],
    ['fueloil', 'Fuel oil', 'fuelOil', 'fueloil', true],
    ['naphta', 'Naphtha', 'nafta', 'naphta', true],
];
// Fuels compared one to one; the reported totals also hold solar and hard coal, which the
// two sources count differently, so gaps use the sum of these instead
const COMPARED = FUELS.filter((f) => f[4] && f[0] !== 'total');
const GAP_FUELS = [['compared', 'Compared total'], ...COMPARED];
const ALL_KEYS = [...FUELS.map(([f]) => f), 'compared'];
const CHUNK_DAYS = 89;
const DAY = 86400000;

const RESOLUTIONS = {
    hourly: { label: 'Hour', key: (k) => k },
    weekly: { label: 'Week starting', key: (k) => mondayOf(k.slice(0, 10)) },
    monthly: { label: 'Month', key: (k) => k.slice(0, 7) },
    yearly: { label: 'Year', key: (k) => k.slice(0, 4) },
};

const isoDay = (d) => d.toISOString().slice(0, 10);

function mondayOf(day) {
    const d = new Date(`${day}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    return isoDay(d);
}

// "2026-10-14T00:00:00+03:00" + "05:00" -> "2026-10-14 05:00"
const hourKey = (item) => `${item.date.slice(0, 10)} ${item.hour || item.time || '00:00'}`;

const fmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });

export const generationComparison = {
    resolution: 'hourly',
    view: 'chart',
    hourly: null,      // joined hourly rows from the last load
    rows: null,        // aggregated rows: { key, plan: {fuel: v}, actual: {...}, gap: {...} }
    rendered: {},      // which views are drawn for the current rows
    loaded: false,
    bound: false,
    requestId: 0,

    setup(helpers) {
        this.helpers = helpers;
    },

    // Runs every time the tab opens
    init() {
        if (!this.bound) {
            this.bind();
            this.bound = true;
        }
        if (!this.loaded) {
            this.loaded = true;
            const end = new Date();
            const start = new Date(end.getTime() - 7 * DAY);
            this.el('comparison_start_date').value = isoDay(start);
            this.el('comparison_end_date').value = isoDay(end);
            this.load();
        } else if (this.view === 'chart' && this.rows) {
            Plotly.Plots.resize(this.el('generation_comparison_chart'));
        }
    },

    el(id) {
        return document.getElementById(id);
    },

    bind() {
        document.querySelectorAll('.comparison-range-btn').forEach((button) => {
            button.addEventListener('click', () => {
                this.resolution = button.dataset.range;
                this.pressed('.comparison-range-btn', (b) => b === button);
                if (this.hourly) this.aggregateAndRender();
            });
        });
        this.el('load_comparison_data').addEventListener('click', () => this.load());
        this.el('download_comparison_excel').addEventListener('click', () => this.downloadExcel());
        document.querySelectorAll('#comparison_views [data-view]').forEach((button) => {
            button.addEventListener('click', () => this.showView(button.dataset.view));
        });
    },

    pressed(selector, isOn) {
        document.querySelectorAll(selector).forEach((b) => b.setAttribute('aria-pressed', String(isOn(b))));
    },

    setStatus(text, isError = false) {
        const status = this.el('comparison_status');
        status.hidden = !text;
        status.classList.toggle('is-error', isError);
        status.innerHTML = text ? `<p>${text}</p>` : '';
        if (text) {
            document.querySelectorAll('[data-view-panel]').forEach((p) => { p.hidden = true; });
            this.el('comparison_stats').hidden = true;
            this.el('comparison_views').hidden = true;
        }
    },

    validRange() {
        const start = this.el('comparison_start_date').value;
        const end = this.el('comparison_end_date').value;
        if (!start || !end) return { error: 'Pick both a start and an end date.' };
        if (start > end) return { error: 'The start date is after the end date. Swap them and try again.' };
        if (end > isoDay(new Date())) return { error: 'The end date is in the future. Realtime data only exists up to today.' };
        return { start, end };
    },

    async load() {
        const range = this.validRange();
        if (range.error) {
            this.setStatus(range.error, true);
            return;
        }
        const id = ++this.requestId;
        const button = this.el('load_comparison_data');
        button.disabled = true;
        this.el('download_comparison_excel').disabled = true;

        try {
            const chunks = this.chunks(range.start, range.end);
            const plan = [];
            const actual = [];
            for (let i = 0; i < chunks.length; i++) {
                this.setStatus(chunks.length > 1
                    ? `Loading part ${i + 1} of ${chunks.length} (${chunks[i][0]} to ${chunks[i][1]}).`
                    : `Loading ${range.start} to ${range.end}.`);
                const data = await this.fetchChunk(chunks[i][0], chunks[i][1]);
                if (id !== this.requestId) return;
                plan.push(...(data.dpp?.items || []));
                actual.push(...(data.realtime?.items || []));
            }
            this.hourly = this.joinHours(plan, actual);
            if (!this.hourly.length) {
                this.setStatus(`There is no planned or realtime data between ${range.start} and ${range.end}.`);
                return;
            }
            this.aggregateAndRender();
            this.el('download_comparison_excel').disabled = false;
        } catch (error) {
            if (id !== this.requestId) return;
            console.error('Generation comparison failed:', error);
            this.setStatus(`The comparison did not load: ${error.message}. Try again, or pick a shorter date range.`, true);
        } finally {
            if (id === this.requestId) button.disabled = false;
        }
    },

    chunks(start, end) {
        const out = [];
        let from = new Date(`${start}T00:00:00Z`);
        const last = new Date(`${end}T00:00:00Z`);
        while (from <= last) {
            const to = new Date(Math.min(from.getTime() + (CHUNK_DAYS - 1) * DAY, last.getTime()));
            out.push([isoDay(from), isoDay(to)]);
            from = new Date(to.getTime() + DAY);
        }
        return out;
    },

    async fetchChunk(start, end) {
        const response = await fetch('/api/generation-comparison?range=daily', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end }),
        });
        let body = null;
        try { body = await response.json(); } catch (e) { /* non-JSON error page */ }
        if (!response.ok || body?.code !== 200) {
            throw new Error(body?.message || `the server answered ${response.status}`);
        }
        return body.data;
    },

    // One row per hour that has both a plan and a realtime value
    joinHours(planItems, actualItems) {
        const plan = new Map(planItems.map((d) => [hourKey(d), d]));
        const actual = new Map(actualItems.map((d) => [hourKey(d), d]));
        const keys = [...new Set([...plan.keys(), ...actual.keys()])].sort();
        return keys.map((key) => {
            const p = plan.get(key);
            const a = actual.get(key);
            const row = { key, plan: {}, actual: {}, gap: {} };
            FUELS.forEach(([fuel, , dppField, rtField, compared]) => {
                const pv = p ? Number(p[dppField] ?? 0) : null;
                const av = a ? Number(a[rtField] ?? 0) : null;
                row.plan[fuel] = pv;
                row.actual[fuel] = av;
                row.gap[fuel] = compared && fuel !== 'total' && pv != null && av != null ? av - pv : null;
            });
            // Like-for-like total: only the fuels both sources count the same way
            const sum = (part) => COMPARED.reduce((t, [f]) => (row[part][f] == null ? null : t == null ? null : t + row[part][f]), 0);
            row.plan.compared = p ? sum('plan') : null;
            row.actual.compared = a ? sum('actual') : null;
            row.gap.compared = row.plan.compared != null && row.actual.compared != null ? row.actual.compared - row.plan.compared : null;
            return row;
        });
    },

    aggregateAndRender() {
        const res = RESOLUTIONS[this.resolution];
        if (this.resolution === 'hourly') {
            this.rows = this.hourly;
        } else {
            const groups = new Map();
            this.hourly.forEach((row) => {
                const k = res.key(row.key);
                if (!groups.has(k)) groups.set(k, []);
                groups.get(k).push(row);
            });
            this.rows = [...groups].map(([key, rows]) => {
                const out = { key, plan: {}, actual: {}, gap: {} };
                ['plan', 'actual', 'gap'].forEach((part) => {
                    ALL_KEYS.forEach((fuel) => {
                        const vals = rows.map((r) => r[part][fuel]).filter((v) => v != null);
                        out[part][fuel] = vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
                    });
                });
                return out;
            });
        }
        this.rendered = {};
        this.setStatus('');
        this.renderStats();
        this.el('comparison_views').hidden = false;
        this.showView(this.view);
    },

    showView(view) {
        this.view = view;
        this.pressed('#comparison_views [data-view]', (b) => b.dataset.view === view);
        document.querySelectorAll('[data-view-panel]').forEach((p) => { p.hidden = p.dataset.viewPanel !== view; });
        if (!this.rows || this.rendered[view]) {
            if (view === 'chart' && this.rows) Plotly.Plots.resize(this.el('generation_comparison_chart'));
            return;
        }
        if (view === 'chart') this.renderChart();
        if (view === 'gap') this.renderGapTable();
        if (view === 'tables') {
            this.renderValueTable('dpp_data_table', 'plan');
            this.renderValueTable('realtime_data_table', 'actual');
        }
        this.rendered[view] = true;
    },

    mean(part, fuel) {
        const vals = this.hourly.map((r) => r[part][fuel]).filter((v) => v != null);
        return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    },

    renderStats() {
        const gap = this.mean('gap', 'compared');
        const fuelGaps = COMPARED
            .map(([f, label]) => [label, this.mean('gap', f)])
            .filter(([, v]) => v != null)
            .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
        const [bigLabel, bigValue] = fuelGaps[0] || ['No data', null];
        const cls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '');
        const stats = this.el('comparison_stats');
        stats.innerHTML = `
            <div><dt>Average planned, compared fuels, MW</dt><dd>${mw.format(this.mean('plan', 'compared') ?? 0)}</dd></div>
            <div><dt>Average realtime, compared fuels, MW</dt><dd>${mw.format(this.mean('actual', 'compared') ?? 0)}</dd></div>
            <div><dt>Average gap, realtime minus plan</dt><dd class="${cls(gap)}">${gap != null ? `${signed(gap)} MW` : 'No data'}</dd></div>
            <div><dt>Largest fuel gap: ${bigLabel}</dt><dd class="${cls(bigValue)}">${bigValue != null ? `${signed(bigValue)} MW` : 'No data'}</dd></div>`;
        stats.hidden = false;
    },

    xValues() {
        return this.rows.map((r) => (this.resolution === 'monthly' ? `${r.key}-01` : this.resolution === 'yearly' ? `${r.key}-01-01` : r.key));
    },

    renderChart() {
        const x = this.xValues();
        const plan = this.rows.map((r) => r.plan.compared);
        const actual = this.rows.map((r) => r.actual.compared);
        const gap = this.rows.map((r) => r.gap.compared);
        const bar = this.resolution === 'hourly' ? {} : { mode: 'lines+markers' };
        const traces = [
            lineTrace('Planned (DPP)', x, plan, SERIES.plan, bar),
            lineTrace('Realtime', x, actual, SERIES.actual, bar),
            {
                name: 'Gap', x, y: gap, type: 'bar', yaxis: 'y2',
                marker: { color: gap.map((v) => (v >= 0 ? SERIES.gapUp : SERIES.gapDown)) },
                hovertemplate: '%{y:+,.0f} MW',
            },
        ];
        const base = baseLayout();
        const layout = baseLayout({
            height: 520,
            yaxis: { ...base.yaxis, title: { text: 'Compared fuels, MW' }, domain: [0.38, 1] },
            yaxis2: { ...base.yaxis, title: { text: 'Gap, MW' }, domain: [0, 0.28], zeroline: true },
            xaxis: { ...base.xaxis, anchor: 'y2' },
            bargap: 0.1,
        });
        Plotly.react('generation_comparison_chart', traces, layout, PLOT_CONFIG);
    },

    rowLabel(key) {
        if (this.resolution === 'hourly') return key;
        if (this.resolution === 'monthly') {
            return new Date(`${key}-01T00:00:00Z`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
        }
        return key;
    },

    renderValueTable(id, part) {
        const head = `<thead><tr><th scope="col">${RESOLUTIONS[this.resolution].label}</th>${FUELS.map(([, label]) => `<th scope="col" class="num">${label}</th>`).join('')}</tr></thead>`;
        const body = this.rows.map((r) => `<tr><td>${this.rowLabel(r.key)}</td>${FUELS.map(([f]) => `<td class="num">${r[part][f] != null ? fmt.format(r[part][f]) : ''}</td>`).join('')}</tr>`).join('');
        this.el(id).innerHTML = head + `<tbody>${body}</tbody>`;
    },

    renderGapTable() {
        const maxAbs = {};
        GAP_FUELS.forEach(([f]) => {
            maxAbs[f] = Math.max(1, ...this.rows.map((r) => Math.abs(r.gap[f] ?? 0)));
        });
        const cell = (f, v) => {
            if (v == null) return '<td class="num"></td>';
            const a = (0.08 + 0.37 * Math.min(1, Math.abs(v) / maxAbs[f])).toFixed(2);
            const cls = v > 0 ? 'gap-pos' : v < 0 ? 'gap-neg' : '';
            return `<td class="num ${cls}" style="--a:${a}">${signed(v)}</td>`;
        };
        const head = `<thead><tr><th scope="col">${RESOLUTIONS[this.resolution].label}</th>${GAP_FUELS.map(([, label]) => `<th scope="col" class="num">${label}</th>`).join('')}</tr></thead>`;
        const body = this.rows.map((r) => `<tr><td>${this.rowLabel(r.key)}</td>${GAP_FUELS.map(([f]) => cell(f, r.gap[f])).join('')}</tr>`).join('');
        this.el('comparison_differences_table').innerHTML = head + `<tbody>${body}</tbody>`;
    },

    async downloadExcel() {
        if (!this.rows) return;
        try {
            const XLSX = await loadXLSX();
            const sheet = (part, fuels) => XLSX.utils.json_to_sheet(this.rows.map((r) => {
                const out = { [RESOLUTIONS[this.resolution].label]: this.rowLabel(r.key) };
                fuels.forEach(([f, label]) => { out[label] = r[part][f] != null ? Math.round(r[part][f] * 100) / 100 : null; });
                return out;
            }));
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, sheet('plan', FUELS), 'Planned (DPP)');
            XLSX.utils.book_append_sheet(wb, sheet('actual', FUELS), 'Realtime');
            XLSX.utils.book_append_sheet(wb, sheet('gap', GAP_FUELS), 'Gap');
            const { start, end } = this.validRange();
            XLSX.writeFile(wb, `generation_comparison_${this.resolution}_${start}_${end}.xlsx`);
        } catch (error) {
            console.error('Excel export failed:', error);
            this.helpers.displayMessage('The Excel file could not be created. Try again in a moment.', 'danger');
        }
    },
};
