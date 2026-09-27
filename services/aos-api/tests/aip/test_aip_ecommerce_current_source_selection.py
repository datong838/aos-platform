"""Current definitions must never be stitched together with legacy rows."""
from types import SimpleNamespace

import pytest

from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller, AipEcommerceCatalogInvalid
from aos_api.aip_solution_pack_publisher import (
    AGENT_LOGIC_COUNTS, CAPABILITY_IDS, CURRENT_SIGNED_CANDIDATE_VERSION, LOGIC_IDS,
)


class FakeRegistry:
    def __init__(self, attr, rows):
        self.attr = attr
        self.rows = rows

    def _list(self, **kwargs):
        return self.rows.get(kwargs["source_revision"], [])

    list_templates = _list
    list_skills = _list
    list_capabilities = _list


def _rows():
    return (
        [SimpleNamespace(template_id=value, revision=1) for value in AGENT_LOGIC_COUNTS],
        [SimpleNamespace(skill_id=f"ecommerce.skill.{value}", revision=1, publication_tenant=None) for value in LOGIC_IDS],
        [SimpleNamespace(capability_id=value, revision=1) for value in CAPABILITY_IDS],
    )


def _installer(current=((), (), ()), legacy=((), (), ())):
    revisions = ("1.2.0", CURRENT_SIGNED_CANDIDATE_VERSION)
    stores = [
        FakeRegistry(key, {revisions[0]: legacy[index], revisions[1]: current[index]})
        for index, key in enumerate(("templates", "skills", "capabilities"))
    ]
    return AipEcommerceAgentInstaller(agents=stores[0], skills=stores[1], capabilities=stores[2])


def test_current_complete_source_is_selected_without_legacy_mix():
    current = _rows()
    templates, skills, capabilities = _installer(current=current, legacy=_rows())._definitions(
        SimpleNamespace(org_id="org-org", project_id="dev-project"),
    )
    assert (len(templates), len(skills), len(capabilities)) == (6, 37, 10)
    assert templates["ecommerce.data_advisor"] is current[0][0]


def test_legacy_complete_source_remains_available_when_current_is_empty():
    templates, skills, capabilities = _installer(legacy=_rows())._definitions(
        SimpleNamespace(org_id="org-org", project_id="dev-project"),
    )
    assert (len(templates), len(skills), len(capabilities)) == (6, 37, 10)


def test_partial_current_source_blocks_even_if_legacy_is_complete():
    current = _rows()
    with pytest.raises(AipEcommerceCatalogInvalid, match="current ecommerce definition source is incomplete"):
        _installer(current=(current[0][:1], (), ()), legacy=_rows())._definitions(
            SimpleNamespace(org_id="org-org", project_id="dev-project"),
        )
