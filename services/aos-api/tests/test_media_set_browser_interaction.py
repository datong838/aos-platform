"""W2-#3 · MediaSet 浏览器交互引擎单元测试。"""
from __future__ import annotations

import pytest

from aos_api.media_reference import MediaReferenceStore
from aos_api.media_set import MediaSetStore
from aos_api.media_set_browser_interaction import (
    AudioTranscriptionEngine,
    BrowserError,
    InteractionError,
    MediaInteractionEngine,
    MediaSetBrowserEngine,
    TranscriptionError,
)


@pytest.fixture(autouse=True)
def reset_engines():
    MediaSetBrowserEngine.reset()
    MediaInteractionEngine.reset()
    AudioTranscriptionEngine.reset()
    yield
    MediaSetBrowserEngine.reset()
    MediaInteractionEngine.reset()
    AudioTranscriptionEngine.reset()


@pytest.fixture
def setup_media(monkeypatch):
    ref_store = MediaReferenceStore()
    r1 = ref_store.register(kind="image", storage="local", bucket="test", path="img/a.png", size_bytes=100)
    r2 = ref_store.register(kind="image", storage="local", bucket="test", path="img/b.png", size_bytes=200)
    r3 = ref_store.register(kind="audio", storage="local", bucket="test", path="audio/sound.mp3", size_bytes=500)
    r4 = ref_store.register(kind="document", storage="local", bucket="test", path="doc/readme.pdf", size_bytes=300)
    r5 = ref_store.register(kind="audio", storage="local", bucket="test", path="audio/speech.zh.mp3", size_bytes=600)
    r6 = ref_store.register(kind="audio", storage="local", bucket="test", path="audio/speech.ja.mp3", size_bytes=700)

    import aos_api.media_reference as mr_mod
    orig_ref_get = mr_mod.get_store
    mr_mod.get_store = lambda: ref_store

    ms_store = MediaSetStore()
    import aos_api.media_set as ms_mod
    orig_ms_get = ms_mod.get_store
    ms_mod.get_store = lambda: ms_store

    orig_ms_get_media = ms_mod.get_media_store
    ms_mod.get_media_store = lambda: ref_store

    ms_images = ms_store.create("images", "image")
    ms_store.add_media(ms_images.id, r1.id)
    ms_store.add_media(ms_images.id, r2.id)

    ms_audio = ms_store.create("audio", "audio")
    ms_store.add_media(ms_audio.id, r3.id)
    ms_store.add_media(ms_audio.id, r5.id)
    ms_store.add_media(ms_audio.id, r6.id)

    ms_docs = ms_store.create("docs", "document")
    ms_store.add_media(ms_docs.id, r4.id)

    yield ms_store, ref_store, ms_images.id, ms_audio.id, ms_docs.id, r1.id, r2.id, r3.id, r4.id, r5.id, r6.id
    mr_mod.get_store = orig_ref_get
    ms_mod.get_store = orig_ms_get
    ms_mod.get_media_store = orig_ms_get_media


# --- MediaSetBrowserEngine 测试 ---


