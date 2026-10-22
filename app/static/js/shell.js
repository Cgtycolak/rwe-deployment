// Page chrome that is not tied to a tab: sidebar collapse and the searchable option lists.

export function setupSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const main = document.querySelector('.main-content');
    const toggle = document.querySelector('.toggle-sidebar');
    if (!sidebar || !toggle) return;
    const narrow = window.matchMedia('(max-width: 768px)');
    const sync = () => {
        const open = narrow.matches ? sidebar.classList.contains('expanded') : !sidebar.classList.contains('collapsed');
        toggle.setAttribute('aria-expanded', String(open));
    };

    // Wide screens collapse the sidebar to icons; narrow screens open it over the content
    toggle.addEventListener('click', () => {
        if (narrow.matches) {
            sidebar.classList.toggle('expanded');
        } else {
            const collapsed = sidebar.classList.toggle('collapsed');
            main?.classList.toggle('expanded', collapsed);
        }
        sync();
    });

    // Picking a tab on a narrow screen closes the open sidebar
    sidebar.addEventListener('click', (e) => {
        if (narrow.matches && e.target.closest('a[data-section]')) {
            sidebar.classList.remove('expanded');
            sync();
        }
    });

    narrow.addEventListener('change', sync);
    sync();
}

// <input data-filter-select="id"> filters the options of <select id="id">;
// <input type="checkbox" data-select-all="id"> selects or clears all of them.
export function setupSelectFilters() {
    document.addEventListener('input', (e) => {
        const id = e.target.dataset?.filterSelect;
        if (!id) return;
        const select = document.getElementById(id);
        const query = e.target.value.toLowerCase();
        Array.from(select?.options || []).forEach((option) => {
            const haystack = [option.text, option.value, option.title || ''].join(' ').toLowerCase();
            option.style.display = haystack.includes(query) ? '' : 'none';
        });
    });

    document.addEventListener('change', (e) => {
        const id = e.target.dataset?.selectAll;
        if (!id) return;
        const select = document.getElementById(id);
        Array.from(select?.options || []).forEach((option) => { option.selected = e.target.checked; });
    });
}
