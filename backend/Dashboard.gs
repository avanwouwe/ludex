/**
 * Ludex dashboard + command entry (bound-sheet UI helpers).
 *
 * The dashboard is a generated, read-only `dashboard` tab summarising minutes per
 * day / user / activity. It is rebuilt on demand (Ludex ▸ Refresh dashboard) rather
 * than via live formulas, because activity_log stores ISO-string timestamps that are
 * awkward to group with sheet formulas.
 */

var DASHBOARD_SHEET = "dashboard";

function ludexRefreshDashboard() {
  buildDashboard_();
  SpreadsheetApp.getActiveSpreadsheet().toast("Dashboard refreshed.", "Ludex", 4);
}

function buildDashboardSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName(DASHBOARD_SHEET)) ss.insertSheet(DASHBOARD_SHEET);
}

function _userLabels_() {
  var map = {};
  table_(SHEETS.users).rows().forEach(function (u) {
    map[u.user_id] = (u.system_username || "?") + " @ " + (u.hostname || "?");
  });
  return map;
}

function buildDashboard_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = ss.getSpreadsheetTimeZone();
  var labels = _userLabels_();

  // aggregate seconds by (local date, user, activity).
  var agg = {};

  // (a) seed from the rolled-up archive (older days, already aggregated)
  table_(ARCHIVE).rows().forEach(function (a) {
    if (!a.date || !a.activity_id) return;
    var who = labels[a.user_id] || a.user_id;
    var key = a.date + "|" + who + "|" + a.activity_id;
    if (!agg[key]) agg[key] = { date: a.date, user: who, activity: a.activity_id, seconds: 0 };
    agg[key].seconds += Number(a.seconds) || 0;
  });

  // (b) add the recent raw rows still in activity_log
  table_(SHEETS.activity_log).rows().forEach(function (r) {
    if (!r.activity_id) return;  // skip empty/idle periods
    var day;
    try {
      day = Utilities.formatDate(new Date(r.period_start), tz, "yyyy-MM-dd");
    } catch (e) {
      return;
    }
    var who = labels[r.user_id] || r.user_id;
    var key = day + "|" + who + "|" + r.activity_id;
    if (!agg[key]) agg[key] = { date: day, user: who, activity: r.activity_id, seconds: 0 };
    agg[key].seconds += Number(r.activity_seconds) || 0;
  });

  var out = Object.keys(agg).map(function (k) { return agg[k]; });
  out.sort(function (a, b) {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;       // newest day first
    if (a.user !== b.user) return a.user < b.user ? -1 : 1;
    return a.activity < b.activity ? -1 : 1;
  });

  var sheet = ss.getSheetByName(DASHBOARD_SHEET) || ss.insertSheet(DASHBOARD_SHEET);
  sheet.clear();
  sheet.getRange(1, 1, 1, 4).setValues([["date", "user", "activity", "minutes"]]).setFontWeight("bold");
  if (out.length) {
    var values = out.map(function (o) { return [o.date, o.user, o.activity, Math.round(o.seconds / 60)]; });
    sheet.getRange(2, 1, values.length, 4).setValues(values);
  }
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, 4);
}

// ===== Command entry (friendlier than hand-editing the commands tab) =====
var COMMAND_TYPES = ["notify-user", "stop-activity", "shutdown-endpoint", "reload-config"];

function ludexSendCommand() {
  var ui = SpreadsheetApp.getUi();
  var users = table_(SHEETS.users).rows();
  if (!users.length) {
    ui.alert("No users yet — an agent has to check in at least once first.");
    return;
  }

  var list = users.map(function (u, i) {
    return (i + 1) + ". " + (u.system_username || "?") + " @ " + (u.hostname || "?");
  }).join("\n");
  var r1 = ui.prompt("Send command (1 of 3)", "Which computer?\n\n" + list + "\n\nType a number:",
                     ui.ButtonSet.OK_CANCEL);
  if (r1.getSelectedButton() !== ui.Button.OK) return;
  var idx = parseInt(r1.getResponseText().trim(), 10) - 1;
  if (isNaN(idx) || idx < 0 || idx >= users.length) { ui.alert("Invalid selection."); return; }
  var user = users[idx];

  var r2 = ui.prompt("Send command (2 of 3)",
    "Command type — type one of:\n  " + COMMAND_TYPES.join("\n  "),
    ui.ButtonSet.OK_CANCEL);
  if (r2.getSelectedButton() !== ui.Button.OK) return;
  var type = r2.getResponseText().trim();
  if (COMMAND_TYPES.indexOf(type) < 0) { ui.alert("Unknown command type."); return; }

  var params = "";
  if (type === "notify-user" || type === "stop-activity") {
    var label = type === "notify-user" ? "Message to show on the computer:" : "activity_id to stop (e.g. chrome):";
    var r3 = ui.prompt("Send command (3 of 3)", label, ui.ButtonSet.OK_CANCEL);
    if (r3.getSelectedButton() !== ui.Button.OK) return;
    params = r3.getResponseText().trim();
  }

  var id = "cmd-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
  table_(SHEETS.commands).append({
    command_id: id, user_id: user.user_id, command_type: type, params: params,
    status: "pending", created: new Date(), executed: "", result: ""
  });
  ui.alert("Queued ✓",
    "Queued '" + type + "' for " + (user.system_username || user.user_id)
    + ".\nThe agent will run it on its next sync.", ui.ButtonSet.OK);
}
