// Supply Demand Price tab: hourly supply-demand table coloured against a threshold.
// Moved from an inline script in index.html.

export const supplyDemandPrice = {
    init() {
        // Set default date to today
        const sdpDateInput = document.getElementById('sdp_date');
        if (sdpDateInput && !sdpDateInput.value) {
            sdpDateInput.value = new Date().toISOString().split('T')[0];
        }

        /**
         * Smooth yellow-only gradient:
         *   val <= 0       → white
         *   0 → threshold  → white → light yellow (#fffef0 → #ffe066)
         *   > threshold    → deeper amber yellow (#ffe066 → #cc8800), capped at 4x threshold
         */
        function getCellColor(val, threshold) {
            if (threshold <= 0) threshold = 1;
            if (val <= 0) return '#ffffff';

            function lerp(a, b, t) { return Math.round(a + (b - a) * t); }

            if (val < threshold) {
                const t = val / threshold;
                // white (255,254,240) → light yellow (255,224,102)
                const r = lerp(255, 255, t);
                const g = lerp(254, 224, t);
                const b = lerp(240, 102, t);
                return `rgb(${r},${g},${b})`;
            } else {
                const t = Math.min(1, (val - threshold) / (threshold * 3));
                // light yellow (255,224,102) → deep amber (204,136,0)
                const r = lerp(255, 204, t);
                const g = lerp(224, 136, t);
                const b = lerp(102, 0,   t);
                return `rgb(${r},${g},${b})`;
            }
        }

        /**
         * Price color: red (low price) → green (high price)
         */
        function getPriceColor(price, minPrice, maxPrice) {
            const range = maxPrice - minPrice || 1;
            const t = (price - minPrice) / range; // 0=red, 1=green
            const r = Math.round(220 * (1 - t));
            const g = Math.round(180 * t);
            return `rgb(${r},${g},40)`;
        }

        document.getElementById('load_sdp').addEventListener('click', function() {
            const date = document.getElementById('sdp_date').value;
            const threshold = parseFloat(document.getElementById('sdp_threshold').value) || 50;

            if (!date) {
                const statusEl = document.getElementById('sdp_status');
                statusEl.style.display = '';
                statusEl.innerHTML = '<div class="alert alert-warning">Select a date to load the table.</div>';
                return;
            }

            const btn = this;
            const spinner = btn.querySelector('.spinner-border');
            const btnContent = btn.querySelector('.button-content');
            btn.disabled = true;
            spinner.classList.remove('d-none');
            btnContent.classList.add('d-none');

            const statusEl = document.getElementById('sdp_status');
            statusEl.style.display = 'none';

            fetch(`/api/supply_demand_price?date=${encodeURIComponent(date)}&threshold=${threshold}`)
                .then(r => {
                    const ct = r.headers.get('content-type') || '';
                    if (!ct.includes('application/json')) {
                        return r.text().then(txt => {
                            throw new Error(`Server returned non-JSON (HTTP ${r.status}): ${txt.substring(0, 300)}`);
                        });
                    }
                    return r.json();
                })
                .then(data => {
                    btn.disabled = false;
                    spinner.classList.add('d-none');
                    btnContent.classList.remove('d-none');

                    if (data.error) {
                        statusEl.style.display = '';
                        statusEl.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle"></i> ${data.error}</div>`;
                        return;
                    }

                    const thead = document.getElementById('sdp_thead');
                    const tbody = document.getElementById('sdp_tbody');
                    const emptyMsg = document.getElementById('sdp_empty');
                    const table = document.getElementById('sdp_table');

                    if (!data.rows || data.rows.length === 0) {
                        thead.innerHTML = '';
                        tbody.innerHTML = '';
                        table.style.display = 'none';
                        emptyMsg.style.display = '';
                        return;
                    }

                    table.style.display = '';
                    emptyMsg.style.display = 'none';

                    // Build header — row 1: column labels
                    let headerHtml = '<tr><th>Date</th><th>Price</th>';
                    data.hour_cols.forEach(h => { headerHtml += `<th>${h}</th>`; });
                    headerHtml += '</tr>';

                    // Row 2: PTF prices
                    headerHtml += '<tr style="background:#1a5276;color:#fff;">';
                    headerHtml += '<th style="background:#1a5276;font-size:0.7rem;">PTF</th>';
                    headerHtml += '<th style="background:#1a5276;font-size:0.7rem;">₺/MWh</th>';
                    if (data.ptf_row && data.ptf_row.length) {
                        data.ptf_row.forEach(val => {
                            const display = val !== null ? val.toFixed(2) : '—';
                            headerHtml += `<th style="background:#1a5276;font-weight:400;font-size:0.7rem;">${display}</th>`;
                        });
                    } else {
                        data.hour_cols.forEach(() => { headerHtml += '<th style="background:#1a5276;">—</th>'; });
                    }
                    headerHtml += '</tr>';

                    thead.innerHTML = headerHtml;

                    // Build rows
                    const minP = data.min_price;
                    const maxP = data.max_price;
                    let bodyHtml = '';
                    data.rows.forEach(row => {
                        const priceColor = getPriceColor(row.price, minP, maxP);
                        bodyHtml += `<tr>`;
                        bodyHtml += `<td>${row.trade_date}</td>`;
                        bodyHtml += `<td style="background-color:${priceColor};color:#fff;font-weight:600;">${row.price.toFixed(2)}</td>`;
                        data.hour_cols.forEach(h => {
                            const val = row.hours[h];
                            const bg = getCellColor(val, data.threshold);
                            bodyHtml += `<td style="background-color:${bg};">${Math.round(val)}</td>`;
                        });
                        bodyHtml += `</tr>`;
                    });
                    tbody.innerHTML = bodyHtml;

                    // JS-based sticky header: translate thead by scroll offset
                    const wrapper = document.getElementById('sdp_wrapper');
                    wrapper.onscroll = function() {
                        thead.style.transform = `translateY(${this.scrollTop}px)`;
                    };
                    // Reset on fresh load
                    thead.style.transform = 'translateY(0)';
                })
                .catch(err => {
                    btn.disabled = false;
                    spinner.classList.add('d-none');
                    btnContent.classList.remove('d-none');
                    statusEl.style.display = '';
                    statusEl.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle"></i> ${err.message}</div>`;
                });
        });
    }
};
