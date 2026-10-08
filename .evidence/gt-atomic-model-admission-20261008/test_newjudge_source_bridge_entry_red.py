"""Registered missing entry RED. Pure compiler surface, no DB installation."""
import importlib.util
from pathlib import Path

def test_new_judge_source_fact_has_separate_compiler_entry():
    root = Path(__file__).resolve().parents[2]
    path = root / 'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py'
    spec = importlib.util.spec_from_file_location('occupation_authority_red', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old_sql = '\n'.join(module.occupation_eval_fact_statements())
    assert 'public.aip_model_eval_budget_reservation' in old_sql
    assert callable(getattr(module, 'occupation_judge_fact_statements', None)), (
        'new Judge original Source fact compiler absent; old Model fact cannot substitute'
    )
