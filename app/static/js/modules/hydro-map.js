export const hydroMap = {
    helpers: null,
    geo: null,              // Turkey province outlines, fetched once
    currentData: null,
    type: 'river',
    loaded: false,
    _groups: [],            // whatever is currently drawn, at the current level

    // Equirectangular plot: a degree of latitude is longer than a degree of
    // longitude at Turkey's latitude, so the y axis is stretched to keep the
    // country from looking squashed, and bubble radii are corrected to match.
    ASPECT: 1.28,

    // Bubbles are sized in PIXELS and converted to data units for every draw.
    // Sizing them in degrees made zooming magnify the blobs instead of revealing
    // detail — at city zoom a single bubble covered the whole viewport.
    RPX_MIN: 7,
    RPX_MAX: 46,
    CAP_REF: 2500,          // MW mapped to RPX_MAX
    CAP_KNEE: 10,           // MW below which the size curve flattens

    // Detail level by visible longitude span. Zoomed out, districts sit on top of
    // each other (309 of them, many within a few km), so they roll up into
    // provinces and then NUTS1 regions — "East Black Sea" as one bubble.
    // Turkey spans ~19.7°, so the default view lands on provinces: 11 region
    // bubbles left most of the map empty, while 71 provinces overlap in only a
    // handful of places. Regions appear when you zoom further out.
    LEVELS: [
        { name: 'region',   minSpan: 26, key: g => g.region || 'Unknown',         label: g => g.region || 'Unknown' },
        { name: 'province', minSpan: 2.5, key: g => g.province,                    label: g => g.province },
        { name: 'district', minSpan: 0,  key: g => `${g.province}|${g.district}`,  label: g => `${g.district} / ${g.province}` },
    ],

    setup(helpers) { this.helpers = helpers; },

    init() {
        const reload = document.getElementById('load_hydro_map');
        if (reload) reload.addEventListener('click', () => this.load());

        const group = document.getElementById('hydro_map_type');
        if (group) {
            group.querySelectorAll('button[data-type]').forEach(btn => {
                btn.addEventListener('click', () => {
                    group.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    this.type = btn.dataset.type;
                    this.load();
                });
            });
        }

        // Changing the date reloads directly — no need to also press Reload.
        const dateInput = document.getElementById('hydro_map_date');
        if (dateInput) dateInput.addEventListener('change', () => this.load());

        // Only fetch when the tab is actually opened — init() runs for every module.
        document.addEventListener('section:activated', (e) => {
            if (e.detail?.section === 'hydro-map' && !this.loaded) {
                this.loaded = true;
                this.load();
            }
        });
    },

    async loadGeo() {
        if (!this.geo) {
            const r = await fetch('/static/data/tr-provinces.geojson');
            this.geo = await r.json();
        }
        return this.geo;
    },

    async load() {
        const button = document.getElementById('load_hydro_map');
        const host = document.getElementById('hydro_map_chart');
        const date = document.getElementById('hydro_map_date')?.value;
        if (!host) return;

        // A slow request must not overwrite a newer one's results
        const requestId = (this._requestId || 0) + 1;
        this._requestId = requestId;

        try {
            if (button) this.helpers.toggleButtonLoading(button, true);
            host.innerHTML = '<div class="text-center p-5"><div class="spinner-border text-primary"></div><p class="mt-2">Loading map...</p></div>';

            const params = new URLSearchParams({ type: this.type });
            if (date) params.set('date', date);
            const [geo, resp] = await Promise.all([
                this.loadGeo(),
                fetch(`/hydro-map-data?${params}`).then(r => r.json())
            ]);
            if (this._requestId !== requestId) return;

            if (resp.code !== 200) {
                host.innerHTML = `<div class="alert alert-warning m-3"><i class="fas fa-exclamation-triangle"></i> ${resp.message || 'No data available'}</div>`;
                document.getElementById('hydro_map_table').innerHTML = '';
                document.getElementById('hydro_map_summary').innerHTML = '';
                return;
            }

            this.currentData = resp.data;
            // Reflect the day actually served, so an empty date box fills itself in
            // and a failed overnight job shows the last good day rather than blanks.
            const input = document.getElementById('hydro_map_date');
            if (input && input.value !== resp.data.date) input.value = resp.data.date;
            // Constrain the picker to days we actually hold, so a date that would
            // only ever 404 cannot be chosen in the first place.
            this.applyDateBounds(input, resp.data.date_range, resp.data.available_dates);

            // summary first: it creates the element updateLevelBadge writes into
            this.renderSummary(resp.data);
            this.plot(geo, resp.data, host);
        } catch (err) {
            if (this._requestId !== requestId) return;
            console.error('hydro map error', err);
            host.innerHTML = `<div class="alert alert-danger m-3"><i class="fas fa-exclamation-triangle"></i> Could not load the map: ${err.message}</div>`;
        } finally {
            if (button) this.helpers.toggleButtonLoading(button, false);
        }
    },

    applyDateBounds(input, range, dates) {
        if (!input || !range) return;
        input.min = range.min;
        input.max = range.max;
        const hint = input.parentElement?.querySelector('small');
        if (hint) {
            hint.textContent = range.min === range.max
                ? `Only ${range.min} is loaded`
                : `Loaded ${range.min} to ${range.max}`;
        }
    },

    // ---- aggregation -------------------------------------------------------

    levelFor(span) {
        return this.LEVELS.find(l => span >= l.minSpan) || this.LEVELS[this.LEVELS.length - 1];
    },

    /** Roll the district rows up to `level`, positioning each group at its
     *  capacity-weighted centroid so the bubble sits where the plants are. */
    aggregate(districts, level) {
        const buckets = new Map();
        districts.forEach(d => {
            const k = level.key(d);
            let b = buckets.get(k);
            if (!b) {
                b = { key: k, label: level.label(d), region: d.region, province: d.province,
                      district: d.district, capacity_mw: 0, generation_mwh: 0,
                      plants: [], _wlat: 0, _wlon: 0, _w: 0 };
                buckets.set(k, b);
            }
            b.capacity_mw += d.capacity_mw;
            b.generation_mwh += d.generation_mwh;
            b.plants.push(...d.plants);
            const w = Math.max(d.capacity_mw, 0.001);
            b._wlat += d.lat * w; b._wlon += d.lon * w; b._w += w;
        });
        return [...buckets.values()].map(b => {
            const ceiling = b.capacity_mw * 24;
            b.lat = b._wlat / b._w;
            b.lon = b._wlon / b._w;
            b.fill = ceiling > 0 ? Math.min(b.generation_mwh / ceiling, 1) : 0;
            b.plants.sort((x, y) => y.capacity_mw - x.capacity_mw);
            return b;
        }).sort((a, b) => b.capacity_mw - a.capacity_mw);
    },

    /** Bubble radius in pixels — log scale, because district capacity spans
     *  1 MW to 2,400 MW and a linear/sqrt scale flattened the small ones. */
    radiusPx(capacityMw) {
        const span = Math.log1p(this.CAP_REF / this.CAP_KNEE);
        const r = this.RPX_MIN + (this.RPX_MAX - this.RPX_MIN) *
                  Math.log1p(Math.max(capacityMw, 0) / this.CAP_KNEE) / span;
        return Math.min(Math.max(r, this.RPX_MIN), this.RPX_MAX);
    },

    /** Lower part of an ellipse, filled to `frac` of its height — the "water". */
    waterPath(cx, cy, rx, ry, frac) {
        if (frac <= 0) return null;
        const f = Math.min(frac, 1);
        const yTop = cy - ry + 2 * ry * f;
        const tTop = Math.acos(Math.max(-1, Math.min(1, (yTop - cy) / ry)));
        const pts = [];
        const N = 28;
        for (let i = 0; i <= N; i++) {
            const t = tTop + (i / N) * (2 * Math.PI - 2 * tTop);
            pts.push(`${(cx + rx * Math.sin(t)).toFixed(4)},${(cy + ry * Math.cos(t)).toFixed(4)}`);
        }
        return 'M ' + pts.join(' L ') + ' Z';
    },

    // ---- drawing -----------------------------------------------------------

    plot(geo, data, host) {
        const lx = [], ly = [];
        geo.features.forEach(f => {
            const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
            polys.forEach(poly => poly.forEach(ring => {
                ring.forEach(([x, y]) => { lx.push(x); ly.push(y); });
                lx.push(null); ly.push(null);
            }));
        });

        const traces = [
            { x: lx, y: ly, mode: 'lines', type: 'scatter', hoverinfo: 'skip',
              line: { color: '#b9c6d4', width: 1 }, showlegend: false },
            // highlight ring for the hovered bubble (shapes cannot be hovered)
            { x: [], y: [], mode: 'markers', type: 'scatter', hoverinfo: 'skip',
              marker: { size: [0], color: 'rgba(0,0,0,0)', line: { color: '#0b4c73', width: 3 } },
              showlegend: false },
            // invisible markers carry the tooltips
            { x: [], y: [], mode: 'markers', type: 'scatter', customdata: [],
              marker: { size: [], color: 'rgba(0,0,0,0)' },
              hovertemplate: '%{customdata}<extra></extra>',
              hoverlabel: { bgcolor: '#ffffff', bordercolor: '#12608f', align: 'left',
                            font: { size: 12, color: '#20313f' } },
              showlegend: false },
        ];
        this.HIGHLIGHT = 1;
        this.TARGETS = 2;

        const layout = {
            margin: { l: 10, r: 10, t: 10, b: 10 },
            xaxis: { visible: false, range: [25.5, 45.2] },
            yaxis: { visible: false, range: [35.5, 42.5], scaleanchor: 'x', scaleratio: this.ASPECT },
            shapes: [],
            paper_bgcolor: '#ffffff', plot_bgcolor: '#f4f8fb',
            hovermode: 'closest', dragmode: 'pan',
        };

        host.innerHTML = '';
        Plotly.newPlot(host, traces, layout, { responsive: true, displayModeBar: true, scrollZoom: true })
            .then(() => {
                this.redraw(host);
                this.bindEvents(host);
            });
    },

    /** Re-aggregate for the current zoom and repaint bubbles. */
    redraw(host) {
        const data = this.currentData;
        if (!data) return;
        const full = host._fullLayout;
        const xr = full.xaxis.range;
        const span = Math.abs(xr[1] - xr[0]);
        const pxPerX = (full.xaxis._length || host.clientWidth || 800) / span;

        const level = this.levelFor(span);
        const groups = this.aggregate(data.districts.filter(d => d.lat != null), level);
        this._groups = groups;
        this._level = level;
        this.renderTable(groups, level);

        const shapes = [];
        groups.forEach(g => {
            const rx = this.radiusPx(g.capacity_mw) / pxPerX;   // px -> data units
            const ry = rx / this.ASPECT;
            const water = this.waterPath(g.lon, g.lat, rx, ry, g.fill);
            if (water) {
                shapes.push({ type: 'path', path: water, xref: 'x', yref: 'y',
                              fillcolor: 'rgba(23,131,199,0.78)', line: { width: 0 }, layer: 'above' });
            }
            shapes.push({ type: 'circle', xref: 'x', yref: 'y',
                          x0: g.lon - rx, x1: g.lon + rx, y0: g.lat - ry, y1: g.lat + ry,
                          line: { color: '#12608f', width: 1.1 },
                          fillcolor: 'rgba(23,131,199,0.07)', layer: 'above' });
        });

        Plotly.relayout(host, { shapes });
        Plotly.restyle(host, {
            x: [groups.map(g => g.lon)],
            y: [groups.map(g => g.lat)],
            customdata: [groups.map(g => this.hoverText(g, level))],
            'marker.size': [groups.map(g => this.radiusPx(g.capacity_mw) * 2)],
        }, [this.TARGETS]);

        this.updateLevelBadge(level, groups.length);
    },

    hoverText(g, level) {
        const n = (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 });
        const top = g.plants.slice(0, 5).map(p =>
            `&nbsp;&nbsp;${p.name.length > 30 ? p.name.slice(0, 29) + '…' : p.name} — ${n(p.capacity_mw)} MW` +
            (p.generation_mwh == null ? '' : ` / ${n(p.generation_mwh)} MWh`)
        ).join('<br>');
        const more = g.plants.length > 5 ? `<br>&nbsp;&nbsp;<i>+${g.plants.length - 5} more</i>` : '';
        const hint = level.name === 'district' ? '' :
            `<br><i style="color:#6b7f90">zoom in to split by ${level.name === 'region' ? 'province' : 'district'}</i>`;
        return `<b>${g.label}</b><br>` +
               `Capacity: <b>${n(g.capacity_mw)} MW</b><br>` +
               `Generation: <b>${n(g.generation_mwh)} MWh</b><br>` +
               `Capacity factor: <b>${(g.fill * 100).toFixed(1)}%</b><br>` +
               `<br>Plants (${g.plants.length}):<br>${top}${more}${hint}`;
    },

    bindEvents(host) {
        let timer = null;
        host.on('plotly_relayout', (ev) => {
            // only zoom/pan changes matter, and only once the gesture settles
            const touched = Object.keys(ev || {}).some(k => k.startsWith('xaxis') || k.startsWith('yaxis'));
            if (!touched) return;
            clearTimeout(timer);
            timer = setTimeout(() => this.redraw(host), 90);
        });

        host.on('plotly_hover', (ev) => {
            const p = ev.points?.[0];
            if (!p || p.curveNumber !== this.TARGETS) return;
            const g = this._groups[p.pointIndex];
            if (!g) return;
            Plotly.restyle(host, {
                x: [[g.lon]], y: [[g.lat]],
                'marker.size': [[this.radiusPx(g.capacity_mw) * 2.3]],   // grows on hover
            }, [this.HIGHLIGHT]);
        });
        host.on('plotly_unhover', () => {
            Plotly.restyle(host, { x: [[]], y: [[]] }, [this.HIGHLIGHT]);
        });
    },

    updateLevelBadge(level, count) {
        const el = document.getElementById('hydro_map_level');
        if (!el) return;
        const names = { region: 'Regions', province: 'Provinces', district: 'Districts' };
        el.textContent = `${names[level.name]} · ${count} bubbles · zoom in for more detail`;
    },

    renderSummary(data) {
        const el = document.getElementById('hydro_map_summary');
        if (!el) return;
        const s = data.summary;
        const label = { river: 'Run-of-river', dammed: 'Dammed', all: 'All hydro' }[data.type] || data.type;
        const n = (v) => Number(v).toLocaleString('en-US');
        el.innerHTML = `<strong>${data.date}</strong> · ${label} · ${s.plants} plants, ${s.districts} districts ·
            Capacity ${n(s.capacity_mw)} MW · Generation ${n(s.generation_mwh)} MWh
            <div id="hydro_map_level" class="mt-1"></div>`;
    },

    renderTable(groups, level) {
        const el = document.getElementById('hydro_map_table');
        if (!el) return;
        const n = (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 });

        // Columns follow the map: at region zoom the table lists regions, not the
        // 309 districts underneath them, so the two always describe the same thing.
        const cols = { region: ['Region'], province: ['Region', 'Province'],
                       district: ['Region', 'Province', 'District'] }[level.name];
        const cellsFor = (g) => ({
            region: [g.region || ''], province: [g.region || '', g.province],
            district: [g.region || '', g.province, g.district],
        }[level.name]);

        const shown = groups.slice(0, 40);
        const body = shown.map(g => `
            <tr>
                ${cellsFor(g).map(c => `<td>${c}</td>`).join('')}
                <td class="text-end">${n(g.capacity_mw)}</td>
                <td class="text-end">${n(g.generation_mwh)}</td>
                <td class="text-end">${(g.fill * 100).toFixed(1)}%</td>
                <td class="text-end">${g.plants.length}</td>
            </tr>`).join('');

        const names = { region: 'regions', province: 'provinces', district: 'districts' };
        const more = groups.length > shown.length
            ? ` Showing the 40 largest by capacity of ${groups.length}.` : '';

        el.innerHTML = `
            <div class="p-2 small text-muted border-bottom">
                The same ${names[level.name]} drawn on the map, largest capacity first.
                <strong>Capacity factor</strong> is generation divided by what the
                ${names[level.name].slice(0, -1)} could have produced running flat out for 24 h —
                it is the bubble's fill level. A low value means the plants were idle or
                water was short, not that data is missing.${more}
            </div>
            <div class="table-responsive">
                <table class="table table-sm table-hover mb-0">
                    <thead class="table-dark"><tr>
                        ${cols.map(c => `<th>${c}</th>`).join('')}
                        <th class="text-end">Capacity (MW)</th>
                        <th class="text-end">Generation (MWh)</th>
                        <th class="text-end">Capacity factor</th>
                        <th class="text-end">Plants</th>
                    </tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>`;
    },
};
