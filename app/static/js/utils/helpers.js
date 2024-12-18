export function postData(url, data) {
    let result = { code: 500 };
    return new Promise(function (res, rej) {
        $.ajax({
            url: url,
            type: "POST",
            contentType: "application/json",
            dataType: "json",
            headers: {
                Accept: "application/json",
            },
            data: JSON.stringify(data),
            success: function (response) {
                res(response);
            },
            error: function (error) {
                const errorMsg = error?.responseJSON?.message
                    ? error.responseJSON.message
                    : "Unknown error unable to load the data";
                result = {
                    code: 500,
                    error: error,
                    message: errorMsg,
                };
                res(result);
            },
        });
    });
}

export function toggleLoading(display = true) {
    if (display) {
        $("#app").hide();
        $("#loading_circle").show();
    } else {
        $("#loading_circle").hide();
        $("#app").show();
    }
}

export function displayMessage(message = null, status = "danger", selector = "#alert_messages") {
    if (message && typeof message === "string") {
        $(selector).html(`
            <div class="alert alert-${status} alert-dismissible fade show m-0 mb-2">
                <button type="button" class="close" data-dismiss="alert">&times;</button>
                <div class="m-0 p-0">${message}</div>
            </div>`);
    } else {
        $(selector).html("");
    }
}

export function isInvalidDuration(start, end) {
    if (!(start && end)) {
        return "Please select start and end date to load organizations.";
    } else if (new Date(start).getTime() > new Date(end).getTime()) {
        return "End Date must be bigger than Start Date.";
    } else {
        return "";
    }
}

export function arraysAreEqual(arr1, arr2) {
    if (arr1.length !== arr2.length) return false;
    return arr1.every((value, index) => value === arr2[index]);
}

export function lineSpliter(sentence = "", charW = 16, maxLine = 500, spliter = "<br>") {
    let res = "";
    let counter = 0;
    for (let i = 0; i < sentence.length; i++) {
        if (counter + charW > maxLine) {
            res += spliter;
            counter = 0;
        }
        res += sentence[i];
        counter += charW;
    }
    return res;
}

export function timeBaseISO8601(tString) {
    if (typeof tString == "string" && !isNaN(new Date(tString))) {
        let lowerT = tString.toLowerCase();
        let res = tString;

        if (lowerT.includes("t") && /(?:\+\d{2}:\d{2}\s*$|\+\d{4}\s*$)/i.test(lowerT)) {
            res = tString.replace(/T.*\+/i, "T00:00:00+");
        } else if (lowerT.includes("t") && /(?:\-\d{2}:\d{2}\s*$|\-\d{4}\s*$)/i.test(lowerT)) {
            res = tString.replace(/T.*\-/i, "T00:00:00-");
        } else if (/\d{2}:\d{2}:\d{2}/.test(lowerT)) {
            res = tString.replace(/\d{2}:\d{2}:\d{2}(?:\.\d*)*/, "00:00:00");
        } else if (/(t|\s+)\d{2}:\d{2}(z|\+|\-|$)/i.test(tString)) {
            const hAndM = tString.match(/(t|\s+)\d{2}:\d{2}(z|\+|\-|$)/i);
            res = tString.replace(hAndM[0], `${hAndM[1]}00:00${hAndM[2]}`);
        } else if (/^(?:\d{2}:\d{2}:\d{2})/i.test(lowerT)) {
            res = tString.replace(/^(?:\d{2}:\d{2}:\d{2})/i, "00:00:00");
        } else if (/^(?:\d{2}:\d{2})/i.test(lowerT)) {
            res = tString.replace(/^(?:\d{2}:\d{2})/i, "00:00");
        }

        return res.trim()
            .replaceAll(/\s+/g, " ")
            .replaceAll(/(?:\:\s+)/g, ":");
    } else {
        throw new Error(`Invalid date string provided: ${tString}`);
    }
}

export function switchTable(e) {
    const tableId = $(e.currentTarget).attr("data-table");
    if (tableId && $(`.table_args[data-table='${tableId}']`).length) {
        $(".table_args").hide();
        $(".table_selector")
            .removeClass("btn-primary")
            .addClass("btn-outline-primary");
        $(e.currentTarget)
            .removeClass("btn-outline-primary")
            .addClass("btn-primary");
        $(`.table_args[data-table='${tableId}']`).slideDown("fast");
    }
}

export function switcher(e) {
    const t = $(e.currentTarget);
    const switchVal = t.attr("data-switch");
    const switchGroup = t.attr("data-group");

    if (switchVal && switchGroup) {
        // Hide all switch_arg elements for this group
        $(`.switch_arg[data-group='${switchGroup}']`).hide();

        // Show the target switch_arg element
        $(`.switch_arg[data-switch='${switchVal}'][data-group='${switchGroup}']`).show();

        // Update button states
        $(`.switch_selector[data-group='${switchGroup}']`)
            .removeClass("btn-primary")
            .addClass("btn-outline-primary");

        t.removeClass("btn-outline-primary")
            .addClass("btn-primary");
    }
}

export function updateGlobal(e, app) {
    const currentTarget = $(e.currentTarget);
    const prop = currentTarget.attr("data-prop");

    if (currentTarget && prop && app?.global?.hasOwnProperty(prop)) {
        const selectedVal = currentTarget.val();
        app.global[prop] = selectedVal || null;
    }
}

export function toggleButtonLoading(buttonSelector, isLoading = true) {
    const button = $(buttonSelector);
    if (isLoading) {
        // Store original text and disable button
        const originalText = button.html();
        button.attr('data-original-text', originalText);
        button.prop('disabled', true);
        button.html(`<span class="spinner-border spinner-border-sm mr-2" role="status" aria-hidden="true"></span> Loading...`);
    } else {
        // Restore original text and enable button
        const originalText = button.attr('data-original-text');
        button.html(originalText);
        button.prop('disabled', false);
        button.removeAttr('data-original-text');
    }
}
