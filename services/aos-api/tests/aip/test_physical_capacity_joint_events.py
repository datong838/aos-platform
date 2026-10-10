from dataclasses import replace
import pytest
from aos_api.aip_physical_capacity_joint_catalog import ForeignKey,Trigger,JointCatalogRejected
from aos_api.aip_physical_capacity_joint_events import (TableEvent,ForeignKeyAction,EventTrigger,EventEffect,EventCatalog,joint_event_closure)
H='a'*64

def base(update='NO ACTION',delete='NO ACTION'):
    return EventCatalog(frozenset({'s.parent','s.child','s.result'}),(ForeignKeyAction(ForeignKey('s.child.fk','s.child','s.parent'),update,delete),),())

def test_fk_check_read_lock_does_not_fire_parent_business_trigger():
    c=base();c=replace(c,triggers=(EventTrigger(Trigger('s.parent.side_effect','s.parent','s.fn()',H),frozenset({'INSERT','UPDATE','DELETE'})),))
    r=joint_event_closure(c,frozenset({TableEvent('s.child','INSERT')}),())
    assert r.events==(TableEvent('s.child','INSERT'),) and r.read_locks==('s.parent',) and r.triggers==() and not r.execution_allowed

@pytest.mark.parametrize('op',['UPDATE','DELETE'])
def test_parent_noaction_reads_child_without_new_events(op):
    r=joint_event_closure(base(),frozenset({TableEvent('s.parent',op)}),())
    assert r.events==(TableEvent('s.parent',op),) and r.read_locks==('s.child',)

@pytest.mark.parametrize('action,op,childop',[('CASCADE','DELETE','DELETE'),('CASCADE','UPDATE','UPDATE'),('SET NULL','DELETE','UPDATE'),('SET DEFAULT','UPDATE','UPDATE')])
def test_fk_writes_generate_followup_trigger_events(action,op,childop):
    c=base(action,action);c=replace(c,triggers=(EventTrigger(Trigger('s.child.effect','s.child','s.fn()',H),frozenset({childop})),))
    e=(EventEffect('s.fn()',H,frozenset({TableEvent('s.result','INSERT')})),)
    r=joint_event_closure(c,frozenset({TableEvent('s.parent',op)}),e)
    assert TableEvent('s.child',childop) in r.events and TableEvent('s.result','INSERT') in r.events and r.triggers==('s.child.effect',)

def test_operation_filtered_effect_and_cycle_are_stable():
    c=base();c=replace(c,triggers=(EventTrigger(Trigger('s.child.effect','s.child','s.fn()',H),frozenset({'INSERT'})),))
    e=(EventEffect('s.fn()',H,frozenset({TableEvent('s.child','INSERT')})),)
    assert joint_event_closure(c,frozenset({TableEvent('s.child','INSERT')}),e).events==(TableEvent('s.child','INSERT'),)
    assert joint_event_closure(c,frozenset({TableEvent('s.child','DELETE')}),()).triggers==()

@pytest.mark.parametrize('case',['missing','drift','disabled','bad_action','unknown_seed','unknown_effect','bad_op','duplicate_fk','duplicate_trigger','duplicate_effect','truncate'])
def test_bad_catalog_or_effect_rejected(case):
    t=EventTrigger(Trigger('s.child.effect','s.child','s.fn()',H),frozenset({'INSERT'}));c=replace(base(),triggers=(t,));e=(EventEffect('s.fn()',H,frozenset()),);seed=frozenset({TableEvent('s.child','INSERT')})
    if case=='missing':e=()
    elif case=='drift':e=(replace(e[0],body_hash='b'*64),)
    elif case=='disabled':c=replace(c,triggers=(replace(t,trigger=replace(t.trigger,enabled=False)),))
    elif case=='bad_action':c=replace(c,foreign_keys=(replace(c.foreign_keys[0],on_update='GUESS'),))
    elif case=='unknown_seed':seed=frozenset({TableEvent('s.unknown','INSERT')})
    elif case=='unknown_effect':e=(replace(e[0],writes=frozenset({TableEvent('s.unknown','INSERT')})),)
    elif case=='bad_op':seed=frozenset({TableEvent('s.child','MERGE')})
    elif case=='duplicate_fk':c=replace(c,foreign_keys=c.foreign_keys+c.foreign_keys)
    elif case=='duplicate_trigger':c=replace(c,triggers=(t,t))
    elif case=='duplicate_effect':e=e+e
    elif case=='truncate':seed=frozenset({TableEvent('s.parent','TRUNCATE')})
    with pytest.raises(JointCatalogRejected):joint_event_closure(c,seed,e)
