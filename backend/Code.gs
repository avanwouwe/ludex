/**
 * Ludex backend — Google Apps Script web app.
 *
 * Bound to a Google Sheet that acts as both the database and the parent's dashboard.
 * The agent sends ONE POST containing a batch of calls; this returns ONE response with the
 * matching results, in order. See docs/protocol.md for the contract.
 *
 * Setup:
 *   1. Create a Google Sheet, Extensions → Apps Script, paste this file.
 *   2. Set SHARED_TOKEN and ADMIN_PASSWORD below (Script Properties recommended over literals).
 *   3. Deploy → New deployment → Web app → Execute as: Me, Access: Anyone.
 *   4. Run setup() once from the editor to create the tabs with headers.
 */

// ===== CONFIG =====
// Prefer Script Properties (File → Project properties → Script properties) over editing literals.
function prop_(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return (v === null || v === undefined || v === "") ? fallback : v;
}
function SHARED_TOKEN_()   { return prop_("SHARED_TOKEN", "change-me-to-a-long-random-string"); }
function ADMIN_PASSWORD_() { return prop_("ADMIN_PASSWORD", "change-me-admin"); }
// Destructive cleanup methods only work when this property is truthy. Leave it UNSET in production.
function DEVELOPMENT_MODE_() { return truthy_(prop_("DEVELOPMENT_MODE", "")); }

var SHEETS = {
  config:         { name: "config",         headers: ["key", "value"] },
  users:          { name: "users",          headers: ["user_id", "host_id", "hostname", "system_username", "public_ip", "os", "version", "first_seen", "last_seen"] },
  activity_log:   { name: "activity_log",   headers: ["server_time", "user_id", "period_start", "period_end", "period_seconds", "activity_id", "activity_seconds"] },
  activity_types: { name: "activity_types", headers: ["activity_id", "name", "definition", "enabled"] },
  commands:       { name: "commands",       headers: ["command_id", "user_id", "command_type", "params", "status", "created", "executed", "result"] }
};

var DEFAULT_CONFIG = {
  sample_interval_s: "20",
  sync_interval_s: "300",
  warn_before_minutes: "10",
  raw_retention_days: "3",       // raw activity_log rows older than this are rolled into activity_daily
  offline_alert_days: "7"        // email if a computer hasn't checked in for this many days
};

// ===== HTTP entry points =====
function doGet(e) {
  return json_({ ok: true, msg: "ludex backend alive" });
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return json_({ ok: false, error: "no post body" });
    }
    var req = JSON.parse(e.postData.contents);

    if (req.token !== SHARED_TOKEN_()) {
      return json_({ ok: false, error: "unauthorized" });
    }

    var calls = Array.isArray(req.calls) ? req.calls : [];
    var lock = LockService.getScriptLock();
    lock.waitLock(30000); // serialize writes across concurrent endpoints
    try {
      var results = calls.map(function (call) {
        var handler = DISPATCH[call.method];
        if (!handler) {
          return { id: call.id, ok: false, error: "unknown method: " + call.method };
        }
        try {
          return { id: call.id, ok: true, data: handler(call.params || {}) };
        } catch (err) {
          return { id: call.id, ok: false, error: String(err && err.message ? err.message : err) };
        }
      });
      return json_({ ok: true, results: results });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message ? err.message : err) });
  }
}

// ===== Method dispatch =====
var DISPATCH = {
  UpdateUser:        UpdateUser_,
  GetConfig:         GetConfig_,
  PutActivityLog:    PutActivityLog_,
  GetActivityLog:    GetActivityLog_,
  GetCommands:       GetCommands_,
  UpdateCommand:     UpdateCommand_,
  PutActivityType:   PutActivityType_,
  // admin-only cleanup (all require admin_password)
  DeleteActivityLog: DeleteActivityLog_,
  DeleteUser:        DeleteUser_,
  DeleteActivityType: DeleteActivityType_,
  DeleteCommand:     DeleteCommand_
};

// ===== Handlers =====
function UpdateUser_(p) {
  requireFields_(p, ["host_id", "user_id"]);
  var t = table_(SHEETS.users);
  var row = t.findRow("user_id", p.user_id);
  var now = new Date();
  if (row) {
    t.update(row, {
      host_id: p.host_id, hostname: p.hostname || "", system_username: p.system_username || "",
      public_ip: p.public_ip || "", os: p.os || "", version: p.version || "", last_seen: now
    });
    return { created: false };
  }
  t.append({
    user_id: p.user_id, host_id: p.host_id, hostname: p.hostname || "",
    system_username: p.system_username || "", public_ip: p.public_ip || "", os: p.os || "",
    version: p.version || "", first_seen: now, last_seen: now
  });
  return { created: true };
}

