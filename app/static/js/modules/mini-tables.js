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
                this.renderOrderSummaryTable(result.data.orderSummary);
                this.renderSMPTable(result.data.smp.data, result.data.smp.average);
                this.renderPFCTable(result.data.pfc.data, result.data.pfc.average);
                this.renderSFCTable(result.data.sfc.data, result.data.sfc.average);
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('Error loading table data:', error);
            this.helpers.displayMessage('Error loading table data', 'error');
        }
    },

    renderOrderSummaryTable(data) {
        const container = document.getElementById('order-summary-table');
        if (!container) return;

        // Find min and max values for color scaling
        const values = data.map(item => item.value);
        const maxPositive = Math.max(...values.filter(v => v > 0), 0);
        const minNegative = Math.min(...values.filter(v => v < 0), 0);

        // Calculate total
        const total = values.reduce((sum, value) => sum + value, 0);

        let html = `
            <div class="mini-table-container">
                <h4>Load/Deload</h4>
                <p class="text-muted mb-2">Total Net: ${total.toFixed(2)} MWh</p>
                <table class="mini-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Amount</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.forEach(item => {
            const value = item.value;
            let backgroundColor;
            
            if (value > 0) {
                // Green scale for positive values
                const intensity = (value / maxPositive) * 100;
                backgroundColor = `rgba(0, 255, 0, ${intensity * 0.65}%)`;
            } else {
                // Red scale for negative values
                const intensity = (value / minNegative) * 100;
                backgroundColor = `rgba(255, 0, 0, ${intensity * 0.65}%)`;
            }

            html += `
                <tr>
                    <td>${item.datetime}</td>
                    <td style="background-color: ${backgroundColor}">${value.toFixed(2)}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    },

    renderSMPTable(data, average) {
        const container = document.getElementById('smp-table');
        if (!container) return;

        // Find min and max values for color scaling
        const values = data.map(item => item.value);
        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);
        const range = maxValue - minValue;

        let html = `
            <div class="mini-table-container">
                <h4>System Marginal Price</h4>
                <p class="text-muted mb-2">Daily Average: ${average.toFixed(2)} ₺/MWh</p>
                <table class="mini-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Price (₺/MWh)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.forEach(item => {
            const value = item.value;
            // Use a blue color scale for prices
            const intensity = ((value - minValue) / range) * 100;
            const backgroundColor = `rgba(0, 0, 255, ${intensity * 0.4}%)`;

            html += `
                <tr>
                    <td>${item.datetime}</td>
                    <td style="background-color: ${backgroundColor}">${value.toFixed(2)}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    },

    renderPFCTable(data, average) {
        const container = document.getElementById('pfc-table');
        if (!container) return;

        // Find min and max values for color scaling
        const values = data.map(item => item.value);
        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);
        const range = maxValue - minValue;

        let html = `
            <div class="mini-table-container">
                <h4>Primary Frequency Cap.</h4>
                <p class="text-muted mb-2">Average Price: ${average.toFixed(2)} ₺/MWh</p>
                <table class="mini-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Price (₺/MWh)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.forEach(item => {
            const value = item.value;
            // Use a purple color scale for PFC prices
            const intensity = ((value - minValue) / range) * 100;
            const backgroundColor = `rgba(128, 0, 128, ${intensity * 0.5}%)`;

            html += `
                <tr>
                    <td>${item.datetime}</td>
                    <td style="background-color: ${backgroundColor}">${value.toFixed(2)}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    },

    renderSFCTable(data, average) {
        const container = document.getElementById('sfc-table');
        if (!container) return;

        // Find min and max values for color scaling
        const values = data.map(item => item.value);
        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);
        const range = maxValue - minValue;

        let html = `
            <div class="mini-table-container">
                <h4>Secondary Frequency Cap.</h4>
                <p class="text-muted mb-2">Average Price: ${average.toFixed(2)} ₺/MWh</p>
                <table class="mini-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Price (₺/MWh)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        data.forEach(item => {
            const value = item.value;
            // Use an orange color scale for SFC prices
            const intensity = ((value - minValue) / range) * 100;
            const backgroundColor = `rgba(255, 165, 0, ${intensity * 0.5}%)`;

            html += `
                <tr>
                    <td>${item.datetime}</td>
                    <td style="background-color: ${backgroundColor}">${value.toFixed(2)}</td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        container.innerHTML = html;
    }
}; 