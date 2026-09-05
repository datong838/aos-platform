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
                              "operationId":"example.read","mode":"exclusive"}]}


def test_session_register_then_invoke_without_ports():
    target=io.BytesIO()
    source=io.BytesIO(encode_frame(frame("register","register",0))+encode_frame(frame("invoke","example.read",1)))
    def handle(operation,payload,ctx):
        with pytest.raises(PermissionError):ctx.request("storage.query",{})
        return {"标题":"隔离会话测试"}
    sdk()(registration,handle,source=source,target=target)
    results=FrameSession(allowed_methods={"register","example.read"}).feed(target.getvalue())
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


@pytest.mark.parametrize("message",[frame("invoke","unknown.read",1),frame("invoke","example.read",3),
    frame("port_request","example.read",1),{**frame("invoke","example.read",1),"parentRequestId":"forged"}])
def test_bad_followup_closes_before_handler(message):
    def handle(*args):raise AssertionError("must not invoke")
    with pytest.raises(ValueError):
        sdk()(registration,handle,source=io.BytesIO(encode_frame(frame("register","register",0))+encode_frame(message)),target=io.BytesIO())
