"""Atomic consumer for an independently approved configuration refresh."""
import json
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
from aos_api.tenant_scope import TenantScope


class EcommerceDispatchConfigurationOwner:
    def __init__(self, *, schema='public'):
        self._schema=schema
        self._approval=EcommerceGrowthCutoverStore(lambda _: None, schema=schema)

    def execute(self, conn, *, scope, command, actor):
        if type(scope) is not TenantScope or type(command) is not dict:
            raise TypeError('trusted scope and refresh command required')
        if type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip() or not actor.isprintable():
            raise PermissionError('canonical configuration maintainer required')
        request=DispatchConfigurationRefreshRequest.model_validate_json(json.dumps(command,allow_nan=False))
        if (request.org_id,request.project_id)!=scope.key:
            raise PermissionError('configuration refresh tenant differs')
        identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if identity is None or (identity['role'],identity['org_id'],identity['project_id'])!=(
                'aos_extension_maintainer',*scope.key):
            raise PermissionError('dedicated configuration maintainer transaction required')
        self._approval._approval_authority(conn,scope,request,
            action_type_id='ecommerce_dispatch_configuration_refresh',
            expected_payload=request.approval_intent())
        receipt_id=conn.execute(
            f'SELECT {self._schema}.extension_dispatch_configuration_refresh_a0v_068(%s,%s) AS receipt_id',
            (Jsonb(request.wire()),actor)).fetchone()['receipt_id']
        # Re-check the same current authority after the mutation and before caller commit.
        self._approval._approval_authority(conn,scope,request,
            action_type_id='ecommerce_dispatch_configuration_refresh',
            expected_payload=request.approval_intent())
        row=conn.execute(f'''SELECT * FROM {self._schema}.extension_dispatch_configuration_refresh_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s''',(*scope.key,UUID(str(receipt_id)))).fetchone()
        if row is None:
            raise RuntimeError('configuration refresh receipt unavailable')
        return decode_receipt(dict(row))