function GetConfig_(p) {
  var cfg = {};
  var ct = table_(SHEETS.config);
  ct.rows().forEach(function (r) { if (r.key) cfg[r.key] = r.value; });
  // fill defaults for anything unset
  Object.keys(DEFAULT_CONFIG).forEach(function (k) {
    if (cfg[k] === undefined || cfg[k] === "") cfg[k] = DEFAULT_CONFIG[k];
  });

  var types = table_(SHEETS.activity_types).rows()
    .filter(function (r) { return r.activity_id; })
    .map(function (r) {
      return { activity_id: r.activity_id, name: r.name || "", definition: r.definition || "", enabled: truthy_(r.enabled) };
    });

  return { config: cfg, activity_types: types };
}

function PutActivityLog_(p) {
  requireFields_(p, ["user_id", "period_start", "period_end"]);
  var start = new Date(p.period_start).getTime();
  var end = new Date(p.period_end).getTime();
  if (!(end > start)) throw new Error("period_end must be after period_start");

  var t = table_(SHEETS.activity_log);
  // overlap check for this user
  var overlap = t.rows().some(function (r) {
    if (r.user_id !== p.user_id) return false;
    var rs = new Date(r.period_start).getTime();
    var re = new Date(r.period_end).getTime();
    return rs < end && start < re; // half-open interval overlap
  });
  if (overlap) throw new Error("overlap: period already logged for this user");

  var now = new Date();
  var acts = Array.isArray(p.activities) ? p.activities : [];
  if (acts.length === 0) {
    t.append({
      server_time: now, user_id: p.user_id, period_start: p.period_start, period_end: p.period_end,
      period_seconds: p.period_seconds || 0, activity_id: "", activity_seconds: 0
    });
  } else {
    acts.forEach(function (a) {
      t.append({
        server_time: now, user_id: p.user_id, period_start: p.period_start, period_end: p.period_end,
        period_seconds: p.period_seconds || 0, activity_id: a.activity_id || "", activity_seconds: a.seconds || 0
      });
    });
  }

  // Email the parent if a daily limit was just crossed (once per user/activity/day).
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  acts.forEach(function (a) {
    if (a.activity_id) { try { checkLimitExceeded_(p.user_id, a.activity_id, tz); } catch (e) {} }
  });

  return { stored: true, rows: Math.max(1, acts.length) };
}

function GetActivityLog_(p) {
  requireFields_(p, ["user_id"]);
  var since = p.since ? new Date(p.since).getTime() : 0;
  var byPeriod = {};
  table_(SHEETS.activity_log).rows().forEach(function (r) {
    if (r.user_id !== p.user_id) return;
    if (new Date(r.period_end).getTime() <= since) return;
    var key = r.period_start + "|" + r.period_end;
    if (!byPeriod[key]) {
      byPeriod[key] = { period_start: r.period_start, period_end: r.period_end, activities: [] };
    }
    if (r.activity_id) {
      byPeriod[key].activities.push({ activity_id: r.activity_id, seconds: Number(r.activity_seconds) || 0 });
    }
  });
  return { periods: Object.keys(byPeriod).map(function (k) { return byPeriod[k]; }) };
}

function GetCommands_(p) {
  requireFields_(p, ["user_id"]);
  var cmds = table_(SHEETS.commands).rows()
    .filter(function (r) { return r.user_id === p.user_id && String(r.status).toLowerCase() === "pending"; })
    .map(function (r) {
      return { command_id: r.command_id, command_type: r.command_type, params: r.params || "" };
    });
  return { commands: cmds };
}

function UpdateCommand_(p) {
  requireFields_(p, ["command_id", "status"]);
  var t = table_(SHEETS.commands);
  var row = t.findRow("command_id", p.command_id);
  if (!row) throw new Error("unknown command_id: " + p.command_id);
  t.update(row, { status: p.status, result: p.result || "", executed: new Date() });
  return { updated: true };
}

function PutActivityType_(p) {
  requireAdmin_(p);
  requireFields_(p, ["activity_id", "definition"]);
  var t = table_(SHEETS.activity_types);
  var row = t.findRow("activity_id", p.activity_id);
  var enabled = (p.enabled === undefined) ? true : truthy_(p.enabled);
  if (row) {
    t.update(row, { definition: p.definition, enabled: enabled,
                    name: (p.name !== undefined ? p.name : (row.name || "")) });
    return { created: false };
  }
  t.append({ activity_id: p.activity_id, definition: p.definition, enabled: enabled, name: p.name || "" });
  return { created: true };
}

