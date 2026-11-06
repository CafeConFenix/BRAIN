# Using BRAIN from your phone or another computer

BRAIN lives on your home computer. To open it from your phone (on the couch or while shopping) or from another PC, we use **Tailscale**: a free private network (for personal use) that links your devices as if they were on the same home network.

* No router port is opened: nobody on the internet can see BRAIN.
* The connection is encrypted (HTTPS).
* BRAIN also asks you for a **password** that you choose.
* The home computer has to be **on** and have BRAIN open (if it starts with Windows, just turning on the PC is enough).

## Steps (only once)

1. **Install Tailscale** on the home computer and on your phone: <https://tailscale.com/download>. Sign in to both with the **same account**.
2. In the Tailscale admin panel (<https://login.tailscale.com/admin/dns>) turn on **HTTPS Certificates**. It's a toggle; you only need it the first time.
3. On the home computer, double-click **`CONFIGURAR_ACCESO.bat`**:
   * Type a password of **8 characters or more** (it's hidden as you type).
   * BRAIN publishes its private address and shows it to you, for example `https://my-pc.tail1234.ts.net`.
   * (You can also set or change the password from BRAIN → gear icon → *Access from phone or another PC*, but that button does not turn on Tailscale: use the `.bat` for that.)
4. On your **phone**, with Tailscale turned on, open that address in the browser and sign in with the password.
5. **As an app:** on Chrome (Android) *menu → Install app*; on Safari (iPhone) *Share → Add to Home Screen*. It will have BRAIN's logo and open full screen.

The microphone works from the phone because the connection is HTTPS. (The voice is transcribed on your home PC, not on the phone.)

## What is `pythonw.exe` in Task Manager?

That's BRAIN running (with no black window). It's normal, and it's what lets alerts sound while the window is closed. To close it completely: right-click the BRAIN icon next to the clock → *Quit BRAIN*, or the gear icon in Settings → *Close BRAIN completely*, or `CERRAR_BRAIN.bat`.

## Security

* No password is asked for from the home computer itself; from anywhere else, it is.
* Sessions last 30 days on that device. If you change the password, **every session is closed**.
* After 5 wrong passwords in a row there is a 60-second lockout.
* The password can only be changed from the home computer.
* If you lose your phone: change the password in BRAIN (this logs the phone's session out) and remove the phone from your Tailscale account.
* BRAIN never controls locks, garages or alarms, not even from outside the home.

## If something goes wrong

| Symptom | What to do |
| --- | --- |
| `CONFIGURAR_ACCESO.bat` says Tailscale is missing | Install it (step 1) and try again |
| It says you haven't signed in | Open Tailscale on the PC, sign in with your account and try again |
| Could not publish BRAIN | Turn on *HTTPS Certificates* (step 2) and try again |
| "This page isn't working" / error 502 | Open BRAIN on the PC (desktop icon), wait 10 seconds and run `CONFIGURAR_ACCESO.bat` again: it now checks that BRAIN responds and shows you what Tailscale has published. Always use the `https://...ts.net` address it gives you, **not** the 100.x.x.x IP or `http://` |
| The phone won't load the address | Check that Tailscale is **turned on** on the phone and that the home PC is on |
| "External access not enabled" | The password is missing: set it in step 3 |
| I changed PC or its name | Run `CONFIGURAR_ACCESO.bat` again |

To stop publishing BRAIN: open a command window and type `tailscale serve reset`.
