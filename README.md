# Happybin Auto

> **Legal notice** — This is an independent, unofficial project and is not affiliated with, endorsed by, or sponsored by NAVER or Happybean. Use it only with accounts and destinations you are authorized to access, and in compliance with applicable laws, [NAVER's Terms of Service](https://policy.naver.com/policy/service.html), and relevant service and community policies. You are responsible for actions performed through your account. The software is provided **as is**, without warranties to the extent permitted by applicable law. Successful collection, continued service access, and protection from account restrictions are not guaranteed. Third-party names and marks belong to their respective owners.

**A Windows desktop tool for automating NAVER Happybean collection workflows with Python and Playwright.**

Start a guided workflow from a desktop interface or the command line, sign in through the browser, and reuse a local browser profile between sessions.

[Getting started](#getting-started) · [Configuration](#configuration) · [Usage](#usage) · [Privacy](#privacy-and-local-data) · [Limitations](#known-limitations)

## Overview

- **Desktop and CLI modes** — Start, stop, and monitor the workflow through a Windows interface, or launch it from a terminal.
- **Browser-based sign-in** — Use QR login or sign in manually in the browser. Account passwords are not configured in the source code.
- **Persistent sessions** — Reuse a local Chromium profile and a session backup when available.
- **Collection workflows** — Attempt blog publishing, optional cafe posting, banner interactions, and Happybean collection, with progress and result reporting.
- **Configurable destinations** — Set the cafe destination through environment variables rather than committed account-specific settings.

The application interface and most runtime messages are currently in Korean.

> **Before running:** This application can publish real blog and cafe posts. Review the account, destination, and generated content in [`content/templates.py`](content/templates.py) first. A collection result is an automation observation, not a guarantee that a reward was credited.

## Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows with an interactive desktop session |
| Python | Python 3.10 or later |
| Browser | Playwright-managed Chromium, installed separately below |
| Account | A NAVER account you are authorized to use |
| Cafe access | Membership and posting permission for the configured cafe, if enabled |

Full automation depends on Windows display APIs. Linux and macOS are not supported for the complete workflow. This repository provides source code; it does not include a packaged executable or an executable build script.

## Getting started

Open **PowerShell** and clone the repository:

```powershell
git clone https://github.com/thsqaz123-dot/happybin_auto_public.git
cd happybin_auto_public
```

Create an isolated environment and install the dependencies and browser:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:PLAYWRIGHT_BROWSERS_PATH = "0"
.\.venv\Scripts\python.exe -m playwright install chromium
```

`PLAYWRIGHT_BROWSERS_PATH=0` installs Chromium where the application's default browser lookup expects it. If you choose another browser directory, use the same value during installation and execution.

Check the available options, then launch the desktop interface:

```powershell
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe main.py
```

Follow the browser prompts to sign in. Keep the browser open and avoid interacting with its tabs while automation is running.

## Configuration

Cafe automation is optional. Set **both** variables in the same PowerShell session before launching the application:

```powershell
# Replace these examples with a cafe you are authorized to use.
$env:HAPPYBIN_CAFE_ID = "12345678"
$env:HAPPYBIN_CAFE_URL = "https://cafe.naver.com/your-cafe"

.\.venv\Scripts\python.exe main.py
```

| Variable | Expected value | Default behavior |
| --- | --- | --- |
| `HAPPYBIN_CAFE_ID` | A positive numeric cafe ID matching the destination | Defaults to `0`; cafe posting is disabled |
| `HAPPYBIN_CAFE_URL` | The corresponding NAVER cafe URL | Defaults to an empty value; cafe posting is disabled |
| `PLAYWRIGHT_BROWSERS_PATH` | `0`, or a custom browser installation directory | The login module defaults to `0` if unset |

With either cafe setting missing, cafe posting and cafe main-page banner scanning are skipped. Other workflow stages remain enabled. A nonnumeric cafe ID causes a configuration error at startup.

The application does **not** automatically load `.env` files. These PowerShell assignments apply to the current terminal session and processes launched from it.

## Usage

Use the virtual environment's Python executable for every command:

| Command | Action |
| --- | --- |
| `main.py` | Open the desktop interface |
| `main.py --cli` | Run the automation workflow in the terminal |
| `main.py --cli --user example-user` | Run with a named local data profile |
| `main.py --status` | Display the local session-backup status |
| `main.py --list-users` | List locally registered profiles |
| `main.py --reset-login` | Delete the selected profile's session backup and browser data |
| `main.py --help` | Show all available options |

For example:

```powershell
.\.venv\Scripts\python.exe main.py --cli
.\.venv\Scripts\python.exe main.py --status
```

`--user` selects a **local data profile**, not a NAVER login ID. The signed-in account is determined by the browser session. Without `--user`, commands use the current operating-system username; the desktop interface also uses that username.

`--reset-login` removes local login data. It does not delete published posts or revoke every session associated with the NAVER account.

## Privacy and local data

User data is stored outside the source directory:

```text
%LOCALAPPDATA%/HappyBeanAuto/<profile>/
├── browser/          # Persistent Chromium profile
├── session.json      # Browser storage-state backup, including cookies
└── user_config.json  # Local profile settings
```

If `LOCALAPPDATA` is unavailable, the fallback root is `~/AppData/Local/HappyBeanAuto/`. A legacy `user_data/` directory can be migrated on first use when the new data root does not yet exist.

Session backups are **not encrypted by this application**. Protect the data directory with operating-system permissions, especially on shared computers. Browser profiles and cookies can carry account access and should be treated as sensitive.

Do not commit or upload session files, browser profiles, `.env` files, authenticated page captures, or unredacted logs. Ignore rules cover common local artifacts, but they do not sanitize files already tracked by Git. Review logs and screenshots before sharing them in an issue.

## Known limitations

- **Blog privacy is not guaranteed.** The workflow attempts private publication but does not verify that the private setting was successfully applied before publishing. Do not use sensitive post content.
- **Cafe posting creates real content.** Check membership, posting permissions, destination settings, and community rules before enabling it.
- **Third-party pages change.** NAVER interface changes, authentication challenges, network conditions, and campaign availability can interrupt the workflow or affect result detection.
- **Reward detection is approximate.** Browser navigation and page text are used as signals; verify actual rewards through NAVER when needed.
- **Source availability is not a security guarantee.** Dependency compatibility and secret-pattern checks do not establish that every runtime path or future dependency version is safe.

## Project structure

```text
main.py               CLI entry point and desktop launcher
automation.py         Shared workflow orchestration
ui.py                 Windows desktop interface
config.py             Environment-based cafe settings and timing
content/templates.py  Generated post titles and bodies
modules/
├── login.py           Browser lifecycle and sign-in
├── session_manager.py Session backup and login-state checks
├── user_manager.py    Local profile settings and data management
├── paths.py           Application and user-data paths
├── blog.py            Blog publishing workflow
├── cafe.py            Cafe posting workflow
├── bean_banner.py     Banner discovery and interaction
├── happybean.py       Happybean collection workflow
├── kin.py             Standalone Knowledge iN banner helper
└── utils.py           Navigation and Windows display helpers
```

## Development and contributions

Read [`AGENTS.md`](AGENTS.md) for repository conventions. Keep changes focused and describe what you verified when opening a pull request. Use placeholders for accounts and destinations in examples.

`test_auto.py`, `test_blog_cafe.py`, `verify_blog.py`, `verify_cafe.py`, and `check_banners.py` are **manual integration tools**. They can open authenticated browser sessions and publish real posts. They are not isolated unit tests and should not be run unattended against a personal or production account.

A basic syntax check that does not execute the workflows is:

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py automation.py ui.py config.py modules content
```

## License

No license has been designated for this repository. This README does not grant an additional license to the project or to third-party software. Dependencies and third-party assets remain subject to their own licenses and terms.
