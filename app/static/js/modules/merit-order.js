export const meritOrder = {
    helpers: null,
    currentData: null,
    originalAicValues: null,  // Original AIC values from API
    supplyDemandCurves: null, // Supply/demand curves for client-side MCP calc
    baseCapacityDeltas: null, // Base capacity deltas before AIC adjustments

    setup(helpers) {
        this.helpers = helpers;
    },

    init() {
        this.setupEventListeners();
        this.setupDateDefaults();
    },

    setupDateDefaults() {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        const genDateInput = document.getElementById('merit_gen_date');
        if (genDateInput) {
            genDateInput.value = yesterday.toISOString().split('T')[0];
        }

        const predDateInput = document.getElementById('merit_pred_date');
        if (predDateInput) {
            const nextWeek = new Date(yesterday);
            nextWeek.setDate(nextWeek.getDate() + 7);
            predDateInput.value = nextWeek.toISOString().split('T')[0];
        }
    },

    setupEventListeners() {
        const loadButton = document.getElementById('load_merit_order');
        const downloadExcelButton = document.getElementById('download_merit_order_excel');
        const resetButton = document.getElementById('reset_aic_values');

        if (loadButton) {
            loadButton.addEventListener('click', () => {
                this.loadMeritOrderData();
            });
        }

        if (downloadExcelButton) {
            downloadExcelButton.addEventListener('click', () => {
                this.downloadExcel();
            });
        }

        if (resetButton) {
            resetButton.addEventListener('click', () => {
                this.resetAicToZero();
            });
        }
    },

    async loadMeritOrderData() {
        const loadButton = document.getElementById('load_merit_order');
        const resultsContainer = document.getElementById('merit_order_results');
        const aicContainer = document.getElementById('merit_order_aic');
        const failureContainer = document.getElementById('merit_order_failure');

        const genDate = document.getElementById('merit_gen_date')?.value;
        const predDate = document.getElementById('merit_pred_date')?.value;

        if (!genDate || !predDate) {
            this.helpers.displayMessage('Please select both Reference Date and Prediction Date', 'warning');
            return;
        }

        try {
            if (loadButton) {
                this.helpers.toggleButtonLoading(loadButton, true);
            }

            if (resultsContainer) resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading merit order data...</p></div>';
            if (aicContainer) aicContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading AIC data...</p></div>';
            if (failureContainer) failureContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading failure data...</p></div>';

            const params = new URLSearchParams({ gen_date: genDate, pred_date: predDate });

            const [resultsResponse, aicResponse, failureResponse] = await Promise.all([
                fetch(`/merit-order-data?${params}`),
                fetch(`/merit-order-aic-data?${params}`),
                fetch(`/merit-order-failure-data`)
            ]);

            const resultsData = await resultsResponse.json();
            const aicData = await aicResponse.json();
            const failureData = await failureResponse.json();

            // Store supply/demand curves and base deltas for client-side recalculation
            if (resultsData.code === 200 && resultsData.data) {
                this.supplyDemandCurves = resultsData.data.supply_demand_curves || {};
                this.baseCapacityDeltas = resultsData.data.base_capacity_deltas || {};
            }

            // Store original AIC values (including base_date for column headers)
            if (aicData.code === 200 && aicData.data) {
                this.originalAicValues = {
                    plants: aicData.data.plants,
                    hours: aicData.data.hours,
                    values: aicData.data.values.map(row => [...row]),
                    base_date: aicData.data.base_date || null
                };
            }

            this.currentData = {
                results: resultsData,
                aic: aicData,
                failure: failureData,
                genDate: genDate,
                predDate: predDate
            };

            if (resultsData.code === 200) {
                this.renderResultsTable(resultsData.data, resultsContainer);
            } else {
                resultsContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${resultsData.error || resultsData.message || 'No results data available'}</div>`;
            }

            if (aicData.code === 200) {
                this.renderEditableAICTable(aicData.data, aicContainer);
            } else {
                aicContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${aicData.error || aicData.message || 'No AIC data available'}</div>`;
            }

            if (failureData.code === 200) {
                this.renderFailureTable(failureData.data, failureContainer);
            } else {
                failureContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${failureData.error || failureData.message || 'No failure data available'}</div>`;
            }

            // Enable buttons
            const downloadBtn = document.getElementById('download_merit_order_excel');
            if (downloadBtn) downloadBtn.disabled = false;
            const resetBtn = document.getElementById('reset_aic_values');
            if (resetBtn) resetBtn.disabled = false;

            this.helpers.displayMessage('Merit order data loaded successfully!', 'success');

        } catch (error) {
            console.error('Error loading merit order data:', error);
            this.helpers.displayMessage(`Error: ${error.message}`, 'danger');

            if (resultsContainer) resultsContainer.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> Failed to load data: ${error.message}</div>`;
            if (aicContainer) aicContainer.innerHTML = '';
            if (failureContainer) failureContainer.innerHTML = '';
        } finally {
            if (loadButton) {
                this.helpers.toggleButtonLoading(loadButton, false);
            }
        }
    },

    renderEditableAICTable(data, container) {
        if (!data || !data.plants || data.plants.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No AIC data available.</div>';
            return;
        }

        const { plants, hours, base_date } = data;
        const dateLabel = base_date ? `<div class="text-muted small mb-1">AIC Date: <strong>${base_date}</strong></div>` : '';

        let html = `
        ${dateLabel}
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover" id="aic_editable_table">
                <thead>
                    <tr class="table-dark">
                        <th class="text-center" style="min-width: 240px;">Plant Name</th>
                        ${hours.map(h => {
                            const label = base_date ? `<span style="font-size:0.65rem;opacity:0.75;display:block;">${base_date}</span>${h}` : h;
                            return `<th class="text-center" style="white-space:nowrap;">${label}</th>`;
                        }).join('')}
                    </tr>
                </thead>
                <tbody>`;

        plants.forEach((plant, idx) => {
            html += `<tr data-plant-idx="${idx}">
                <td class="fw-bold" style="white-space: nowrap;">
                    <button class="aic-toggle-btn me-1" data-plant-idx="${idx}" title="Toggle 100% capacity for all hours">
                        <i class="fas fa-power-off"></i> ON
                    </button>
                    ${plant}
                </td>
                ${hours.map((h, hIdx) => `
                    <td class="text-center p-1">
                        <input type="number"
                            class="aic-editable-input"
                            data-plant-idx="${idx}"
                            data-hour-idx="${hIdx}"
                            data-hour="${h}"
                            value="0"
                            min="0"
                            step="1">
                    </td>
                `).join('')}
            </tr>`;
        });

        html += `</tbody></table></div>`;
        container.innerHTML = html;

        // Bind events for dynamic updates
        this.bindAicEvents(container);
    },

    bindAicEvents(container) {
        // Debounce timer for recalculation
        let debounceTimer = null;

        // Input change events on AIC cells
        container.querySelectorAll('.aic-editable-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value) || 0;
                if (val !== 0) {
                    e.target.classList.add('aic-nonzero');
                } else {
                    e.target.classList.remove('aic-nonzero');
                }

                // Debounced recalculation
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.recalculateFromAic();
                }, 300);
            });
        });

        // Toggle buttons per plant row
        container.querySelectorAll('.aic-toggle-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const plantIdx = parseInt(btn.dataset.plantIdx);
                const isActive = btn.classList.contains('active');

                if (isActive) {
                    // Turn off: set all hours to 0
                    btn.classList.remove('active');
                    this.setPlantAicValues(plantIdx, 0);
                } else {
                    // Turn on: set all hours to original AIC values
                    btn.classList.add('active');
                    this.setPlantAicValues(plantIdx, null); // null = use original
                }

                this.recalculateFromAic();
            });
        });
    },

    setPlantAicValues(plantIdx, value) {
        const inputs = document.querySelectorAll(`.aic-editable-input[data-plant-idx="${plantIdx}"]`);

        inputs.forEach((input, hIdx) => {
            if (value === null) {
                // Use original AIC value
                const origVal = this.originalAicValues?.values[plantIdx]?.[hIdx] ?? 0;
                input.value = Math.round(origVal);
            } else {
                input.value = value;
            }

            if (parseFloat(input.value) !== 0) {
                input.classList.add('aic-nonzero');
            } else {
                input.classList.remove('aic-nonzero');
            }
        });
    },

    resetAicToZero() {
        const inputs = document.querySelectorAll('.aic-editable-input');
        inputs.forEach(input => {
            input.value = 0;
            input.classList.remove('aic-nonzero');
        });

        // Reset all toggle buttons
        document.querySelectorAll('.aic-toggle-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        this.recalculateFromAic();
    },

    recalculateFromAic() {
        if (!this.currentData?.results?.data || !this.baseCapacityDeltas || !this.supplyDemandCurves) {
            return;
        }

        const hours = this.originalAicValues?.hours || [];

        // Sum AIC adjustments per hour across all plants
        const aicAdjustments = {};
        hours.forEach(h => { aicAdjustments[h] = 0; });

        const inputs = document.querySelectorAll('.aic-editable-input');
        inputs.forEach(input => {
            const hour = input.dataset.hour;
            const val = parseFloat(input.value) || 0;
            aicAdjustments[hour] = (aicAdjustments[hour] || 0) + val;
        });

        // Calculate adjusted capacity deltas
        const adjustedCapacityDeltas = {};
        for (const hour of Object.keys(this.baseCapacityDeltas)) {
            const baseDelta = this.baseCapacityDeltas[hour];
            const aicAdj = aicAdjustments[hour] || 0;
            adjustedCapacityDeltas[hour] = baseDelta - aicAdj;
        }

        // Recalculate MCP merit using client-side supply/demand curves
        const mcpMeritByHour = {};
        for (const hour of Object.keys(adjustedCapacityDeltas)) {
            const curve = this.supplyDemandCurves[hour];
            if (curve) {
                mcpMeritByHour[hour] = this.calculateMeritPrice(
                    curve.prices, curve.capacities, adjustedCapacityDeltas[hour]
                );
            }
        }

        // Update the results table with new capacity deltas and MCP merit values
        this.updateResultsTable(adjustedCapacityDeltas, mcpMeritByHour);
    },

    calculateMeritPrice(prices, capacities, capacityDelta) {
        // Port of _calculate_merit_order_price for a single hour
        if (!prices || !capacities || prices.length === 0) return null;

        // Find trade capacity (where abs(capacity) is minimum = market clearing point)
        let minAbsIdx = 0;
        let minAbs = Math.abs(capacities[0]);
        for (let i = 1; i < capacities.length; i++) {
            const abs = Math.abs(capacities[i]);
            if (abs < minAbs) {
                minAbs = abs;
                minAbsIdx = i;
            }
        }
        const tradeCapacity = capacities[minAbsIdx];
        const targetCapacity = tradeCapacity - capacityDelta;

        // Find price point at target capacity
        const minCapacity = Math.min(...capacities);

        if (targetCapacity < minCapacity) {
            // Search from high to low capacity
            for (let i = capacities.length - 1; i >= 0; i--) {
                if (capacities[i] >= targetCapacity) {
                    return prices[i];
                }
            }
            return prices[prices.length - 1];
        } else {
            // Search from low to high capacity
            for (let i = 0; i < capacities.length; i++) {
                if (capacities[i] <= targetCapacity) {
                    return prices[i];
                }
            }
            return prices[0];
        }
    },

    updateResultsTable(adjustedCapacityDeltas, mcpMeritByHour) {
        const data = this.currentData?.results?.data;
        if (!data || !data.rows) return;

        const { rows } = data;

        // Update each row's capacity_delta and mcp_merit
        let totalCapacityDelta = 0;

        rows.forEach((row, idx) => {
            const refTime = this.extractTime(row.date_ref);

            // Find the matching hour key (HH:MM format)
            const hourKey = refTime;

            if (adjustedCapacityDeltas[hourKey] !== undefined) {
                row.capacity_delta = adjustedCapacityDeltas[hourKey];
            }
            if (mcpMeritByHour[hourKey] !== undefined) {
                row.mcp_merit = mcpMeritByHour[hourKey];
            }

            totalCapacityDelta += (row.capacity_delta || 0);
        });

        // Update summary
        if (data.summary_row) {
            data.summary_row.capacity_delta = totalCapacityDelta;
        }

        // Re-render
        const resultsContainer = document.getElementById('merit_order_results');
        if (resultsContainer) {
            this.renderResultsTable(data, resultsContainer);
        }
    },

    renderResultsTable(data, container) {
        if (!data || !data.rows || data.rows.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No comparison data available for selected dates.</div>';
            return;
        }

        const { rows, summary_row } = data;

        let html = `
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover merit-order-table">
                <thead>
                    <tr class="table-dark">
                        <th rowspan="2" class="text-center align-middle">Date Ref</th>
                        <th rowspan="2" class="text-center align-middle">Date Pred</th>
                        <th rowspan="2" class="text-center align-middle" style="background: #ef9a9a;">MCP Ref</th>
                        <th rowspan="2" class="text-center align-middle" style="background: #ff8a65;">MCP Merit</th>
                        <th rowspan="2" class="text-center align-middle" style="background: #ffab91;">MCP Pred</th>
                        <th colspan="1" class="text-center" style="background: #ffb74d;">Capacity</th>
                        <th colspan="3" class="text-center" style="background: #90caf9;">Demand</th>
                        <th colspan="3" class="text-center" style="background: #ce93d8;">River</th>
                        <th colspan="3" class="text-center" style="background: #80deea;">Wind</th>
                        <th colspan="3" class="text-center" style="background: #fff176;">Solar</th>
                    </tr>
                    <tr class="table-secondary">
                        <th class="text-center" style="background: #ffb74d;">\u0394</th>
                        <th class="text-center">Ref</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">\u0394</th>
                        <th class="text-center">Ref</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">\u0394</th>
                        <th class="text-center">Ref</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">\u0394</th>
                        <th class="text-center">Ref</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">\u0394</th>
                    </tr>
                </thead>
                <tbody>`;

        rows.forEach(row => {
            const refTime = this.extractTime(row.date_ref);
            const predTime = this.extractTime(row.date_pred);
            html += `<tr>
                <td class="text-center fw-bold">${refTime}</td>
                <td class="text-center fw-bold">${predTime}</td>
                <td class="text-center" style="background: #ffebee;">${row.mcp_ref !== null && row.mcp_ref !== undefined ? Number(row.mcp_ref).toFixed(2) : '-'}</td>
                <td class="text-center" style="background: #fff3e0;">${row.mcp_merit !== null && row.mcp_merit !== undefined ? Number(row.mcp_merit).toFixed(2) : '-'}</td>
                <td class="text-center" style="background: #fbe9e7;">${row.mcp_pred !== null && row.mcp_pred !== undefined ? Number(row.mcp_pred).toFixed(2) : '-'}</td>
                <td class="text-center ${this.getDeltaClass(row['capacity_delta'])}" style="font-weight: 600;">${this.formatNumber(row['capacity_delta'])}</td>
                <td class="text-center">${this.formatNumber(row.demand_ref)}</td>
                <td class="text-center">${this.formatNumber(row.demand_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.demand_delta)}">${this.formatNumber(row.demand_delta)}</td>
                <td class="text-center">${this.formatNumber(row.river_ref)}</td>
                <td class="text-center">${this.formatNumber(row.river_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.river_delta)}">${this.formatNumber(row.river_delta)}</td>
                <td class="text-center">${this.formatNumber(row.wind_ref)}</td>
                <td class="text-center">${this.formatNumber(row.wind_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.wind_delta)}">${this.formatNumber(row.wind_delta)}</td>
                <td class="text-center">${this.formatNumber(row.solar_ref)}</td>
                <td class="text-center">${this.formatNumber(row.solar_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.solar_delta)}">${this.formatNumber(row.solar_delta)}</td>
            </tr>`;
        });

        if (summary_row) {
            html += `<tr class="table-warning fw-bold">
                <td class="text-center" colspan="5">TOTAL</td>
                <td class="text-center ${this.getDeltaClass(summary_row['capacity_delta'])}">${this.formatNumber(summary_row['capacity_delta'])}</td>
                <td class="text-center">${this.formatNumber(summary_row.demand_ref)}</td>
                <td class="text-center">${this.formatNumber(summary_row.demand_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.demand_delta)}">${this.formatNumber(summary_row.demand_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.river_ref)}</td>
                <td class="text-center">${this.formatNumber(summary_row.river_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.river_delta)}">${this.formatNumber(summary_row.river_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.wind_ref)}</td>
                <td class="text-center">${this.formatNumber(summary_row.wind_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.wind_delta)}">${this.formatNumber(summary_row.wind_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.solar_ref)}</td>
                <td class="text-center">${this.formatNumber(summary_row.solar_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.solar_delta)}">${this.formatNumber(summary_row.solar_delta)}</td>
            </tr>`;
        }

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    },

    renderFailureTable(data, container) {
        if (!data || !data.rows || data.rows.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No active failures found.</div>';
            return;
        }

        const { rows } = data;

        let html = `
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover">
                <thead>
                    <tr class="table-dark">
                        <th>Plant Name</th>
                        <th class="text-center">Start Date</th>
                        <th class="text-center">End Date</th>
                        <th class="text-center">Operator Power (MW)</th>
                        <th class="text-center">Capacity at Case (MW)</th>
                        <th class="text-center">Failure Amount (MW)</th>
                    </tr>
                </thead>
                <tbody>`;

        rows.forEach(row => {
            const failureClass = row.failureAmount > 0 ? 'text-danger' : 'text-success';
            html += `<tr>
                <td class="fw-bold">${row.uevcbName}</td>
                <td class="text-center">${this.formatDate(row.caseStartDate)}</td>
                <td class="text-center">${this.formatDate(row.caseEndDate)}</td>
                <td class="text-center">${this.formatNumber(row.operatorPower)}</td>
                <td class="text-center">${this.formatNumber(row.capacityAtCaseTime)}</td>
                <td class="text-center fw-bold ${failureClass}">${this.formatNumber(row.failureAmount)}</td>
            </tr>`;
        });

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    },

    extractTime(dateStr) {
        if (!dateStr) return '-';
        try {
            const parts = dateStr.split(' ');
            if (parts.length >= 2) {
                return parts[1].substring(0, 5);
            }
            return dateStr;
        } catch {
            return dateStr;
        }
    },

    formatNumber(value) {
        if (value === null || value === undefined) return '-';
        return Math.round(value).toLocaleString('tr-TR');
    },

    formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString('tr-TR', {
                year: 'numeric', month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit'
            });
        } catch {
            return dateStr;
        }
    },

    getDeltaClass(value) {
        if (value === null || value === undefined) return '';
        if (value > 0) return 'text-success';
        if (value < 0) return 'text-danger';
        return '';
    },

    async downloadExcel() {
        if (!this.currentData) {
            this.helpers.displayMessage('Please load data first before downloading', 'warning');
            return;
        }

        const downloadBtn = document.getElementById('download_merit_order_excel');

        try {
            if (downloadBtn) {
                downloadBtn.disabled = true;
                downloadBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Preparing...';
            }

            const { genDate, predDate } = this.currentData;

            // Collect current capacity deltas from edited AIC state
            const capacityDeltas = this._getCurrentCapacityDeltas();

            this.helpers.displayMessage('Preparing Excel file for download...', 'info');

            const response = await fetch('/download-merit-order-excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    gen_date: genDate,
                    pred_date: predDate,
                    capacity_deltas: capacityDeltas
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server error ${response.status}`);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `merit_order_${genDate}_vs_${predDate}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.helpers.displayMessage('Excel file downloaded!', 'success');

        } catch (error) {
            console.error('Error downloading Excel file:', error);
            this.helpers.displayMessage(`Error: ${error.message}`, 'danger');
        } finally {
            if (downloadBtn) {
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '<i class="fas fa-file-excel"></i> Download Excel';
            }
        }
    },

    _getCurrentCapacityDeltas() {
        // Returns {hour: adjustedCapacityDelta} using current AIC inputs
        if (!this.baseCapacityDeltas || !this.originalAicValues) return {};

        const hours = this.originalAicValues.hours || [];
        const aicAdjustments = {};
        hours.forEach(h => { aicAdjustments[h] = 0; });

        document.querySelectorAll('.aic-editable-input').forEach(input => {
            const hour = input.dataset.hour;
            const val = parseFloat(input.value) || 0;
            aicAdjustments[hour] = (aicAdjustments[hour] || 0) + val;
        });

        const result = {};
        for (const hour of Object.keys(this.baseCapacityDeltas)) {
            result[hour] = this.baseCapacityDeltas[hour] - (aicAdjustments[hour] || 0);
        }
        return result;
    }
};
