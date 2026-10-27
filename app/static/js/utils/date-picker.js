// Every date field in the dashboard opens the same calendar (flatpickr, loaded
// in base.html) instead of the browser's own. The original <input> stays the
// source of truth: it keeps its id and its YYYY-MM-DD value, and fires
// 'change' when a day is picked, so modules read and write it as before.
// Writes to value, valueAsDate, min and max are passed on to the calendar.

const NATIVE = {
    value: Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value'),
    valueAsDate: Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'valueAsDate'),
};

const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function mirrorWrites(input, picker) {
    Object.defineProperty(input, 'value', {
        configurable: true,
        get: () => NATIVE.value.get.call(input),
        set: (v) => {
            NATIVE.value.set.call(input, v);
            // flatpickr writes the same value back, which stops here
            const shown = picker.selectedDates[0] ? isoDay(picker.selectedDates[0]) : '';
            if (v !== shown) picker.setDate(v || null, false);
        },
    });
    Object.defineProperty(input, 'valueAsDate', {
        configurable: true,
        get: () => NATIVE.valueAsDate.get.call(input),
        // valueAsDate takes the UTC calendar day, as the native input does
        set: (d) => { input.value = d ? d.toISOString().slice(0, 10) : ''; },
    });
    for (const [prop, option] of [['min', 'minDate'], ['max', 'maxDate']]) {
        Object.defineProperty(input, prop, {
            configurable: true,
            get: () => input.getAttribute(prop) || '',
            set: (v) => {
                input.setAttribute(prop, v);
                picker.set(option, v || null);
            },
        });
    }
}

export function setupDatePickers(root = document) {
    if (!window.flatpickr) return;  // CDN unavailable: the native date fields still work
    root.querySelectorAll('input[type="date"]').forEach((input) => {
        if (input._flatpickr) return;
        // read before flatpickr turns the input into a hidden one, which has no labels
        const labels = [...(input.labels || [])];
        const picker = window.flatpickr(input, {
            dateFormat: 'Y-m-d',        // what the input holds and the modules read
            altInput: true,
            altFormat: 'd.m.Y',         // what people see and type
            allowInput: true,
            minDate: input.getAttribute('min') || null,
            maxDate: input.getAttribute('max') || null,
            locale: { firstDayOfWeek: 1 },
            monthSelectorType: 'static',
            prevArrow: '<i class="fas fa-chevron-left" aria-hidden="true"></i>',
            nextArrow: '<i class="fas fa-chevron-right" aria-hidden="true"></i>',
        });
        // the visible field takes over the label, so clicking the label opens the calendar
        picker.altInput.id = `${input.id || 'date'}_display`;
        labels.forEach((label) => label.setAttribute('for', picker.altInput.id));
        if (!labels.length) picker.altInput.setAttribute('aria-label', 'Date');
        mirrorWrites(input, picker);
    });
}
