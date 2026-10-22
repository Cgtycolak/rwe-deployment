// Shared Plotly styling so charts match the tokens in base.css.

export const SERIES = {
    capacity: '#1B2B3A',   // AIC, ink
    plan: '#1F5F99',       // DPP, accent
    actual: '#C2702E',     // realtime, amber
    gapUp: '#2C7A5B',      // realtime above plan
    gapDown: '#B4532A',    // realtime below plan
};

// Fuel colours used by the per-fuel gap chart; hues are spaced so neighbours stay distinct
export const FUEL_COLORS = {
    naturalGas: '#1F5F99',
    wind: '#3E9C8F',
    solar: '#D9A21B',
    lignite: '#7A5C3E',
    importCoal: '#4A4F57',
    hardCoal: '#8C8F94',
    fueloil: '#9A3E5C',
    geothermal: '#C2702E',
    dammedHydro: '#2E7FC0',
    river: '#7FB3E0',
    biomass: '#5E8C3A',
    naphta: '#B07CC6',
};

export function baseLayout(overrides = {}) {
    return {
        font: { family: "'RWE Sans Web', -apple-system, 'Segoe UI', sans-serif", size: 12, color: '#1F2933' },
        paper_bgcolor: '#FFFFFF',
        plot_bgcolor: '#FFFFFF',
        margin: { t: 16, r: 16, b: 48, l: 64 },
        hovermode: 'x unified',
        hoverlabel: { bgcolor: '#FFFFFF', bordercolor: '#D5DCE3' },
        legend: { orientation: 'h', x: 0, y: 1.08, xanchor: 'left' },
        xaxis: { type: 'date', gridcolor: '#EDF0F3', linecolor: '#D5DCE3', zeroline: false },
        yaxis: { gridcolor: '#EDF0F3', linecolor: '#D5DCE3', zerolinecolor: '#B9C3CD', ticksuffix: ' ', separatethousands: true },
        ...overrides,
    };
}

export const PLOT_CONFIG = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
};

// WebGL traces stay fast past a few thousand points (yearly and 5-year ranges)
export function lineTrace(name, x, y, color, extra = {}) {
    return {
        name, x, y,
        type: x.length > 2000 ? 'scattergl' : 'scatter',
        mode: 'lines',
        line: { color, width: 1.6 },
        hovertemplate: '%{y:,.0f} MW',
        ...extra,
    };
}

export const mw = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
export const pct = new Intl.NumberFormat('en-GB', { style: 'percent', maximumFractionDigits: 1 });

export function signed(value) {
    return `${value > 0 ? '+' : value < 0 ? '−' : ''}${mw.format(Math.abs(value))}`;
}
