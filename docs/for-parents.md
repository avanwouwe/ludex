# Installing Ludex (for parents)

A plain-language guide to setting up Ludex yourself. No programming needed. You'll need a Google
account and about 15 minutes. There are two parts: **(1)** your private database (a Google Sheet),
and **(2)** the small app on each child's computer.

---

## Part 1 — Your backend (a Google Sheet you own)

Everything Ludex records lives in **your own Google Sheet**. No one else can see it.

1. **Open the Ludex template link** you were given and choose **File ▸ Make a copy**. This gives you
   your own private copy. (Your copy starts empty — none of anyone else's data or passwords come
   with it.)
2. **Reload the page.** A new **Ludex** menu appears at the top, next to *Help*.
3. Click **Ludex ▸ ① Set credentials** and enter two things you make up:
   - a **shared key** — like a password; every computer you monitor will use it to report to the dashboard.
   - an **admin password** — used should you need to add new activities. (⚠️ dp not re-use "your regular password")
   
   Write both down somewhere safe.
4. Click **Ludex ▸ ③ How to deploy the backend** and follow the five steps it shows. At the end,
   **copy the Web app URL** (it ends in `/exec`) — that URL, plus your shared key, is what each
   computer needs.

That's the database done. The **Ludex** menu is also where you'll manage things day to day (see
Part 3).

---

## Part 2 — The agent (on each child's computer)

The agent is a small app that runs quietly as your child's normal user account (it needs no
administrator rights). You'll need your **Backend URL** (the one ending in `/exec`) and your
**shared key** from Part 1. Installing opens a simple form in your web browser.

**Download it** from the releases page — pick the file for that computer:

➡️ **[Download Ludex](https://github.com/avanwouwe/ludex/releases/latest)**

| Computer | File to download |
|----------|------------------|
| Mac (Apple chip) | `ludex-macos-arm64.zip` |
| Linux (64-bit) | `ludex-linux-x86_64.tar.gz` |
| Windows | *not supported yet* |

> Tip: after unpacking, move the `ludex` file somewhere it can stay (e.g. your Applications or home
> folder). The background service points at wherever it was when you installed — if you move or
> delete it later, just run the installer again.

### macOS

1. Double-click the downloaded `.zip` to unpack it — you get a file called `ludex`.
2. **Right-click (or Control-click) `ludex` ▸ Open**, then click **Open** in the warning box. (macOS
   warns because the app isn't from the App Store; this is expected. You only do this once.)
3. A Terminal window opens and the **installer appears in your web browser**. Paste your Backend URL
   and shared key, then click **Install**.

When the first warning pops up later, macOS may ask you to allow notifications — say yes, so your
child actually sees them.

### Linux

1. Extract the `.tar.gz` (double-click, or `tar xzf ludex-linux-x86_64.tar.gz`).
2. Run it: `./ludex` (from a terminal, or "Run" from your file manager). The **installer opens in
   your browser** — enter your Backend URL and shared key and click **Install**.

For the on-screen warnings to appear, the computer needs the standard notification helper. On
Debian/Ubuntu: `sudo apt install libnotify-bin`. (Most desktops already have it.)

### Afterwards

- **Change the shared key or URL:** run the installer again (open `ludex`, or `./ludex install`).
- **Remove Ludex from a computer:** `./ludex uninstall` in a terminal.

---

## Part 3 — Using it day to day

All from the **Ludex** menu in your Sheet:

- **Define what to watch.** On the child's computer, run `ludex detect-app`: it lists what's running,
  you pick one (say, a game), and it adds it as an "activity" (you'll enter your admin password).
- **See the time spent.** Click **Ludex ▸ Refresh dashboard** to see minutes per day, per child, per
  activity.
- **Set limits.** In the `activity_types` tab, an activity can carry limits (a daily maximum, a
  required break). When a limit is hit, your child gets an on-screen warning.
- **Take action.** Click **Ludex ▸ Send a command…** to send a message to a computer, stop an
  activity, or shut it down. **Ludex never stops anything by itself** — it warns; you decide.

---

## Good to know

- **Transparency, not spying.** Ludex only tracks the activities *you* define, and only how much
  time they take. It does not read messages, capture the screen, or log keystrokes.
- **You're in control of the data.** It's your Sheet. You can edit or delete anything in it.
- **It's a cooperation tool, not a cage.** A determined, tech-savvy teenager could stop the agent —
  Ludex is built to make screen time *visible and discussable*, not to be unbeatable.

For the technical details, see [`SETUP.md`](../backend/SETUP.md) and
[`architecture.md`](architecture.md).
