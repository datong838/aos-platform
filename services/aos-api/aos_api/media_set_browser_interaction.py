"""W2-#3 · MediaSet 浏览器交互引擎。"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

import importlib


def _get_media_store():
    mod = importlib.import_module(".media_reference", "aos_api")
    return mod.get_store()


def _get_media_set_store():
    mod = importlib.import_module(".media_set", "aos_api")
    return mod.get_store()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "msi-" + uuid.uuid4().hex[:12]


class BrowserItem(BaseModel):
    id: str
    media_ref_id: str
    name: str
    type: str
    size_bytes: int
    created_at: str


class BrowserError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MediaSetBrowserEngine:
    _instance: MediaSetBrowserEngine | None = None
    _lock = threading.Lock()
    _max_cache = 200

    def __new__(cls) -> MediaSetBrowserEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._cache: dict[str, list[BrowserItem]] = {}
        self._cache_order: list[str] = []
        self._lock = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _evict_if_needed(self) -> None:
        while len(self._cache) > self._max_cache:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]

    def _update_cache(self, key: str, items: list[BrowserItem]) -> None:
        with self._lock:
            if key in self._cache_order:
                self._cache_order.remove(key)
            self._cache_order.append(key)
            self._cache[key] = items
            self._evict_if_needed()

    def browse_items(self, media_set_id: str, file_type: str | None = None) -> list[BrowserItem]:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise BrowserError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        ref_store = _get_media_store()
        items = []
        for ref_id in ms.media_ref_ids:
            try:
                ref = ref_store.get(ref_id)
            except Exception:
                continue
            if file_type and ref.kind != file_type:
                continue
            items.append(BrowserItem(
                id=_new_id(), media_ref_id=ref.id, name=ref.path.split("/")[-1],
                type=ref.kind, size_bytes=ref.size_bytes, created_at=ref.created_at))
        cache_key = f"{media_set_id}:{file_type or 'all'}"
        self._update_cache(cache_key, items)
        return items

    def get_item(self, media_set_id: str, item_id: str) -> BrowserItem:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise BrowserError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        ref_store = _get_media_store()
        for ref_id in ms.media_ref_ids:
            try:
                ref = ref_store.get(ref_id)
            except Exception:
                continue
            if ref.id == item_id:
                return BrowserItem(
                    id=item_id, media_ref_id=ref.id, name=ref.path.split("/")[-1],
                    type=ref.kind, size_bytes=ref.size_bytes, created_at=ref.created_at)
        raise BrowserError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")

    def search_items(self, media_set_id: str, query: str) -> list[BrowserItem]:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise BrowserError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        ref_store = _get_media_store()
        query_lower = query.lower()
        items = []
        for ref_id in ms.media_ref_ids:
            try:
                ref = ref_store.get(ref_id)
            except Exception:
                continue
            if query_lower in ref.path.lower() or query_lower in ref.id.lower():
                items.append(BrowserItem(
                    id=_new_id(), media_ref_id=ref.id, name=ref.path.split("/")[-1],
                    type=ref.kind, size_bytes=ref.size_bytes, created_at=ref.created_at))
        return items

    def delete_item(self, media_set_id: str, item_id: str) -> None:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise BrowserError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        ref_store = _get_media_store()
        if item_id not in ms.media_ref_ids:
            raise BrowserError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")
        ms_store.remove_media(media_set_id, item_id)
        try:
            ref_store.delete(item_id)
        except Exception:
            pass
        with self._lock:
            for key in list(self._cache.keys()):
                if media_set_id in key:
                    del self._cache[key]
                    self._cache_order.remove(key)

    def get_item_preview(self, media_set_id: str, item_id: str) -> dict[str, Any]:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise BrowserError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        if item_id not in ms.media_ref_ids:
            raise BrowserError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")
        ref_store = _get_media_store()
        try:
            ref = ref_store.get(item_id)
        except Exception as exc:
            raise BrowserError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在") from exc
        return {
            "item_id": item_id, "preview_url": ref_store.get_signed_url(item_id),
            "name": ref.path.split("/")[-1], "type": ref.kind, "mime": ref.mime}


class ViewAnnotation(BaseModel):
    id: str
    x: float
    y: float
    width: float
    height: float
    content: str
    created_at: str = Field(default_factory=_now)


class ViewState(BaseModel):
    brightness: float = 1.0
    contrast: float = 1.0
    zoom: float = 1.0


class MediaView(BaseModel):
    id: str
    media_set_id: str
    item_id: str
    view_type: Literal["image", "video", "audio"]
    annotations: list[ViewAnnotation] = Field(default_factory=list)
    state: ViewState = Field(default_factory=ViewState)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class InteractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MediaInteractionEngine:
    _instance: MediaInteractionEngine | None = None
    _lock = threading.Lock()
    _max_cache = 200

    def __new__(cls) -> MediaInteractionEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._views: dict[str, MediaView] = {}
        self._views_order: list[str] = []
        self._lock = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _evict_if_needed(self) -> None:
        while len(self._views) > self._max_cache:
            oldest = self._views_order.pop(0)
            del self._views[oldest]

    def _update_view(self, view_id: str, view: MediaView) -> None:
        if view_id in self._views_order:
            self._views_order.remove(view_id)
        self._views_order.append(view_id)
        self._views[view_id] = view
        self._evict_if_needed()

    def create_view(self, media_set_id: str, item_id: str, view_type: str) -> MediaView:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise InteractionError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        if item_id not in ms.media_ref_ids:
            raise InteractionError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")
        if view_type not in {"image", "video", "audio"}:
            raise InteractionError("INVALID_TYPE", f"无效视图类型 {view_type!r}")
        view = MediaView(id=_new_id(), media_set_id=media_set_id, item_id=item_id, view_type=view_type)
        with self._lock:
            self._update_view(view.id, view)
        return view

    def get_view(self, view_id: str) -> MediaView:
        with self._lock:
            if view_id not in self._views:
                raise InteractionError("VIEW_NOT_FOUND", f"视图 {view_id!r} 不存在")
            return self._views[view_id]

    def update_view(self, view_id: str, **kwargs: Any) -> MediaView:
        with self._lock:
            if view_id not in self._views:
                raise InteractionError("VIEW_NOT_FOUND", f"视图 {view_id!r} 不存在")
            view = self._views[view_id]
            if "brightness" in kwargs:
                view.state.brightness = kwargs["brightness"]
            if "contrast" in kwargs:
                view.state.contrast = kwargs["contrast"]
            if "zoom" in kwargs:
                view.state.zoom = kwargs["zoom"]
            view.updated_at = _now()
            self._update_view(view_id, view)
            return view

    def delete_view(self, view_id: str) -> None:
        with self._lock:
            if view_id not in self._views:
                raise InteractionError("VIEW_NOT_FOUND", f"视图 {view_id!r} 不存在")
            del self._views[view_id]
            self._views_order.remove(view_id)

    def get_annotations(self, view_id: str) -> list[ViewAnnotation]:
        view = self.get_view(view_id)
        return view.annotations

    def add_annotation(self, view_id: str, x: float, y: float, width: float, height: float, content: str) -> ViewAnnotation:
        with self._lock:
            if view_id not in self._views:
                raise InteractionError("VIEW_NOT_FOUND", f"视图 {view_id!r} 不存在")
            annotation = ViewAnnotation(id=_new_id(), x=x, y=y, width=width, height=height, content=content)
            view = self._views[view_id]
            view.annotations.append(annotation)
            view.updated_at = _now()
            self._update_view(view_id, view)
            return annotation

    def delete_annotation(self, view_id: str, annotation_id: str) -> None:
        with self._lock:
            if view_id not in self._views:
                raise InteractionError("VIEW_NOT_FOUND", f"视图 {view_id!r} 不存在")
            view = self._views[view_id]
            idx = None
            for i, ann in enumerate(view.annotations):
                if ann.id == annotation_id:
                    idx = i
                    break
            if idx is None:
                raise InteractionError("ANNOTATION_NOT_FOUND", f"注释 {annotation_id!r} 不存在")
            view.annotations.pop(idx)
            view.updated_at = _now()
            self._update_view(view_id, view)


class TranscriptionJob(BaseModel):
    id: str
    media_set_id: str
    item_id: str
    language: str
    status: Literal["pending", "processing", "completed", "cancelled", "failed"] = "pending"
    transcript: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class TranscriptionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class AudioTranscriptionEngine:
    _instance: AudioTranscriptionEngine | None = None
    _lock = threading.Lock()
    _max_jobs = 200
    _SUPPORTED_LANGUAGES = {"zh", "en", "ja", "ko", "fr", "de"}

    def __new__(cls) -> AudioTranscriptionEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._jobs: dict[str, TranscriptionJob] = {}
        self._jobs_order: list[str] = []
        self._lock = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _evict_if_needed(self) -> None:
        while len(self._jobs) > self._max_jobs:
            oldest = self._jobs_order.pop(0)
            del self._jobs[oldest]

    def _update_job(self, job_id: str, job: TranscriptionJob) -> None:
        with self._lock:
            if job_id in self._jobs_order:
                self._jobs_order.remove(job_id)
            self._jobs_order.append(job_id)
            self._jobs[job_id] = job
            self._evict_if_needed()

    def create_job(self, media_set_id: str, item_id: str, language: str = "en") -> TranscriptionJob:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise TranscriptionError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        if item_id not in ms.media_ref_ids:
            raise TranscriptionError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")
        if language not in self._SUPPORTED_LANGUAGES:
            raise TranscriptionError("INVALID_LANGUAGE", f"不支持的语言 {language!r}")
        job = TranscriptionJob(id=_new_id(), media_set_id=media_set_id, item_id=item_id, language=language, status="processing")
        self._update_job(job.id, job)
        job.status = "completed"
        job.transcript = f"[模拟转录结果] 语言: {language}"
        job.updated_at = _now()
        self._update_job(job.id, job)
        return job

    def get_job(self, job_id: str) -> TranscriptionJob:
        with self._lock:
            if job_id not in self._jobs:
                raise TranscriptionError("JOB_NOT_FOUND", f"任务 {job_id!r} 不存在")
            return self._jobs[job_id]

    def list_jobs(self, status: str | None = None, media_set_id: str | None = None) -> list[TranscriptionJob]:
        with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            if media_set_id:
                jobs = [j for j in jobs if j.media_set_id == media_set_id]
            return jobs

    def cancel_job(self, job_id: str) -> TranscriptionJob:
        with self._lock:
            if job_id not in self._jobs:
                raise TranscriptionError("JOB_NOT_FOUND", f"任务 {job_id!r} 不存在")
            job = self._jobs[job_id]
            if job.status == "completed":
                raise TranscriptionError("CANNOT_CANCEL_COMPLETED", "已完成的任务无法取消")
            job.status = "cancelled"
            job.updated_at = _now()
            self._update_job(job_id, job)
            return job

    def get_transcript(self, job_id: str) -> str:
        job = self.get_job(job_id)
        if job.status != "completed":
            raise TranscriptionError("TRANSCRIPT_NOT_READY", "转录未完成")
        return job.transcript

    def estimate_language(self, media_set_id: str, item_id: str) -> str:
        ms_store = _get_media_set_store()
        try:
            ms = ms_store.get(media_set_id)
        except Exception as exc:
            raise TranscriptionError("MEDIA_SET_NOT_FOUND", f"MediaSet {media_set_id!r} 不存在") from exc
        if item_id not in ms.media_ref_ids:
            raise TranscriptionError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在")
        ref_store = _get_media_store()
        try:
            ref = ref_store.get(item_id)
        except Exception as exc:
            raise TranscriptionError("ITEM_NOT_FOUND", f"项目 {item_id!r} 不存在") from exc
        if ref.path.endswith(".zh.mp3"):
            return "zh"
        if ref.path.endswith(".ja.mp3"):
            return "ja"
        return "en"


def get_browser_engine() -> MediaSetBrowserEngine:
    return MediaSetBrowserEngine()


def get_interaction_engine() -> MediaInteractionEngine:
    return MediaInteractionEngine()


def get_transcription_engine() -> AudioTranscriptionEngine:
    return AudioTranscriptionEngine()
