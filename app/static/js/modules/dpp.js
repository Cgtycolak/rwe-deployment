import { DPPDayReport } from '../classes/DPPDayReport.js';
import { postData, toggleLoading, displayMessage, isInvalidDuration } from '../utils/helpers.js';
import { getEndpoints } from '../config/endpoints.js';
import { THead } from '../classes/THead.js';
import { TBody } from '../classes/TBody.js';

export const dpp = {
    installed: false,
    optionsDisplayed: false,
    _orgs: null,
    _uevcbids: null,
    _columns: null,
    _rows: null,
    _dayReport: null,
    orgsDuration: {
        start: null,
        end: null,
    },
    uevcbDuration: {
        start: null,
        end: null,
    },
    dppDuration: {
        start: null,
        end: null,
    },
    set orgs(reqAndRes) {
        /* req 1 */
        //console.log("cascade captrue relation orgs");
        this._orgs = reqAndRes ? {} : null;
        // convert array to obj with id (fastest access for select html input val)
        if (this._orgs != null) {
            /* can create new org class */
            reqAndRes.data.forEach((obj) => {
                if (obj.organizationId) {
                    this._orgs[obj.organizationId] = obj;
                }
            });
        }

        this.uevcbids = null; /* clear new based data */
        this.setDuration(reqAndRes, "orgsDuration");
    },
    get orgs() {
        return this._orgs;
    },

    set uevcbids(reqAndRes) {
        /* req 2 */
        // !console.log("cascade captrue relation uevcbids");
        this._uevcbids = reqAndRes ? {} : null;
        // convert array of uevcb to obj with id (fastest access for select html input val)
        if (this._uevcbids != null) {
            for (let orgId in reqAndRes.data) {
                /* can create new uevcbid class */
                reqAndRes.data[orgId].forEach((uevcbObj) => {
                    if (uevcbObj.id) {
                        this._uevcbids[uevcbObj.id] = {
                            ...uevcbObj,
                            orgId,
                        };
                    }
                });
            }
        }
        this.columns = null; /* clear new based data */
        this.rows = null;
        this.dayReport = null;
        this.setDuration(reqAndRes, "uevcbDuration");
    },
    get uevcbids() {
        return this._uevcbids;
    },

    set columns(columns) {
        /* req 3 (part 1) table columns specific */
        this._columns = columns;
        /* here update html for headers of table global class for 3 tables so same methods order */
        new THead(this.columns, "#dpp_table");
    },
    get columns() {
        return this._columns;
    },
    set rows(reqAndRes) {
        /* req 3 (part 2) table rows specific ( update only table rows so for ex checkbox of header col order not need remembered or or recreated) */
        this._rows = reqAndRes ? reqAndRes.data : null;
        this.setDuration(reqAndRes, "dppDuration");
        //console.log("cascade captrue relation rows");

        new TBody(this._rows, "#dpp_table", this.columns);
    },
    get rows() {
        return this._rows;
    },
    set dayReport(orgsData) {
        const orgsDataArg = orgsData ? orgsData : null;

        this._dayReport = new DPPDayReport(orgsDataArg);
    },
    get dayReport() {
        return this._dayReport;
    },
    setDuration: function (reqAndRes, prop) {
        // set current res's req duration start and end for orgsDuration, uevcbDuration, dppDuration dynamic by prop arg
        if (this.hasOwnProperty(prop)) {
            if (
                reqAndRes &&
                reqAndRes.hasOwnProperty("start") &&
                reqAndRes.hasOwnProperty("end")
            ) {
                this[prop].start = reqAndRes.start;
                this[prop].end = reqAndRes.end;
            } else {
                this[prop].start = null;
                this[prop].end = null;
            }
        }
    },
    getOrgsData: function () {
        // payload of req 3 from system data
        let orgsData = {};
        $("#org_select")
            .val()
            .forEach((htmlOrgId) => {
                const systemOrg = app.dpp.orgs[htmlOrgId];
                // console.log('org', systemOrg);
                if (systemOrg) {
                    let orgData = {
                        ...systemOrg,
                        uevcbids: [],
                    };
                    $("#adi_select")
                        .val()
                        .forEach((htmlUevcbId) => {
                            const systemUevcb = app.dpp.uevcbids[htmlUevcbId];
                            // console.log('uevcb', systemUevcb, systemUevcb.orgId == htmlOrgId);
                            if (systemUevcb && systemUevcb.orgId == htmlOrgId) {
                                orgData.uevcbids.push({
                                    ...systemUevcb,
                                    rows: [],
                                });
                            }
                        });
                    if (orgData.uevcbids.length > 0) {
                        orgsData[htmlOrgId] = orgData;
                    }
                }
            });
        return orgsData;
    },
    getRowsObjsArr: function (orgsData) {
        /* (take orgsData and return [{},{}] list of table rows data with private props to for data-attrs) js format response of req 3 res and reduce size  (!note called after ajax req only) */
        const rows = [];
        for (let orgId in orgsData) {
            for (let u = 0; u < orgsData[orgId].uevcbids.length; u++) {
                const uevcbObj = orgsData[orgId].uevcbids[u];
                for (let i = 0; i < uevcbObj.rows.length; i++) {
                    rows.push({
                        ...uevcbObj.rows[i],
                        _org: orgId,
                        _uevcb: uevcbObj.id,
                    });
                }
            }
        }
        return rows;
    },



    async loadOrgs(app) {
        try {
            // cascade clear all orgs and childs before new request
            app.dpp.orgs = null;

            toggleLoading(true);
            const orgSelect = $("#org_select");
            if (orgSelect.length) {
                // clear old orgs, adis and filters before any handle
                orgSelect.html("").trigger("change");
                $("#adi_select").html("").trigger("change");

                const durationError = isInvalidDuration(
                    app.global.start,
                    app.global.end
                );
                if (!durationError) {
                    displayMessage();
                    /* Ajax request load orgs */
                    const reqData = {
                        start: app.global.start,
                        end: app.global.end,
                    };
                    const endpoints = getEndpoints();
                    const res = await postData(endpoints.getOrgs, reqData);
                    if (res && res.code == 200 && Array.isArray(res.data)) {
                        // console.log("load orgs", res);
                        let orgOptions = "";
                        const orgsData = res.data.forEach((orgObj) => {
                            orgOptions += `<option value="${orgObj.organizationId}" title="${orgObj.organizationName}">${orgObj.organizationShortName}</option>`;
                        });
                        orgSelect.html(orgOptions);

                        // update orgs incase successfull res;
                        app.dpp.orgs = {
                            data: res.data,
                            start: reqData.start,
                            end: reqData.end,
                        };

                        // display select inputs first time got data to loaded
                        if (!app.dpp.installed) {
                            $("#dpp_args").show();
                            app.dpp.installed = true;
                        }
                    } else {
                        const errorMsg = res.message
                            ? res.message
                            : "Connection error unable to load organizations.";
                        displayMessage(errorMsg, "danger");
                    }
                } else {
                    displayMessage(durationError, "danger");
                }
            } else {
                displayMessage("System error unable to load organizations.", "danger");
            }
            toggleLoading(false);
        } catch (error) {
            console.error("loadOrgs Error", error);
            displayMessage("System error while loading orgs", "danger");
            toggleLoading(false);
        }
    },

    async getOrgbasedOptions(app) {
        try {
            // cascade clear all uevcbids and it cascade remove it childs capturing
            app.dpp.uevcbids = null;

            const orgElm = $("#org_select[multiple]");
            const uevcbElm = $("#adi_select[multiple]");
            //data-cacheid
            if (orgElm.length && uevcbElm.length) {
                uevcbElm
                    .html("")
                    .trigger("change");

                const durationError = isInvalidDuration(
                    app.global.start,
                    app.global.end
                );
                if (!durationError) {
                    if (orgElm.val().length > 0) {
                        toggleLoading(true);
                        displayMessage();
                        const orgIds = orgElm.val();
                        const reqData = {
                            orgIds: orgIds,
                            start: app.global.start,
                            end: app.global.end,
                        };
                        const endpoints = getEndpoints();
                        const res = await postData(endpoints.getUevcbids, reqData);
                        if (res.code == 200 && typeof res.data === "object") {
                            let optionsHtml = "";
                            for (const orgId in res.data) {
                                res.data[orgId].forEach((uevcbIdObj) => {
                                    optionsHtml += `<option data-org="${orgId}" value="${uevcbIdObj.id}">${uevcbIdObj.name}</option>`;
                                });
                            }
                            uevcbElm.html(optionsHtml);
                            app.dpp.uevcbids = {
                                data: res.data,
                                start: reqData.start,
                                end: reqData.end,
                            };
                        } else {
                            displayMessage(
                                res.message
                                    ? res.message
                                    : "Unable to load UEVCB list due to connection error",
                                "danger"
                            );
                        }
                        toggleLoading(false);
                    } else {
                        displayMessage(
                            "Unable to load UEVCB options please select organizations",
                            "warning"
                        );
                    }
                } else {
                    displayMessage(durationError, "danger");
                }
            } else {
                displayMessage("Unable to load UEVCB list system error", "danger");
            }
        } catch (error) {
            console.error("getOrgbasedOptions Error", error);
            displayMessage("System error while loading uevcbids.", "danger");
            toggleLoading(false);
        }
    },

    async getDPPTableData(app) {
        try {
            app.dpp.columns = null;
            app.dpp.rows = null;
            app.dayReport = null;

            const durationError = isInvalidDuration(app.global.start, app.global.end);
            if (!durationError) {
                const orgsData = app.dpp.getOrgsData();
                if (Object.keys(orgsData).length > 0) {
                    toggleLoading(true);
                    displayMessage();

                    const reqData = {
                        orgsData: orgsData,
                        start: app.global.start,
                        end: app.global.end,
                    };
                    const endpoints = getEndpoints();
                    const res = await postData(endpoints.getDPPTable, reqData);
                    if (res.code == 200 && typeof res.data === "object") {
                        // Reorder the columns according to the desired fuel order
                        const orderedColumns = ["Organization", "DATE", "HOUR", "TOTAL"];
                        const fuelOrder = [
                            "NG",
                            "WIND",
                            "LIGNITE",
                            "HARDCOAL",
                            "IMPORTCOAL",
                            "FUELOIL",
                            "HEPP",
                            "ROR",
                            "NAPHTHA",
                            "BIO",
                            "GEOTHERMAL"
                        ];

                        // Add fuels in specified order
                        fuelOrder.forEach(fuel => {
                            if (res.data.columns.includes(fuel)) {
                                orderedColumns.push(fuel);
                            }
                        });

                        // Add any remaining columns (except the ones we've already positioned and OTHER)
                        res.data.columns.forEach(col => {
                            if (!orderedColumns.includes(col) &&
                                !['Organization', 'date', 'HOUR', 'TOTAL', 'OTHER'].includes(col)) {
                                orderedColumns.push(col);
                            }
                        });

                        // Replace 'date' with 'DATE' in the data columns
                        const finalColumns = orderedColumns.map(col =>
                            col === 'date' ? 'DATE' : col
                        );

                        // Update the columns in the response
                        res.data.columns = finalColumns;

                        // Process the rows to ensure date is populated
                        const processedRows = app.dpp.getRowsObjsArr(res.data.orgsData).map(row => {
                            // Extract date from the full date-time string
                            if (row.date) {
                                // Split the date-time string and take only the date part
                                row.DATE = row.date.split('T')[0];
                            }
                            // Remove the old date field and OTHER field if they exist
                            delete row.date;
                            delete row.OTHER;
                            return row;
                        });

                        app.dpp.columns = finalColumns;
                        app.dpp.rows = {
                            data: processedRows,
                            start: reqData.start,
                            end: reqData.end,
                        };
                        app.dpp.dayReport = res.data.orgsData;

                        /* display table options buttons and containers one time after load dpp data */
                        if (!app.dpp.optionsDisplayed) {
                            $(".dpp_options").show();
                            app.dpp.optionsDisplayed = true;
                        }

                        // Hide all views first
                        $(`.switch_arg[data-group='dpp_nested']`).hide();

                        // Show days table view by default
                        $(`.switch_arg[data-switch='fuel_types_table']`).show();

                        // Update button states
                        $(`.switch_selector[data-group='dpp_nested']`)
                            .removeClass("btn-primary")
                            .addClass("btn-outline-primary");

                        $(`.switch_selector[data-switch='fuel_types_table']`)
                            .removeClass("btn-outline-primary")
                            .addClass("btn-primary");

                    } else {
                        displayMessage(
                            res.message
                                ? res.message
                                : "Unable to load DPP Table Data due to connection error",
                            "danger"
                        );
                    }
                    toggleLoading(false);
                } else {
                    // reload org when error detected (by selected invalid uevcb of modifed orgs) (note this click is UX it so just notify user he selet uevcb for removed org by him so load the selected orgs uevcb for him to notice and continue)
                    $("#load_uevcbids").click();
                    displayMessage(
                        "Unable to load Table data, New changes detected in organizations. Please click 'Load Uevcbids' next time when make changes to org first to detect the changes, then select 'Uevcbids' and click 'Display Table'. I clicked for u ",
                        "warning"
                    );
                }
            } else {
                displayMessage(durationError, "warning");
            }
        } catch (error) {
            console.error("getDPPTableData Error", error);
            displayMessage("System error while loading DPP data.", "danger");
            toggleLoading(false);
        }
    }
};