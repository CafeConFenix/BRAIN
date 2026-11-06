# Security policy

BRAIN runs on your own computer and listens on `127.0.0.1` by default. Remote access (phone, outside the home) is optional, goes through Tailscale and is protected by a password.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private "Report a vulnerability" button on the Security tab of this repository, and include:

- what you found and how to reproduce it,
- the BRAIN version (see the top of the web interface or `CHANGELOG.md`),
- whether remote access was enabled.

You will get a first answer within a few days. Fixes are released as patch versions and credited in the changelog unless you prefer otherwise.

## Things worth knowing

- The Home Assistant token is stored locally and is never sent to the web interface.
- Remote access requires a password; set one before enabling it (`CONFIGURE_ACCESS.bat`).
- BRAIN never sends your data to any service by itself: the language model runs locally through Ollama.
