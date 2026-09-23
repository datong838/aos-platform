"""W2-#3 · MediaSet 浏览器交互 API —— **路由层**端到端测试（TestClient）。

存在理由（09-24 签名漂移普查结论）：
`tests/test_media_set_browser_interaction.py` 的 51 个用例**全部直调引擎**，
没有一条经过 HTTP 路由 ⇒ 路由与引擎签名漂移时（6 个端点必然 500、
`create_transcription_job` 字段错位绑定、3 处静默语义漂移）测试**全绿**。
本文件补上门面层契约测试：**只要路由与引擎签名不一致，这里必然红**。

覆盖：19 个 HTTP 操作 + 3 条本轮新确诊缺陷的回归断言
（① delete 后缓存不得回显已删项；② 缺失 MediaSet 必须是 404 而非 400；
③ kind 与 MediaSet 类型不匹配必须是 400 而非 500，且不留孤儿引用）。
"""
from __future__ import annotations

import pytest

from aos_api.auth import Principal, require_principal
from aos_api.media_reference import get_store as get_media_store
from aos_api.media_set import get_store as get_media_set_store
from aos_api.media_set_browser_interaction import (
    AudioTranscriptionEngine,
    MediaInteractionEngine,
    MediaSetBrowserEngine,
)

BASE = "/media-set-browser-interaction"


@pytest.fixture(autouse=True)
def reset_engines():
    for engine in (MediaSetBrowserEngine, MediaInteractionEngine, AudioTranscriptionEngine):
        engine.reset()
    yield
    for engine in (MediaSetBrowserEngine, MediaInteractionEngine, AudioTranscriptionEngine):
        engine.reset()


