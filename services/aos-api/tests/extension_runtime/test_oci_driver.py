import pytest

from aos_api.extension_runtime.oci_driver import OciDriver


def test_only_fixed_digest_and_parameters():
    driver = OciDriver(context="colima-aos-extension")
    args = driver.registration_command("sha256:" + "a" * 64, "aos-ext-test", "owner")
    assert "--pull=never" in args
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert "--no-healthcheck" in args
    assert "--privileged" not in args
    assert "--volume" not in args
    for image in ("python:latest", "sha256:" + "A" * 64, "a;sh"):
        with pytest.raises(ValueError):
            driver.registration_command(image, "aos-ext-test", "owner")


def test_untrusted_context_rejected():
    with pytest.raises(ValueError):
        OciDriver(context="unix:///arbitrary.sock")


def test_cleanup_uses_observed_container_id_not_reusable_name(monkeypatch):
    driver=OciDriver(context="colima-aos-extension")
    calls=[]
    def run(*args):
        calls.append(args)
        return "a"*64+" owner" if args[0]=="inspect" else ""
    monkeypatch.setattr(driver,"_run",run)
    assert driver.remove_owned("aos-ext-test","owner")
    assert calls[-1]==("rm","--force","--volumes","a"*64)


def test_image_declared_volume_rejected(monkeypatch):
    import json
    driver = OciDriver(context="colima-aos-extension")
    digest = "sha256:" + "a" * 64
    monkeypatch.setattr(driver, "_run", lambda *args: json.dumps([
        {"Id": digest, "Config": {"Volumes": {"/escape": {}}}}]))
    with pytest.raises(ValueError, match="volumes"):
        driver.create_registration(digest, "aos-ext-test", "owner")


@pytest.mark.parametrize("appears", [True, False])
def test_create_timeout_reconciles_or_retains_reference(monkeypatch, appears):
    import json
    import subprocess
    from aos_api.extension_runtime.oci_driver import CleanupUncertainError
    driver = OciDriver(context="colima-aos-extension")
    digest = "sha256:" + "a" * 64
    monkeypatch.setattr(driver, "_run", lambda *args: json.dumps([{"Id": digest, "Config": {}}]))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 15)
    monkeypatch.setattr("aos_api.extension_runtime.oci_driver.subprocess.run", timeout)
    monkeypatch.setattr("aos_api.extension_runtime.oci_driver.time.sleep", lambda _: None)
    attempts = []
    def reconcile(*args):
        attempts.append(args)
        return appears and len(attempts) == 3
    monkeypatch.setattr(driver, "remove_owned", reconcile)
    if appears:
        with pytest.raises(subprocess.TimeoutExpired):
            driver.create_registration(digest, "aos-ext-test", "owner")
        assert len(attempts) == 3
    else:
        with pytest.raises(CleanupUncertainError) as error:
            driver.create_registration(digest, "aos-ext-test", "owner")
        assert len(attempts) == 10
        assert error.value.cleanup_reference == {"context": driver.context, "name": "aos-ext-test", "owner": "owner"}
