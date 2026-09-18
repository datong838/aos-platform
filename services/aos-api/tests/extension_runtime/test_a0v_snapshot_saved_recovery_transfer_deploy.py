"""a0v084 deployment is fixed to one backed-up isolated migration."""
from pathlib import Path


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_snapshot_saved_recovery_transfer_deploy.py'


def test_deploy_is_exact_backed_up_and_data_preserving():
    source=PATH.read_text(encoding='utf-8')
    assert "SOURCE,TARGET='a0v_083','a0v_084'" in source
    assert "'pg_dump'" in source and "'--snapshot'" in source
    assert "if after!=before" in source
    assert "command.upgrade(cfg,TARGET)" in source
    assert "'businessWrites':0,'sourceReads':0" in source
