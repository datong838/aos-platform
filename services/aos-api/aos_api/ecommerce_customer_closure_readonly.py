"""Bounded historical customer closure snapshots, never operating authority."""
from time import monotonic
import json

import psycopg
from psycopg import IsolationLevel

from aos_api.db import connect_read_only
from aos_api.ecommerce_three_module_closure_readonly import (
    MAX_ITEM_BYTES, MAX_TOTAL_BYTES, _TABLES, _SavedBindings, _strict_price_raw,
    _time, _visible, CreatorClosureReadonlyError, CreatorClosureReadonlyReader,
)
from aos_api.ecommerce_workshop_three_module_closure import (
    EcommerceWorkshopThreeModuleClosureService, ThreeModule,
)


class CustomerClosureReadonlyError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _deny(suffix):
    raise CustomerClosureReadonlyError('CUSTOMER_CLOSURE_READ_' + suffix)


class CustomerClosureReadonlyReader:
    def __init__(self, *, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    @staticmethod
    def _row(conn, scope, kind, closure_id):
        table, _ = _TABLES[kind]
        identity = 'closure_id' if kind == 'closure' else 'binding_id'
        source = ('CASE WHEN length(source_id)<=240 THEN source_id ELSE NULL END AS source_id'
                  if kind == 'closure' else 'NULL AS source_id')
        predicate = 'module=%s' if kind == 'closure' else 'closure_id=%s'
        return conn.execute(
            f'''SELECT org_id,project_id,
                CASE WHEN length({identity})<=240 THEN {identity} ELSE NULL END AS resource_id,
                CASE WHEN length(closure_id)<=240 THEN closure_id ELSE NULL END AS closure_id,
                revision,module,{source},content_hash,created_at,
                octet_length(authority_data::text) AS payload_bytes,
                CASE WHEN octet_length(authority_data::text)<={MAX_ITEM_BYTES}
                     THEN authority_data ELSE NULL END AS authority_data
                FROM {table} WHERE org_id=%s AND project_id=%s AND {predicate}
                ORDER BY created_at DESC,{identity} LIMIT 1''',
            (*scope.key, 'customer' if kind == 'closure' else closure_id),
        ).fetchone()

    @staticmethod
    def _decode(row, scope, kind, cutoff, closure):
        raw = row['authority_data']
        if type(raw) is not dict:
            _deny('AUTHORITY_DRIFT')
        _strict_price_raw(raw)
        item = CreatorClosureReadonlyReader._decode(
            row, scope, kind, cutoff, closure, ThreeModule.CUSTOMER)
        if item.model_dump(mode='json', by_alias=True) != raw:
            _deny('AUTHORITY_DRIFT')
        if kind == 'closure' and any(
                value.receipt_ref is not None and value.receipt_ref.resource_type != 'ActionReceipt'
                for value in item.items):
            _deny('CONTENT_UNSUPPORTED')
        visible = json.dumps(_visible(item.model_dump(mode='json', by_alias=True)), ensure_ascii=False).lower()
        if any(word in visible for word in ('mobile', 'openid', 'email', 'address', 'contactvalue', 'providerpayload')):
            _deny('CONTENT_UNSUPPORTED')
        return item

    def read(self, scope):
        started = monotonic()

        def deadline():
            if monotonic() - started > 10:
                _deny('LIMIT_EXCEEDED')

        try:
            with self._connect(scope) as conn:
                if (conn.read_only is not True or conn.autocommit is not False
                        or conn.isolation_level != IsolationLevel.REPEATABLE_READ):
                    _deny('UNAVAILABLE')
                deadline()
                conn.execute("SET LOCAL statement_timeout='3000ms'")
                conn.execute("SET LOCAL lock_timeout='500ms'")
                cutoff = conn.execute('SELECT transaction_timestamp() AS cutoff').fetchone()['cutoff']
                if not _time(cutoff, cutoff):
                    _deny('AUTHORITY_DRIFT')
                bindings = dict(closure=None, usage=None, effect=None, handoff=None)
                total = 0
                for kind in _TABLES:
                    deadline()
                    closure = bindings['closure']
                    if kind != 'closure' and closure is None:
                        break
                    row = self._row(conn, scope, kind, getattr(closure, 'closure_id', None))
                    if row is None:
                        continue
                    size = row['payload_bytes']
                    if type(size) is not int or size < 1:
                        _deny('AUTHORITY_DRIFT')
                    total += size
                    if size > MAX_ITEM_BYTES or total > MAX_TOTAL_BYTES:
                        _deny('LIMIT_EXCEEDED')
                    bindings[kind] = self._decode(row, scope, kind, cutoff, closure)
                    deadline()
                view = EcommerceWorkshopThreeModuleClosureService(_SavedBindings(bindings)).contribution_view(
                    scope, ThreeModule.CUSTOMER, now=cutoff)
                data = view.model_dump(mode='json', by_alias=True)
                data.update(allowedCommands=[], handoffConsumeAllowed=False,
                            memoryPromotionAllowed=False, externalEffectsAllowed=False)
                result = type(view).model_validate(data)
                if len(result.model_dump_json(by_alias=True).encode()) > MAX_TOTAL_BYTES:
                    _deny('LIMIT_EXCEEDED')
                deadline()
                return result
        except CustomerClosureReadonlyError:
            raise
        except CreatorClosureReadonlyError as exc:
            raise CustomerClosureReadonlyError(
                exc.code.replace('CREATOR_CLOSURE_READ_', 'CUSTOMER_CLOSURE_READ_', 1)) from exc
        except RecursionError:
            _deny('LIMIT_EXCEEDED')
        except psycopg.Error:
            _deny('UNAVAILABLE')
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            _deny('AUTHORITY_DRIFT')
