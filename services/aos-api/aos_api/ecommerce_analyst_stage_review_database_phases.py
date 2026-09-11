"""Separate database transactions around installed stage-review IPC."""

from __future__ import annotations

import inspect
from typing import Callable

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.ecommerce_analyst_stage_review_coordinator import (
    PreparedStageReviewValidation,StageReviewValidationExchange)


class StageReviewDatabasePhases:
    """Build coordinator callbacks without retaining a transaction during IPC."""

    def __init__(self,*,transaction_factory:Callable,prepare_in_transaction:Callable,
            load_current_snapshot:Callable,publish_in_transaction:Callable):
        dependencies=(transaction_factory,prepare_in_transaction,
            load_current_snapshot,publish_in_transaction)
        if any(not callable(value) or inspect.iscoroutinefunction(value) for value in dependencies):
            raise TypeError("synchronous stage review database dependencies required")
        self.transaction_factory=transaction_factory
        self.prepare_in_transaction=prepare_in_transaction
        self.load_current_snapshot=load_current_snapshot
        self.publish_in_transaction=publish_in_transaction

    def _transaction(self,command):
        transaction=self.transaction_factory(command)
        if not callable(getattr(transaction,"__enter__",None)) or not callable(
                getattr(transaction,"__exit__",None)):
            raise TypeError("stage review transaction context manager required")
        return transaction

    async def prepare(self,command:dict[str,object])->PreparedStageReviewValidation:
        if type(command) is not dict:
            raise TypeError("stage review command object required")
        canonical_json(command)
        with self._transaction(command) as transaction:
            value=self.prepare_in_transaction(transaction,command)
        if type(value) is not tuple or len(value)!=2:
            raise TypeError("stage review prepare snapshot and exchanges required")
        authority_snapshot,exchanges=value
        if type(exchanges) is not tuple or any(
                type(item) is not StageReviewValidationExchange for item in exchanges):
            raise TypeError("stage review validation exchanges required")
        return PreparedStageReviewValidation(canonical_sha256(command),exchanges,authority_snapshot)

    async def commit(self,command:dict[str,object],prepared:PreparedStageReviewValidation,
            results:tuple[dict[str,object],...])->dict[str,object]:
        if type(command) is not dict or type(prepared) is not PreparedStageReviewValidation:
            raise TypeError("prepared stage review command required")
        if (type(results) is not tuple or len(results)!=len(prepared.exchanges)
                or any(type(item) is not dict for item in results)):
            raise ValueError("complete stage review validation results required")
        canonical_json(command);canonical_json(list(results));prepared.verify()
        if prepared.command_hash!=canonical_sha256(command):
            raise ValueError("prepared stage review command drifted")
        with self._transaction(command) as transaction:
            current=self.load_current_snapshot(transaction,command)
            if type(current) is not dict or not current:
                raise ValueError("current stage review authority snapshot required")
            canonical_json(current)
            if current!=prepared.authority_snapshot:
                raise ValueError("stage review authority snapshot changed")
            result=self.publish_in_transaction(transaction,command,prepared,results)
            if type(result) is not dict:
                raise TypeError("stage review publish result object required")
            canonical_json(result)
        return result


__all__=["StageReviewDatabasePhases"]
