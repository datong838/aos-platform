from aos_api.aip_capability_data_deps import DATA_ASSET_TYPE, data_ref_for, dataset_id_for


def test_dataset_id_and_ref_shape() -> None:
    assert dataset_id_for("strategy.plan") == "ecommerce.shared.evalset.strategy.plan"
    ref = data_ref_for("ecommerce.shared.evalset.strategy.plan", 1, "a" * 64)
    assert ref.asset_type == DATA_ASSET_TYPE
    assert ref.revision == 1
    assert len(ref.content_hash) == 64
