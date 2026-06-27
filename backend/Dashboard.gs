/**
 * Ludex dashboard + command entry (bound-sheet UI helpers).
 *
 * The dashboard is a generated, read-only `dashboard` tab summarising minutes per
 * day / user / activity. It is rebuilt on demand (Ludex ▸ Refresh dashboard) rather
 * than via live formulas, because activity_log stores ISO-string timestamps that are
 * awkward to group with sheet formulas.
 */

var DASHBOARD_SHEET = "dashboard";
var PEOPLE = { name: "people", headers: ["user_id", "name"] };  // optional friendly names

function ludexRefreshDashboard() {
  buildDashboard_();
  SpreadsheetApp.getActiveSpreadsheet().toast("Dashboard refreshed.", "Ludex", 4);
}

function buildDashboardSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName(DASHBOARD_SHEET)) ss.insertSheet(DASHBOARD_SHEET);
}

// Ensure the `people` tab has a row per known user (default name = system_username), so the parent
// just edits the friendly name. Never overwrites a name the parent set.
function syncPeople_() {
  var pT = table_(PEOPLE);
  var have = {};
  pT.rows().forEach(function (r) { if (r.user_id) have[r.user_id] = true; });
  table_(SHEETS.users).rows().forEach(function (u) {
    if (u.user_id && !have[u.user_id]) pT.append({ user_id: u.user_id, name: u.system_username || "" });
  });
}

// user_id -> label: the friendly name from `people` if set, else system_username @ hostname.
function _userLabels_() {
  var names = {};
  table_(PEOPLE).rows().forEach(function (r) { if (r.user_id && r.name) names[r.user_id] = r.name; });
  var map = {};
  table_(SHEETS.users).rows().forEach(function (u) {
    map[u.user_id] = names[u.user_id] || ((u.system_username || "?") + " @ " + (u.hostname || "?"));
  });
  return map;
}

// activity_id -> display name (falls back to the id).
function _activityNames_() {
  var m = {};
  table_(SHEETS.activity_types).rows().forEach(function (a) {
    if (a.activity_id) m[a.activity_id] = a.name || a.activity_id;
  });
  return m;
}

// activity_id -> { daily_max, warn_before } parsed from each activity's definition limits.
function _activityLimits_() {
  var out = {};
  table_(SHEETS.activity_types).rows().forEach(function (r) {
    if (!r.activity_id) return;
    try {
      var lim = (JSON.parse(r.definition || "{}").limits) || {};
      out[r.activity_id] = {
        daily_max: Number(lim.daily_max_minutes) || 0,
        warn_before: Number(lim.warn_before_minutes) || 0
      };
    } catch (e) { /* non-JSON definition: no highlight */ }
  });
  return out;
}

function buildDashboard_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = ss.getSpreadsheetTimeZone();
  syncPeople_();
  var labels = _userLabels_();
  var limits = _activityLimits_();
  var actNames = _activityNames_();

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
  sheet.getRange(1, 4).setNote("Red = over the activity's daily limit; amber = within warn-before of it.");
  if (out.length) {
    var values = out.map(function (o) {
      return [o.date, o.user, actNames[o.activity] || o.activity, Math.round(o.seconds / 60)];
    });
    // background per row: red if over the daily limit, amber if near it (B6)
    var WHITE = null, RED = "#f4cccc", AMBER = "#fff2cc";
    var bg = out.map(function (o) {
      var lim = limits[o.activity];
      var mins = Math.round(o.seconds / 60);
      var c = WHITE;
      if (lim && lim.daily_max > 0) {
        if (mins >= lim.daily_max) c = RED;
        else if (lim.warn_before > 0 && mins >= lim.daily_max - lim.warn_before) c = AMBER;
      }
      return [c, c, c, c];
    });
    sheet.getRange(2, 1, values.length, 4).setValues(values).setBackgrounds(bg);
  }
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, 4);
}

// B5: open the friendly-names tab for editing.
function ludexEditNames() {
  syncPeople_();
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(PEOPLE.name);
  if (sh) sh.activate();
  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Edit the 'name' column, then Ludex ▸ Refresh dashboard.", "Ludex", 6);
}

// Command entry, settings and limits editors now live in Forms.gs (HTML dialogs).
