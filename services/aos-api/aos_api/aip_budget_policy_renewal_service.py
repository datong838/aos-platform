"""Five renewal operations behind protected configuration and at-most-once IPC.

Human JWTs are memory-only. This service never provisions roles or approves on
behalf of a user; issuer decisions require the exact explicit request and JWT.
"""
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, SecretStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_policy_renewal_contracts import (
    RenewalProposalCommand,RenewalDecisionCommand,RenewalRevocationCommand,RenewalConsumeCommand,
)
from aos_api.aip_budget_policy_renewal_connection import (
    ProtectedRenewalConfig,open_purpose_connection,
)
from aos_api.aip_budget_policy_renewal_identity import _database_identity,authenticate_checker
from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore,RenewalStoreBlocked
from aos_api.aip_network_issuer_attempt import (
    AttemptReceipt,AttemptAlreadyRecorded,AttemptConflict,AttemptUnknown,_reserve_attempt_receipt,
)

COMMANDS={'propose':RenewalProposalCommand,'decide':RenewalDecisionCommand,
          'revoke':RenewalRevocationCommand,'consume':RenewalConsumeCommand}
PURPOSES={'propose':'maker','decide':'issuer','revoke':'issuer','consume':'consumer'}


class RenewalServiceBlocked(ValueError):
    pass


class RenewalRequest(AipContractModel):
    model_config=ConfigDict(frozen=True)
    schema_version: Literal[1]
    mode: Literal['execute','reconcile']
    operation: Literal['propose','decide','revoke','consume']
    command: RenewalProposalCommand|RenewalDecisionCommand|RenewalRevocationCommand|RenewalConsumeCommand
    bearer_token: SecretStr|None=None

    @model_validator(mode='before')
    @classmethod
    def public_identity_fields(cls,value):
        if (type(value) is dict and value.get('operation') not in {'decide','revoke'}
                and any(key in value for key in ('bearerToken','bearer_token'))):
            raise ValueError('machine token field forbidden')
        return value

    @field_validator('schema_version',mode='before')
    @classmethod
    def version(cls,value):
        if type(value) is not int:
            raise ValueError('exact version required')
        return value

    @field_validator('command',mode='before')
    @classmethod
    def exact_command(cls,value,info):
        expected=COMMANDS.get(info.data.get('operation'))
        if expected is None:
            raise ValueError('operation required')
        if type(value) is expected:
            value=value.model_dump(mode='python',by_alias=True)
        if type(value) is not dict:
            raise ValueError('exact command required')
        return expected.model_validate(value)

    @field_validator('bearer_token',mode='before')
    @classmethod
    def secret(cls,value):
        if value is None:
            return None
        if type(value) is SecretStr:
            value=value.get_secret_value()
        if type(value) is not str or not 0<len(value)<=16384:
            raise ValueError('bounded token required')
        return SecretStr(value)

    @model_validator(mode='after')
    def identity_kind(self):
        if type(self.command) is not COMMANDS[self.operation]:
            raise ValueError('command operation mismatch')
        if (self.operation in {'decide','revoke'})!=(self.bearer_token is not None):
            raise ValueError('issuer token required; machine token forbidden')
        return self

    def revalidated(self):
        excluded={'bearer_token'} if self.bearer_token is None else set()
        return type(self).model_validate(self.model_dump(mode='python',by_alias=True,exclude=excluded))


