import importlib.util
import io
from pathlib import Path
import sys
import pytest
from aos_api.extension_runtime.ipc import encode_frame, FrameSession


def sdk():
    root=Path(__file__).resolve().parents[4]/"packages/aos-extension-sdk/python"
    sys.path.insert(0,str(root))
    try:
        from aos_extension_sdk.session import serve_session
        return serve_session
    finally:
        sys.path.remove(str(root))


def frame(kind,method,number,payload=None):
    return {"schemaVersion":1,"type":kind,"method":method,"requestId":f"request-{number}",
            "parentRequestId":None,"payload":payload or {},"sequence":number}


def registration(ctx):
    return {"contributions":[{"kind":"api","method":"POST","path":"/example/read",
                              "operationId":"example_read","mode":"exclusive"}]}


def test_session_register_then_invoke_without_ports():
    target=io.BytesIO()
    source=io.BytesIO(encode_frame(frame("register","register",0))+encode_frame(frame("invoke","example_read",1)))
    def handle(operation,payload,ctx):
        with pytest.raises(PermissionError):ctx.request("storage.query",{})
        return {"标题":"隔离会话测试"}
    sdk()(registration,handle,source=source,target=target)
    results=FrameSession(allowed_methods={"register","example_read"}).feed(target.getvalue())
    assert len(results)==2
    assert results[1]["payload"]=={"标题":"隔离会话测试"}


def test_heartbeat_is_bounded_and_never_calls_business_handler():
    nonce='a'*32
    target=io.BytesIO()
    source=io.BytesIO(encode_frame(frame('register','register',0))+
        encode_frame(frame('heartbeat','heartbeat',1,{'nonce':nonce})))
    def handle(*args):raise AssertionError('heartbeat must not call business handler')
    sdk()(registration,handle,source=source,target=target)
    result=FrameSession(allowed_methods={'register','heartbeat'}).feed(target.getvalue())
    assert result[1]['payload']=={'nonce':nonce,'protocol':'aos-extension/1','status':'alive'}


def test_4096_heartbeats_keep_business_session_alive():
    messages=[frame('register','register',0)]
    messages.extend(frame('heartbeat','heartbeat',n,{'nonce':'a'*32}) for n in range(1,4097))
    messages.append(frame('invoke','example_read',4097,{'value':'after-heartbeats'}))
    calls=[];target=io.BytesIO()
    sdk()(registration,lambda op,payload,ctx:calls.append(payload) or {'ok':True},
        source=io.BytesIO(b''.join(encode_frame(m) for m in messages)),target=target)
    assert calls==[{'value':'after-heartbeats'}]
    decoder=FrameSession(allowed_methods={'register','heartbeat','example_read'})
    raw=target.getvalue();results=[]
    for offset in range(0,len(raw),65536): results.extend(decoder.feed(raw[offset:offset+65536]))
    decoder.finish()
    assert len(results)==4098 and results[-1]['payload']=={'ok':True}


def test_business_request_id_stays_protected_after_heartbeat_window_rotates():
    messages=[frame('register','register',0),frame('invoke','example_read',1)]
    messages.extend(frame('heartbeat','heartbeat',n,{'nonce':'a'*32}) for n in range(2,2050))
    messages.append({**frame('invoke','example_read',2050),'requestId':'request-1'})
    calls=[]
    with pytest.raises(ValueError,match='replayed'):
        sdk()(registration,lambda *args:calls.append(True) or {},
            source=io.BytesIO(b''.join(encode_frame(m) for m in messages)),target=io.BytesIO())
    assert len(calls)==1


def test_business_request_budget_stays_bounded():
    messages=[frame('register','register',0)]
    messages.extend(frame('invoke','example_read',n) for n in range(1,1025))
    calls=[]
    with pytest.raises(ValueError,match='request budget exhausted'):
        sdk()(registration,lambda *args:calls.append(True) or {},
            source=io.BytesIO(b''.join(encode_frame(m) for m in messages)),target=io.BytesIO())
    assert len(calls)==1023


def test_recent_heartbeat_request_id_cannot_repeat_with_new_sequence():
    messages=[frame('register','register',0),frame('heartbeat','heartbeat',1,{'nonce':'a'*32}),
        {**frame('heartbeat','heartbeat',2,{'nonce':'b'*32}),'requestId':'request-1'}]
    with pytest.raises(ValueError,match='replayed'):
        sdk()(registration,lambda *args:pytest.fail('heartbeat invoked handler'),
            source=io.BytesIO(b''.join(encode_frame(m) for m in messages)),target=io.BytesIO())


@pytest.mark.parametrize('method,payload', [('other',{'nonce':'a'*32}),('heartbeat',{}),
    ('heartbeat',{'nonce':'a'*31}),('heartbeat',{'nonce':'A'*32}),
    ('heartbeat',{'nonce':'a'*32,'extra':True}),('heartbeat',{'nonce':1})])
def test_invalid_heartbeat_is_rejected(method,payload):
    def handle(*args):raise AssertionError('must not call business handler')
    with pytest.raises(ValueError):
        sdk()(registration,handle,source=io.BytesIO(encode_frame(frame('register','register',0))+
            encode_frame(frame('heartbeat',method,1,payload))),target=io.BytesIO())


def test_heartbeat_cannot_replace_initial_registration():
    with pytest.raises(ValueError,match='registration required'):
        sdk()(registration,lambda *args:{},source=io.BytesIO(
            encode_frame(frame('heartbeat','heartbeat',0,{'nonce':'a'*32}))),target=io.BytesIO())


def test_registration_rejects_operation_id_outside_platform_contract():
    def dotted(_context):
        return {"contributions": [{"kind": "api", "method": "POST", "path": "/example",
                                    "operationId": "example.read", "mode": "exclusive"}]}
    with pytest.raises(ValueError, match="invalid API operation"):
        sdk()(dotted, lambda *args: {}, source=io.BytesIO(
            encode_frame(frame("register", "register", 0))), target=io.BytesIO())


@pytest.mark.parametrize("message",[frame("invoke","unknown.read",1),frame("invoke","example_read",3),
    frame("port_request","example_read",1),{**frame("invoke","example_read",1),"parentRequestId":"forged"}])
def test_bad_followup_closes_before_handler(message):
    def handle(*args):raise AssertionError("must not invoke")
    with pytest.raises(ValueError):
        sdk()(registration,handle,source=io.BytesIO(encode_frame(frame("register","register",0))+encode_frame(message)),target=io.BytesIO())
