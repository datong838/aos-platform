"""Narrow trusted-host Docker driver. No bundle-controlled engine arguments."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path


class CleanupUncertainError(RuntimeError):
    """Exact cleanup reference must be retained by the lifecycle journal."""
    def __init__(self, context, name, owner):
        self.cleanup_reference = {"context": context, "name": name, "owner": owner}
        super().__init__("container creation outcome is uncertain; reconciliation required")


class OciDriver:
    def __init__(self, *, context: str):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", context):
            raise ValueError("invalid engine context")
        self.context = context

    def _run(self, *arguments):
        return subprocess.run(["docker", "--context", self.context, *arguments],
                              capture_output=True, check=True, text=True, timeout=15).stdout

    def require_isolation(self):
        info = json.loads(self._run("info", "--format", "{{json .}}"))
        options = info.get("SecurityOptions", [])
        if info.get("OSType") != "linux" or "name=userns" not in options or not any(
                item.startswith("name=seccomp") for item in options):
            raise RuntimeError("engine lacks required userns/seccomp isolation")

    def registration_command(self, image_id: str, name: str, owner: str) -> list[str]:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("only verified image configuration digests are accepted")
        if not re.fullmatch(r"aos-ext-[a-z0-9-]+", name) or not re.fullmatch(r"[a-zA-Z0-9-]+", owner):
            raise ValueError("invalid platform-generated ownership marker")
        return ["docker", "--context", self.context, "create", "--pull=never", "--name", name,
                "--label", "aos.extension.owner=" + owner,
                "--network", "none", "--read-only", "--user", "65534:65534",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--security-opt", "seccomp=" + str(Path(__file__).with_name("internal-python-v1-seccomp.json")),
                "--pids-limit", "64", "--memory", "512m", "--memory-swap", "512m",
                "--cpus", "1", "--ipc", "private", "--log-driver", "none", "--no-healthcheck",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=67108864,mode=1777",
                "--entrypoint", "/usr/local/bin/python3", "-i", image_id,
                "-I", "/aos/runner.py"]

    def create_registration(self, image_id: str, name: str, owner: str) -> str:
        return self._create(image_id, name, owner, persistent=False)

    def session_command(self, image_id: str, name: str, owner: str) -> list[str]:
        return self.registration_command(image_id, name, owner) + ["--serve"]

    def create_session(self, image_id: str, name: str, owner: str) -> str:
        return self._create(image_id, name, owner, persistent=True)

    def _create(self, image_id: str, name: str, owner: str, *, persistent: bool) -> str:
        command = (self.session_command if persistent else self.registration_command)(image_id, name, owner)
        metadata = json.loads(self._run("image", "inspect", image_id))
        if len(metadata) != 1 or metadata[0].get("Id") != image_id:
            raise ValueError("image identity mismatch")
        if metadata[0].get("Config", {}).get("Volumes"):
            raise ValueError("image-declared writable volumes are forbidden")
        try:
            result = subprocess.run(command, capture_output=True, check=True, text=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            # CLI termination does not cancel the daemon's in-flight create.
            for _ in range(10):
                if self.remove_owned(name, owner):
                    raise exc
                time.sleep(.2)
            raise CleanupUncertainError(self.context, name, owner) from exc
        container_id = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise RuntimeError("invalid created container identity")
        return container_id

    def start_command(self, container_id: str) -> list[str]:
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise ValueError("invalid container identity")
        return ["docker", "--context", self.context, "start", "--attach", "--interactive", container_id]

    def require_stopped_owned(self, name: str, owner: str, container_id: str) -> None:
        """Prove an exact persisted container can be attached without replacement."""
        if (not re.fullmatch(r'aos-ext-[a-z0-9-]+',name)
                or not re.fullmatch(r'[a-zA-Z0-9-]+',owner)
                or not re.fullmatch(r'[0-9a-f]{64}',container_id)):
            raise ValueError('invalid persisted container identity')
        metadata=json.loads(self._run('inspect',container_id))
        if len(metadata)!=1:
            raise RuntimeError('persisted container observation differs')
        item=metadata[0]
        labels=item.get('Config',{}).get('Labels') or {}
        if (item.get('Id')!=container_id or item.get('Name')!='/'+name
                or labels.get('aos.extension.owner')!=owner):
            raise RuntimeError('persisted container ownership differs')
        if item.get('State',{}).get('Running') is not False:
            raise RuntimeError('persisted container is not stopped')

    def remove_owned(self, name: str, owner: str, *, expected_container_id: str | None = None) -> bool:
        if expected_container_id is not None and not re.fullmatch(r'[0-9a-f]{64}',expected_container_id):
            raise ValueError('invalid persisted container identity')
        try:
            observation = self._run("inspect", "--format", '{{.Id}} {{index .Config.Labels "aos.extension.owner"}}', name).strip().split()
        except subprocess.CalledProcessError as exc:
            if "no such" in (exc.stderr or '').lower():
                return False
            raise
        if len(observation)!=2 or not re.fullmatch(r"[0-9a-f]{64}",observation[0]) or observation[1] != owner:
            raise RuntimeError("refusing to remove a resource with another owner")
        if expected_container_id is not None and observation[0]!=expected_container_id:
            raise RuntimeError('refusing to remove a different persisted container identity')
        self._run("rm", "--force", "--volumes", observation[0])
        return True

    def confirm_absent(self, name: str, owner: str, *, expected_container_id: str) -> bool:
        """Confirm both persisted identifiers are absent after an unknown cleanup outcome."""
        if (not re.fullmatch(r"aos-ext-[a-z0-9-]+", name)
                or not re.fullmatch(r"[a-zA-Z0-9-]+", owner)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_container_id)):
            raise ValueError("invalid persisted cleanup identity")
        for identifier in (name, expected_container_id):
            try:
                observed = self._run(
                    "inspect", "--format",
                    '{{.Id}} {{index .Config.Labels "aos.extension.owner"}}', identifier,
                ).strip().split()
            except subprocess.CalledProcessError as exc:
                if "no such" in (exc.stderr or "").lower():
                    continue
                raise
            if observed:
                return False
        return True

    def confirm_name_absent(self, name: str, owner: str) -> bool:
        """Name-only absence for claimed create that never recorded a container ID."""
        if (not re.fullmatch(r"aos-ext-[a-z0-9-]+", name)
                or not re.fullmatch(r"[a-zA-Z0-9-]+", owner)):
            raise ValueError("invalid persisted cleanup identity")
        try:
            observed = self._run(
                "inspect", "--format",
                '{{.Id}} {{index .Config.Labels "aos.extension.owner"}}', name,
            ).strip().split()
        except subprocess.CalledProcessError as exc:
            if "no such" in (exc.stderr or "").lower():
                return True
            raise
        return not observed


class CleanupOnlyOciDriver:
    """Composition facade for recovery; intentionally has no create/start surface."""

    def __init__(self, driver: OciDriver):
        if type(driver) is not OciDriver:
            raise TypeError("cleanup facade requires the concrete OCI driver")
        self.__driver = driver

    @property
    def context(self) -> str:
        return self.__driver.context

    def require_isolation(self):
        return self.__driver.require_isolation()

    def remove_owned(self, name: str, owner: str, *, expected_container_id: str | None = None) -> bool:
        return self.__driver.remove_owned(
            name, owner, expected_container_id=expected_container_id
        )

    def confirm_absent(self, name: str, owner: str, *, expected_container_id: str) -> bool:
        return self.__driver.confirm_absent(
            name, owner, expected_container_id=expected_container_id
        )

    def confirm_name_absent(self, name: str, owner: str) -> bool:
        return self.__driver.confirm_name_absent(name, owner)
