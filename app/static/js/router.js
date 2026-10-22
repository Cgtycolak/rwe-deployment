// Hash router for the dashboard tabs. Every tab is a .content-section[data-section] in the
// page; links are <a href="#id" data-section="id">. Showing a tab fires 'section:activated'
// exactly once, after every module has registered its listeners.

let config = null;

function sectionEl(id) {
    return document.querySelector(`.content-section[data-section="${id}"]`);
}

function show(id) {
    if (!sectionEl(id)) id = config.fallback;

    config.beforeEnter?.(id);
    // Each tab is its own page to the user, so it opens at the top
    window.scrollTo(0, 0);

    document.querySelectorAll('.content-section').forEach((section) => {
        const active = section.dataset.section === id;
        section.classList.toggle('active', active);
        section.style.display = active ? 'block' : 'none';
    });

    document.querySelectorAll('.sidebar a[data-section]').forEach((link) => {
        const active = link.dataset.section === id;
        link.classList.toggle('active', active && link.classList.contains('nav-link'));
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });

    try {
        config.onEnter?.[id]?.();
    } catch (err) {
        console.error(`Opening section "${id}" failed:`, err);
    }
    document.dispatchEvent(new CustomEvent('section:activated', { detail: { section: id } }));
}

function currentHash() {
    return decodeURIComponent(window.location.hash.slice(1));
}

export function navigate(id) {
    if (currentHash() !== id) history.pushState(null, '', `#${id}`);
    show(id);
}

export function startRouter({ fallback = 'home', beforeEnter, onEnter } = {}) {
    config = { fallback, beforeEnter, onEnter };

    document.addEventListener('click', (e) => {
        const link = e.target.closest('a[data-section]');
        if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        navigate(link.dataset.section);
    });

    window.addEventListener('popstate', () => show(currentHash() || fallback));

    show(currentHash() || fallback);
}
