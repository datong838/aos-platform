"""The configure gate requires the original held PreparedJob and exact staged ref."""

import pytest

import a0v_w5c3l_natural_configure as wave


@pytest.mark.parametrize("broken", ["released", "observed", "missing"])
def test_configure_rejects_lost_resource(broken):
    resources = [{"cleanup_state": "pending", "observed_release": False}
                 for _ in range(3)]
    assert wave._held(resources)
    if broken == "released":
        resources[0]["cleanup_state"] = "released"
    elif broken == "observed":
        resources[0]["observed_release"] = True
    else:
        resources.pop()
    assert not wave._held(resources)
