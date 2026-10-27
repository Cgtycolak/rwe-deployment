// Previous/next-day buttons around a tab's date input, plus the left and
// right arrow keys while that tab is open. A changed day (stepped or picked) is loaded by pressing
// the tab's own load button, once the stepping pauses, so holding an arrow
// sends one request rather than one per day. If a load is still running, the
// new day loads as soon as it finishes.
import { istanbulDate } from './helpers.js';

const SETTLE_MS = 300;

function shift(isoDate, days) {
    const d = new Date(`${isoDate}T12:00:00Z`);  // midday, so DST never moves the day
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
}

function whenEnabled(button) {
    if (!button.disabled) return Promise.resolve();
    return new Promise((resolve) => {
        const observer = new MutationObserver(() => {
            if (!button.disabled) {
                observer.disconnect();
                resolve();
            }
        });
        observer.observe(button, { attributes: true, attributeFilter: ['disabled'] });
    });
}

/**
 * root:          the .date-stepper element (input plus buttons with data-step)
 * section:       the tab id whose arrow keys step the date
 * loadButton:    the tab's load button, pressed for every new day
 * maxDaysAhead:  latest selectable day relative to today in Istanbul (DPP is published a day ahead)
 */
export function setupDateStepper(root, { section, loadButton, maxDaysAhead = 1 }) {
    const input = root.querySelector('input[type="date"]');
    const next = root.querySelector('[data-step="1"]');
    let timer = null;
    let pending = null;

    const latest = () => istanbulDate(-maxDaysAhead);
    const refresh = () => {
        input.max = latest();
        next.disabled = !input.value || input.value >= input.max;
    };

    const load = async () => {
        pending = input.value;
        await whenEnabled(loadButton);
        // Only the last day asked for is loaded
        if (pending !== input.value || !input.value) return;
        pending = null;
        loadButton.click();
    };

    const changed = () => {
        refresh();
        clearTimeout(timer);
        timer = setTimeout(load, SETTLE_MS);
    };

    const step = (days) => {
        if (!input.value) return;
        const day = shift(input.value, days);
        if (day > latest()) return;
        input.value = day;
        changed();
    };

    root.querySelectorAll('[data-step]').forEach((button) => {
        button.addEventListener('click', () => step(Number(button.dataset.step)));
    });
    // a day picked in the calendar loads the same way
    input.addEventListener('change', changed);

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
        if (document.querySelector('.content-section.active')?.dataset.section !== section) return;
        // Arrow keys keep their usual job inside fields and menus
        if (e.target.closest('input, select, textarea, [contenteditable]')) return;
        e.preventDefault();
        step(e.key === 'ArrowLeft' ? -1 : 1);
    });

    refresh();
}
