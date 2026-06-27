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
   - a **shared key** — like a long password; every computer you monitor will use it. Make it long
     and hard to guess.
   - an **admin password** — used when you add new activities or clean up data.
   
   Write both down somewhere safe.
4. Click **Ludex ▸ ③ How to deploy the backend** and follow the five steps it shows. At the end you
   copy a **web address ending in `/exec`** — this is your backend's address. Keep it with your
   shared key.

That's the database done. The **Ludex** menu is also where you'll manage things day to day (see
Part 3).

---

## Part 2 — The agent (on each child's computer)

The agent is a small app that runs quietly as your child's normal user account (it needs no
administrator rights). You'll need the **backend address** (the `/exec` URL) and your **shared key**
from Part 1.

**Download it** from the releases page — pick the file for that computer:

➡️ **[Download Ludex](https://github.com/avanwouwe/ludex/releases/latest)**

| Computer | File to download |
|----------|------------------|
| Mac (Apple chip) | `ludex-macos-arm64` |
| Linux (64-bit) | `ludex-linux-x86_64` |
| Windows | *not supported yet* |

### macOS

Open the **Terminal** app (Applications ▸ Utilities ▸ Terminal) and run, one line at a time:

```bash
cd ~/Downloads
xattr -dr com.apple.quarantine ludex-macos-*   # clears the "downloaded from internet" flag
chmod +x ludex-macos-*                          # make it runnable
mv ludex-macos-* ludex                          # tidy name
./ludex install                                 # asks for the backend URL + shared key
```

The first time a warning pops up, macOS may ask you to allow notifications/alerts for it — say yes,
so your child actually sees the warnings.

### Linux

Open a terminal and run:

```bash
cd ~/Downloads
chmod +x ludex-linux-x86_64
mv ludex-linux-x86_64 ludex
./ludex install            # asks for the backend URL + shared key
```

For the on-screen warnings to appear, the computer needs the standard notification helper. On
Debian/Ubuntu: `sudo apt install libnotify-bin`. (Most desktops already have it.)

### Afterwards

- **Change the shared key later:** run `./ludex install` again with the new key.
- **Remove Ludex from a computer:** run `./ludex uninstall`.

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
