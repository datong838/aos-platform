from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver


def test_cleanup_facade_exposes_no_creation_or_execution_surface():
    driver = OciDriver(context="colima-aos-extension")
    calls = []
    driver.require_isolation = lambda: calls.append("isolation")
    driver.remove_owned = lambda name, owner, expected_container_id=None: calls.append(
        (name, owner, expected_container_id)
    ) or True
    cleanup = CleanupOnlyOciDriver(driver)
    assert cleanup.context == "colima-aos-extension"
    for forbidden in ("create_registration", "create_session", "start_command", "registration_command", "_run"):
        assert not hasattr(cleanup, forbidden)
    assert calls == []
    cleanup.require_isolation()
    assert cleanup.remove_owned("aos-ext-one", "owner", expected_container_id="a" * 64)
    assert calls == ["isolation", ("aos-ext-one", "owner", "a" * 64)]