// ===== Admin cleanup handlers (development only) =====
// Destructive: gated behind the DEVELOPMENT_MODE property AND the admin password.
// On a production backend (DEVELOPMENT_MODE unset) these refuse to run at all.
function DeleteActivityLog_(p) {
  requireDevMode_();
  requireAdmin_(p);
  requireFields_(p, ["user_id"]);
  var before = p.before ? new Date(p.before).getTime() : null;
  var deleted = table_(SHEETS.activity_log).deleteWhere(function (r) {
    if (r.user_id !== p.user_id) return false;
    if (before !== null && new Date(r.period_end).getTime() > before) return false;
    return true;
  });
  return { deleted: deleted };
}

function DeleteUser_(p) {
  requireDevMode_();
  requireAdmin_(p);
  requireFields_(p, ["user_id"]);
  var deleted = table_(SHEETS.users).deleteWhere(function (r) { return r.user_id === p.user_id; });
  return { deleted: deleted };
}

function DeleteActivityType_(p) {
  requireDevMode_();
  requireAdmin_(p);
  requireFields_(p, ["activity_id"]);
  var deleted = table_(SHEETS.activity_types).deleteWhere(function (r) { return r.activity_id === p.activity_id; });
  return { deleted: deleted };
}

function DeleteCommand_(p) {
  requireDevMode_();
  requireAdmin_(p);
  requireFields_(p, ["command_id"]);
  var deleted = table_(SHEETS.commands).deleteWhere(function (r) {
    return String(r.command_id) === String(p.command_id);
  });
  return { deleted: deleted };
}

// ===== Sheet access (header-indexed table helper) =====
function table_(spec) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(spec.name);
  if (!sheet) {
    sheet = ss.insertSheet(spec.name);
    sheet.appendRow(spec.headers);
  }
  var headers = spec.headers;
  var colOf = {};
  headers.forEach(function (h, i) { colOf[h] = i; });

  function readAll() {
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) return [];
    var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
    return values.map(function (v, idx) {
      var obj = { __row: idx + 2 };
      headers.forEach(function (h, i) { obj[h] = v[i]; });
      return obj;
    });
  }

  return {
    rows: readAll,
    findRow: function (key, value) {
      var found = null;
      readAll().some(function (r) {
        if (String(r[key]) === String(value)) { found = r; return true; }
        return false;
      });
      return found;
    },
    append: function (obj) {
      sheet.appendRow(headers.map(function (h) { return obj[h] !== undefined ? obj[h] : ""; }));
    },
    update: function (rowObj, changes) {
      Object.keys(changes).forEach(function (h) {
        if (colOf[h] === undefined) return;
        sheet.getRange(rowObj.__row, colOf[h] + 1).setValue(changes[h]);
      });
    },
    deleteWhere: function (predicate) {
      var rownums = readAll().filter(predicate).map(function (r) { return r.__row; });
      rownums.sort(function (a, b) { return b - a; }); // delete bottom-up to keep indices valid
      rownums.forEach(function (n) { sheet.deleteRow(n); });
      return rownums.length;
    }
  };
}

// ===== Utilities =====
function requireAdmin_(p) {
  if (p.admin_password !== ADMIN_PASSWORD_()) throw new Error("unauthorized: bad admin_password");
}

function requireDevMode_() {
  if (!DEVELOPMENT_MODE_()) throw new Error("forbidden: development-only method (set DEVELOPMENT_MODE)");
}

function requireFields_(p, fields) {
  fields.forEach(function (f) {
    if (p[f] === undefined || p[f] === null || p[f] === "") throw new Error("missing field: " + f);
  });
}

// Normalise a date value from a sheet cell to a yyyy-MM-dd string.
// Cells formatted as dates come back as JS Date objects; text cells come back as strings.
function _toDateKey_(val, tz) {
  if (!val) return null;
  if (val instanceof Date) return Utilities.formatDate(val, tz, "yyyy-MM-dd");
  var s = String(val).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  var d = new Date(s);
  return isNaN(d.getTime()) ? null : Utilities.formatDate(d, tz, "yyyy-MM-dd");
}

function truthy_(v) {
  if (typeof v === "boolean") return v;
  var s = String(v).toLowerCase().trim();
  return s === "true" || s === "1" || s === "yes" || s === "y";
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ===== One-time setup: create tabs + seed config defaults =====
function setup() {
  Object.keys(SHEETS).forEach(function (k) { table_(SHEETS[k]); });  // ensure each sheet exists
  var ct = table_(SHEETS.config);
  var existing = {};
  ct.rows().forEach(function (r) { existing[r.key] = true; });
  Object.keys(DEFAULT_CONFIG).forEach(function (k) {
    if (!existing[k]) ct.append({ key: k, value: DEFAULT_CONFIG[k] });
  });
}
