import { dpp } from './modules/dpp.js';
import { realtime } from './modules/realtime.js';
import { postData, toggleLoading, displayMessage, updateGlobal, switcher } from './utils/helpers.js';
import { HTMLSearchableSelect } from './classes/HTMLSearchableSelect.js';
import { aic } from './modules/aic.js';
import { generationComparison } from './modules/generation-comparison.js';
import { heatmap } from './modules/heatmap.js';
import { importCoalHeatmap } from './modules/importCoalHeatmap.js';
import { ligniteHeatmap } from './modules/ligniteHeatmap.js';
import { miniTables } from './modules/mini-tables.js';
import { hydroHeatmap } from './modules/hydro-heatmap.js';
import { forecasting } from './modules/forecasting.js';

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
    miniTables,
    hydroHeatmap,
    forecasting,
    helpers: {
        toggleLoading: function (show) {
            const loader = document.getElementById('aic_loading');
            if (loader) {
                loader.style.display = show ? 'block' : 'none';
            }
        },
        displayMessage: function (message, type) {
            const alertContainer = document.getElementById('alert_messages');
            if (alertContainer) {
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
                alertDiv.role = 'alert';
                alertDiv.innerHTML = `
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                alertContainer.appendChild(alertDiv);
                
                // Auto-dismiss after 5 seconds
                setTimeout(() => {
                    alertDiv.remove();
                }, 5000);
            }
        },
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

    // Add cleanup method
    cleanup() {
        // Clear any intervals
        if (this.intervals) {
            Object.values(this.intervals).forEach(interval => {
                if (interval) clearInterval(interval);
            });
        }
        
        // Reset any active requests
        if (this.activeRequests) {
            Object.values(this.activeRequests).forEach(request => {
                if (request && request.abort) request.abort();
            });
        }

        // Clear any error messages
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
            this.hydroHeatmap.setup(this.helpers);
            this.miniTables.setup(this.helpers);
            
            // Initialize forecasting module
            this.forecasting.setup({
                toggleLoading: this.helpers.toggleLoading,
                displayMessage: this.helpers.displayMessage,
                toggleButtonLoading: this.helpers.toggleButtonLoading
            });
            this.forecasting.init();
            
            // Initialize mini-tables when showing home section
            this.miniTables.init();
            
            // Store intervals and active requests
            this.intervals = {};
            this.activeRequests = {};
            
            // Add event dispatching for section changes
            document.addEventListener('click', function(e) {
                const target = e.target.closest('[data-section]');
                if (target) {
                    const section = target.dataset.section;
                    // Dispatch a custom event when a section is activated
                    document.dispatchEvent(new CustomEvent('section:activated', {
                        detail: { section }
                    }));
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