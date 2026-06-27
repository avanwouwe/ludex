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
    .addSeparator()
    .addItem("Refresh dashboard", "ludexRefreshDashboard")
    .addItem("Send a command…", "ludexSendCommand")
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

function ludexSetCredentials() {
  var ui = SpreadsheetApp.getUi();
  var props = PropertiesService.getScriptProperties();

  var r1 = ui.prompt("Ludex setup (1 of 2)",
    "Shared key — every agent on your computers uses this. Make it long and secret:",
    ui.ButtonSet.OK_CANCEL);
  if (r1.getSelectedButton() !== ui.Button.OK) return;
  var token = r1.getResponseText().trim();

  var r2 = ui.prompt("Ludex setup (2 of 2)",
    "Admin password — needed to add activities and to clean up data:",
    ui.ButtonSet.OK_CANCEL);
  if (r2.getSelectedButton() !== ui.Button.OK) return;
  var admin = r2.getResponseText().trim();

  if (!token || !admin) { ui.alert("Both values are required — nothing was saved."); return; }
  props.setProperty("SHARED_TOKEN", token);
  props.setProperty("ADMIN_PASSWORD", admin);

  ludexSetup();  // make sure the data tabs exist
  ui.alert("Saved ✓",
    "Credentials stored. Next step: deploy the backend as a web app — "
    + "open the Ludex menu ▸ ③ How to deploy.", ui.ButtonSet.OK);
}

function ludexSetup() {
  setup();                 // from Code.gs: creates data tabs + seeds config defaults
  buildDashboardSheet_();  // ensure the dashboard tab exists
  SpreadsheetApp.getActiveSpreadsheet().toast("Sheets ready.", "Ludex", 4);
}

function ludexDeployHelp() {
  SpreadsheetApp.getUi().alert("Deploy the Ludex backend (one time)",
    "In the script editor (Extensions ▸ Apps Script):\n\n"
    + "1. Click  Deploy ▸ New deployment\n"
    + "2. Select type:  Web app\n"
    + "3. Execute as:  Me\n"
    + "4. Who has access:  Anyone\n"
    + "5. Click Deploy, authorize, and copy the Web app URL (ends in /exec)\n\n"
    + "Give that URL and your shared key to each computer's agent:  ludex install\n\n"
    + "If you change the code later, repeat with Deploy ▸ Manage deployments ▸ "
    + "edit ▸ New version (this keeps the same URL).",
    SpreadsheetApp.getUi().ButtonSet.OK);
}
