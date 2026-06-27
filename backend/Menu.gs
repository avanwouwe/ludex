/**
 * Ludex onboarding + management menu (bound-sheet UI).
 *
 * Progressive disclosure: until credentials are set, only the setup items show. Once configured,
 * the full menu appears (rare/technical items live under an "Advanced" submenu). A non-developer
 * parent never has to touch the code; the only manual step Google forces is the one-time web-app
 * deployment (see ludexDeployHelp).
 */

function onOpen() {
  buildMenu_();
  if (!ludexIsConfigured_()) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Welcome! Open the Ludex menu ▸ ① Set credentials to begin.", "Ludex setup", 8);
  }
}

function buildMenu_() {
  var ui = SpreadsheetApp.getUi();
  var menu = ui.createMenu("Ludex");

  if (!ludexIsConfigured_()) {
    menu.addItem("① Set credentials", "ludexSetCredentials")
        .addItem("② How to deploy the dashboard", "ludexDeployHelp");
  } else {
    menu.addItem("Refresh dashboard", "ludexRefreshDashboard")
        .addItem("Activity analysis", "ludexUsageChart")
        .addItem("Send a command", "ludexSendCommand")
        .addItem("Edit people", "ludexEditNames")
        .addItem("Edit activity limits", "ludexLimits")
        .addSeparator()
        .addItem("Settings", "ludexSettings")
        .addItem("Set credentials", "ludexSetCredentials")
        .addSubMenu(ui.createMenu("Advanced")
          .addItem("How to deploy the dashboard", "ludexDeployHelp")
          .addItem("Create / repair sheets", "ludexSetup")
          .addItem("Install standard activities", "ludexInstallStandardActivities")
          .addItem("Run maintenance now", "ludexRunMaintenance"));
  }
  menu.addToUi();
}

function ludexIsConfigured_() {
  var p = PropertiesService.getScriptProperties();
  return !!p.getProperty("SHARED_TOKEN") && !!p.getProperty("ADMIN_PASSWORD");
}

// ① Credentials — an HTML form. Shared key shown, admin password hidden; both prefilled.
function ludexSetCredentials() {
  var html = HtmlService.createHtmlOutputFromFile("Setup").setWidth(440).setHeight(300);
  SpreadsheetApp.getUi().showModalDialog(html, "Ludex — set credentials");
}

// called from Setup.html to prefill the form
function getCredentials() {
  var p = PropertiesService.getScriptProperties();
  return { token: p.getProperty("SHARED_TOKEN") || "", admin: p.getProperty("ADMIN_PASSWORD") || "" };
}

// called from Setup.html via google.script.run
function ludexSaveCredentials(token, admin) {
  token = (token || "").trim();
  admin = (admin || "").trim();
  if (!token || !admin) throw new Error("Both fields are required.");
  var p = PropertiesService.getScriptProperties();
  var firstTime = !ludexIsConfigured_();
  p.setProperty("SHARED_TOKEN", token);
  p.setProperty("ADMIN_PASSWORD", admin);

  ludexSetup();                  // create/repair the data tabs, dashboard, people, formatting
  if (firstTime) {
    installStandardActivities_();// seed common games so there's something to track immediately
    enableNightlyMaintenance_(); // schedule the nightly rollup
    enableHeartbeat_();          // schedule the hourly offline-device check
  }
  buildMenu_();                  // reveal the full menu now that we're configured

  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Saved. Next: Ludex ▸ ② How to deploy the backend.", "Ludex", 6);
}

function ludexSetup() {
  setup();                   // from Code.gs: creates data tabs + seeds config defaults
  buildDashboardSheet_();    // ensure the dashboard tab exists
  syncPeople_();             // ensure the people (friendly names) tab exists
  applyCommandFormatting_(); // color the commands status column (pending/done/failed)
  applySheetHeaderStyles_(); // pretty headers on commands, people, users sheets
  SpreadsheetApp.getActiveSpreadsheet().toast("Sheets ready.", "Ludex", 4);
}

function ludexDeployHelp() {
  SpreadsheetApp.getUi().alert("Deploy the Ludex dashboard (one time)",
    "In the script editor (Extensions ▸ Apps Script):\n\n"
    + "1. Click  Deploy ▸ New deployment\n"
    + "2. Select type:  Web app\n"
    + "3. Execute as:  Me\n"
    + "4. Who has access:  Anyone\n"
    + "5. Click Deploy and authorize\n\n"
    + "Copy the Web app URL it shows (it ends in /exec). Give that URL and your shared key to "
    + "each computer when you install Ludex there.",
    SpreadsheetApp.getUi().ButtonSet.OK);
}
