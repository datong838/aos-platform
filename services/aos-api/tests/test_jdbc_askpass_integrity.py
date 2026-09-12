from pathlib import Path
import subprocess
from unittest.mock import MagicMock

from aos_api import jdbc_connector_runtime as module


def test_password_helper_preserves_literal_and_checks_host(monkeypatch, tmp_path):
    marker = tmp_path / "must-not-exist"
    password = "literal'; printf bad > " + str(marker) + "; printf 'tail$(id)\\n"
    process = MagicMock()
    launch = MagicMock(return_value=process)
    monkeypatch.setattr(module.subprocess, "Popen", launch)
    monkeypatch.setattr(module.SshTunnel, "_wait_ready", lambda self: self._local_port)
    tunnel = module.SshTunnel(ssh_host="fixture.invalid", ssh_port=22, ssh_user="fixture",
                              remote_host="127.0.0.1", remote_port=3306, ssh_password=password)
    tunnel._local_port = 23456
    tunnel._open_with_password()
    helper = Path(tunnel._askpass_file)
    try:
        assert helper.stat().st_mode & 0o777 == 0o700
        monkeypatch.undo()
        output = subprocess.run([str(helper)], capture_output=True, check=True)
        assert output.stdout == (password + "\n").encode()
        assert not marker.exists()
        assert "StrictHostKeyChecking=yes" in launch.call_args.args[0]
        assert password not in repr(launch.call_args)
    finally:
        tunnel.close()
    assert not helper.exists()
