// Home tab: the latest market day from /get_all_table_data. Renders the 24-hour system
// marginal price strip and the hourly tables for load/deload, SMP, PFC and SFC.

// Sequential price scale: soft blue -> accent -> deep blue (matches --accent in base.css)
const PRICE_STOPS = [[227, 237, 246], [31, 95, 153], [14, 47, 79]];
// Diverging load/deload scale: rust (deload) <- white -> green (load)
const DELOAD = [180, 83, 42];
const LOAD = [44, 122, 91];

const number = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dayLabel = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
const shortDay = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' });

function mix(a, b, t) {
    return a.map((v, i) => Math.round(v + (b[i] - v) * t));
}

// Relative luminance (WCAG) to pick readable text on a coloured cell
function luminance(rgb) {
    const [r, g, b] = rgb.map((v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function priceColor(t) {
    const rgb = t <= 0.5 ? mix(PRICE_STOPS[0], PRICE_STOPS[1], t * 2) : mix(PRICE_STOPS[1], PRICE_STOPS[2], (t - 0.5) * 2);
    // White text wins once contrast with white beats contrast with the dark text colour
    return { bg: `rgb(${rgb})`, fg: luminance(rgb) < 0.2 ? '#fff' : 'var(--text)' };
}

// "2026-10-21 05:00" -> { day: "2026-10-21", hour: "05" }
function parts(datetime) {
    const [day, time = ''] = datetime.split(' ');
    return { day, hour: time.slice(0, 2) };
}

function toDate(day) {
    return new Date(`${day}T00:00:00`);
}

function scale(values) {
    const min = Math.min(...values);
    const max = Math.max(...values);
    return { min, max, at: (v) => (max === min ? 0.5 : (v - min) / (max - min)) };
}

export const miniTables = {
    setup(helpers) {
        this.helpers = helpers;
    },

    async init() {
        await this.loadAllData();
    },

    async loadAllData() {
        try {
            const response = await fetch('/get_all_table_data');
            const result = await response.json();

            if (result.code === 200) {
                const { orderSummary, smp, pfc, sfc } = result.data;
                this.renderCoverage(smp.data, sfc.data);
                this.renderPriceStrip(smp.data, smp.average);
                this.renderOrderSummaryTable(orderSummary);
                this.renderPriceTable('smp-table', 'System marginal price', 'Daily average', smp.data, smp.average);
                this.renderPriceTable('pfc-table', 'Primary frequency capacity', 'Average', pfc.data, pfc.average);
                this.renderPriceTable('sfc-table', 'Secondary frequency capacity', 'Average', sfc.data, sfc.average);
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('Error loading table data:', error);
            const coverage = document.getElementById('market-coverage');
            if (coverage) coverage.textContent = 'The market data did not load. Reload the page to try again.';
            this.helpers.displayMessage('Error loading table data', 'error');
        }
    },

    renderCoverage(smpData, sfcData) {
        const el = document.getElementById('market-coverage');
        if (!el || !smpData.length) return;
        const smpDay = toDate(parts(smpData[0].datetime).day);
        let text = `System marginal price for ${dayLabel.format(smpDay)}`;
        if (sfcData.length) {
            const lastCapacityDay = toDate(parts(sfcData[sfcData.length - 1].datetime).day);
            text += `, frequency capacity prices through ${shortDay.format(lastCapacityDay)}.`;
        }
        el.textContent = text;
    },

    renderPriceStrip(data, average) {
        const strip = document.getElementById('price-strip');
        const stats = document.getElementById('price-day-stats');
        if (!strip || !data.length) return;

        const values = data.map((d) => d.value);
        const s = scale(values);
        const low = data[values.indexOf(s.min)];
        const high = data[values.indexOf(s.max)];

        strip.innerHTML = data.map((d) => {
            const { hour } = parts(d.datetime);
            const { bg, fg } = priceColor(s.at(d.value));
            const mark = d === high ? 'High' : d === low ? 'Low' : '';
            const label = `${hour}:00, ${decimal.format(d.value)} ₺/MWh${mark ? `, daily ${mark.toLowerCase()}` : ''}`;
            return `<li style="background:${bg};color:${fg}" title="${label}" aria-label="${label}">
                        <span class="hour">${hour}</span>
                        <span class="value">${number.format(d.value)}</span>
                        <span class="extreme">${mark}</span>
                    </li>`;
        }).join('');

        if (stats) {
            stats.innerHTML = `
                <div><dt>Average, ₺/MWh</dt><dd>${decimal.format(average)}</dd></div>
                <div><dt>Low at ${parts(low.datetime).hour}:00</dt><dd>${decimal.format(s.min)}</dd></div>
                <div><dt>High at ${parts(high.datetime).hour}:00</dt><dd>${decimal.format(s.max)}</dd></div>`;
        }
    },

    // Rows grouped by day; a rule marks where a new day starts
    tableRows(data, cellStyle) {
        let previousDay = null;
        return data.map((d) => {
            const { day, hour } = parts(d.datetime);
            const breakRow = previousDay !== null && day !== previousDay;
            const label = previousDay !== day ? `${shortDay.format(toDate(day))} ${hour}:00` : `${hour}:00`;
            previousDay = day;
            return `<tr${breakRow ? ' class="day-break"' : ''}>
                        <td>${label}</td>
                        <td style="${cellStyle(d.value)}">${decimal.format(d.value)}</td>
                    </tr>`;
        }).join('');
    },

    tableShell(title, summary, valueHeader, rows) {
        return `
            <div class="mini-table-container">
                <h3>${title}</h3>
                <p class="summary">${summary}</p>
                <div class="mini-table-scroll">
                    <table class="mini-table">
                        <thead><tr><th scope="col">Hour</th><th scope="col">${valueHeader}</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>`;
    },

    renderOrderSummaryTable(data) {
        const container = document.getElementById('order-summary-table');
        if (!container) return;

        const values = data.map((d) => d.value);
        const maxLoad = Math.max(...values, 0);
        const maxDeload = Math.min(...values, 0);
        const total = values.reduce((sum, v) => sum + v, 0);

        const style = (v) => {
            if (v === 0) return '';
            const t = v > 0 ? v / maxLoad : v / maxDeload;
            const rgb = mix([255, 255, 255], v > 0 ? LOAD : DELOAD, 0.15 + t * 0.35);
            return `background-color: rgb(${rgb})`;
        };

        container.innerHTML = this.tableShell(
            'Load and deload',
            `Net ${decimal.format(total)} MWh. Load is green, deload is rust.`,
            'MWh',
            this.tableRows(data, style)
        );
    },

    renderPriceTable(containerId, title, averageLabel, data, average) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const s = scale(data.map((d) => d.value));
        const style = (v) => `background-color: rgb(${mix(PRICE_STOPS[0], [143, 179, 214], s.at(v))})`;

        container.innerHTML = this.tableShell(
            title,
            `${averageLabel} ${decimal.format(average)} ₺/MWh`,
            '₺/MWh',
            this.tableRows(data, style)
        );
    }
};
