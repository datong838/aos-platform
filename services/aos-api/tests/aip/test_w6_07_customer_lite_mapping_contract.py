from pathlib import Path

import yaml

from aos_api.ec_source_adapter import _PUBLIC_FIELDS_BY_TABLE


def test_p08_mapping_matches_runtime_allowlist_and_customer_lite_v2():
    root = Path(__file__).parents[4]
    manifest = yaml.safe_load((root / "bundles/platforms/ecommerce-niushop/content/mappings/p08-customer-lite.yaml").read_text())
    assert manifest["customer_lite_schema_version"] == 2
    assert set(manifest["public_source_allowlist"]) == set(_PUBLIC_FIELDS_BY_TABLE["ns_member"])
    mappings = {(item["source"], item["target"]) for item in manifest["field_mappings"]}
    assert mappings == {("member_id", "id"), ("member_level", "memberLevel"), ("reg_time", "createdAt"), ("last_visit_time", "updatedAt"), ("status", "status")}
    serialized = str(manifest["field_mappings"]).lower()
    for forbidden in ("mobile", "email", "nickname", "avatar", "realname", "address", "openid", "password"):
        assert forbidden not in serialized
