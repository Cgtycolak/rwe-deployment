// Gas Consumption & GM tab: two exported Plotly reports embedded as iframes. They are ~5 MB
// each, so they load on first visit, and their layout is adjusted to fit the dashboard.

function enhance(iframe) {
    const win = iframe.contentWindow;
    if (!win) return;
    const apply = () => {
        if (!win.Plotly) return;
        win.document.querySelectorAll('.plotly-graph-div').forEach((gd) => {
            try {
                const layout = gd.layout || {};
                // The exported reports have a fixed width; fit them to the frame instead
                gd.style.width = '100%';
                const updates = {
                    width: win.document.documentElement.clientWidth - 16,
                    showlegend: true,
                    legend: { orientation: 'h', x: 0, xanchor: 'left', y: -0.2, yanchor: 'top', font: { size: 11 } },
                    margin: { t: Math.max(60, (layout.margin && layout.margin.t) || 60), r: 60, l: 60, b: 150 },
                    xaxis: Object.assign({}, layout.xaxis || {}, { tickangle: -90, automargin: true, ticklabelstandoff: 6 })
                };
                if (layout.xaxis2) updates.xaxis2 = Object.assign({}, layout.xaxis2, { tickangle: -45, automargin: true, ticklabelstandoff: 6 });
                win.Plotly.relayout(gd, updates);
                win.Plotly.Plots.resize(gd);
            } catch (e) { /* report layout varies; skip what does not apply */ }
        });
    };
    apply();
    setTimeout(apply, 300);
    setTimeout(apply, 800);
}

function frames() {
    return document.querySelectorAll('.content-section[data-section="gas-gm"] iframe.ata-iframe');
}

export const gasGm = {
    init() {
        document.addEventListener('section:activated', (e) => {
            if (e.detail.section !== 'gas-gm') return;
            frames().forEach((iframe) => {
                if (!iframe.dataset.enhancerAttached) {
                    iframe.addEventListener('load', () => enhance(iframe));
                    iframe.dataset.enhancerAttached = 'true';
                }
                if (!iframe.getAttribute('src') && iframe.dataset.src) {
                    iframe.src = iframe.dataset.src;
                } else if (iframe.contentDocument?.readyState === 'complete') {
                    enhance(iframe);
                }
            });
        });

        window.addEventListener('resize', () => {
            frames().forEach((iframe) => { if (iframe.getAttribute('src')) enhance(iframe); });
        });
    }
};
