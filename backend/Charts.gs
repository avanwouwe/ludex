/**
 * Usage analysis: pick a user, get a per-day stacked column chart of minutes per activity,
 * rendered on a dedicated `chart` tab. Data comes from the archive + recent raw log (same sources
 * as the dashboard), filtered to one user.
 */

var CHART_SHEET = "analysis";

function ludexUsageChart() {
  if (!table_(SHEETS.users).rows().some(function (u) { return u.user_id; })) {
    SpreadsheetApp.getUi().alert("No computers yet — an agent has to check in at least once first.");
    return;
  }
  var h = HtmlService.createHtmlOutputFromFile("UsageChart").setWidth(360).setHeight(170);
  SpreadsheetApp.getUi().showModalDialog(h, "Ludex — activity analysis");
}

function getChartUsers() {
  var labels = _userLabels_();
  return table_(SHEETS.users).rows().filter(function (u) { return u.user_id; })
    .map(function (u) { return { id: u.user_id, label: labels[u.user_id] || u.user_id }; });
}

// Build a {name, header, rows} pivot of minutes per (day x activity) for one user.
function _usagePivot_(user_id, tz) {
  var names = _activityNames_();
  var byDay = {};        // date -> { activity_id -> seconds }
  var activitySet = {};

  function add(date, aid, seconds) {
    if (!byDay[date]) byDay[date] = {};
    byDay[date][aid] = (byDay[date][aid] || 0) + seconds;
    activitySet[aid] = true;
  }
  table_(ARCHIVE).rows().forEach(function (a) {
    if (a.user_id === user_id && a.date && a.activity_id) add(a.date, a.activity_id, Number(a.seconds) || 0);
  });
  table_(SHEETS.activity_log).rows().forEach(function (r) {
    if (r.user_id !== user_id || !r.activity_id) return;
    var d;
    try { d = Utilities.formatDate(new Date(r.period_start), tz, "yyyy-MM-dd"); } catch (e) { return; }
    add(d, r.activity_id, Number(r.activity_seconds) || 0);
  });

  var dates = Object.keys(byDay).sort();                 // chronological
  var activities = Object.keys(activitySet).sort();
  var header = ["date"].concat(activities.map(function (a) { return names[a] || a; }));
  var rows = dates.map(function (d) {
    return [d].concat(activities.map(function (a) { return Math.round((byDay[d][a] || 0) / 60); }));
  });
  return { name: (_userLabels_()[user_id] || user_id), header: header, rows: rows };
}

// called from UsageChart.html. Built from an explicit DataTable (named columns) and inserted as an
// image, so the activity legend is always labelled — no reliance on the chart's row-1-as-header
// auto-detection (which doesn't trigger for programmatically inserted charts).
function ludexBuildUsageChart(user_id) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pivot = _usagePivot_(user_id, ss.getSpreadsheetTimeZone());
  var sheet = ss.getSheetByName(CHART_SHEET) || ss.insertSheet(CHART_SHEET);
  sheet.clear();
  sheet.getImages().forEach(function (im) { im.remove(); });

  if (!pivot.rows.length) {
    sheet.getRange(1, 1).setValue("No usage recorded for " + pivot.name + " yet.");
    sheet.activate();
    return true;
  }

  // Reference table (with a real-Date first column so it reads as dates).
  var cols = pivot.header.length;
  sheet.getRange(1, 1, 1, cols).setValues([pivot.header]).setFontWeight("bold");
  sheet.getRange(2, 1, pivot.rows.length, cols).setValues(pivot.rows.map(function (r) {
    return [new Date(r[0] + "T00:00:00")].concat(r.slice(1));
  }));

  // Build a DataTable with explicit column labels -> guaranteed-named series.
  var dt = Charts.newDataTable().addColumn(Charts.ColumnType.STRING, pivot.header[0]);
  for (var i = 1; i < pivot.header.length; i++) {
    dt.addColumn(Charts.ColumnType.NUMBER, pivot.header[i]);
  }
  pivot.rows.forEach(function (r) { dt.addRow(r); });

  var chart = Charts.newColumnChart()
    .setDataTable(dt.build())
    .setStacked()
    .setTitle("Activity analysis — " + pivot.name)
    .setDimensions(820, 420)
    .setLegendPosition(Charts.Position.RIGHT)
    .build();
  sheet.insertImage(chart.getAs("image/png"), cols + 2, 1);
  sheet.activate();
  return true;
}
