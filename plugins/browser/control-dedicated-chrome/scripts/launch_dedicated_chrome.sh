#!/bin/zsh

set -euo pipefail

readonly chrome_app="/Applications/Google Chrome.app"
readonly start_url="${1:-about:blank}"
readonly dedicated_profile_root="${2:-${HOME}/Library/Application Support/AOS Dedicated Chrome}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "control-dedicated-chrome only supports macOS."
  exit 2
fi

if [[ ! -d "${chrome_app}" ]]; then
  print -u2 "Google Chrome was not found at ${chrome_app}."
  exit 3
fi

case "${dedicated_profile_root}" in
  "${HOME}/Library/Application Support/Google/Chrome"|\
  "${HOME}/Library/Application Support/Google/Chrome/"*)
    print -u2 "Refusing to use the user's normal Google Chrome data directory."
    exit 4
    ;;
esac

case "${start_url}" in
  about:*|http://*|https://*) ;;
  *)
    print -u2 "Start URL must use about:, http://, or https://."
    exit 5
    ;;
esac

mkdir -p "${dedicated_profile_root}"

open -na "${chrome_app}" --args \
  "--user-data-dir=${dedicated_profile_root}" \
  --no-first-run \
  --no-default-browser-check \
  "${start_url}"

print "Dedicated Chrome launch requested."
print "Profile: ${dedicated_profile_root}"
print "URL: ${start_url}"
