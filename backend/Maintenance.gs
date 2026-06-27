/**
 * Ludex maintenance: keep activity_log small by rolling old rows into a compact archive.
 *
 * Why: every agent sync scans the whole activity_log (overlap check in PutActivityLog, and
 * GetActivityLog for state recovery). Left unbounded it grows with every computer, every day,
 * forever — eventually slow and quota-hungry. But the agent only ever needs *recent* raw rows
 * (it recovers just "today" and never re-logs old periods), so older rows can be aggregated to
 * one row per (day, user, activity) and the raw rows deleted. The dashboard reads both, so full
 * history is preserved.
 *
 * Run it from Ludex ▸ Run maintenance now, or enable a nightly trigger (Ludex ▸ Enable nightly
 * maintenance).
 */

var ARCHIVE = { name: "activity_daily", headers: ["date", "user_id", "activity_id", "seconds"] };

function _retentionDays_() {
  var v = null;
  table_(SHEETS.config).rows().forEach(function (r) { if (r.key === "raw_retention_days") v = r.value; });
  var n = parseInt(v, 10);
  return (isNaN(n) || n < 1) ? 3 : n;
}

/** Aggregate activity_log rows older than the retention window into activity_daily, then delete
 *  them from the raw log. Returns the number of raw rows removed. */
function rollupOldActivityLog_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = ss.getSpreadsheetTimeZone();
  var cutoff = Date.now() - _retentionDays_() * 24 * 3600 * 1000;
  var logT = table_(SHEETS.activity_log);

  function isOld(r) {
    var endMs = new Date(r.period_end).getTime();
    return !isNaN(endMs) && endMs < cutoff;
  }

  // 1. aggregate the old, non-idle rows by (local day, user, activity)
  var agg = {};
  logT.rows().forEach(function (r) {
    if (!isOld(r) || !r.activity_id) return;
    var day;
    try { day = Utilities.formatDate(new Date(r.period_start), tz, "yyyy-MM-dd"); } catch (e) { return; }
    var key = day + "|" + r.user_id + "|" + r.activity_id;
    agg[key] = (agg[key] || 0) + (Number(r.activity_seconds) || 0);
  });

  // 2. merge aggregates into the archive (sum into existing day rows, else append)
  var arcT = table_(ARCHIVE);
  var existing = {};
  arcT.rows().forEach(function (a) { existing[a.date + "|" + a.user_id + "|" + a.activity_id] = a; });
  Object.keys(agg).forEach(function (key) {
    var row = existing[key];
    if (row) {
      arcT.update(row, { seconds: (Number(row.seconds) || 0) + agg[key] });
    } else {
      var p = key.split("|");
      arcT.append({ date: p[0], user_id: p[1], activity_id: p[2], seconds: agg[key] });
    }
  });

  // 3. delete all old raw rows (including idle markers) now that they're archived
  return logT.deleteWhere(isOld);
}

// ===== Menu entry points =====
function ludexRunMaintenance() {
  var removed = rollupOldActivityLog_();
  buildDashboard_();
  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Maintenance done — archived " + removed + " old log row(s).", "Ludex", 5);
}

function ludexNightlyMaintenance() {
  rollupOldActivityLog_();
  buildDashboard_();
}

function ludexEnableNightlyMaintenance() {
  var ui = SpreadsheetApp.getUi();
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "ludexNightlyMaintenance") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("ludexNightlyMaintenance").timeBased().everyDays(1).atHour(3).create();
  ui.alert("Nightly maintenance enabled",
    "Each night (~3am) Ludex will roll old logs into the archive and refresh the dashboard. "
    + "Your full history stays visible on the dashboard.", ui.ButtonSet.OK);
}
