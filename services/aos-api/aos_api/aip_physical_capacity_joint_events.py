"""Operation-aware dependency contract for the complete joint end protocol.

Installation-reviewed inputs only: a catalog or effect DTO is not authority.
Possible events and FK read/lock dependencies are distinct. The result is not
an observed database event queue or permission to commit. Owner/ACL/native
binary provenance and effect semantics remain separate installation checks.
"""
from dataclasses import dataclass,field
from aos_api.aip_physical_capacity_joint_catalog import (
    ForeignKey,Trigger,_require,_key,_function,_relation,
)


@dataclass(frozen=True,order=True)
class TableEvent:
    relation: str
    operation: str


@dataclass(frozen=True)
class ForeignKeyAction:
    foreign_key: ForeignKey
    on_update: str
    on_delete: str


@dataclass(frozen=True)
class EventTrigger:
    trigger: Trigger
    operations: frozenset[str]


@dataclass(frozen=True)
class EventEffect:
    function: str
    body_hash: str
    writes: frozenset[TableEvent]


@dataclass(frozen=True)
class EventCatalog:
    relations: frozenset[str]
    foreign_keys: tuple[ForeignKeyAction,...]
    triggers: tuple[EventTrigger,...]


@dataclass(frozen=True)
class JointEventClosure:
    events: tuple[TableEvent,...]
    read_locks: tuple[str,...]
    foreign_keys: tuple[str,...]
    triggers: tuple[str,...]
    execution_allowed: bool=field(default=False,init=False)


_OPERATIONS=frozenset({'INSERT','UPDATE','DELETE','TRUNCATE'})
_ACTIONS=frozenset({'NO ACTION','RESTRICT','CASCADE','SET NULL','SET DEFAULT'})


def _event(event,relations):
    return (type(event) is TableEvent and type(event.relation) is str
            and event.relation in relations and type(event.operation) is str
            and event.operation in _OPERATIONS)


def joint_event_closure(catalog: EventCatalog,seeds: frozenset[TableEvent],
                        reviewed_effects: tuple[EventEffect,...]) -> JointEventClosure:
    """Conservative possible writes, without treating FK reads as new writes.

    UPDATE may change any key column. CASCADE/SET actions therefore propagate
    even without a column-level witness. TRUNCATE with FK dependencies requires
    a separate protocol and is rejected rather than guessing CASCADE semantics.
    Matching trigger WHEN conditions may be true; they are not silently pruned.
    """
    _require(type(catalog) is EventCatalog and type(catalog.relations) is frozenset
             and bool(catalog.relations) and all(_relation(x) for x in catalog.relations)
             and type(catalog.foreign_keys) is tuple and type(catalog.triggers) is tuple,
             'EXACT_EVENT_CATALOG_REQUIRED')
    _require(type(seeds) is frozenset and bool(seeds) and all(_event(x,catalog.relations) for x in seeds),
             'EXACT_WRITE_EVENTS_REQUIRED')
    fk_keys,trigger_keys,effects=set(),set(),{}
    for link in catalog.foreign_keys:
        _require(type(link) is ForeignKeyAction and type(link.foreign_key) is ForeignKey,
                 'EXACT_FOREIGN_KEY_ACTION_REQUIRED')
        fk=link.foreign_key
        _require(type(fk.relation) is str and type(fk.referenced_relation) is str
                 and fk.relation in catalog.relations and fk.referenced_relation in catalog.relations
                 and _key(fk.key,fk.relation) and fk.key not in fk_keys
                 and type(link.on_update) is str and type(link.on_delete) is str
                 and link.on_update in _ACTIONS and link.on_delete in _ACTIONS,
                 'EXACT_FOREIGN_KEY_ACTION_REQUIRED')
        fk_keys.add(fk.key)
    for entry in catalog.triggers:
        _require(type(entry) is EventTrigger and type(entry.trigger) is Trigger,'EXACT_EVENT_TRIGGER_REQUIRED')
        t=entry.trigger
        _require(type(t.relation) is str and t.relation in catalog.relations and _key(t.key,t.relation)
                 and t.key not in trigger_keys and _function(t.function,t.body_hash)
                 and type(t.enabled) is bool and type(t.internal) is bool
                 and type(entry.operations) is frozenset and bool(entry.operations)
                 and entry.operations<=_OPERATIONS,'EXACT_EVENT_TRIGGER_REQUIRED')
        trigger_keys.add(t.key)
    _require(type(reviewed_effects) is tuple,'EXACT_EVENT_EFFECT_REQUIRED')
    for effect in reviewed_effects:
        _require(type(effect) is EventEffect and _function(effect.function,effect.body_hash)
                 and type(effect.writes) is frozenset and all(_event(x,catalog.relations) for x in effect.writes)
                 and effect.function not in effects,'EXACT_EVENT_EFFECT_REQUIRED')
        effects[effect.function]=effect
    seen,locks,required_fks,required_triggers=set(),set(),set(),set()
    pending=set(seeds)
    while pending:
        event=min(pending);pending.remove(event)
        if event in seen:continue
        seen.add(event)
        for link in catalog.foreign_keys:
            fk=link.foreign_key
            if event.operation=='TRUNCATE':
                _require(event.relation not in (fk.relation,fk.referenced_relation),'JOINT_TRUNCATE_POLICY_REQUIRED')
            if event.relation==fk.relation and event.operation in ('INSERT','UPDATE'):
                locks.add(fk.referenced_relation);required_fks.add(fk.key)
            if event.relation==fk.referenced_relation and event.operation in ('UPDATE','DELETE'):
                locks.add(fk.relation);required_fks.add(fk.key)
                action=link.on_update if event.operation=='UPDATE' else link.on_delete
                if action=='CASCADE':pending.add(TableEvent(fk.relation,event.operation))
                elif action in ('SET NULL','SET DEFAULT'):pending.add(TableEvent(fk.relation,'UPDATE'))
        for entry in catalog.triggers:
            t=entry.trigger
            if t.relation!=event.relation or event.operation not in entry.operations:continue
            _require(t.enabled,'ORIGIN_TRIGGER_REQUIRED')
            effect=effects.get(t.function)
            _require(effect is not None,'TRIGGER_EFFECT_REQUIRED')
            _require(effect.body_hash==t.body_hash,'TRIGGER_EFFECT_BODY_DRIFTED')
            required_triggers.add(t.key);pending.update(effect.writes-seen)
        pending.difference_update(seen)
    return JointEventClosure(tuple(sorted(seen)),tuple(sorted(locks)),tuple(sorted(required_fks)),tuple(sorted(required_triggers)))
