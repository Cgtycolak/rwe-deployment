export class TBody {
    constructor(rows, tableSelector, columns) {
        if (tableSelector && $(tableSelector).length) {
            $(`${tableSelector} tbody`).html("");
            if (
                Array.isArray(rows) &&
                rows.length &&
                Array.isArray(columns) &&
                columns.length
            ) {
                let rowsHtml = "";
                let rowAttrs = "";

                for (let prop in rows[0]) {
                    /* loop on first obj to get private attrs for whole row */
                    if (prop.startsWith("_")) {
                        rowAttrs += ` data-${prop.slice(1)}="${rows[0][prop]}"`;
                    }
                }

                rows.forEach((rowObj) => {
                    rowsHtml += `<tr${rowAttrs}>`;
                    rowsHtml += columns
                        .map((colName) => {
                            const val = rowObj[colName] || "";
                            const title = val ? ` title="${val}"` : '';
                            return `<td${title}>${val}</td>`;
                        })
                        .join("");
                    rowsHtml += "</tr>";
                });

                $(`${tableSelector} tbody`).html(rowsHtml);
                this.rows = rows;
            }
        }
    }
}
