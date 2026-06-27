/**
 * HTML-dialog forms for the management UI: send a command, edit settings, edit activity limits.
 * Each opener shows an HTML file; the page loads its data via a get* function and saves via a
 * ludex* function (called with google.script.run). Also applies status coloring to the commands tab.
 */

var COMMAND_TYPES = ["notify-user", "stop-activity", "shutdown-endpoint", "reload-config"];

var CONFIG_FIELDS = [
  { key: "sample_interval_s",   label: "Sample interval (seconds)",  desc: "How often the agent checks what's running." },
  { key: "sync_interval_s",     label: "Sync interval (seconds)",    desc: "How often the agent talks to this sheet." },
  { key: "warn_before_minutes", label: "Default warn-before (min)",  desc: "Minutes before a daily limit to warn, if an activity doesn't set its own." },
  { key: "raw_retention_days",  label: "Keep raw log (days)",        desc: "Days of detailed log kept before rolling into the archive." }
];

var LIMIT_FIELDS = ["daily_max_minutes", "pause_after_minutes", "pause_duration_minutes", "warn_before_minutes"];

// ----- Send a command -----
function ludexSendCommand() {
  if (!table_(SHEETS.users).rows().some(function (u) { return u.user_id; })) {
    SpreadsheetApp.getUi().alert("No computers yet — an agent has to check in at least once first.");
    return;
  }
  var h = HtmlService.createHtmlOutputFromFile("Command").setWidth(380).setHeight(320);
  SpreadsheetApp.getUi().showModalDialog(h, "Ludex — send a command");
}

function getCommandFormData() {
  var labels = _userLabels_();
  var users = table_(SHEETS.users).rows().filter(function (u) { return u.user_id; })
    .map(function (u) { return { id: u.user_id, label: labels[u.user_id] || u.user_id }; });
  var acts = table_(SHEETS.activity_types).rows().filter(function (a) { return a.activity_id; })
    .map(function (a) { return a.activity_id; });
  return { users: users, activities: acts };
}

function ludexQueueCommand(userId, type, params) {
  userId = (userId || "").trim();
  type = (type || "").trim();
  params = (params || "").trim();
  if (!userId) throw new Error("Pick a computer.");
  if (COMMAND_TYPES.indexOf(type) < 0) throw new Error("Pick a command type.");
  if (type === "notify-user" && !params) throw new Error("Enter a message.");
  if (type === "stop-activity" && !params) throw new Error("Pick an activity.");
  var id = "cmd-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
  table_(SHEETS.commands).append({
    command_id: id, user_id: userId, command_type: type, params: params,
    status: "pending", created: new Date(), executed: "", result: ""
  });
  return true;
}

// ----- Settings (config tab) -----
function ludexSettings() {
  var h = HtmlService.createHtmlOutputFromFile("Settings").setWidth(420).setHeight(380);
  SpreadsheetApp.getUi().showModalDialog(h, "Ludex — settings");
}

function getSettings() {
  var cur = {};
  table_(SHEETS.config).rows().forEach(function (r) { if (r.key) cur[r.key] = r.value; });
  return CONFIG_FIELDS.map(function (f) {
    return { key: f.key, label: f.label, desc: f.desc, value: (cur[f.key] !== undefined ? cur[f.key] : "") };
  });
}

function ludexSaveSettings(values) {
  var t = table_(SHEETS.config);
  CONFIG_FIELDS.forEach(function (f) {
    if (values[f.key] === undefined) return;
    var v = String(values[f.key]).trim();
    var row = t.findRow("key", f.key);
    if (row) t.update(row, { value: v });
    else t.append({ key: f.key, value: v });
  });
  return true;
}

// ----- Activity limits (activity_types definitions) -----
function ludexLimits() {
  if (!table_(SHEETS.activity_types).rows().some(function (a) { return a.activity_id; })) {
    SpreadsheetApp.getUi().alert("No activities yet — add some (Install standard activities, or ludex detect-app).");
    return;
  }
  var h = HtmlService.createHtmlOutputFromFile("Limits").setWidth(400).setHeight(420);
  SpreadsheetApp.getUi().showModalDialog(h, "Ludex — edit activity limits");
}

function getLimitsData() {
  return table_(SHEETS.activity_types).rows().filter(function (a) { return a.activity_id; })
    .map(function (a) {
      var lim;
      try { lim = (JSON.parse(a.definition || "{}").limits) || {}; }
      catch (e) { lim = null; }  // non-JSON definition: not editable here
      return { id: a.activity_id, limits: lim };
    });
}

function ludexSaveLimits(activityId, limits) {
  var t = table_(SHEETS.activity_types);
  var row = t.findRow("activity_id", activityId);
  if (!row) throw new Error("Unknown activity.");
  var def;
  try { def = JSON.parse(row.definition || "{}"); }
  catch (e) { throw new Error("This activity's definition isn't editable here (not JSON). Edit it manually."); }
  var clean = {};
  LIMIT_FIELDS.forEach(function (k) {
    var v = limits[k];
    if (v !== undefined && v !== null && String(v).trim() !== "") {
      var n = Number(v);
      if (!isNaN(n) && n > 0) clean[k] = n;
    }
  });
  if (Object.keys(clean).length) def.limits = clean; else delete def.limits;
  t.update(row, { definition: JSON.stringify(def) });
  return true;
}

// ----- Commands status coloring (applied once; auto-updates as values change) -----
function applyCommandFormatting_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEETS.commands.name);
  if (!sh) return;
  var statusCol = SHEETS.commands.headers.indexOf("status") + 1;
  var rng = sh.getRange(2, statusCol, Math.max(sh.getMaxRows() - 1, 1), 1);
  function rule(text, color) {
    return SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(text).setBackground(color).setRanges([rng]).build();
  }
  sh.setConditionalFormatRules([
    rule("pending", "#fff2cc"),
    rule("done", "#d9ead3"),
    rule("failed", "#f4cccc")
  ]);
}
