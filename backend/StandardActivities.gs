/**
 * A small library of common activities, so parents don't have to define everything by hand.
 *
 * These are STARTING POINTS. Process names vary by version/installer, so verify on the actual
 * computers (run `ludex detect-app`) and tune the limits in the activity_types tab. Matching is
 * case-insensitive substring, so a brand name in the process name (e.g. "roblox") usually works on
 * every OS; the per-platform `platforms` form is used only where the process name truly differs
 * (e.g. Minecraft's launcher is `javaw` on Windows, `java` elsewhere).
 *
 * Install via: Ludex ▸ Install standard activities (existing activity_ids are left untouched).
 */

var STANDARD_ACTIVITIES = [
  {
    activity_id: "minecraft", name: "Minecraft",
    definition: {
      platforms: {
        linux:   { match_any: [{ name_contains: "java",  cmdline_contains: ["net.minecraft"] }, { name_contains: "minecraft" }] },
        mac:     { match_any: [{ name_contains: "java",  cmdline_contains: ["net.minecraft"] }, { name_contains: "minecraft" }] },
        windows: { match_any: [{ name_contains: "javaw", cmdline_contains: ["net.minecraft"] }, { name_contains: "minecraft" }] }
      },
      min_cpu_percent: 5,
      limits: { daily_max_minutes: 120, pause_after_minutes: 45, pause_duration_minutes: 10, warn_before_minutes: 10 }
    }
  },
  { activity_id: "roblox", name: "Roblox",
    definition: { match_any: [{ name_contains: "roblox" }], min_cpu_percent: 3, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "fortnite", name: "Fortnite",
    definition: { match_any: [{ name_contains: "fortnite" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "steam-games", name: "Steam games",
    definition: { match_any: [{ name_contains: "steam" }], min_cpu_percent: 5, limits: { daily_max_minutes: 120, warn_before_minutes: 10 } } },
  { activity_id: "discord", name: "Discord",
    definition: { match_any: [{ name_contains: "discord" }], min_cpu_percent: 1, limits: { daily_max_minutes: 120, warn_before_minutes: 15 } } },
  { activity_id: "league-of-legends", name: "League of Legends",
    definition: { match_any: [{ name_contains: "league of legends" }, { name_contains: "leagueclient" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "valorant", name: "Valorant",
    definition: { match_any: [{ name_contains: "valorant" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "rocket-league", name: "Rocket League",
    definition: { match_any: [{ name_contains: "rocketleague" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "genshin-impact", name: "Genshin Impact",
    definition: { match_any: [{ name_contains: "genshin" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "gta-v", name: "GTA V",
    definition: { match_any: [{ name_contains: "gta5" }, { name_contains: "gtav" }], min_cpu_percent: 5, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "among-us", name: "Among Us",
    definition: { match_any: [{ name_contains: "among us" }], min_cpu_percent: 3, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "terraria", name: "Terraria",
    definition: { match_any: [{ name_contains: "terraria" }], min_cpu_percent: 3, limits: { daily_max_minutes: 90, warn_before_minutes: 10 } } },
  { activity_id: "epic-games-launcher", name: "Epic Games Launcher",
    definition: { match_any: [{ name_contains: "epicgames" }], min_cpu_percent: 3, limits: { daily_max_minutes: 120, warn_before_minutes: 10 } } },
  { activity_id: "spotify", name: "Spotify",
    definition: { match_any: [{ name_contains: "spotify" }], min_cpu_percent: 1, limits: { daily_max_minutes: 180, warn_before_minutes: 15 } } },
  { activity_id: "zoom", name: "Zoom",
    definition: { match_any: [{ name_contains: "zoom" }], min_cpu_percent: 1, limits: { daily_max_minutes: 240, warn_before_minutes: 15 } } }
];

function ludexInstallStandardActivities() {
  var ui = SpreadsheetApp.getUi();
  var t = table_(SHEETS.activity_types);
  var have = {};
  t.rows().forEach(function (r) { if (r.activity_id) have[r.activity_id] = true; });

  var added = 0, skipped = 0;
  STANDARD_ACTIVITIES.forEach(function (a) {
    if (have[a.activity_id]) { skipped++; return; }
    t.append({ activity_id: a.activity_id, name: a.name || "", definition: JSON.stringify(a.definition), enabled: true });
    added++;
  });

  ui.alert("Standard activities",
    "Added " + added + ", skipped " + skipped + " already present.\n\n"
    + "These are starting points — verify the process names on your computers with "
    + "`ludex detect-app`, and adjust the limits in the activity_types tab.",
    ui.ButtonSet.OK);
}
