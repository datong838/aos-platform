---
name: control-dedicated-chrome
description: macOS-only workflow for launching and controlling a dedicated ordinary Google Chrome with its own persistent user-data directory, without a Chrome extension and without copying the user's main Chrome profile or credentials. Use when the user wants a reusable signed-in browser for publishing or operations while keeping daily Chrome tabs, accounts, and site state separate. First login must be completed manually by the user. Windows and Linux are not supported.
---

# Control Dedicated Chrome

## Purpose

Launch a visible ordinary Google Chrome on macOS with a dedicated persistent profile. This separates its accounts, tabs, history, extensions, and site sessions from the user's daily Chrome profile.

Use this skill when the browser task should not modify the user's daily Chrome tabs or account context. Use `control-existing-chrome` instead when the task must reuse a Chrome window that is already running and authenticated.

## Platform and interaction boundary

- Supported operating system: macOS only.
- Supported browser: `/Applications/Google Chrome.app`.
- No Chrome extension is required.
- The browser is visible and user-controllable; this is not a headless or hidden browser.
- Visual control can still activate the dedicated window and temporarily use keyboard or mouse focus. Profile isolation reduces interference but does not guarantee background, focus-free automation.
- Windows, Linux, remote hosts without a supported macOS visual surface, and fully unattended login are not supported.
- Multiple Chrome processes can expose the same macOS bundle identifier. Before any automated page mutation, the control tool must prove it can distinguish the dedicated process/window from the user's daily Chrome. If it cannot, stop; never guess based only on the app name `Google Chrome` or bundle ID `com.google.Chrome`.

## Profile contract

The default profile root is:

```text
~/Library/Application Support/AOS Dedicated Chrome
```

Rules:

1. Keep this profile outside the Git repository.
2. Never copy the user's main Chrome profile, cookies, tokens, password database, Local Storage, or Keychain entries into it.
3. On first use, the user manually signs in inside the dedicated Chrome window.
4. Never type, inspect, capture, log, or store the user's password, verification code, recovery code, or passkey interaction.
5. Later runs may reuse the login state that Chrome itself persisted in this dedicated profile.
6. Do not delete or reset the profile unless the user explicitly requests it and understands that the dedicated login state will be removed.

## Launch workflow

1. Confirm the host is macOS and Google Chrome is installed at the supported path.
2. Confirm the desired URL. Use a public neutral page when no destination is specified.
3. Run:

```bash
plugins/browser/control-dedicated-chrome/scripts/launch_dedicated_chrome.sh "https://example.com"
```

4. Confirm a separate visible Chrome window opened with the dedicated profile.
5. If the site requires authentication, hand control to the user for all credential, passkey, CAPTCHA, and verification-code steps.
6. After the user says login is complete, read only the visible page title, URL, and signed-in UI state needed to verify success. Do not inspect authentication storage.
7. Before later page operations, verify that the selected window belongs to the dedicated Profile. If macOS Computer Use or Accessibility merges it with the daily Chrome under the same bundle ID, report that control selection is not validated and stop.
8. Only after target-window identity is unambiguous, use macOS Computer Use or Accessibility and reread the visible state after each mutation.

An optional second argument can override the profile root for a separately named task profile:

```bash
plugins/browser/control-dedicated-chrome/scripts/launch_dedicated_chrome.sh \
  "https://example.com" \
  "$HOME/Library/Application Support/AOS Dedicated Chrome - Publishing"
```

Do not use a path inside the user's normal Google Chrome data directory.

## Login acceptance test

The first-use test passes only when all conditions hold:

1. The dedicated Chrome window launched successfully.
2. Its profile root is the intended dedicated path, not the user's main Chrome profile.
3. The user manually completed login.
4. The visible destination page shows the expected signed-in state.
5. No credential or authentication storage was read, copied, or logged.

Login success proves only that the dedicated persistent profile works. It does not prove that publishing, site review, risk controls, or every later operation will succeed.

User confirmation that manual login completed is sufficient for the first-login acceptance requested by the user. It is not sufficient evidence that an automation surface can safely distinguish and control the dedicated Chrome process.

## Safety boundaries

- Stop and hand off on password entry, passkeys, CAPTCHA, verification codes, account-risk prompts, or browser security warnings.
- Never suppress or spoof `navigator.webdriver`, fingerprint signals, challenges, or access controls.
- Do not claim the dedicated ordinary Chrome is undetectable or guaranteed to pass site controls.
- Require the appropriate user authorization before publishing, deleting, sending, purchasing, or changing account settings.
- Do not operate the user's daily Chrome window when the dedicated window is the requested target.
