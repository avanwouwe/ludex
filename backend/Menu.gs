/**
 * Ludex onboarding + management menu (bound-sheet UI).
 *
 * Designed so a non-developer parent can: copy this Sheet, set their credentials from a menu,
 * and deploy — without ever touching the code. The only manual step Google forces is the
 * one-time web-app deployment (see ludexDeployHelp).
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Ludex")
    .addItem("① Set credentials…", "ludexSetCredentials")
    .addItem("② Create / repair sheets", "ludexSetup")
    .addItem("③ How to deploy the backend…", "ludexDeployHelp")
    .addItem("Check setup", "ludexCheckSetup")
    .addItem("Install standard activities", "ludexInstallStandardActivities")
    .addItem("Edit activity limits…", "ludexLimits")
    .addItem("Settings…", "ludexSettings")
    .addSeparator()
    .addItem("Refresh dashboard", "ludexRefreshDashboard")
    .addItem("Edit names", "ludexEditNames")
    .addItem("Send a command…", "ludexSendCommand")
    .addSeparator()
    .addItem("Run maintenance now", "ludexRunMaintenance")
    .addItem("Enable nightly maintenance", "ludexEnableNightlyMaintenance")
    .addItem("Toggle development mode", "ludexToggleDevMode")
    .addToUi();

  if (!ludexIsConfigured_()) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Not configured yet — open the Ludex menu ▸ ① Set credentials.", "Ludex setup", 8);
  }
}

function ludexIsConfigured_() {
  var p = PropertiesService.getScriptProperties();
  return !!p.getProperty("SHARED_TOKEN") && !!p.getProperty("ADMIN_PASSWORD");
}

// ① Credentials — a small masked HTML form (passwords aren't echoed in plain prompts).
function ludexSetCredentials() {
  var html = HtmlService.createHtmlOutputFromFile("Setup").setWidth(420).setHeight(320);
  SpreadsheetApp.getUi().showModalDialog(html, "Ludex — set credentials");
}

// called from Setup.html via google.script.run
function ludexSaveCredentials(token, admin) {
  token = (token || "").trim();
  admin = (admin || "").trim();
  if (!token || !admin) throw new Error("Both fields are required.");
  var p = PropertiesService.getScriptProperties();
  p.setProperty("SHARED_TOKEN", token);
  p.setProperty("ADMIN_PASSWORD", admin);
  ludexSetup();  // make sure the data tabs exist
  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Credentials saved. Next: Ludex ▸ ③ How to deploy.", "Ludex", 6);
}

function ludexSetup() {
  setup();                  // from Code.gs: creates data tabs + seeds config defaults
  buildDashboardSheet_();   // ensure the dashboard tab exists
  syncPeople_();            // ensure the people (friendly names) tab exists
  applyCommandFormatting_();// color the commands status column (pending/done/failed)
  SpreadsheetApp.getActiveSpreadsheet().toast("Sheets ready.", "Ludex", 4);
}

function ludexDeployHelp() {
  SpreadsheetApp.getUi().alert("Deploy the Ludex backend (one time)",
    "In the script editor (Extensions ▸ Apps Script):\n\n"
    + "1. Click  Deploy ▸ New deployment\n"
    + "2. Select type:  Web app\n"
    + "3. Execute as:  Me\n"
    + "4. Who has access:  Anyone\n"
    + "5. Click Deploy and authorize\n\n"
    + "Copy the Web app URL it shows (it ends in /exec). Give that URL and your shared key to "
    + "each computer when you install Ludex there.\n\n"
    + "If you change the code later, repeat with Deploy ▸ Manage deployments ▸ "
    + "edit ▸ New version (this keeps the same URL).",
    SpreadsheetApp.getUi().ButtonSet.OK);
}

// In-process setup check (no external request scope needed).
function ludexCheckSetup() {
  var ui = SpreadsheetApp.getUi();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var lines = [];
  lines.push(ludexIsConfigured_() ? "✓ Credentials are set"
    : "✗ Credentials NOT set — use ① Set credentials");

  var need = ["config", "users", "activity_log", "activity_types", "commands"];
  var missing = need.filter(function (n) { return !ss.getSheetByName(n); });
  lines.push(missing.length ? "✗ Missing tabs: " + missing.join(", ") + " — use ② Create / repair sheets"
    : "✓ All data tabs exist");

  var raw = "";
  try { raw = ScriptApp.getService().getUrl() || ""; } catch (e) {}
  lines.push(raw ? "✓ Web app is deployed" : "✗ Not deployed — use ③ How to deploy");

  try { GetConfig_({}); lines.push("✓ Backend logic responds"); }
  catch (e) { lines.push("✗ Backend error: " + e.message); }

  lines.push("", "Final check: open your /exec URL in a browser — it should say \"ludex backend alive\".");
  ui.alert("Ludex setup check", lines.join("\n"), ui.ButtonSet.OK);
}
