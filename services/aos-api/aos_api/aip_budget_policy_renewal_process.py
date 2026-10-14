"""One stdin request per private process; no retry or stdout-based permission."""
import argparse
from contextlib import redirect_stdout
import json
import logging
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

from aos_api.aip_budget_policy_renewal_connection import load_protected_config
from aos_api.aip_budget_policy_renewal_service import RenewalRequest,RenewalService

MAX_BYTES=65536


class RenewalProtocolBlocked(ValueError):
    pass


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError()
        result[key]=value
    return result


def decode_renewal_request(raw):
    try:
        if type(raw) is not bytes or not 0<len(raw)<=MAX_BYTES:
            raise ValueError()
        body=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(body) is not dict:
            raise ValueError()
        return RenewalRequest.model_validate(body)
    except Exception:
        raise RenewalProtocolBlocked('RENEWAL_WIRE_INVALID') from None


def _response(request,result):
    if (type(result) is not dict or result.get('operation')!=request.operation
            or result.get('requestHash')!=request.command.request_hash
            or result.get('activationEligible') is not False
            or result.get('status') not in {'prepared','decided','revoked','observed','unresolved','conflict','blocked'}):
        raise RenewalProtocolBlocked('RENEWAL_NATIVE_RESPONSE_REQUIRED')
    return {'schemaVersion':1,'operation':request.operation,'requestHash':request.command.request_hash,
            'activationEligible':False,'result':result}


def observe_process(child,raw,timeout):
    """Bound both buffers while preserving a timed-out/overflowed live handle."""
    deadline=time.monotonic()+timeout
    buffers={'stdout':bytearray(),'stderr':bytearray()}
    pending=memoryview(raw)
    with selectors.DefaultSelector() as selector:
        for stream,event,label in ((child.stdin,selectors.EVENT_WRITE,'stdin'),
                                   (child.stdout,selectors.EVENT_READ,'stdout'),
                                   (child.stderr,selectors.EVENT_READ,'stderr')):
            os.set_blocking(stream.fileno(),False)
            selector.register(stream,event,label)
        while selector.get_map():
            remaining=deadline-time.monotonic()
            if remaining<=0:
                return 'running',None,None
            for key,_ in selector.select(min(remaining,.1)):
                stream,label=key.fileobj,key.data
                if label=='stdin':
                    try:
                        written=os.write(stream.fileno(),pending[:4096])
                        pending=pending[written:]
                    except BrokenPipeError:
                        pending=pending[:0]
                    if not pending:
                        selector.unregister(stream);stream.close()
                        child.stdin=None
                else:
                    chunk=os.read(stream.fileno(),4096)
                    if not chunk:
                        selector.unregister(stream);stream.close()
                        setattr(child,label,None)
                    elif len(buffers[label])+len(chunk)>MAX_BYTES:
                        return 'overflow',None,None
                    else:
                        buffers[label].extend(chunk)
    remaining=max(0,deadline-time.monotonic())
    try:
        child.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        return 'running',None,None
    return 'terminal',bytes(buffers['stdout']),bytes(buffers['stderr'])


def run_renewal_process(config_path,attempt_directory,raw,*,timeout=15):
    """Parent never accepts child stdout as a publication or retry decision."""
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=60:
        raise RenewalProtocolBlocked('RENEWAL_PARENT_DEADLINE_REQUIRED')
    request=decode_renewal_request(raw)
    config=load_protected_config(config_path)
    child=subprocess.Popen([sys.executable,'-m','aos_api.aip_budget_policy_renewal_process','--config',str(config.path),
                             '--attempt-directory',str(attempt_directory)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    state,stdout,stderr=observe_process(child,raw,timeout)
    if state!='terminal':
        # Keep actual ownership/handle; no terminate/restart on observation expiry.
        return {'status':'process-running' if state=='running' else 'unknown',
                'process':child,'requestHash':request.command.request_hash,
                'activationEligible':False}
    if len(stdout)>MAX_BYTES or len(stderr)>MAX_BYTES or child.returncode!=0:
        return {'status':'unknown','requestHash':request.command.request_hash,'activationEligible':False}
    try:
        value=json.loads(stdout,object_pairs_hook=_unique)
        if (type(value) is not dict or set(value)!=
                {'schemaVersion','operation','requestHash','activationEligible','result'}
                or type(value['schemaVersion']) is not int or value['schemaVersion']!=1):
            raise ValueError()
        _response(request,value['result'])
        if value!=_response(request,value['result']):
            raise ValueError()
    except Exception:
        return {'status':'unknown','requestHash':request.command.request_hash,'activationEligible':False}
    # Independent native READONLY proof, even if child stdout was forged.
    try:
        return _response(request,RenewalService(config,attempt_directory).reconcile(request))
    except Exception:
        return {'status':'unknown','requestHash':request.command.request_hash,'activationEligible':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--attempt-directory',required=True)
    args=parser.parse_args()
    try:
        # Package initialization may already hold the original stdout object.
        # This CLI owns the process; preserve logger format but redirect its sink.
        for handler in logging.getLogger().handlers:
            if isinstance(handler,logging.StreamHandler) and handler.stream is sys.stdout:
                handler.setStream(sys.stderr)
        # Audited legacy imports may configure logging on sys.stdout. Keep all
        # internal output off the single-result channel before loading them.
        with redirect_stdout(sys.stderr):
            raw=sys.stdin.buffer.read(MAX_BYTES+1)
            request=decode_renewal_request(raw)
            config=load_protected_config(Path(args.config))
            result=RenewalService(config,Path(args.attempt_directory)).execute(request)
            response=_response(request,result)
        print(json.dumps(response,ensure_ascii=False,separators=(',',':')),flush=True)
        return 0
    except Exception:
        # No exception representation, request data, JWT or credential on wire.
        print('RENEWAL_PRIVATE_PROCESS_BLOCKED',file=sys.stderr,flush=True)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
