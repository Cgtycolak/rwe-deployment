import { dpp } from './modules/dpp.js';
import { realtime } from './modules/realtime.js';
import { postData, toggleLoading, displayMessage, updateGlobal, switcher, toggleButtonLoading } from './utils/helpers.js';
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

    // DPP events with loading states
    $("#load_orgs").on("click", async (e) => {
        toggleButtonLoading(e.currentTarget, true);
        await app.dpp.loadOrgs(app);
        toggleButtonLoading(e.currentTarget, false);
    });

    $("#load_uevcbids").on("click", async (e) => {
        toggleButtonLoading(e.currentTarget, true);
        await app.dpp.getOrgbasedOptions(app);
        toggleButtonLoading(e.currentTarget, false);
    });

    $("#load_dpp").on("click", async (e) => {
        toggleButtonLoading(e.currentTarget, true);
        await app.dpp.getDPPTableData(app);
        toggleButtonLoading(e.currentTarget, false);
    });

    // Switch events
    $(".switch_selector").on("click", switcher);

    // Realtime events with loading states
    $("#load_powerplants").on("click", async (e) => {
        toggleButtonLoading(e.currentTarget, true);
        await app.realtime.loadPowerPlants(app);
        toggleButtonLoading(e.currentTarget, false);
    });

    $("#load_realtime").on("click", async (e) => {
        toggleButtonLoading(e.currentTarget, true);
        await app.realtime.getRealtimeData(app);
        toggleButtonLoading(e.currentTarget, false);
    });
}

// Wait for document and plugins to be ready
$(document).ready(() => {
    app.init();
});

export default app;