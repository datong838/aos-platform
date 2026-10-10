"""Installation-review dependency closure for the complete joint end protocol.

This is a conservative catalog graph, never the actual deferred event queue.
Reviewed effects are trusted installation inputs, not runtime caller DTOs. Their
semantic review and original native library/Owner/ACL provenance are separate
requirements; a matching body hash alone does not establish those properties.
No SQL, permissions, commit, finalization or execution authority is produced.
"""
from dataclasses import dataclass, field
import re


class JointCatalogRejected(ValueError):
    pass


@dataclass(frozen=True)
class ForeignKey:
    key: str
    relation: str
    referenced_relation: str


@dataclass(frozen=True)
class Trigger:
    key: str
    relation: str
    function: str
    body_hash: str
    enabled: bool = True
    internal: bool = False


@dataclass(frozen=True)
class TriggerEffect:
    function: str
    body_hash: str
    writes: frozenset[str]


@dataclass(frozen=True)
class JointCatalog:
    relations: frozenset[str]
    foreign_keys: tuple[ForeignKey, ...]
    triggers: tuple[Trigger, ...]


@dataclass(frozen=True)
class JointConstraintClosure:
    relations: tuple[str, ...]
    foreign_keys: tuple[str, ...]
    triggers: tuple[str, ...]
    execution_allowed: bool = field(default=False, init=False)


_IDENTIFIER = r'[A-Za-z_][A-Za-z0-9_]{0,62}'


def _require(value: bool, reason: str) -> None:
    if not value:
        raise JointCatalogRejected(reason)


def _relation(value: str) -> bool:
    return type(value) is str and re.fullmatch(_IDENTIFIER+r'\.'+_IDENTIFIER, value) is not None


def _function(function: str, digest: str) -> bool:
    return (type(function) is str and 0 < len(function) <= 1024
            and function == function.strip() and '\x00' not in function
            and type(digest) is str and re.fullmatch(r'[0-9a-f]{64}', digest) is not None)


def _key(key: str, relation: str) -> bool:
    return (type(key) is str and key.startswith(relation+'.')
            and re.fullmatch(_IDENTIFIER, key[len(relation)+1:]) is not None)


def joint_constraint_closure(catalog: JointCatalog, written_relations: frozenset[str],
                             reviewed_effects: tuple[TriggerEffect, ...]) -> JointConstraintClosure:
    """Expand FK components and reviewed trigger writes to a stable fixed point.

    Both FK directions deliberately over-approximate referential actions and
    locks. Callers must not reinterpret this result as proof that constraints
    ran, no subsequent event can occur, or a business commit may be accepted.
    """
    _require(type(catalog) is JointCatalog and type(catalog.relations) is frozenset
             and type(catalog.foreign_keys) is tuple and type(catalog.triggers) is tuple,
             'EXACT_CATALOG_REQUIRED')
    _require(bool(catalog.relations) and all(_relation(x) for x in catalog.relations),
             'QUALIFIED_RELATION_REQUIRED')
    _require(type(written_relations) is frozenset and bool(written_relations)
             and written_relations <= catalog.relations, 'KNOWN_WRITE_SET_REQUIRED')
    _require(type(reviewed_effects) is tuple, 'EXACT_EFFECT_CONTRACTS_REQUIRED')
    fk_keys, trigger_keys, effects = set(), set(), {}
    for fk in catalog.foreign_keys:
        _require(type(fk) is ForeignKey and fk.relation in catalog.relations
                 and fk.referenced_relation in catalog.relations and _key(fk.key, fk.relation)
                 and fk.key not in fk_keys, 'EXACT_FOREIGN_KEY_REQUIRED')
        fk_keys.add(fk.key)
    for trigger in catalog.triggers:
        _require(type(trigger) is Trigger and trigger.relation in catalog.relations
                 and _key(trigger.key, trigger.relation) and trigger.key not in trigger_keys
                 and _function(trigger.function, trigger.body_hash)
                 and type(trigger.enabled) is bool and type(trigger.internal) is bool,
                 'EXACT_TRIGGER_REQUIRED')
        trigger_keys.add(trigger.key)
    for effect in reviewed_effects:
        _require(type(effect) is TriggerEffect and _function(effect.function, effect.body_hash)
                 and type(effect.writes) is frozenset and effect.writes <= catalog.relations
                 and effect.function not in effects, 'EXACT_TRIGGER_EFFECT_REQUIRED')
        effects[effect.function] = effect
    relations, required_fks, required_triggers = set(written_relations), set(), set()
    while True:
        previous = len(relations)
        for fk in catalog.foreign_keys:
            if fk.relation in relations or fk.referenced_relation in relations:
                relations.update((fk.relation, fk.referenced_relation))
                required_fks.add(fk.key)
        for trigger in catalog.triggers:
            if trigger.relation not in relations:
                continue
            _require(trigger.enabled, 'ORIGIN_TRIGGER_REQUIRED')
            effect = effects.get(trigger.function)
            _require(effect is not None, 'TRIGGER_EFFECT_REQUIRED')
            _require(effect.body_hash == trigger.body_hash, 'TRIGGER_EFFECT_BODY_DRIFTED')
            required_triggers.add(trigger.key)
            relations.update(effect.writes)
        if len(relations) == previous:
            return JointConstraintClosure(tuple(sorted(relations)), tuple(sorted(required_fks)),
                                          tuple(sorted(required_triggers)))
