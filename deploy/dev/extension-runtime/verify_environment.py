"""Bounded real environment probe; never selects or mutates the shared engine."""
import json
import subprocess

CONTEXT = "colima-aos-extension"
IMAGE = "sha256:e0e8b3cbfed68a90084781e2962f9c0deead51c5a3f11a488eef0283a4284bc2"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30).stdout.strip()


def main():
    before = run("docker", "context", "show")
    info = json.loads(run("docker", "--context", CONTEXT, "info", "--format", "{{json .SecurityOptions}}"))
    assert "name=userns" in info, "dedicated daemon must enable user namespaces"
    script = """set -eu
test "$(id -u)" = 65534
test "$(id -g)" = 65534
awk '$1 == 0 && $2 > 0 && $3 == 65536 {ok=1} END {exit !ok}' /proc/self/uid_map
awk '$1 == 0 && $2 > 0 && $3 == 65536 {ok=1} END {exit !ok}' /proc/self/gid_map
grep -q 'CapEff:.*0000000000000000' /proc/self/status
grep -q 'NoNewPrivs:.*1' /proc/self/status
grep -q 'Seccomp:.*2' /proc/self/status
if touch /aos-probe 2>/dev/null; then exit 21; fi
test ! -S /var/run/docker.sock
test ! -e /Users/ddt
test -z "$(ip route)"
cat /proc/self/uid_map /proc/self/gid_map
echo isolation-probe-pass
"""
    output = run("docker", "--context", CONTEXT, "run", "--rm", "--pull=never",
                 "--name", "aos-ar1b-isolation-probe", "--network", "none", "--read-only",
                 "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt",
                 "no-new-privileges", "--pids-limit", "16", "--memory", "32m",
                 "--cpus", "0.25", "--entrypoint", "/bin/sh", IMAGE, "-c", script)
    assert before == run("docker", "context", "show"), "default context changed"
    print(json.dumps({"context": CONTEXT, "defaultContext": before, "securityOptions": info,
                      "probe": output, "result": "passed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
