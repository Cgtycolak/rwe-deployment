export const meritOrder = {
    helpers: null,
    currentData: null,
    
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
        
        // Default gen_date to yesterday
        const genDateInput = document.getElementById('merit_gen_date');
        if (genDateInput) {
            genDateInput.value = yesterday.toISOString().split('T')[0];
        }
        
        // Default pred_date to a week from gen_date
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
    },
    
    async loadMeritOrderData() {
        const loadButton = document.getElementById('load_merit_order');
        const resultsContainer = document.getElementById('merit_order_results');
        const aicContainer = document.getElementById('merit_order_aic');
        const failureContainer = document.getElementById('merit_order_failure');
        
        const genDate = document.getElementById('merit_gen_date')?.value;
        const predDate = document.getElementById('merit_pred_date')?.value;
        
        if (!genDate || !predDate) {
            this.helpers.displayMessage('Please select both Generation Date and Prediction Date', 'warning');
            return;
        }
        
        try {
            // Show loading state
            if (loadButton) {
                this.helpers.toggleButtonLoading(loadButton, true);
            }
            
            // Clear previous results
            if (resultsContainer) resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading merit order data...</p></div>';
            if (aicContainer) aicContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading AIC data...</p></div>';
            if (failureContainer) failureContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"></div><p class="mt-2">Loading failure data...</p></div>';
            
            // Fetch all data in parallel
            const params = new URLSearchParams({ gen_date: genDate, pred_date: predDate });
            
            const [resultsResponse, aicResponse, failureResponse] = await Promise.all([
                fetch(`/merit-order-data?${params}`),
                fetch(`/merit-order-aic-data?${params}`),
                fetch(`/merit-order-failure-data`)
            ]);
            
            const resultsData = await resultsResponse.json();
            const aicData = await aicResponse.json();
            const failureData = await failureResponse.json();
            
            // Store data for Excel download
            this.currentData = {
                results: resultsData,
                aic: aicData,
                failure: failureData,
                genDate: genDate,
                predDate: predDate
            };
            
            // Render results
            if (resultsData.code === 200) {
                this.renderResultsTable(resultsData.data, resultsContainer);
            } else {
                resultsContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${resultsData.error || resultsData.message || 'No results data available'}</div>`;
            }
            
            if (aicData.code === 200) {
                this.renderAICTable(aicData.data, aicContainer);
            } else {
                aicContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${aicData.error || aicData.message || 'No AIC data available'}</div>`;
            }
            
            if (failureData.code === 200) {
                this.renderFailureTable(failureData.data, failureContainer);
            } else {
                failureContainer.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${failureData.error || failureData.message || 'No failure data available'}</div>`;
            }
            
            // Enable download button
            const downloadBtn = document.getElementById('download_merit_order_excel');
            if (downloadBtn) downloadBtn.disabled = false;
            
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
    
    renderResultsTable(data, container) {
        if (!data || !data.rows || data.rows.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No comparison data available for selected dates.</div>';
            return;
        }
        
        const { columns, rows, summary_row } = data;
        
        // Build header groups
        const sources = ['capacity', 'demand', 'dam', 'river', 'wind', 'solar'];
        
        let html = `
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover merit-order-table">
                <thead>
                    <tr class="table-dark">
                        <th rowspan="2" class="text-center align-middle">Date Gen</th>
                        <th rowspan="2" class="text-center align-middle">Date Pred</th>
                        <th rowspan="2" class="text-center align-middle" style="background: #ef9a9a;">MCP</th>
                        <th colspan="1" class="text-center" style="background: #ffb74d;">Capacity</th>
                        <th colspan="3" class="text-center" style="background: #90caf9;">Demand</th>
                        <th colspan="3" class="text-center" style="background: #a5d6a7;">Dam</th>
                        <th colspan="3" class="text-center" style="background: #ce93d8;">River</th>
                        <th colspan="3" class="text-center" style="background: #80deea;">Wind</th>
                        <th colspan="3" class="text-center" style="background: #fff176;">Solar</th>
                    </tr>
                    <tr class="table-secondary">
                        <th class="text-center" style="background: #ffb74d;">Δ</th>
                        <th class="text-center">Gen</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">Δ</th>
                        <th class="text-center">Gen</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">Δ</th>
                        <th class="text-center">Gen</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">Δ</th>
                        <th class="text-center">Gen</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">Δ</th>
                        <th class="text-center">Gen</th>
                        <th class="text-center">Pred</th>
                        <th class="text-center">Δ</th>
                    </tr>
                </thead>
                <tbody>`;
        
        // Data rows
        rows.forEach(row => {
            const genTime = this.extractTime(row.date_gen);
            const predTime = this.extractTime(row.date_pred);
            html += `<tr>
                <td class="text-center fw-bold">${genTime}</td>
                <td class="text-center fw-bold">${predTime}</td>
                <td class="text-center" style="background: #ffebee;">${row.mcp !== null ? row.mcp.toFixed(2) : '-'}</td>
                <td class="text-center ${this.getDeltaClass(row['capacity_delta'])}" style="font-weight: 600;">${this.formatNumber(row['capacity_delta'])}</td>
                <td class="text-center">${this.formatNumber(row.demand_gen)}</td>
                <td class="text-center">${this.formatNumber(row.demand_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.demand_delta)}">${this.formatNumber(row.demand_delta)}</td>
                <td class="text-center">${this.formatNumber(row.dam_gen)}</td>
                <td class="text-center">${this.formatNumber(row.dam_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.dam_delta)}">${this.formatNumber(row.dam_delta)}</td>
                <td class="text-center">${this.formatNumber(row.river_gen)}</td>
                <td class="text-center">${this.formatNumber(row.river_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.river_delta)}">${this.formatNumber(row.river_delta)}</td>
                <td class="text-center">${this.formatNumber(row.wind_gen)}</td>
                <td class="text-center">${this.formatNumber(row.wind_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.wind_delta)}">${this.formatNumber(row.wind_delta)}</td>
                <td class="text-center">${this.formatNumber(row.solar_gen)}</td>
                <td class="text-center">${this.formatNumber(row.solar_pred)}</td>
                <td class="text-center ${this.getDeltaClass(row.solar_delta)}">${this.formatNumber(row.solar_delta)}</td>
            </tr>`;
        });
        
        // Summary row
        if (summary_row) {
            html += `<tr class="table-warning fw-bold">
                <td class="text-center" colspan="3">TOTAL</td>
                <td class="text-center ${this.getDeltaClass(summary_row['capacity_delta'])}">${this.formatNumber(summary_row['capacity_delta'])}</td>
                <td class="text-center">${this.formatNumber(summary_row.demand_gen)}</td>
                <td class="text-center">${this.formatNumber(summary_row.demand_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.demand_delta)}">${this.formatNumber(summary_row.demand_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.dam_gen)}</td>
                <td class="text-center">${this.formatNumber(summary_row.dam_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.dam_delta)}">${this.formatNumber(summary_row.dam_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.river_gen)}</td>
                <td class="text-center">${this.formatNumber(summary_row.river_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.river_delta)}">${this.formatNumber(summary_row.river_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.wind_gen)}</td>
                <td class="text-center">${this.formatNumber(summary_row.wind_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.wind_delta)}">${this.formatNumber(summary_row.wind_delta)}</td>
                <td class="text-center">${this.formatNumber(summary_row.solar_gen)}</td>
                <td class="text-center">${this.formatNumber(summary_row.solar_pred)}</td>
                <td class="text-center ${this.getDeltaClass(summary_row.solar_delta)}">${this.formatNumber(summary_row.solar_delta)}</td>
            </tr>`;
        }
        
        html += `</tbody></table></div>`;
        container.innerHTML = html;
    },
    
    renderAICTable(data, container) {
        if (!data || !data.plants || data.plants.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No AIC data available.</div>';
            return;
        }
        
        const { plants, hours, values } = data;
        
        let html = `
        <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover">
                <thead>
                    <tr class="table-dark">
                        <th class="text-center" style="min-width: 200px;">Plant Name</th>
                        ${hours.map(h => `<th class="text-center">${h}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>`;
        
        plants.forEach((plant, idx) => {
            html += `<tr>
                <td class="fw-bold" style="white-space: nowrap;">${plant}</td>
                ${values[idx].map(v => `<td class="text-center">${v !== null ? Math.round(v) : '-'}</td>`).join('')}
            </tr>`;
        });
        
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
            // Extract HH:MM from timestamp string like "2026-02-20 00:00:00"
            const parts = dateStr.split(' ');
            if (parts.length >= 2) {
                return parts[1].substring(0, 5); // "00:00"
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
    
    downloadExcel() {
        if (!this.currentData) {
            this.helpers.displayMessage('Please load data first before downloading', 'warning');
            return;
        }
        
        try {
            const { genDate, predDate } = this.currentData;
            const params = new URLSearchParams({ gen_date: genDate, pred_date: predDate });
            const downloadUrl = `/download-merit-order-excel?${params}`;
            
            this.helpers.displayMessage('Preparing Excel file for download...', 'info');
            window.location.href = downloadUrl;
            
            setTimeout(() => {
                this.helpers.displayMessage('Excel file download started!', 'success');
            }, 500);
            
        } catch (error) {
            console.error('Error downloading Excel file:', error);
            this.helpers.displayMessage(`Error: ${error.message}`, 'danger');
        }
    }
};
