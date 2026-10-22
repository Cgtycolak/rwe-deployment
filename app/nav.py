"""Dashboard tabs: the single source for the sidebar, the home page index and the section partials.

Each section id is the URL hash (``/#merit-order``), the ``data-section`` value the JS
router listens for, and the partial name under ``templates/sections/<id>.html``.
"""

# (id, label, Font Awesome icon, one-line description shown on the home page)
NAV_GROUPS = [
    (None, [
        ('home', 'Home', 'fa-home', 'Latest prices and an index of every tab.'),
    ]),
    ('Reports and heatmaps', [
        ('generation-heatmap', 'Natural Gas DPP Heatmap', 'fa-fire',
         'First and final DPP and realtime output for gas plants, by hour.'),
        ('import-coal-heatmap', 'Import Coal DPP Heatmap', 'fa-industry',
         'First and final DPP for import coal plants, with a date comparison.'),
        ('hydro-heatmap', 'Hydro DPP Heatmap', 'fa-water',
         'First and final DPP and realtime output for hydro plants, by hour.'),
        ('lignite-heatmap', 'Lignite DPP Heatmap', 'fa-industry',
         'First and final DPP and realtime output for lignite plants, by hour.'),
        ('source-heatmap', 'Generation by Source DPP Heatmap', 'fa-solar-panel',
         'First and final DPP and realtime output by generation source.'),
    ]),
    ('Data analysis', [
        ('rolling-averages', 'CAO Charts', 'fa-chart-line',
         'Rolling averages of production, demand and solar.'),
    ]),
    ('Expectations', [
        ('gas-gm', 'Gas Consumption & GM', 'fa-gas-pump',
         'Expected gas consumption and gross margin for the month.'),
    ]),
    ('Forecasting', [
        ('forecasting', 'System Direction Forecast', 'fa-chart-line',
         'Upload the daily report to forecast the system direction.'),
        ('forecast-performance', 'Forecast Performance', 'fa-chart-bar',
         'How the forecasting models compared with realised prices.'),
    ]),
    ('Analysis', [
        ('merit-order', 'Merit Order', 'fa-balance-scale',
         'Generation against predictions, with available capacity and outages.'),
        ('hydro-map', 'Hydro Map', 'fa-water',
         'Hydro plants and their generation on a map of Turkey.'),
        ('supply-demand-price', 'Supply Demand Price', 'fa-table',
         'Hourly supply and demand by price level for a chosen day.'),
        ('sfc-price', 'SFC Price', 'fa-wave-square',
         'Secondary frequency capacity prices as a line chart and heatmap.'),
    ]),
    # Used less often, so this group sits at the bottom of the sidebar
    ('Plan vs realtime', [
        ('kgup-realtime', 'DPP - Realtime', 'fa-bolt',
         'Hourly planned and realtime generation for the organisations, units or plants you pick.'),
        ('aic-realtime', 'AIC - Realtime - DPP', 'fa-chart-line',
         'System-wide available capacity against planned and realtime generation.'),
        ('generation-comparison', 'Generation Comparison', 'fa-chart-bar',
         'Planned against realtime generation by fuel, and the gap between them.'),
    ]),
]


def nav_groups():
    return [
        {'label': label,
         'sections': [{'id': sid, 'label': text, 'icon': icon, 'description': desc}
                      for sid, text, icon, desc in items]}
        for label, items in NAV_GROUPS
    ]


def section_ids():
    return [sid for _, items in NAV_GROUPS for sid, _, _, _ in items]