class TestMediaSetBrowserEngine:
    def setup_method(self):
        MediaSetBrowserEngine.reset()

    def test_singleton_instance(self):
        engine1 = MediaSetBrowserEngine()
        engine2 = MediaSetBrowserEngine()
        assert engine1 is engine2

    def test_browse_items_empty(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        items = engine.browse_items(ms_id)
        assert isinstance(items, list)

    def test_browse_items_by_file_type(self, setup_media):
        _, _, ms_images, ms_audio, ms_docs, r1_id, _, r3_id, r4_id, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        images = engine.browse_items(ms_images, file_type="image")
        assert len(images) == 2
        assert images[0].media_ref_id == r1_id

        audio = engine.browse_items(ms_audio, file_type="audio")
        assert len(audio) == 3
        assert images[0].media_ref_id != r3_id

        docs = engine.browse_items(ms_docs, file_type="document")
        assert len(docs) == 1
        assert docs[0].media_ref_id == r4_id

    def test_browse_items_invalid_media_set(self):
        engine = MediaSetBrowserEngine()
        with pytest.raises(BrowserError) as exc:
            engine.browse_items("invalid-ms")
        assert exc.value.code == "MEDIA_SET_NOT_FOUND"

    def test_get_item_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        item = engine.get_item(ms_id, r1_id)
        assert item.media_ref_id == r1_id
        assert item.name == "a.png"

    def test_get_item_not_found(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        with pytest.raises(BrowserError) as exc:
            engine.get_item(ms_id, "ghost-id")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_search_items(self, setup_media):
        _, _, ms_images, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        results = engine.search_items(ms_images, "a.png")
        assert len(results) >= 1

    def test_search_items_no_results(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        results = engine.search_items(ms_id, "nonexistent")
        assert len(results) == 0

    def test_delete_item_success(self, setup_media):
        ms_store, _, ms_id, _, _, r1_id, r2_id, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        engine.delete_item(ms_id, r1_id)
        ms = ms_store.get(ms_id)
        assert r1_id not in ms.media_ref_ids
        assert r2_id in ms.media_ref_ids

    def test_delete_item_not_found(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        with pytest.raises(BrowserError) as exc:
            engine.delete_item(ms_id, "ghost-id")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_get_item_preview_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        preview = engine.get_item_preview(ms_id, r1_id)
        assert preview["item_id"] == r1_id
        assert "preview_url" in preview

    def test_get_item_preview_not_found(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        with pytest.raises(BrowserError) as exc:
            engine.get_item_preview(ms_id, "ghost-id")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_invalid_file_type(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()
        items = engine.browse_items(ms_id, file_type="invalid_type")
        assert len(items) == 0

    def test_fifo_eviction(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaSetBrowserEngine()

        for i in range(201):
            engine.browse_items(ms_id, file_type=f"type_{i}")

        assert len(engine._cache) == 200
        assert f"{ms_id}:type_0" not in engine._cache
        assert f"{ms_id}:type_200" in engine._cache


# --- MediaInteractionEngine 测试 ---


class TestMediaInteractionEngine:
    def setup_method(self):
        MediaInteractionEngine.reset()

    def test_singleton_instance(self):
        engine1 = MediaInteractionEngine()
        engine2 = MediaInteractionEngine()
        assert engine1 is engine2

    def test_create_view_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        assert view.id is not None
        assert view.media_set_id == ms_id
        assert view.item_id == r1_id
        assert view.view_type == "image"

    def test_create_view_invalid_item(self, setup_media):
        _, _, ms_id, _, _, _, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        with pytest.raises(InteractionError) as exc:
            engine.create_view(ms_id, "ghost-id", "image")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_create_view_invalid_type(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        with pytest.raises(InteractionError) as exc:
            engine.create_view(ms_id, r1_id, "invalid_type")
        assert exc.value.code == "INVALID_TYPE"

    def test_get_view_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        retrieved = engine.get_view(view.id)
        assert retrieved.id == view.id

    def test_get_view_not_found(self):
        engine = MediaInteractionEngine()
        with pytest.raises(InteractionError) as exc:
            engine.get_view("ghost-view")
        assert exc.value.code == "VIEW_NOT_FOUND"

    def test_update_view_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        updated = engine.update_view(view.id, brightness=1.5)
        assert updated.state.brightness == 1.5

    def test_update_view_not_found(self):
        engine = MediaInteractionEngine()
        with pytest.raises(InteractionError) as exc:
            engine.update_view("ghost-view", brightness=1.5)
        assert exc.value.code == "VIEW_NOT_FOUND"

    def test_update_view_annotations(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        annotation = engine.add_annotation(view.id, 10.0, 20.0, 100.0, 80.0, "测试注释")
        annotations = engine.get_annotations(view.id)
        assert len(annotations) == 1
        assert annotations[0].content == "测试注释"

    def test_delete_view_success(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        engine.delete_view(view.id)
        with pytest.raises(InteractionError):
            engine.get_view(view.id)

    def test_delete_view_not_found(self):
        engine = MediaInteractionEngine()
        with pytest.raises(InteractionError) as exc:
            engine.delete_view("ghost-view")
        assert exc.value.code == "VIEW_NOT_FOUND"

    def test_get_annotations(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        annotations = engine.get_annotations(view.id)
        assert isinstance(annotations, list)
        assert len(annotations) == 0

    def test_add_annotation(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        annotation = engine.add_annotation(view.id, 0.0, 0.0, 50.0, 50.0, "标注")
        assert annotation.id is not None
        assert annotation.content == "标注"

    def test_delete_annotation(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        annotation = engine.add_annotation(view.id, 0.0, 0.0, 50.0, 50.0, "标注")
        engine.delete_annotation(view.id, annotation.id)
        annotations = engine.get_annotations(view.id)
        assert len(annotations) == 0

    def test_delete_annotation_not_found(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        with pytest.raises(InteractionError) as exc:
            engine.delete_annotation(view.id, "ghost-annotation")
        assert exc.value.code == "ANNOTATION_NOT_FOUND"

    def test_view_state_fields(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()
        view = engine.create_view(ms_id, r1_id, "image")
        assert view.state.brightness == 1.0
        assert view.state.contrast == 1.0
        assert view.state.zoom == 1.0

        updated = engine.update_view(view.id, brightness=1.2, contrast=0.8, zoom=2.0)
        assert updated.state.brightness == 1.2
        assert updated.state.contrast == 0.8
        assert updated.state.zoom == 2.0

    def test_fifo_eviction(self, setup_media):
        _, _, ms_id, _, _, r1_id, _, _, _, _, _ = setup_media
        engine = MediaInteractionEngine()

        views = []
        for i in range(201):
            view = engine.create_view(ms_id, r1_id, "image")
            views.append(view.id)

        assert len(engine._views) == 200
        assert views[0] not in engine._views
        assert views[200] in engine._views


# --- AudioTranscriptionEngine 测试 ---


class TestAudioTranscriptionEngine:
    def setup_method(self):
        AudioTranscriptionEngine.reset()

    def test_singleton_instance(self):
        engine1 = AudioTranscriptionEngine()
        engine2 = AudioTranscriptionEngine()
        assert engine1 is engine2

    def test_create_job_success(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        assert job.id is not None
        assert job.status == "completed"
        assert job.transcript != ""

    def test_create_job_invalid_item(self, setup_media):
        _, _, _, ms_audio, _, _, _, _, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.create_job(ms_audio, "ghost-id", "en")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_create_job_invalid_language(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.create_job(ms_audio, r3_id, "invalid-lang")
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_get_job_success(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        retrieved = engine.get_job(job.id)
        assert retrieved.id == job.id

    def test_get_job_not_found(self):
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.get_job("ghost-job")
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_list_jobs(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        engine.create_job(ms_audio, r3_id, "en")
        engine.create_job(ms_audio, r3_id, "zh")
        jobs = engine.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_by_status(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        engine.create_job(ms_audio, r3_id, "en")
        jobs = engine.list_jobs(status="completed")
        assert len(jobs) >= 1
        jobs = engine.list_jobs(status="pending")
        assert len(jobs) == 0

    def test_list_jobs_by_media_set(self, setup_media):
        _, _, ms_images, ms_audio, _, r1_id, _, _, _, _, r6_id = setup_media
        engine = AudioTranscriptionEngine()
        engine.create_job(ms_audio, r6_id, "en")
        engine.create_job(ms_images, r1_id, "en")
        jobs = engine.list_jobs(media_set_id=ms_audio)
        assert len(jobs) == 1

    def test_cancel_job_success(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        with pytest.raises(TranscriptionError) as exc:
            engine.cancel_job(job.id)
        assert exc.value.code == "CANNOT_CANCEL_COMPLETED"

    def test_cancel_job_not_found(self):
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.cancel_job("ghost-job")
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_cancel_job_completed(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        with pytest.raises(TranscriptionError) as exc:
            engine.cancel_job(job.id)
        assert exc.value.code == "CANNOT_CANCEL_COMPLETED"

    def test_get_transcript_success(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        transcript = engine.get_transcript(job.id)
        assert isinstance(transcript, str)
        assert transcript != ""

    def test_get_transcript_not_found(self):
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.get_transcript("ghost-job")
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_get_transcript_pending(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        job = engine.create_job(ms_audio, r3_id, "en")
        job.status = "pending"
        with pytest.raises(TranscriptionError) as exc:
            engine.get_transcript(job.id)
        assert exc.value.code == "TRANSCRIPT_NOT_READY"

    def test_estimate_language(self, setup_media):
        _, _, _, ms_audio, _, _, _, _, _, r5_id, r6_id = setup_media
        engine = AudioTranscriptionEngine()
        lang_zh = engine.estimate_language(ms_audio, r5_id)
        assert lang_zh == "zh"
        lang_ja = engine.estimate_language(ms_audio, r6_id)
        assert lang_ja == "ja"

    def test_estimate_language_not_found(self, setup_media):
        _, _, _, ms_audio, _, _, _, _, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()
        with pytest.raises(TranscriptionError) as exc:
            engine.estimate_language(ms_audio, "ghost-id")
        assert exc.value.code == "ITEM_NOT_FOUND"

    def test_fifo_eviction(self, setup_media):
        _, _, _, ms_audio, _, _, _, r3_id, _, _, _ = setup_media
        engine = AudioTranscriptionEngine()

        jobs = []
        for i in range(201):
            job = engine.create_job(ms_audio, r3_id, "en")
            jobs.append(job.id)

        assert len(engine._jobs) == 200
        assert jobs[0] not in engine._jobs
        assert jobs[200] in engine._jobs