import { timeBaseISO8601, lineSpliter, arraysAreEqual } from '../utils/helpers.js';

export class DPPDayReport {
    constructor(orgsData) {
        /* this class takes 2 arugments [orgsData] or [null] as all samilir classes it responsible for [display the data] or [clear it] */
        this.chartBtns = $("#dpp_chart_btns");
        this.daysTable = $("#dpp_fuel_types_table");
        this.daysTableCont = $("#days_report_table_cont");
        this.plotlyChartCont = $("#plotly_chart");
        this.plotlyChartId = "plotly_chart";

        // Clear existing content
        this.daysTable.html("");
        this.chartBtns.html("");
        this.clearPlotly();

        if (orgsData) {
            /* when orgsData not null */
            this.orgsData = orgsData;
            this.sDateObj = null;
            this.startDate = null;
            this.endDate = null;
            this.dayBase = [
                "00:00",
                "01:00",
                "02:00",
                "03:00",
                "04:00",
                "05:00",
                "06:00",
                "07:00",
                "08:00",
                "09:00",
                "10:00",
                "11:00",
                "12:00",
                "13:00",
                "14:00",
                "15:00",
                "16:00",
                "17:00",
                "18:00",
                "19:00",
                "20:00",
                "21:00",
                "22:00",
                "23:00",
            ];
            this.fuels = [
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
            this.plotlyColorScale = "RdBu";
            this.plotlyConfig = { responsive: true };
            this.data = {};
            this.oneDayInMilliseconds = 1000 * 60 * 60 * 24; // 86,400,000 milliseconds
            this.distinctDates = this.getDistinctDaysDates(orgsData);
            this.lastScrollX = -1;

            // Define mapping between DPP and realtime fuel names
            this.fuelMapping = {
                "NG": "dogalgaz",
                "WIND": "ruzgar",
                "LIGNITE": "linyit",
                "HARDCOAL": "tasKomur",
                "IMPORTCOAL": "ithalKomur",
                "FUELOIL": "fuelOil",
                "HEPP": "barajli",
                "ROR": "akarsu",
                "NAPHTHA": "nafta",
                "BIO": "biokutle",
                "GEOTHERMAL": "jeotermal"
            };

            // Order of fuels to display
            this.orderedFuels = [
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

            /* (create data) loop over each org and create day report for each uevcb but note create reports precreated for all fuels types so with button click get rows created with just org id and no run again every button click */
            for (let i = 0; i < this.distinctDates.length; i++) {
                const cBaseDate = this.distinctDates[i];
                this.startDate = null;
                this.sDateObj = null;
                this.data[cBaseDate] = {};

                for (let orgIdK in orgsData) {
                    const org = orgsData[orgIdK];
                    this.data[cBaseDate][orgIdK] = {
                        id: orgIdK,
                        orgName: org.organizationShortName,
                        orgFullName: org.organizationName,
                        etso: org.organizationEtsoCode,
                        uevcbids: {},
                    };
                    org.uevcbids.forEach((uevcb) => {
                        // get first (lowest day) 24 hours rows only from uevcbids (note it dynamic continue ex first date was hour 5 of day so rest will be 0)
                        /* this is smallest day datetime in provided rows usally api return 00:00:00 as first but incase it ignore some hours like samllest value recorded at 05:00:00 now i use base so valid check within 1 day only else it will take 5 hours from next day */
                        this.sDateObj = this.sDateObj
                            ? this.sDateObj
                            : this.getSmallestDateObjOf(uevcb.rows, cBaseDate);

                        if (this.sDateObj && this.sDateObj.date) {
                            if (!this.startDate) {
                                this.startDate = new Date(
                                    timeBaseISO8601(this.sDateObj.date)
                                ).getTime();
                            }

                            // (note both getUTCDate and geDate will be same except getUTCDate better as it deal with strings more base so if in result day 4 it may yes with timezone handled with getDate but getUTCDate more logical proven i not test prev) get only rows of sDate date (as this 1 day report) (use of getSmallestDayRow can decide what day here smallest day start date sDate)
                            const currentDateRows = uevcb.rows.filter((rowObj) => {
                                const rowDate = new Date(rowObj.date).getTime();

                                // note <= the = with end date mean include even last milisecond 2024-11-05T23:59:59+03:00 no it (wrong) right is like loop think logiacal <.length mean length or max is the first day of next not included point so any prev is included even latest 23:59:59, = in start mean include 0 second 2024-11-05T00:00:00+03:00
                                return (
                                    rowDate >= this.startDate &&
                                    rowDate - this.startDate < this.oneDayInMilliseconds
                                );
                            });
                            // if leangth less than 24 i continue also start and end date is dyanmic

                            //can strict say if currentDateRows.length >= 24 but already 0 default obj used created from dayBase so if 24 issue value ex 22 the other 2 will be 0 now proven both same, remeber new Date('2024-11-04T23:59:59+03:00') < new Date('2024-11-05T00:00:00+03:00')  asper anypc specific to my pc new Date('2024-11-05T00:00:00+03:00') is equal to Mon Nov 04 2024 23:00:00 and max of prev day is 2024-11-04T23:59:59 according to my timezone yes both have 4 but time point diff
                            this.data[cBaseDate][orgIdK].uevcbids[uevcb.id] = {
                                uevcbName: uevcb.name,
                                reports: {},
                            };
                            this.fuels.forEach((fuel) => {
                                this.data[cBaseDate][orgIdK].uevcbids[uevcb.id].reports[
                                    fuel
                                ] = {};
                                this.dayBase.forEach((dayHour) => {
                                    // (note currentDateRows is 24 objs of smallest day of all provided rows (so it 1 day and smallest from start to end selected 13,17 is 13,14 report))

                                    // targetRow is value of each row of the hour of that day get the fuel value or other data from it(dayHour)
                                    const targetRow = currentDateRows.find(
                                        (row) => row.HOUR.trim() == dayHour.trim()
                                    );
                                    if (
                                        targetRow &&
                                        targetRow.hasOwnProperty(fuel) &&
                                        !isNaN(parseFloat(targetRow[fuel]))
                                    ) {
                                        // org's uevcb report for fueltype hourly val
                                        this.data[cBaseDate][orgIdK].uevcbids[uevcb.id].reports[
                                            fuel
                                        ][dayHour] = parseFloat(targetRow[fuel]);
                                    } else {
                                        console.warn(
                                            `one uevcb not include all hours ignored ${uevcb.name}`,
                                            dayHour,
                                            currentDateRows,
                                            currentDateRows.find(
                                                (row) => row.HOUR.trim() == dayHour.trim()
                                            )
                                        );
                                        this.data[cBaseDate][orgIdK].uevcbids[uevcb.id].reports[
                                            fuel
                                        ][
                                            dayHour
                                        ] = 0; /* not log this mean no ignoring (note usally not always missing value ignore incase api is not strict and return only 4 hours records for that date the system will continue with 0 fill remaning not provided hour it best logical and generate new flexbilty for api (but also add small options need understand)) */
                                    }
                                });
                            });
                        }
                    });
                }
            }

            // Create fuel buttons only once
            this.createFuelsBtns();

            /* display initial fuel type table */
            this.displayDaysTable();

            /* add scroll Effect */
            this.daysTableCont.on("scroll", (e) => {
                this.scrollEffect(e);
            }); /* opt2 this.scrollEffect.bind(this) */

            /* display initial fuel type chart */
            this.displayPlotlyChart();
        }
    }
    formatDate(date) {
        return (
            date.getFullYear() +
            "-" +
            (date.getMonth() + 1).padStart(2, "0") +
            "-" +
            date.getDate().padStart(2, "0")
        );
    }
    getSmallestDayRow(rowObjs) {
        /* Get from provided rows the smallest day obj */
        // console.log('runing', rowObjs);
        return rowObjs.reduce((lowest, current) => {
            return lowest == null ||
                new Date(current.date).getDate() < new Date(lowest.date).getDate()
                ? current
                : lowest;
        }, null);
    }
    getSmallestDateObjOf(rows, dateOf) {
        /*get the rows that same day of dateOf , then get the smallest row datetime of this day*/
        let dayRows = [];
        const dateOfMilis = new Date(dateOf).getTime();
        rows.forEach((r) => {
            const currentRowMili = new Date(r.date).getTime();
            if (
                currentRowMili >= dateOfMilis &&
                currentRowMili - dateOfMilis < this.oneDayInMilliseconds
            ) {
                dayRows.push(r);
            }
        });
        return this.getSmallestDayRow(dayRows);
    }
    getDistinctDaysDates(orgsData) {
        const distinct = [];
        for (let orgId in orgsData) {
            orgsData[orgId].uevcbids.forEach((uevcbidObj) => {
                uevcbidObj.rows.forEach((rowObj) => {
                    const baseDateStr = timeBaseISO8601(rowObj.date);
                    if (!distinct.includes(baseDateStr)) {
                        distinct.push(baseDateStr);
                    }
                });
            });
        }
        return distinct;
    }
    fuelsBtnActivate(e) {
        const selector = $(e.currentTarget).attr("data-selector");
        $(`${selector}.btn-dark`)
            .removeClass("btn-dark")
            .addClass("btn-outline-dark");
        $(e.currentTarget).removeClass("btn-outline-dark").addClass("btn-dark");
    }
    scrollEffect(e) {
        const newScrollX = $(e.currentTarget).scrollLeft();
        if (newScrollX !== this.lastScrollX) {
            /* execute only when scrollLeft happend */
            this.lastScrollX = newScrollX;
            $(".day_table_info").css("padding-left", `${this.lastScrollX}px`);
        }
    }
    getMaxAndMin(rowObj) {
        // Get only hour values (non-underscore properties except _Total)
        const hourValues = Object.entries(rowObj)
            .filter(([key, value]) =>
                !key.startsWith('_') &&
                !isNaN(parseFloat(value)))
            .map(([_, value]) => parseFloat(value));

        // Filter out zero values for min/max calculation
        const nonZeroValues = hourValues.filter(val => val > 0);

        return {
            min: nonZeroValues.length > 0 ? Math.min(...nonZeroValues) : 0,
            max: nonZeroValues.length > 0 ? Math.max(...nonZeroValues) : 0
        };
    }
    getTableNumColor(num, minAndMax) {
        const value = parseFloat(num);
        if (value === 0) return '';

        if (value === minAndMax.min && value !== minAndMax.max) {
            /* small */
            return "#ffcdcd";
        } else if (value === minAndMax.max && value !== minAndMax.min) {
            /* large */
            return "#b9ffb9";
        } else if (value > minAndMax.min && value < minAndMax.max) {
            /* between */
            return "#a5fff4";
        } else {
            return "";
        }
    }
    createFuelsBtns() {
        if (this.fuels.length > 0) {
            let btnsHtml = "";

            // Filter and sort fuels based on orderedFuels
            const displayFuels = this.orderedFuels.filter(fuel => this.fuels.includes(fuel));

            displayFuels.forEach((fuel, index) => {
                const btnClass = index === 0 ? "btn-dark" : "btn-outline-dark";
                btnsHtml += `
                    <button 
                        class="btn ${btnClass} btn-sm fuels_btns_charts" 
                        data-fuel="${fuel}" 
                        data-selector=".fuels_btns_charts" 
                        title="Click to display Table For Fuel:${fuel}"
                    >
                        ${fuel}
                    </button>`;
            });

            this.chartBtns.html(btnsHtml);
            this.chartBtns.addClass("d-flex flex-wrap justify-content-start align-items-center p-2 mx-2 shadow");

            // Add click handlers for table only
            this.chartBtns.find(".fuels_btns_charts").on("click", (e) => {
                const t = $(e.currentTarget);
                const selector = t.attr("data-selector");
                const fuel = t.attr("data-fuel");

                $(selector)
                    .removeClass("btn-dark")
                    .addClass("btn-outline-dark");
                t.removeClass("btn-outline-dark")
                    .addClass("btn-dark");

                // Update table only
                this.displayDaysTable(e, fuel);
            });
        }
    }
    getDaysData(fuelProp, specificDay = null) {
        let propFound = false;
        const res = {
            rows: {},
            headers: [],
        };
        if (fuelProp) {
            for (let dayDate in this.data) {
                // if specific day (chart) continue until found
                if (specificDay && dayDate != specificDay) {
                    continue;
                }
                res.rows[dayDate] = [];
                for (let orgId in this.data[dayDate]) {
                    const org = this.data[dayDate][orgId];
                    for (let uevcbId in org.uevcbids) {
                        const uevcb = org.uevcbids[uevcbId];
                        /* get the only fuel obj needed */
                        if (
                            uevcb.reports.hasOwnProperty(fuelProp) &&
                            uevcb.reports[fuelProp]
                        ) {
                            propFound = true; /* any time prop Found this will be true */

                            const uevcbDayFuel = uevcb.reports[fuelProp];

                            // calc headers and make sure equal (note the table tds use this also as object props also charts may need clear which hours and which other data)
                            const currentHeaders = [
                                "_orgName",
                                "_orgFullName",
                                "_uevcbName",
                                "_Total",
                                ...Object.keys(uevcbDayFuel),
                            ];
                            if (res.headers.length == 0) {
                                // set the headers 1time at begning
                                res.headers = currentHeaders;
                            }

                            // only append valid rows that have same headers (usally if no prev issues no row ignored)
                            if (arraysAreEqual(res.headers, currentHeaders)) {
                                let total = 0.00;
                                for (let hour in uevcbDayFuel) {
                                    const hourVal = parseFloat(uevcbDayFuel[hour]);
                                    if (!isNaN(hourVal)) {
                                        total += hourVal;
                                    }
                                }
                                total = parseFloat(total.toFixed(3));
                                const rowObj = {
                                    _orgName: org.orgName,
                                    _orgFullName: org.orgFullName,
                                    _uevcbName: uevcb.uevcbName,
                                    _Total: total,
                                    ...uevcbDayFuel,
                                };
                                console.log('rowObj', rowObj);
                                res.rows[dayDate].push(rowObj);
                            } else {
                                console.warn(
                                    "Note the are row ignored that includes diff headers for uevcb:",
                                    uevcb
                                );
                            }
                        }
                    }
                }
                // if specific and found it break not continue
                if (specificDay && dayDate == specificDay) {
                    break;
                }
            }
            if (propFound === false) {
                /* here no uevcbid obj have this prop so clear the object (note incase 10 days will got 10 empty days while in begning the prop wrong) (incase high wrong i not know will see this warn and headers) */
                console.warn("Prop not found at any uevcb removed empty day array");
                res.rows = {};
            }
            /* order rows by total prop DESC */
            for (let day in res.rows) {
                res.rows[day].sort((current, next) => next._Total - current._Total);
            }
        } else {
            console.warn("fuel type not provided");
        }
        return res;
    }
    displayDaysTable(e, fuel = null) {
        let targetFuel = fuel ? fuel : this.fuels.length > 0 ? this.fuels[0] : null;
        if (e) {
            targetFuel = $(e.currentTarget).attr("data-fuel");
        }
        if (targetFuel) {
            const data = this.getDaysData(targetFuel);

            // Add compact table class
            this.daysTable.addClass('compact-table');

            /* create headers */
            let headers = '<tr class="table-dark">';
            headers += data.headers
                .map((colProp) => {
                    const colPropN = colProp.startsWith("_")
                        ? colProp.replace("_", "")
                        : colProp;
                    // Add title for header tooltip
                    return `<th title="${colPropN}">${colPropN}</th>`;
                })
                .join("");
            headers += "</tr>";

            let tableHTML = "";
            for (let dayDate in data.rows) {
                tableHTML += "<tbody>";
                tableHTML += `
                    <tr>
                        <td colspan="${data.headers.length}" class="day-header">
                            <span class="day_table_info">
                                <strong>${dayDate}</strong> | ${targetFuel}
                            </span>
                        </td>
                    </tr>`;
                tableHTML += headers;

                // Sort rows by organization and UEVCB
                const sortedRows = data.rows[dayDate].sort((a, b) => {
                    if (a._orgName !== b._orgName) {
                        return a._orgName.localeCompare(b._orgName);
                    }
                    return a._uevcbName.localeCompare(b._uevcbName);
                });

                sortedRows.forEach((rowObj) => {
                    const minAndMax = this.getMaxAndMin(rowObj);

                    tableHTML += "<tr>";
                    data.headers.forEach((headColKey) => {
                        let val;
                        if (headColKey.startsWith('_')) {
                            if (headColKey === '_Total') {
                                val = parseFloat(rowObj[headColKey] || 0).toFixed(2);
                            } else {
                                val = rowObj[headColKey] || '';
                            }
                        } else {
                            val = parseFloat(rowObj[headColKey] || 0).toFixed(2);
                        }

                        const background = !headColKey.startsWith('_')
                            ? this.getTableNumColor(val, minAndMax)
                            : '';

                        let cellClass = '';
                        if (headColKey === '_orgName') {
                            cellClass = 'org-name';
                        }

                        // Add title attribute for tooltip on hover
                        const title = val ? ` title="${val}"` : '';
                        const tdStyle = background ? ` style="background:${background};"` : '';

                        tableHTML += `<td class="${cellClass}"${title}${tdStyle}>${val}</td>`;
                    });
                    tableHTML += "</tr>";
                });
                tableHTML += "</tbody>";
            }
            this.daysTable.html(tableHTML);
        }
    }
    displayPlotlyChart() {
        if (this.fuels && this.fuels.length > 0) {
            const traces = [];

            // Filter and sort fuels based on orderedFuels
            const displayFuels = this.orderedFuels.filter(fuel => this.fuels.includes(fuel));

            displayFuels.forEach(fuel => {
                const data = this.getDaysData(fuel);

                Object.keys(data.rows).forEach(dayDate => {
                    const hours = data.headers.filter(h => !h.startsWith('_'));

                    data.rows[dayDate].forEach(org => {
                        const trace = {
                            type: "scatter",
                            mode: "lines+markers",
                            name: `${org._orgName} - ${fuel}`,
                            x: hours,
                            y: hours.map(hour => org[hour] || 0),
                            hovertemplate:
                                "<b>Hour:</b> %{x}<br>" +
                                "<b>Generation:</b> %{y:.2f} MW<br>" +
                                "<b>Organization:</b> " + org._orgName + "<br>" +
                                "<b>Fuel Type:</b> " + fuel + "<br>" +
                                "<b>UEVCB:</b> " + org._uevcbName +
                                "<extra></extra>"
                        };
                        traces.push(trace);
                    });
                });
            });

            const layout = {
                title: 'Power Generation by Organization and Fuel Type',
                xaxis: {
                    title: "Hour",
                    tickangle: -45
                },
                yaxis: {
                    title: "Generation (MW)"
                },
                showlegend: true,
                legend: {
                    x: 1,
                    xanchor: "right",
                    y: 1
                },
                hovermode: 'closest'
            };

            Plotly.newPlot(
                this.plotlyChartId,
                traces,
                layout,
                {
                    responsive: true,
                    displayModeBar: true
                }
            );
        }
    }
    clearPlotly() {
        // clear chart will done
        try {
            Plotly.purge(this.plotlyChartId);
            this.plotlyChartCont.html(""); // safe
        } catch (err) {
            this.plotlyChartCont.html("");
            console.log(err, "polty chart purge");
        }
    }
}
