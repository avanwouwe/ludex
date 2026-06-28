/**
 * Email alerts: heartbeat-gap (a computer stopped checking in) and daily-limit-exceeded.
 *
 * Recipients come from the `email` column of the `people` tab (comma/semicolon-separated for
 * several). An alert about a child goes to that child's addresses; if none are set, it falls back
 * to every address found in the people tab. Needs the script.send_mail OAuth scope.
 *
 * Dedup state is kept in Script Properties so an alert fires once, not every run:
 *   offline_alerted:<user_id>            (cleared when the device checks in again)
 *   limit_alerted:<user_id>:<aid>:<date> (per day)
 */

function splitEmails_(s) {
  return String(s || "").split(/[,;\s]+/).map(function (x) { return x.trim(); }).filter(Boolean);
}

function _recipientsFor_(user_id) {
  var mine = [], all = [];
  table_(PEOPLE).rows().forEach(function (r) {
    var es = splitEmails_(r.email);
    all = all.concat(es);
    if (r.user_id === user_id) mine = mine.concat(es);
  });
  var list = mine.length ? mine : all;
  var seen = {}, out = [];
  list.forEach(function (e) { var k = e.toLowerCase(); if (!seen[k]) { seen[k] = 1; out.push(e); } });
  return out;
}

function sendAlert_(user_id, subject, body) {
  var to = _recipientsFor_(user_id);
  if (!to.length) return false;  // no recipients configured -> nothing to do
  try { MailApp.sendEmail(to.join(","), subject, body); return true; }
  catch (e) { return false; }
}

function _offlineDays_() {
  var v = null;
  table_(SHEETS.config).rows().forEach(function (r) { if (r.key === "offline_alert_days") v = r.value; });
  var n = parseInt(v, 10);
  return (isNaN(n) || n < 1) ? 7 : n;
}

// Hourly trigger: alert when a computer hasn't checked in for offline_alert_days.
function ludexHeartbeatCheck() {
  var labels = _userLabels_();
  var thresholdMs = _offlineDays_() * 24 * 3600 * 1000;
  var props = PropertiesService.getScriptProperties();
  var now = Date.now();
  table_(SHEETS.users).rows().forEach(function (u) {
    if (!u.user_id || !u.last_seen) return;
    var seen = new Date(u.last_seen).getTime();
    if (isNaN(seen)) return;
    var key = "offline_alerted:" + u.user_id;
    var stale = (now - seen) > thresholdMs;
    if (stale && !props.getProperty(key)) {
      var who = labels[u.user_id] || u.user_id;
      if (sendAlert_(u.user_id, "Ludex: " + who + "'s computer is offline",
            who + "'s computer (" + (u.hostname || "?") + ") hasn't checked in since "
            + u.last_seen + ".\n\nLudex may have been closed/stopped, or the computer is off.")) {
        props.setProperty(key, "1");
      }
    } else if (!stale) {
      props.deleteProperty(key);  // checked in again -> reset so a future gap re-alerts
    }
  });
}

// Called from PutActivityLog_ after storing: alert once when a daily limit is crossed.
function checkLimitExceeded_(user_id, activity_id, tz) {
  var lim = _activityLimits_()[activity_id];
  if (!lim || !lim.daily_max) return;
  var today = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd");

  var total = 0;
  table_(SHEETS.activity_log).rows().forEach(function (r) {
    if (r.user_id !== user_id || r.activity_id !== activity_id) return;
    var d;
    try { d = Utilities.formatDate(new Date(r.period_start), tz, "yyyy-MM-dd"); } catch (e) { return; }
    if (d === today) total += Number(r.activity_seconds) || 0;
  });
  if (total / 60 < lim.daily_max) return;

  var props = PropertiesService.getScriptProperties();
  var key = "limit_alerted:" + user_id + ":" + activity_id + ":" + today;
  if (props.getProperty(key)) return;

  var who = _userLabels_()[user_id] || user_id;
  var name = _activityNames_()[activity_id] || activity_id;
  if (sendAlert_(user_id, "Ludex: daily limit reached for " + name,
        who + " has reached the daily limit for " + name + " (" + lim.daily_max + " min today).")) {
    props.setProperty(key, "1");
  }
}

// Called from PutActivityLog_ after storing: alert once when the global daily screen-time limit
// (set per-person in the people tab) is crossed.
function checkGlobalLimitExceeded_(user_id, tz) {
  var pRow = table_(PEOPLE).findRow("user_id", user_id);
  if (!pRow) return;
  var daily_max = _numOrNull_(pRow.daily_max_minutes);
  if (!daily_max) return;

  var today = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd");

  // Sum all tracked activity seconds for this user today.
  var total = 0;
  table_(SHEETS.activity_log).rows().forEach(function (r) {
    if (r.user_id !== user_id || !r.activity_id) return;
    var d;
    try { d = Utilities.formatDate(new Date(r.period_start), tz, "yyyy-MM-dd"); } catch (e) { return; }
    if (d === today) total += Number(r.activity_seconds) || 0;
  });
  if (total / 60 < daily_max) return;

  var props = PropertiesService.getScriptProperties();
  var key = "global_limit_alerted:" + user_id + ":" + today;
  if (props.getProperty(key)) return;

  var who = _userLabels_()[user_id] || user_id;
  if (sendAlert_(user_id,
        "Ludex: daily screen time limit reached for " + who,
        who + " has reached the daily screen time limit (" + daily_max + " min today across all tracked activities).")) {
    props.setProperty(key, "1");
  }
}

// Schedule the hourly heartbeat check (idempotent). Called on first install.
function enableHeartbeat_() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === "ludexHeartbeatCheck") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("ludexHeartbeatCheck").timeBased().everyHours(1).create();
}
