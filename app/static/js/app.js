import { dpp } from './modules/dpp.js';
import { realtime } from './modules/realtime.js';
import { postData, toggleLoading, displayMessage, updateGlobal, switcher } from './utils/helpers.js';
import { HTMLSearchableSelect } from './classes/HTMLSearchableSelect.js';
import { aic } from './modules/aic.js';

// Main app object
const app = {
    global: {
        start: null,
        end: null,
    },
    dpp,
    realtime,
    aic,
    
    init() {
        setupEvents();
        
        // Initialize AIC module with helper functions
        this.aic.setup({
            // toggleLoading,
            displayMessage
        });
        this.aic.init();
        
        // Load AIC data when that section becomes active
        document.querySelectorAll('.nav-button').forEach(button => {
            button.addEventListener('click', () => {
                if (button.dataset.section === 'aic-realtime') {
                    this.aic.loadAICData('week'); // Default to weekly view
                }
            });
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

    // Realtime events  
    $("#load_powerplants").on("click", () => app.realtime.loadPowerPlants(app));
    $("#load_realtime").on("click", () => app.realtime.getRealtimeData(app));
    $("#download_realtime_excel").on("click", () => app.realtime.downloadExcel());

    // AIC events
    $("#load_aic").on("click", () => app.aic.loadAICData());
    $("#download_aic_excel").on("click", () => app.aic.downloadExcel());
}

// Wait for document and plugins to be ready
$(document).ready(() => {
    app.init();
});

export default app;