"""Joint end-protocol dependencies; these tests grant no transaction authority."""
from dataclasses import replace
import pytest
from aos_api.aip_physical_capacity_joint_catalog import (
    ForeignKey, Trigger, TriggerEffect, JointCatalog, JointCatalogRejected,
    joint_constraint_closure,
)
H='a'*64

def fixture():
    return JointCatalog(frozenset({'risk.intent','risk.binding','risk.debit','budget.hold','source.head','source.audit'}),
        (ForeignKey('risk.intent.fk','risk.intent','risk.binding'),ForeignKey('risk.binding.fk','risk.binding','risk.debit'),ForeignKey('source.audit.fk','source.audit','source.head')),
        (Trigger('risk.debit.guard','risk.debit','risk.guard()',H),Trigger('budget.hold.guard','budget.hold','budget.guard()',H)))

def effects():
    return (TriggerEffect('risk.guard()',H,frozenset({'budget.hold'})),TriggerEffect('budget.guard()',H,frozenset({'source.head'})))

def test_multihop_reverse_fk_and_trigger_write_fixed_point():
    c=fixture();result=joint_constraint_closure(c,frozenset({'risk.intent'}),effects())
    assert result.relations==tuple(sorted(c.relations))
    assert result.foreign_keys==tuple(sorted(x.key for x in c.foreign_keys))
    assert result.triggers==tuple(sorted(x.key for x in c.triggers))
    assert result.execution_allowed is False and c==fixture()

def test_cycles_and_catalog_order_are_stable():
    c=fixture();e=effects()+(TriggerEffect('unused.fn()',H,frozenset()),)
    c=replace(c,foreign_keys=c.foreign_keys+(ForeignKey('risk.debit.back','risk.debit','risk.intent'),))
    original=joint_constraint_closure(c,frozenset({'risk.intent'}),e)
    reverse=replace(c,foreign_keys=c.foreign_keys[::-1],triggers=c.triggers[::-1])
    assert original==joint_constraint_closure(reverse,frozenset({'risk.intent'}),e[::-1])

@pytest.mark.parametrize('case',['unknown_seed','unknown_fk','unknown_write','missing_effect','hash_drift','disabled','duplicate_fk','duplicate_trigger','duplicate_effect','ambiguous_relation','empty_seed'])
def test_incomplete_or_drifted_installation_rejected(case):
    c=fixture();e=effects();seed=frozenset({'risk.intent'})
    if case=='unknown_seed':seed=frozenset({'risk.unknown'})
    elif case=='unknown_fk':c=replace(c,foreign_keys=c.foreign_keys+(ForeignKey('risk.bad.fk','risk.intent','risk.unknown'),))
    elif case=='unknown_write':e=(replace(e[0],writes=frozenset({'risk.unknown'})),e[1])
    elif case=='missing_effect':e=e[1:]
    elif case=='hash_drift':e=(replace(e[0],body_hash='b'*64),e[1])
    elif case=='disabled':c=replace(c,triggers=(replace(c.triggers[0],enabled=False),c.triggers[1]))
    elif case=='duplicate_fk':c=replace(c,foreign_keys=c.foreign_keys+(c.foreign_keys[0],))
    elif case=='duplicate_trigger':c=replace(c,triggers=c.triggers+(c.triggers[0],))
    elif case=='duplicate_effect':e=e+(e[0],)
    elif case=='ambiguous_relation':c=replace(c,relations=c.relations|{'intent'})
    elif case=='empty_seed':seed=frozenset()
    with pytest.raises(JointCatalogRejected):joint_constraint_closure(c,seed,e)

def test_internal_ri_never_auto_approved():
    c=fixture();c=replace(c,triggers=(replace(c.triggers[0],internal=True),c.triggers[1]))
    with pytest.raises(JointCatalogRejected,match='TRIGGER_EFFECT_REQUIRED'):
        joint_constraint_closure(c,frozenset({'risk.intent'}),())

@pytest.mark.parametrize('value',['','not-a-hash','A'*64])
def test_invalid_function_hash_rejected(value):
    c=fixture();c=replace(c,triggers=(replace(c.triggers[0],body_hash=value),c.triggers[1]))
    with pytest.raises(JointCatalogRejected):joint_constraint_closure(c,frozenset({'risk.intent'}),effects())
