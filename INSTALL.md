# Installing Quakpit 🦆✈️

Quakpit is a little desktop companion: a duck in a plane flies across your screen
a few minutes before each meeting, towing a banner with the meeting name. It reads
your **Google Calendar** and runs quietly in your system tray.

Takes about 2 minutes to set up. **No admin rights needed.**

---

## 1. Install

1. Double-click **`Quakpit-Setup.exe`**.
2. Windows may show a blue **“Windows protected your PC”** box.
   → Click **More info**, then **Run anyway**. *(This is expected — the app is
   internal and not signed by a commercial certificate.)*
3. Follow the installer. Leave **“Start Quakpit automatically when I sign in”**
   checked so it’s always there for you.
4. Quakpit opens its settings window and adds a 🦆 icon to your system tray
   (bottom-right, near the clock — you may need to click the **^** arrow to see it).

## 2. Connect your Google Calendar

1. In the Quakpit window, click **Connect**.
2. Your browser opens. Pick your work Google account.
3. Google shows a screen saying **“Google hasn’t verified this app.”**
   → Click **Advanced**, then **Go to Quakpit (unsafe)**.
   *(This warning is normal for internal company apps. Quakpit only ever **reads**
   your calendar — it can’t edit or delete anything.)*
4. Click **Continue / Allow**.
5. Back in Quakpit it should now say **“Connected as you@company.com.”** ✅

You don’t need to enter any keys or IDs — sign-in is already set up for you.

## 3. Try it

- Click **Send a test flight 🛫** (or press **Ctrl + Shift + D**) — the duck should
  fly across your screen, on top of whatever you’re doing.
- Set how early you want the heads-up under **Lead time** (default: 5 minutes
  before).
- That’s it. Leave it running; it’ll fly automatically before your meetings.

## Good to know

- **Privacy:** Quakpit has no server. Your calendar is read directly from Google on
  your own laptop and kept only in memory. Your sign-in is stored encrypted in the
  Windows Credential Manager. No tracking, no data sent anywhere.
- **It lives in the tray:** closing the window doesn’t quit it. To quit, right-click
  the 🦆 tray icon → **Quit Quakpit**.
- **Multiple monitors:** by default the duck flies on whichever screen your mouse is
  on. Change this under **Show on** in settings.

## Signing out / removing it

- **Sign out:** open Settings and click **Disconnect** — this revokes Quakpit’s
  access at Google, not just on your laptop.
- **Uninstall:** removing Quakpit (Windows *Add or remove programs*) now also
  **revokes and erases your Google connection automatically** — nothing is left
  behind. (Older builds left the sign-in in the Windows Credential Manager, so a
  reinstall reconnected silently; this build cleans up on uninstall.)
- You can always review or revoke access yourself at
  **myaccount.google.com → Security → Your connections to third-party apps**.

## Troubleshooting

| Problem | Fix |
|---|---|
| “Windows protected your PC” | **More info → Run anyway** (see step 1). |
| “Google hasn’t verified this app” | **Advanced → Go to Quakpit (unsafe)** (see step 2). It only reads your calendar. |
| The duck doesn’t fly | Make sure it says *Connected*, send a **test flight**, and check the meeting has a set time (all-day events are skipped). |
| It says “Not connected” again later | Just click **Connect** once more. |
| The app won’t run at all | Your laptop’s security policy may block it — contact IT to allow `Quakpit.exe`. |

## Need help?

Ping **[your name / IT channel here]**.
