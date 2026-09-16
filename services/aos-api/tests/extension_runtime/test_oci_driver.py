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


@pytest.mark.parametrize('message',['Error: No such object: aos-ext-test','error: no such object: aos-ext-test','connection refused'])
def test_missing_resource_is_not_positive_deletion(monkeypatch,message):
    import subprocess
    driver=OciDriver(context='colima-aos-extension')
    def run(*args):raise subprocess.CalledProcessError(1,['docker'],stderr=message)
    monkeypatch.setattr(driver,'_run',run)
    if 'no such' in message.lower():assert driver.remove_owned('aos-ext-test','owner') is False
    else:
        with pytest.raises(subprocess.CalledProcessError):driver.remove_owned('aos-ext-test','owner')


def test_cleanup_uses_observed_container_id_not_reusable_name(monkeypatch):
    driver=OciDriver(context="colima-aos-extension")
    calls=[]
    def run(*args):
        calls.append(args)
        return "a"*64+" owner" if args[0]=="inspect" else ""
    monkeypatch.setattr(driver,"_run",run)
    assert driver.remove_owned("aos-ext-test","owner")
    assert calls[-1]==("rm","--force","--volumes","a"*64)


@pytest.mark.parametrize('expected',['a'*64,'b'*64,'bad'])
def test_recovery_cleanup_compares_persisted_container_id(monkeypatch,expected):
    driver=OciDriver(context='colima-aos-extension')
    calls=[]
    def run(*args):
        calls.append(args)
        return 'a'*64+' owner' if args[0]=='inspect' else ''
    monkeypatch.setattr(driver,'_run',run)
    if expected=='a'*64:
        assert driver.remove_owned('aos-ext-test','owner',expected_container_id=expected)
        assert calls[-1]==('rm','--force','--volumes',expected)
    else:
        with pytest.raises((ValueError,RuntimeError)):
            driver.remove_owned('aos-ext-test','owner',expected_container_id=expected)
        assert not any(call[0]=='rm' for call in calls)


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
def test_persistent_command_is_fixed_and_keeps_isolation():
    from aos_api.extension_runtime.oci_driver import OciDriver
    driver=OciDriver(context="colima-aos-extension")
    image="sha256:"+"a"*64
    ordinary=driver.registration_command(image,"aos-ext-test","test")
    assert driver.session_command(image,"aos-ext-test","test")==ordinary+["--serve"]


@pytest.mark.parametrize('change',['running','owner','name','container'])
def test_rehydration_requires_exact_stopped_owned_container(monkeypatch,change):
    import json
    driver=OciDriver(context='colima-aos-extension')
    container='a'*64
    item={'Id':container,'Name':'/aos-ext-test',
          'Config':{'Labels':{'aos.extension.owner':'owner'}},'State':{'Running':False}}
    if change=='running':item['State']['Running']=True
    if change=='owner':item['Config']['Labels']['aos.extension.owner']='other'
    if change=='name':item['Name']='/aos-ext-other'
    if change=='container':item['Id']='b'*64
    monkeypatch.setattr(driver,'_run',lambda *args:json.dumps([item]))
    with pytest.raises(RuntimeError):
        driver.require_stopped_owned('aos-ext-test','owner',container)


def test_rehydration_accepts_exact_stopped_owned_container(monkeypatch):
    import json
    driver=OciDriver(context='colima-aos-extension')
    container='a'*64
    monkeypatch.setattr(driver,'_run',lambda *args:json.dumps([{'Id':container,
        'Name':'/aos-ext-test','Config':{'Labels':{'aos.extension.owner':'owner'}},
        'State':{'Running':False}}]))
    assert driver.require_stopped_owned('aos-ext-test','owner',container) is None
