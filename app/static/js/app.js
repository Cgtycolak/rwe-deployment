import { dpp } from './modules/dpp.js';
import { realtime } from './modules/realtime.js';
import { postData, toggleLoading, displayMessage, updateGlobal, switcher } from './utils/helpers.js';
import { HTMLSearchableSelect } from './classes/HTMLSearchableSelect.js';
import { aic } from './modules/aic.js';
import { generationComparison } from './modules/generation-comparison.js';

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
    
    init() {
        $(document).ready(() => {
            setupEvents();
            
            // Initialize modules
            this.aic.setup({ displayMessage });
            this.generationComparison.setup({ displayMessage });
            
            // Initial section visibility is handled by base.html script
        });
    }
};

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
    
    // Generation comparison specific switches
    $("[data-group='comparison_view']").on("click", (e) => {
        const button = $(e.currentTarget);
        const targetView = button.data('switch');
        
        // Update buttons
        $("[data-group='comparison_view']").removeClass('active');
        button.addClass('active');
        
        // Show/hide views
        $(".switch_arg[data-group='comparison_view']").hide();
        $(`.switch_arg[data-switch='${targetView}']`).show();
    });

    // Realtime events  
    $("#load_powerplants").on("click", () => app.realtime.loadPowerPlants(app));
    $("#load_realtime").on("click", () => app.realtime.getRealtimeData(app));
    $("#download_realtime_excel").on("click", () => app.realtime.downloadExcel());

    // AIC events
    $("#load_aic").on("click", () => app.aic.loadAICData());
    $("#download_aic_excel").on("click", () => app.aic.downloadExcel());

    // AIC specific events
    document.querySelectorAll('.aic-range-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            // Update button states
            document.querySelectorAll('.aic-range-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            e.target.classList.add('active');

            // Load data for selected range
            const range = e.target.dataset.range;
            if (window.app?.aic) {
                window.app.aic.loadAICData(range);
            }
        });
    });
}

// Wait for document and plugins to be ready
$(document).ready(() => {
    app.init();
});

export default app;