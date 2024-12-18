export class HTMLSearchableSelect {
    constructor(selector) {
        this.selector = selector;
        this.element = $(selector);
        this.init();
    }

    init() {
        if (this.element.length) {
            if (typeof this.element.searchableSelect === 'function') {
                this.element.searchableSelect({
                    // Add any configuration options here
                });
            } else {
                // Fallback to basic select functionality if plugin not loaded
                console.warn('HTMLSearchableSelect plugin not loaded, using basic select');
                this.element.addClass('form-control');
            }
        }
    }

    // Add methods to interact with the select
    val() {
        return this.element.val();
    }

    html(content) {
        this.element.html(content);
        return this;
    }

    trigger(event) {
        this.element.trigger(event);
        return this;
    }
}