@pytest.fixture
def client():
    """轻量 app：只挂目标 router + 异常处理器。

    不用 conftest 的全量 app fixture——那会走完整启动链（含 bundle allowlist
    加载依赖 `.aos-recovery-20260913/state`，该目录已不存在，与本文件无关）。
    门面契约测试只需要 router→engine 一层。
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aos_api.errors import register_exception_handlers
    from aos_api.routers.media_set_browser_interaction import router

    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def api(client):
    """带认证覆写的客户端 + image/audio 两个真实 MediaSet（引擎为进程内单例）。"""
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="media-router-test",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer", "admin"],
        markings=["public"],
        token_kind="test",
    )
    store = get_media_set_store()
    image_set = store.create(name="路由验收-图像集", set_type="image")
    audio_set = store.create(name="路由验收-音频集", set_type="audio")
    try:
        yield client, image_set, audio_set
    finally:
        client.app.dependency_overrides.pop(require_principal, None)


def _create_item(client, media_set_id: str, *, kind: str, path: str) -> dict:
    resp = client.post(
        f"{BASE}/items",
        json={
            "media_set_id": media_set_id,
            "file_name": path,
            "file_type": kind,
            "file_size": 2048,
            "metadata": {"path": path},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_browser_item_lifecycle(api):
    client, image_set, _ = api
    ms_id = image_set.id

    # POST /items —— 引擎原先缺 create_item（AttributeError ⇒ 500）
    item = _create_item(client, ms_id, kind="image", path="frame.png")
    item_id = item["id"]
    assert item["name"] == "frame.png" and item["type"] == "image"

    # GET /items
    resp = client.get(f"{BASE}/items", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["count"] == 1

    # GET /items/search
    resp = client.get(f"{BASE}/items/search", params={"media_set_id": ms_id, "query": "frame"})
    assert resp.status_code == 200 and resp.json()["count"] == 1

    # GET /items/{item_id} —— 原先少传 media_set_id（TypeError ⇒ 500）
    resp = client.get(f"{BASE}/items/{item_id}", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["id"] == item_id

    # GET /items/{item_id}/preview —— 同族
    resp = client.get(f"{BASE}/items/{item_id}/preview", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["item_id"] == item_id

    # GET /items/{item_id}/estimate-language —— 原先少传 media_set_id 且返回裸 str
    resp = client.get(f"{BASE}/items/{item_id}/estimate-language", params={"media_set_id": ms_id})
    assert resp.status_code == 200
    assert resp.json() == {"itemId": item_id, "language": "en"}

    # DELETE /items/{item_id} —— 同族
    resp = client.delete(f"{BASE}/items/{item_id}", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json() == {"deleted": item_id}

    # ★ 回归 ①：delete 后 browse 不得回显已删项（缓存失效）
    resp = client.get(f"{BASE}/items", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["count"] == 0

    # ★ 回归 ②：not-found 必须是 404（原先 mapper 只认裸 "NOT_FOUND"，降级为 400）
    resp = client.get(f"{BASE}/items/{item_id}", params={"media_set_id": ms_id})
    assert resp.status_code == 404
    assert resp.json()["code"] == "ITEM_NOT_FOUND"


def test_missing_media_set_is_404(api):
    """★ 回归 ②：缺失 MediaSet 曾因 mapper 死分支返回 400。"""
    client, _, _ = api
    resp = client.get(f"{BASE}/items", params={"media_set_id": "ms-does-not-exist"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "MEDIA_SET_NOT_FOUND"


def test_incompatible_kind_is_400_not_500(api):
    """★ 回归 ③：kind 与 MediaSet 类型不匹配必须 400，且不留孤儿引用。"""
    client, image_set, _ = api
    ms_id = image_set.id

    resp = client.post(
        f"{BASE}/items",
        json={
            "media_set_id": ms_id,
            "file_name": "voice.mp3",
            "file_type": "audio",
            "file_size": 1024,
            "metadata": {"path": "voice.mp3"},
        },
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "TYPE_MISMATCH"

    # 被拒的 create 不得污染集合，也不得在引用库里留下孤儿
    resp = client.get(f"{BASE}/items", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["count"] == 0
    assert all(ref.path != "voice.mp3" for ref in get_media_store().list_all())


def test_view_annotation_and_unsupported_fields(api):
    client, image_set, _ = api
    ms_id = image_set.id
    item = _create_item(client, ms_id, kind="image", path="frame.png")

    # POST /views
    resp = client.post(
        f"{BASE}/views",
        json={"media_set_id": ms_id, "item_id": item["id"], "view_type": "image"},
    )
    assert resp.status_code == 200, resp.text
    view_id = resp.json()["id"]

    # GET /views/{view_id}
    assert client.get(f"{BASE}/views/{view_id}").status_code == 200

    # PUT /views/{view_id} —— 支持字段
    resp = client.put(f"{BASE}/views/{view_id}", json={"brightness": 1.2, "zoom": 2.0})
    assert resp.status_code == 200
    assert resp.json()["state"]["brightness"] == pytest.approx(1.2)
    assert resp.json()["state"]["zoom"] == pytest.approx(2.0)

    # PUT /views/{view_id} —— 不支持字段必须显式 400（原先静默丢弃）
    resp = client.put(f"{BASE}/views/{view_id}", json={"pan_x": 10.0})
    assert resp.status_code == 400
    assert resp.json()["code"] == "UNSUPPORTED_VIEW_FIELD"

    # POST /views/{view_id}/annotations —— 原先传 dict（TypeError ⇒ 500）
    resp = client.post(
        f"{BASE}/views/{view_id}/annotations",
        json={"x": 1.0, "y": 2.0, "width": 10.0, "height": 20.0, "content": "here"},
    )
    assert resp.status_code == 200, resp.text
    annotation_id = resp.json()["id"]
    assert resp.json()["content"] == "here"

    # GET /views/{view_id}/annotations
    resp = client.get(f"{BASE}/views/{view_id}/annotations")
    assert resp.status_code == 200 and resp.json()["count"] == 1

    # DELETE /views/{view_id}/annotations/{annotation_id}
    resp = client.delete(f"{BASE}/views/{view_id}/annotations/{annotation_id}")
    assert resp.status_code == 200

    # DELETE /views/{view_id}
    assert client.delete(f"{BASE}/views/{view_id}").status_code == 200
    assert client.get(f"{BASE}/views/{view_id}").status_code == 404


def test_transcription_job_contract(api):
    client, _, audio_set = api
    ms_id = audio_set.id
    item = _create_item(client, ms_id, kind="audio", path="voice.zh.mp3")

    # POST /transcription-jobs —— 原先 body.item_id 错位绑定到 media_set_id
    # （类型兼容不抛错，400 报文完全误导），且默认 language="auto" 不在支持集
    resp = client.post(
        f"{BASE}/transcription-jobs",
        json={"media_set_id": ms_id, "item_id": item["id"], "language": "zh"},
    )
    assert resp.status_code == 200, resp.text
    job = resp.json()
    assert job["media_set_id"] == ms_id and job["item_id"] == item["id"]
    assert job["status"] == "completed"
    job_id = job["id"]

    # 默认语言必须是引擎支持集内的值（不能再是 "auto"）
    resp = client.post(
        f"{BASE}/transcription-jobs",
        json={"media_set_id": ms_id, "item_id": item["id"]},
    )
    assert resp.status_code == 200 and resp.json()["language"] == "en"

    # 不支持的语言仍应被拒（引擎语义未被路由改写）
    resp = client.post(
        f"{BASE}/transcription-jobs",
        json={"media_set_id": ms_id, "item_id": item["id"], "language": "auto"},
    )
    assert resp.status_code == 400

    # GET /transcription-jobs/{job_id}
    assert client.get(f"{BASE}/transcription-jobs/{job_id}").status_code == 200

    # GET /transcription-jobs
    resp = client.get(f"{BASE}/transcription-jobs", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["count"] == 2

    # GET /transcription-jobs/{job_id}/transcript —— 原先返回裸 str（契约漂移）
    resp = client.get(f"{BASE}/transcription-jobs/{job_id}/transcript")
    assert resp.status_code == 200
    assert resp.json()["jobId"] == job_id
    assert isinstance(resp.json()["transcript"], str)

    # POST /transcription-jobs/{job_id}/cancel —— 已完成任务不可取消
    resp = client.post(f"{BASE}/transcription-jobs/{job_id}/cancel")
    assert resp.status_code == 400

    # estimate_language 走确定性后缀判定（.zh.mp3 → zh）
    resp = client.get(f"{BASE}/items/{item['id']}/estimate-language", params={"media_set_id": ms_id})
    assert resp.status_code == 200 and resp.json()["language"] == "zh"
