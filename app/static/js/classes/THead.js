export class THead {
    constructor(columns, tableSelector) {
        if (tableSelector && $(tableSelector).length) {
            $(`${tableSelector} thead`).html("");
            if (Array.isArray(columns) && columns.length) {
                $(`${tableSelector} thead`).html(
                    `<tr>${columns
                        .map((col) => {
                            return `<th title="${col}">${col}</th>`;
                        })
                        .join("")}</tr>`
                );
            }
            this.columns = columns;
        }
    }
}