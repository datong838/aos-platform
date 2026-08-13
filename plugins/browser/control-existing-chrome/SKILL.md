---
name: control-existing-chrome
description: macOS-only workflow for safely reusing and controlling a user's already-open, already-signed-in ordinary Chrome session without requiring a Chrome extension, through macOS visual control, Computer Use, or Accessibility. Use on macOS when a task depends on the user's existing tabs, account login, or normal Chrome session; when an independently launched automation browser is blocked or incompatible; or when the user explicitly asks to operate their logged-in browser. Windows and Linux are not supported by this skill. Do not use it to bypass security challenges, CAPTCHAs, browser warnings, or authentication controls.
---

# Control Existing Chrome

## Platform boundary

This skill currently supports macOS only.

- Supported: ordinary Google Chrome running in the user's current macOS desktop session.
- Required control surface: macOS Computer Use, Accessibility, or an equivalent supported macOS visual-control capability.
- Not supported: Windows, Windows UI Automation, Linux, remote desktop sessions without a supported macOS visual-control surface, or background control of a browser that is not visible in the active macOS session.
- Not claimed: cross-platform compatibility merely because Chrome itself is cross-platform.

On Windows or Linux, stop before operating the browser and report that this skill has no implemented or validated control path for that platform. Do not reinterpret the macOS instructions as Windows or Linux support. A future cross-platform version requires a separate implementation and platform-specific validation.

## Core capability

The primary capability is to reuse the ordinary Chrome browser that the user has already opened and signed in to.

- No Chrome extension is required.
- Do not launch a separate automated Chrome when the task depends on the existing login.
- Do not ask the user to sign in again when the target tab is already authenticated.
- Do not read, export, or copy cookies, tokens, passwords, or the Chrome profile.
- Operate the visible existing Chrome window through macOS visual control, Computer Use, Accessibility, or an equivalent supported macOS system-level surface.

An extension connection or CDP endpoint may be used when already available and authorized, but neither is a prerequisite for this skill.

## Select this surface

Use this decision order:

1. Confirm the host operating system is macOS. If it is Windows or Linux, stop and report that the current skill does not support that platform.
2. Use supported macOS visual control, Computer Use, or Accessibility to operate the running ordinary Chrome app directly. This path requires no Chrome extension and preserves the user's existing login and tabs.
3. If the macOS host already exposes a native Chrome connection, it may be used as an optional semantic control surface; do not require the user to install an extension for this workflow.
4. Use CDP Bridge only on the supported macOS host when the user has explicitly launched that Chrome with remote debugging enabled and authorized the connection. CDP being cross-platform does not make this skill cross-platform.
5. If none is available, stop and tell the user what connection is missing. Do not silently launch a different automated browser when the task requires the existing login.

Use Kitewright instead for isolated local testing, batch E2E, console/network capture, deterministic screenshots, or a disposable browser profile.

## Core workflow

1. Read current tabs and visible page state without changing anything.
2. Confirm the intended site, account context, target record, and requested mutation.
3. Keep one browser task on one Chrome window/profile. Avoid concurrent writers to the same tab.
4. Before typing or clicking, refresh the accessibility/visual state and derive fresh element references.
5. Prefer semantic element actions. Use screenshot coordinates only when accessibility data is incomplete.
6. After every state-changing action, reread the page and verify the expected visible result.
7. For publishing, distinguish editor confirmation from platform review. Verify the authoritative management/list page.
8. Leave the user's unrelated tabs and windows unchanged.

## Safety boundaries

- Never inspect, export, copy, or log cookies, passwords, tokens, Local Storage, saved cards, or profile files.
- Never copy the user's Chrome profile into an automation profile.
- Never suppress or spoof `navigator.webdriver`, fingerprint signals, CAPTCHA, risk verification, browser warnings, or access controls.
- Stop on CAPTCHA, unexpected login, account-risk prompts, permission prompts, or ambiguous targets.
- Require user authorization before publishing, sending, deleting, purchasing, or changing account/security settings according to the active tool policy.
- Do not claim that using ordinary Chrome guarantees acceptance by a website. It only reuses the user's genuine session and browser surface.

## Text editor discipline

Rich-text and split Markdown editors can desynchronize their source and preview panes.

1. Record the title and expected source length before replacement.
2. Replace content using the editor's set-value/semantic input method when it supports Unicode.
3. If keyboard simulation corrupts non-ASCII text, stop, clear to a short marker, and retry with a Unicode-safe value setter.
4. Verify title, first paragraph, last paragraph, character count, preview, and absence of old-content markers.
5. Do not press the final publish/update button until all checks agree.

## Strong-risk site fallback

If an isolated automation browser reaches `Please wait...`, a security challenge, CAPTCHA, or risk verification:

1. Do not attempt evasion.
2. Record the visible symptom and relevant read-only browser facts.
3. Close or stop the isolated automation task.
4. Reuse the user's already-open ordinary Chrome only if the user authorized that site and the control surface is supported.
5. If ordinary Chrome is not already authenticated, ask the user to sign in manually.

## Detailed reference

Read [references/普通Chrome可视化控制与掘金发布实践.md](references/普通Chrome可视化控制与掘金发布实践.md) when handling a publishing site, recovering a corrupted editor, choosing between Kitewright and ordinary Chrome, or explaining evidence from the Juejin case.
