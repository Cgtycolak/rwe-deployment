// Loads Plotly (3.5 MB) without holding up the dashboard. Until it has loaded,
// window.Plotly is a stand-in whose methods wait for it and then call the real
// one, in call order, returning the real call's promise. Plotly's own script
// replaces the stand-in once it runs, so later calls go straight to it.
// Code that needs the chart element afterwards (gd.on, gd._fullLayout) must
// wait for the promise newPlot/react returns, as it already has to for Plotly.
(function () {
    const SRC = 'https://cdn.plot.ly/plotly-2.29.1.min.js';

    const failed = () => {
        const box = document.getElementById('alert_messages');
        if (box) box.innerHTML = '<div class="alert alert-danger" role="alert">'
            + 'The chart library could not be loaded. Reload the page to try again.</div>';
        return new Error('Plotly failed to load');
    };

    const ready = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = SRC;
        script.async = true;
        // the stand-in still in place means the script ran without defining Plotly
        script.onload = () => (window.Plotly === standIn ? reject(failed()) : resolve());
        script.onerror = () => reject(failed());
        document.head.appendChild(script);
    });

    const whenLoaded = (name) => (...args) => ready.then(() => window.Plotly[name](...args));

    const standIn = {
        newPlot: whenLoaded('newPlot'),
        react: whenLoaded('react'),
        relayout: whenLoaded('relayout'),
        restyle: whenLoaded('restyle'),
        purge: whenLoaded('purge'),
        downloadImage: whenLoaded('downloadImage'),
        Plots: { resize: (...args) => ready.then(() => window.Plotly.Plots.resize(...args)) },
    };
    window.Plotly = standIn;
})();
