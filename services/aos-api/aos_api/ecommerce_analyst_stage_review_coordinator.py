"""Three-phase no-retry coordinator for installed stage-review validation."""

from dataclasses import dataclass, field
import inspect
import re

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort

_HASH=re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class StageReviewValidationExchange:
    payload: dict[str, object]
    expected: dict[str, object]
    _snapshot_hash: str=field(init=False,repr=False)

    def __post_init__(self):
        if type(self.payload) is not dict or type(self.expected) is not dict:
            raise TypeError("stage review exchange requires JSON objects")
        object.__setattr__(self,"_snapshot_hash",canonical_sha256([self.payload,self.expected]))

    def verify(self):
        if canonical_sha256([self.payload,self.expected])!=self._snapshot_hash:
            raise ValueError("stage review validation exchange changed")


@dataclass(frozen=True, slots=True)
class PreparedStageReviewValidation:
    command_hash: str
    exchanges: tuple[StageReviewValidationExchange,...]
    authority_snapshot: dict[str,object]
    _snapshot_hash: str=field(init=False,repr=False)

    def __post_init__(self):
        if type(self.command_hash) is not str or _HASH.fullmatch(self.command_hash) is None:
            raise ValueError("canonical stage review command hash required")
        if type(self.exchanges) is not tuple or not 1<=len(self.exchanges)<=4:
            raise ValueError("bounded stage review exchanges required")
        if any(type(item) is not StageReviewValidationExchange for item in self.exchanges):
            raise ValueError("unique stage review exchanges required")
        kinds=tuple(item.payload.get("kind") for item in self.exchanges)
        if len(kinds)!=len(set(kinds)):
            raise ValueError("unique stage review exchanges required")
        if type(self.authority_snapshot) is not dict or not self.authority_snapshot:
            raise ValueError("non-empty stage review authority snapshot required")
        canonical_json(self.authority_snapshot)
        object.__setattr__(self,"_snapshot_hash",canonical_sha256([
            [[item.payload,item.expected] for item in self.exchanges],self.authority_snapshot]))

    def verify(self):
        for item in self.exchanges:item.verify()
        if canonical_sha256([[[item.payload,item.expected] for item in self.exchanges],
                self.authority_snapshot])!=self._snapshot_hash:
            raise ValueError("prepared stage review validation changed")


class AsyncStageReviewCommandCoordinator:
    def __init__(self,*,prepare,port,commit):
        if not inspect.iscoroutinefunction(prepare) or not inspect.iscoroutinefunction(commit):
            raise TypeError("async stage review prepare and commit required")
        if type(port) is not InstalledGrowthStageReviewPort:
            raise TypeError("installed stage review port required")
        self.prepare,self.port,self.commit=prepare,port,commit

    async def execute(self,command:dict[str,object]):
        if type(command) is not dict:raise TypeError("stage review command object required")
        canonical_json(command)
        prepared=await self.prepare(command)
        if type(prepared) is not PreparedStageReviewValidation or prepared.command_hash!=canonical_sha256(command):
            raise ValueError("prepared stage review command drifted")
        prepared.verify();results=[]
        for exchange in prepared.exchanges:
            exchange.verify()
            results.append(await self.port.validate(payload=exchange.payload,expected=exchange.expected))
            exchange.verify()
        prepared.verify()
        result=await self.commit(command,prepared,tuple(results))
        canonical_json(result)
        return result


__all__=["AsyncStageReviewCommandCoordinator","PreparedStageReviewValidation","StageReviewValidationExchange"]
