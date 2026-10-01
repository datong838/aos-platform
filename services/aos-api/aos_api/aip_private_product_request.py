"""Durable original request recovery shared by private product commands."""
import json
import os
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_budget_activation_product import BudgetProductBlocked
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_private_request_file import create_private_request_file


def recover_private_product_request(directory, key, body, *, make_command, make_envelope,
                                    read_original, send, code_prefix, before_reserve=None):
    envelope = raw = None
    if body is not None:
        try:
            make_command(body)
            envelope = make_envelope(body)
            raw = json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode()
            if len(raw)>4096:
                raise ValueError()
        except Exception:
            raise BudgetProductBlocked(code_prefix+'_REQUEST_INVALID',422) from None
    reserved = False
    try:
        fd = _private_directory_fd(directory)
        try:
            original = read_original(fd)
            if original is None and body is not None:
                if before_reserve is not None:
                    before_reserve(body)
                reserved = create_private_request_file(fd,key+'.json',raw)
                if not reserved:
                    original = read_original(fd)
                    if original is None:
                        raise ValueError('reservation disappeared')
            if original is not None:
                if envelope is not None and canonical_hash(envelope)!=canonical_hash(make_envelope(original)):
                    raise BudgetProductBlocked(code_prefix+'_REQUEST_CONFLICT',409)
                body = original
        finally:
            os.close(fd)
    except BudgetProductBlocked:
        raise
    except Exception:
        raise BudgetProductBlocked(code_prefix+'_SAVED_REQUEST_UNTRUSTED',503) from None
    if body is None:
        return {'status':'not_attempted'}
    command = make_command(body)
    if reserved:
        try:
            result = send('execute_once',command)
            # The service already reconciled its immutable Receipt.
            # A bounded one-connection service need not remain up for another read.
            if result['status'] == 'observed':
                return result
        except Exception:
            # The durable request stays even if connection/response is lost.
            pass
    try:
        return send('inquiry',command)
    except Exception:
        return {'status':'unresolved'}
