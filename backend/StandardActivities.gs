/**
 * A small library of common activities, so parents don't have to define everything by hand.
 *
 * Each entry has a single keyword matched case-insensitively (after stripping spaces, dots,
 * slashes and dashes) against the process name, exe path, and full command line. A keyword
 * like "minecraft" therefore matches both a process named "minecraft" and a Java invocation
 * whose cmdline contains "net.minecraft".
 *
 * These are starting points — verify on the actual computers via Ludex › Add tracked activity,
 * and adjust the limits directly in the activity_types tab.
 *
 * Install via: Ludex ▸ Install standard activities (existing activity_ids are left untouched).
 */

var STANDARD_ACTIVITIES = [
  { activity_id: "minecraft",           name: "Minecraft",
    keyword: "minecraft",       min_cpu_percent: 5,  daily_max_minutes: 120, warn_before_minutes: 10, pause_after_minutes: 45, pause_duration_minutes: 10 },

  { activity_id: "roblox",              name: "Roblox",
    keyword: "roblox",          min_cpu_percent: 3,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "fortnite",            name: "Fortnite",
    keyword: "fortnite",        min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "discord",             name: "Discord",
    keyword: "discord",         min_cpu_percent: 1,  daily_max_minutes: 120, warn_before_minutes: 15 },

  { activity_id: "league-of-legends",   name: "League of Legends",
    keyword: "league",          min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "valorant",            name: "Valorant",
    keyword: "valorant",        min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "rocket-league",       name: "Rocket League",
    keyword: "rocketleague",    min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "genshin-impact",      name: "Genshin Impact",
    keyword: "genshin",         min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "gta-v",               name: "GTA V",
    keyword: "gta",             min_cpu_percent: 5,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "among-us",            name: "Among Us",
    keyword: "amongus",         min_cpu_percent: 3,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "terraria",            name: "Terraria",
    keyword: "terraria",        min_cpu_percent: 3,  daily_max_minutes: 90,  warn_before_minutes: 10 },

  { activity_id: "epic-games-launcher", name: "Epic Games Launcher",
    keyword: "epicgames",       min_cpu_percent: 3,  daily_max_minutes: 120, warn_before_minutes: 10 },

  { activity_id: "spotify",             name: "Spotify",
    keyword: "spotify",         min_cpu_percent: 1,  daily_max_minutes: 180, warn_before_minutes: 15 },

  { activity_id: "zoom",                name: "Zoom",
    keyword: "zoom",            min_cpu_percent: 1,  daily_max_minutes: 240, warn_before_minutes: 15 }
];

// Insert any standard activities not already present. Returns {added, skipped}. Silent (no UI),
// so it can run during install.
function installStandardActivities_() {
  var t = table_(SHEETS.activity_types);
  var have = {};
  t.rows().forEach(function (r) { if (r.activity_id) have[r.activity_id] = true; });

  var added = 0, skipped = 0;
  STANDARD_ACTIVITIES.forEach(function (a) {
    if (have[a.activity_id]) { skipped++; return; }
    t.append({
      activity_id:          a.activity_id,
      name:                 a.name || "",
      keyword:              a.keyword || "",
      min_cpu_percent:      a.min_cpu_percent  !== undefined ? a.min_cpu_percent  : "",
      daily_max_minutes:    a.daily_max_minutes !== undefined ? a.daily_max_minutes : "",
      warn_before_minutes:  a.warn_before_minutes !== undefined ? a.warn_before_minutes : "",
      pause_after_minutes:  a.pause_after_minutes !== undefined ? a.pause_after_minutes : "",
      pause_duration_minutes: a.pause_duration_minutes !== undefined ? a.pause_duration_minutes : "",
      enabled: true
    });
    added++;
  });
  return { added: added, skipped: skipped };
}

function ludexInstallStandardActivities() {
  var r = installStandardActivities_();
  SpreadsheetApp.getUi().alert("Standard activities",
    "Added " + r.added + ", skipped " + r.skipped + " already present.\n\n"
    + "These are starting points — verify on your computers via Ludex › Add tracked activity, "
    + "and adjust limits directly in the activity_types tab.",
    SpreadsheetApp.getUi().ButtonSet.OK);
}