def protocol_schema():
    schema=RenewalRequest.model_json_schema(by_alias=True)
    schema['$id']='aos.budget-policy-renewal.ipc/v1'
    metadata={
        'operation':{'type':'string','enum':list(COMMANDS)},
        'requestHash':{'type':'string','pattern':'^[0-9a-f]{64}$'},
        'activationEligible':{'type':'boolean','const':False},
    }
    schema['$defs']['RenewalResponseFrame']={
        'type':'object','additionalProperties':False,
        'required':['schemaVersion','operation','requestHash','activationEligible','result'],
        'properties':{'schemaVersion':{'type':'integer','const':1},**metadata,
            'result':{'type':'object','additionalProperties':True,
                '$comment':'Native SQL artifact fields remain governed by A Store and independent readonly history.',
                'required':['operation','requestHash','activationEligible','status'],
                'properties':{**metadata,'status':{'type':'string','enum':[
                    'prepared','decided','revoked','observed','unresolved','conflict','blocked']}}}},
        'allOf':[{'if':{'properties':{'operation':{'const':operation}},'required':['operation']},
            'then':{'properties':{'result':{'properties':{'operation':{'const':operation}}}}}}
            for operation in COMMANDS],
    }
    schema['allOf']=[]
    for operation,command in COMMANDS.items():
        then={'properties':{'command':{'$ref':'#/$defs/'+command.__name__}}}
        if operation in {'decide','revoke'}:
            then['required']=['bearerToken']
            then['properties']['bearerToken']={'type':'string','minLength':1,'maxLength':16384}
        else:
            then['not']={'required':['bearerToken']}
        schema['allOf'].append({'if':{'properties':{'operation':{'const':operation}},'required':['operation']},'then':then})
    return schema


class RenewalService:
    def __init__(self,config,attempt_directory):
        if type(config) is not ProtectedRenewalConfig or not Path(attempt_directory).is_absolute():
            raise RenewalServiceBlocked('RENEWAL_PRIVATE_SERVICE_REQUIRED')
        self.config=config
        self.attempt_directory=Path(attempt_directory)

    def reconcile(self,request):
        request=request.revalidated()
        purpose=PURPOSES[request.operation]
        with open_purpose_connection(self.config,purpose,True) as conn:
            store=RenewalAuthorityStore(conn,checker_binding=self.config.binding)
            return store.reconcile(request.command,token=request.bearer_token)

    def execute(self,request):
        if type(request) is not RenewalRequest:
            raise RenewalServiceBlocked('RENEWAL_EXACT_PRIVATE_REQUEST_REQUIRED')
        request=request.revalidated()
        if request.mode=='reconcile':
            return self.reconcile(request)
        purpose=PURPOSES[request.operation]
        # Current authentication precedes reservation; A rechecks in its write tx.
        with open_purpose_connection(self.config,purpose,True) as conn:
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY')
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                login=_database_identity(conn,purpose)
                subject=('postgres-service:'+login if purpose!='issuer' else
                         authenticate_checker(request.bearer_token,binding=self.config.binding,conn=conn).subject)
        command=request.command
        identifier=(command.source_policy_id if request.operation=='propose' else command.proposal_id)
        marker=AttemptReceipt(command.org_id,command.project_id,identifier,
                              command.idempotency_key,command.request_hash,subject)
        try:
            _reserve_attempt_receipt(self.attempt_directory,marker,
                                    namespace='budget-policy-renewal/v1/'+request.operation)
        except AttemptAlreadyRecorded:
            return self.reconcile(request)
        except AttemptConflict:
            return self._history_status(request,'conflict')
        except AttemptUnknown:
            return self._history_status(request,'unresolved')
        # No exception can cause another execute call after the marker exists.
        try:
            with open_purpose_connection(self.config,purpose,False) as conn:
                store=RenewalAuthorityStore(conn,checker_binding=self.config.binding)
                if purpose=='issuer':
                    return getattr(store,request.operation)(command,token=request.bearer_token)
                return getattr(store,request.operation)(command)
        except RenewalStoreBlocked:
            # Confirmed rollback/pre-write refusal is not an unknown COMMIT.
            # The durable marker still prevents a later automatic execute.
            return self._history_status(request,'blocked')
        except Exception:
            try:
                return self.reconcile(request)
            except Exception:
                return self._history_status(request,'unresolved')

    @staticmethod
    def _history_status(request,status):
        return {'operation':request.operation,'requestHash':request.command.request_hash,
                'status':status,'activationEligible':False}
