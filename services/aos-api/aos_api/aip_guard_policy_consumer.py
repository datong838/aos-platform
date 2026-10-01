"""Authenticated low-privilege, at-most-once guard policy activation client."""
from pydantic import Field, SecretStr, field_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_guard_policy_issuer import _authenticate
from aos_api.aip_network_issuer_attempt import AttemptReceipt, AttemptAlreadyRecorded, _reserve_attempt_receipt
from aos_api.aip_runtime_guard_policy_store import canonical_hash


SIGNATURE = 'public.aip_guard_activation_a0v_129(text,text,text,text,text,text,text,text,boolean)'


class GuardConsumerBlocked(ValueError):
    pass


class GuardConsumeCommand(AipContractModel):
    org_id: str = Field(min_length=1,max_length=120)
    project_id: str = Field(min_length=1,max_length=120)
    bearer_token: SecretStr
    proposal_id: str = Field(min_length=1,max_length=160)
    approval_event_id: str = Field(min_length=1,max_length=160)
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    target_content_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    binding_hash: str = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('org_id','project_id','proposal_id','approval_event_id')
    @classmethod
    def _canonical(cls,value):
        if value!=value.strip() or not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError('exact identifier required')
        return value

    @field_validator('bearer_token')
    @classmethod
    def _bounded(cls,value):
        if not 1<=len(value.get_secret_value())<=8192: raise ValueError('bounded JWT required')
        return value


class GuardPolicyConsumer:
    def __init__(self,connect_factory,attempt_directory,*,expected_database):
        if not callable(connect_factory) or type(expected_database) is not str or not expected_database:
            raise GuardConsumerBlocked('GUARD_CONSUMER_PRIVATE_CONFIGURATION_REQUIRED')
        self._connect,self._attempts,self._database=connect_factory,attempt_directory,expected_database

    def _identity(self,conn,scope,read_only):
        row=conn.execute("""SELECT session_user AS login,current_user AS role,current_database() AS db,
          current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
          current_setting('transaction_isolation') AS isolation,
          EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN('aos_guard_policy_consumer_call','aos_guard_policy_consumer_owner')
            AND (rolsuper OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                 OR (rolname='aos_guard_policy_consumer_owner' AND rolcanlogin)
                 OR (rolname='aos_guard_policy_consumer_call' AND NOT rolcanlogin))) AS unsafe,
          EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN('aos_guard_policy_consumer_call'::regrole,'aos_guard_policy_consumer_owner'::regrole)
             OR member IN('aos_guard_policy_consumer_call'::regrole,'aos_guard_policy_consumer_owner'::regrole)) AS extra_roles,
          (SELECT prosecdef AND proowner='aos_guard_policy_consumer_owner'::regrole
             AND proconfig=ARRAY['search_path=pg_catalog'] FROM pg_proc WHERE oid=%s::regprocedure) AS correct_function,
          has_function_privilege(session_user,%s,'EXECUTE') AS can_call""",(SIGNATURE,SIGNATURE)).fetchone()
        if (not row or row['login']!='aos_guard_policy_consumer_call' or row['role']!=row['login']
            or row['db']!=self._database or (row['org'],row['project'])!=scope.key
            or row['unsafe'] or row['extra_roles'] or row['correct_function'] is not True or row['can_call'] is not True
            or conn.read_only is not read_only or row['isolation']!=('repeatable read' if read_only else 'serializable')):
            raise GuardConsumerBlocked('GUARD_CONSUMER_DATABASE_IDENTITY_REQUIRED')

    def _call(self,c,principal,scope,write):
        with self._connect(scope,not write) as conn:
            self._identity(conn,scope,not write)
            row=conn.execute('SELECT public.aip_guard_activation_a0v_129(%s,%s,%s,%s,%s,%s,%s,%s,%s) AS result',
                (*scope.key,c.proposal_id,c.approval_event_id,principal.subject,c.proposal_hash,
                 c.target_content_hash,c.binding_hash,write)).fetchone()
            return row['result']

    def inquire(self,command):
        c,principal,scope=_authenticate(command,GuardConsumeCommand)
        return self._call(c,principal,scope,False)

    def execute(self,command):
        c,principal,scope=_authenticate(command,GuardConsumeCommand)
        before=self._call(c,principal,scope,False)
        if before['status']=='observed': return before
        if before['status']!='ready': raise GuardConsumerBlocked('GUARD_CONSUMER_NOT_READY')
        digest=canonical_hash({'domain':'guard-policy-consumer/v1',
            **c.model_dump(mode='json',by_alias=True,exclude={'bearer_token'}),'actorId':principal.subject})
        receipt=AttemptReceipt(c.org_id,c.project_id,c.proposal_id,c.proposal_id,digest,principal.subject)
        try:
            _reserve_attempt_receipt(self._attempts,receipt,namespace='guard-policy-consumer/v1')
        except AttemptAlreadyRecorded:
            after=self._call(c,principal,scope,False)
            return after if after['status']=='observed' else {'status':'unresolved'}
        try:
            self._call(c,principal,scope,True)
        except Exception:
            # Includes commit transport errors: no retry of the write function.
            pass
        try:
            after=self._call(c,principal,scope,False)
            return after if after['status']=='observed' else {'status':'unresolved'}
        except Exception:
            return {'status':'unresolved'}
