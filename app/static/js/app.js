import { dpp } from './modules/dpp.js';
import { realtime } from './modules/realtime.js';
import { postData, toggleLoading, displayMessage, updateGlobal, switcher } from './utils/helpers.js';
import { HTMLSearchableSelect } from './classes/HTMLSearchableSelect.js';
import { aic } from './modules/aic.js';
import { generationComparison } from './modules/generation-comparison.js';
import { heatmap } from './modules/heatmap.js';
import { importCoalHeatmap } from './modules/importCoalHeatmap.js';
import { ligniteHeatmap } from './modules/ligniteHeatmap.js';
import { sourceHeatmap } from './modules/sourceHeatmap.js';
import { miniTables } from './modules/mini-tables.js';
import { hydroHeatmap } from './modules/hydro-heatmap.js';
import { forecasting } from './modules/forecasting.js';
import { forecastPerformance } from './modules/forecast-performance.js';
import { meritOrder } from './modules/merit-order.js';
import { hydroMap } from './modules/hydro-map.js';
import { sfcChart } from './modules/sfc-chart.js';
import { rollingAverages } from './modules/rolling-averages.js';
import { supplyDemandPrice } from './modules/supply-demand-price.js';
import { gasGm } from './modules/gas-gm.js';
import { startRouter } from './router.js';
import { setupSidebar, setupSelectFilters } from './shell.js';

// Main app object
const app = {
    global: {
        start: null,
        end: null,
    },
    dpp,
    realtime,
    aic,
    generationComparison,
    heatmap,
    importCoalHeatmap,
    ligniteHeatmap,
    sourceHeatmap,
    miniTables,
    hydroHeatmap,
    forecasting,
    forecastPerformance,
    meritOrder,
    hydroMap,
    sfcChart,
    rollingAverages,
    supplyDemandPrice,
    gasGm,
    endpoints: JSON.parse(document.getElementById('endpoints-data')?.textContent || '{}'),
    helpers: {
        toggleLoading: function (show) {
            const loader = document.getElementById('aic_loading');
            if (loader) {
                loader.style.display = show ? 'block' : 'none';
            }
        },
        displayMessage,
        toggleButtonLoading: function (button, isLoading) {
            if (!button) return;

            const spinner = button.querySelector('.spinner-border');
            const content = button.querySelector('.button-content');

            if (isLoading) {
                button.disabled = true;
                if (spinner) spinner.classList.remove('d-none');
                if (content) content.style.opacity = '0.5';
            } else {
                button.disabled = false;
                if (spinner) spinner.classList.add('d-none');
                if (content) content.style.opacity = '1';
            }
        }
    },

    // Runs before every tab switch
    cleanup() {
        const alertContainer = document.getElementById('alert_messages');
        if (alertContainer) {
            alertContainer.innerHTML = '';
        }
    },

    init() {
        $(document).ready(() => {
            setupEvents();
            
            // Initialize modules
            this.aic.setup(this.helpers);
            this.generationComparison.setup({ displayMessage });
            this.heatmap.setup(this.helpers);
            this.importCoalHeatmap.setup(this.helpers);
            this.ligniteHeatmap.setup(this.helpers);
            this.sourceHeatmap.setup(this.helpers);
            this.hydroHeatmap.setup(this.helpers);
            this.heatmap.init();
            this.importCoalHeatmap.init();
            this.ligniteHeatmap.init();
            this.sourceHeatmap.init();
            this.miniTables.setup(this.helpers);
            
            // Initialize forecasting module
            this.forecasting.setup({
                toggleLoading: this.helpers.toggleLoading,
                displayMessage: this.helpers.displayMessage,
                toggleButtonLoading: this.helpers.toggleButtonLoading
            });
            
            // Initialize forecast performance module
            this.forecastPerformance.setup(this.helpers);
            this.forecastPerformance.init();
            
            // Initialize merit order module
            this.meritOrder.setup(this.helpers);
            this.meritOrder.init();

            // Initialize hydro map module
            this.hydroMap.setup(this.helpers);
            this.hydroMap.init();

            // Initialize SFC price module (line chart + heatmap)
            this.sfcChart.setup(this.helpers);
            this.sfcChart.init();
            
            // Initialize mini-tables when showing home section
            this.miniTables.init();

            this.rollingAverages.init();
            this.supplyDemandPrice.init();
            this.gasGm.init();

            setupSidebar();
            setupSelectFilters();
            autoloadOnFirstVisit();

            // Started last so the first 'section:activated' reaches every module
            startRouter({
                beforeEnter: () => this.cleanup(),
                onEnter: {
                    'aic-realtime': () => this.aic.init(),
                    'generation-comparison': () => this.generationComparison.init(),
                },
            });
        });
    }
};

// Tabs whose defaults (today, or the last 30 days) are always valid load on their first visit
// by pressing their own load button, so they show data straight away like the other tabs.
// DPP - Realtime and the forecast need choices or a file first, so they are not listed.
const AUTOLOAD = {
    'generation-heatmap': 'load_heatmap',
    'import-coal-heatmap': 'load_import_coal_heatmap',
    'hydro-heatmap': 'load_hydro_heatmap',
    'lignite-heatmap': 'load_lignite_heatmap',
    'source-heatmap': 'load_source_heatmap',
    'forecast-performance': 'load_forecast_performance',
    'merit-order': 'load_merit_order',
    'supply-demand-price': 'load_sdp',
};

function autoloadOnFirstVisit() {
    const visited = new Set();
    document.addEventListener('section:activated', (e) => {
        const section = e.detail.section;
        if (!AUTOLOAD[section] || visited.has(section)) return;
        visited.add(section);
        const button = document.getElementById(AUTOLOAD[section]);
        if (button && !button.disabled) button.click();
    });
}

// Setup events
function setupEvents() {
    $('[data-toggle="tooltip"]').tooltip();

    // Initialize searchable selects
    app.orgSelect = new HTMLSearchableSelect("#org_select");
    app.adiSelect = new HTMLSearchableSelect("#adi_select");

    // Global events
    $("#global_start").on("change", (e) => updateGlobal(e, app));
    $("#global_end").on("change", (e) => updateGlobal(e, app));

    // DPP events
    $("#load_orgs").on("click", () => app.dpp.loadOrgs(app));
    $("#load_uevcbids").on("click", () => app.dpp.getOrgbasedOptions(app));
    $("#load_dpp").on("click", () => app.dpp.getDPPTableData(app));
    $("#download_dpp_excel").on("click", () => app.dpp.downloadExcel());

    // Switch events
    $(".switch_selector").on("click", switcher);
    
    // Realtime events  
    $("#load_powerplants").on("click", () => app.realtime.loadPowerPlants(app));
    $("#load_realtime").on("click", () => app.realtime.getRealtimeData(app));
    $("#download_realtime_excel").on("click", () => app.realtime.downloadExcel());

}

window.app = app;
app.init();

export default app;