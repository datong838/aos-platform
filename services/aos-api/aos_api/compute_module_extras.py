"""W2-AT · Compute Module Extras 引擎（#155 #156 #157）."""
from __future__ import annotations

import random
import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_CONTAINER_CONFIGS = 200
_MAX_SCALE_POLICIES = 200
_MAX_ALERTS = 200
_MAX_SCAFFOLD_TEMPLATES = 200
_MAX_GENERATED_SCAFFOLDS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class ContainerConfigError(Exception):
    """容器标签页配置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScaleToZeroError(Exception):
    """缩容至零与冷启动告警错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DevScaffoldError(Exception):
    """本地开发脚手架错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #155 Container Config ════════════════════

class ContainerTabConfig(BaseModel):
    tab_config_id: str = ""
    module_id: str
    tab_name: str  # configure | query | overview
    config_data: dict = {}
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_TAB_NAMES = {"configure", "query", "overview"}
_VALID_CONFIG_STATUSES = {"active", "inactive"}


class ContainerConfigEngine:
    """容器标签页配置引擎."""

    _instance: ContainerConfigEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._configs: dict[str, ContainerTabConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ContainerConfigEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_config(self, config: ContainerTabConfig) -> ContainerTabConfig:
        if not config.module_id or not config.module_id.strip():
            raise ContainerConfigError("MISSING_MODULE", "module_id is required")
        if not config.tab_name or not config.tab_name.strip():
            raise ContainerConfigError("MISSING_TAB_NAME", "tab_name is required")
        if config.tab_name not in _VALID_TAB_NAMES:
            raise ContainerConfigError(
                "INVALID_TAB_NAME", f"tab_name must be one of {_VALID_TAB_NAMES}")
        if config.status not in _VALID_CONFIG_STATUSES:
            raise ContainerConfigError(
                "INVALID_STATUS", f"status must be one of {_VALID_CONFIG_STATUSES}")

        now = _utcnow()
        cid = f"tc-{uuid.uuid4().hex[:8]}"
        stored = config.model_copy(update={
            "tab_config_id": cid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._configs) >= _MAX_CONTAINER_CONFIGS:
                oldest = min(self._configs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._configs[oldest.tab_config_id]
            self._configs[cid] = stored
        return stored

    def get_config(self, tab_config_id: str) -> ContainerTabConfig:
        with self._lock:
            config = self._configs.get(tab_config_id)
        if config is None:
            raise ContainerConfigError(
                "NOT_FOUND", f"config {tab_config_id} not found")
        return config

    def list_configs(
        self,
        module_id: str | None = None,
        tab: str | None = None,
        status: str | None = None,
    ) -> list[ContainerTabConfig]:
        with self._lock:
            results = list(self._configs.values())
        if module_id:
            results = [c for c in results if c.module_id == module_id]
        if tab:
            results = [c for c in results if c.tab_name == tab]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results,
                      key=lambda c: c.created_at or datetime.min,
                      reverse=True)

    def update_config(self, tab_config_id: str,
                      updates: dict) -> ContainerTabConfig:
        if "status" in updates and updates["status"] not in _VALID_CONFIG_STATUSES:
            raise ContainerConfigError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_CONFIG_STATUSES}")
        if "tab_name" in updates and updates["tab_name"] not in _VALID_TAB_NAMES:
            raise ContainerConfigError(
                "INVALID_TAB_NAME",
                f"tab_name must be one of {_VALID_TAB_NAMES}")

        with self._lock:
            config = self._configs.get(tab_config_id)
            if config is None:
                raise ContainerConfigError(
                    "NOT_FOUND", f"config {tab_config_id} not found")
            data = config.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = ContainerTabConfig(**data)
            self._configs[tab_config_id] = updated
        return updated

    def delete_config(self, tab_config_id: str) -> None:
        with self._lock:
            if tab_config_id not in self._configs:
                raise ContainerConfigError(
                    "NOT_FOUND", f"config {tab_config_id} not found")
            del self._configs[tab_config_id]

    def get_module_overview(self, module_id: str) -> dict:
        if not module_id or not module_id.strip():
            raise ContainerConfigError("MISSING_MODULE", "module_id is required")
        configs = self.list_configs(module_id=module_id)
        overview: dict[str, ContainerTabConfig | None] = {}
        for tab in _VALID_TAB_NAMES:
            tab_configs = [c for c in configs if c.tab_name == tab]
            overview[tab] = tab_configs[0] if tab_configs else None
        return overview


_container_config_engine: ContainerConfigEngine | None = None
_container_config_engine_lock = threading.Lock()


def get_container_config_engine() -> ContainerConfigEngine:
    global _container_config_engine
    if _container_config_engine is None:
        with _container_config_engine_lock:
            if _container_config_engine is None:
                _container_config_engine = ContainerConfigEngine.get_instance()
    return _container_config_engine


# ════════════════════ #156 Scale To Zero ════════════════════

class ScaleToZeroPolicy(BaseModel):
    policy_id: str = ""
    module_id: str
    idle_timeout_seconds: int = 300
    min_replicas: int = 0
    scale_up_delay_seconds: int = 0
    status: str = "active"  # active | inactive
    created_at: datetime | None = None


class ColdStartAlert(BaseModel):
    alert_id: str = ""
    module_id: str
    alert_type: str  # cold_start | scale_up
    wait_duration_ms: int = 0
    severity: str = "info"  # info | warning
    cleared: bool = False
    created_at: datetime | None = None


_VALID_SCALE_STATUSES = {"active", "inactive"}
_VALID_ALERT_TYPES = {"cold_start", "scale_up"}
_VALID_SEVERITIES = {"info", "warning"}


class ScaleToZeroEngine:
    """缩容至零与冷启动告警引擎."""

    _instance: ScaleToZeroEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._policies: dict[str, ScaleToZeroPolicy] = {}
        self._alerts: dict[str, ColdStartAlert] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ScaleToZeroEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_policy(self, policy: ScaleToZeroPolicy) -> ScaleToZeroPolicy:
        if not policy.module_id or not policy.module_id.strip():
            raise ScaleToZeroError("MISSING_MODULE", "module_id is required")
        if policy.idle_timeout_seconds <= 0:
            raise ScaleToZeroError(
                "INVALID_IDLE_TIMEOUT", "idle_timeout_seconds must be > 0")
        if policy.min_replicas < 0:
            raise ScaleToZeroError(
                "INVALID_MIN_REPLICAS", "min_replicas must be >= 0")
        if policy.scale_up_delay_seconds < 0:
            raise ScaleToZeroError(
                "INVALID_SCALE_UP_DELAY",
                "scale_up_delay_seconds must be >= 0")
        if policy.status not in _VALID_SCALE_STATUSES:
            raise ScaleToZeroError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_SCALE_STATUSES}")

        now = _utcnow()
        pid = f"sz-{uuid.uuid4().hex[:8]}"
        stored = policy.model_copy(update={
            "policy_id": pid,
            "created_at": now,
        })
        with self._lock:
            if len(self._policies) >= _MAX_SCALE_POLICIES:
                oldest = min(self._policies.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._policies[oldest.policy_id]
            self._policies[pid] = stored
        return stored

    def get_policy(self, policy_id: str) -> ScaleToZeroPolicy:
        with self._lock:
            policy = self._policies.get(policy_id)
        if policy is None:
            raise ScaleToZeroError(
                "NOT_FOUND", f"policy {policy_id} not found")
        return policy

    def list_policies(
        self,
        module_id: str | None = None,
        status: str | None = None,
    ) -> list[ScaleToZeroPolicy]:
        with self._lock:
            results = list(self._policies.values())
        if module_id:
            results = [p for p in results if p.module_id == module_id]
        if status:
            results = [p for p in results if p.status == status]
        return sorted(results,
                      key=lambda p: p.created_at or datetime.min,
                      reverse=True)

    def update_policy(self, policy_id: str,
                      updates: dict) -> ScaleToZeroPolicy:
        if "status" in updates and updates["status"] not in _VALID_SCALE_STATUSES:
            raise ScaleToZeroError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_SCALE_STATUSES}")

        with self._lock:
            policy = self._policies.get(policy_id)
            if policy is None:
                raise ScaleToZeroError(
                    "NOT_FOUND", f"policy {policy_id} not found")
            data = policy.model_dump()
            data.update(updates)

            if "idle_timeout_seconds" in updates:
                if data.get("idle_timeout_seconds", 0) <= 0:
                    raise ScaleToZeroError(
                        "INVALID_IDLE_TIMEOUT",
                        "idle_timeout_seconds must be > 0")
            if "min_replicas" in updates:
                if data.get("min_replicas", 0) < 0:
                    raise ScaleToZeroError(
                        "INVALID_MIN_REPLICAS",
                        "min_replicas must be >= 0")
            if "scale_up_delay_seconds" in updates:
                if data.get("scale_up_delay_seconds", 0) < 0:
                    raise ScaleToZeroError(
                        "INVALID_SCALE_UP_DELAY",
                        "scale_up_delay_seconds must be >= 0")

            data["updated_at"] = _utcnow()
            updated = ScaleToZeroPolicy(**data)
            self._policies[policy_id] = updated
        return updated

    def delete_policy(self, policy_id: str) -> None:
        with self._lock:
            if policy_id not in self._policies:
                raise ScaleToZeroError(
                    "NOT_FOUND", f"policy {policy_id} not found")
            del self._policies[policy_id]

    def trigger_alert(
        self,
        module_id: str,
        alert_type: str,
        wait_duration_ms: int,
        severity: str,
    ) -> ColdStartAlert:
        if not module_id or not module_id.strip():
            raise ScaleToZeroError("MISSING_MODULE", "module_id is required")
        if alert_type not in _VALID_ALERT_TYPES:
            raise ScaleToZeroError(
                "INVALID_ALERT_TYPE",
                f"alert_type must be one of {_VALID_ALERT_TYPES}")
        if severity not in _VALID_SEVERITIES:
            raise ScaleToZeroError(
                "INVALID_ALERT_TYPE",
                f"severity must be one of {_VALID_SEVERITIES}")

        now = _utcnow()
        aid = f"al-{uuid.uuid4().hex[:8]}"
        alert = ColdStartAlert(
            alert_id=aid,
            module_id=module_id,
            alert_type=alert_type,
            wait_duration_ms=wait_duration_ms,
            severity=severity,
            cleared=False,
            created_at=now,
        )
        with self._lock:
            if len(self._alerts) >= _MAX_ALERTS:
                oldest = min(self._alerts.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._alerts[oldest.alert_id]
            self._alerts[aid] = alert
        return alert

    def list_alerts(
        self,
        module_id: str | None = None,
        alert_type: str | None = None,
        cleared: bool | None = None,
    ) -> list[ColdStartAlert]:
        with self._lock:
            results = list(self._alerts.values())
        if module_id:
            results = [a for a in results if a.module_id == module_id]
        if alert_type:
            results = [a for a in results if a.alert_type == alert_type]
        if cleared is not None:
            results = [a for a in results if a.cleared == cleared]
        return sorted(results,
                      key=lambda a: a.created_at or datetime.min,
                      reverse=True)

    def clear_alert(self, alert_id: str) -> ColdStartAlert:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                raise ScaleToZeroError(
                    "NOT_FOUND", f"alert {alert_id} not found")
            updated = alert.model_copy(update={"cleared": True})
            self._alerts[alert_id] = updated
        return updated

    def simulate_cold_start(self, module_id: str) -> int:
        if not module_id or not module_id.strip():
            raise ScaleToZeroError("MISSING_MODULE", "module_id is required")
        return random.randint(150, 3000)


_scale_to_zero_engine: ScaleToZeroEngine | None = None
_scale_to_zero_engine_lock = threading.Lock()


def get_scale_to_zero_engine() -> ScaleToZeroEngine:
    global _scale_to_zero_engine
    if _scale_to_zero_engine is None:
        with _scale_to_zero_engine_lock:
            if _scale_to_zero_engine is None:
                _scale_to_zero_engine = ScaleToZeroEngine.get_instance()
    return _scale_to_zero_engine


# ════════════════════ #157 Dev Scaffold ════════════════════

class ScaffoldFile(BaseModel):
    filename: str
    content: str


class ScaffoldTemplate(BaseModel):
    template_id: str = ""
    language: str  # python | typescript
    name: str
    description: str = ""
    file_templates: list[ScaffoldFile] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GeneratedScaffold(BaseModel):
    scaffold_id: str = ""
    module_id: str
    template_id: str
    rendered_files: list[ScaffoldFile] = []
    status: str = "generated"  # generated | applied
    created_at: datetime | None = None


_VALID_SCAFFOLD_LANGUAGES = {"python", "typescript"}
_VALID_SCAFFOLD_STATUSES = {"generated", "applied"}


class DevScaffoldEngine:
    """本地开发脚手架引擎."""

    _instance: DevScaffoldEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._templates: dict[str, ScaffoldTemplate] = {}
        self._scaffolds: dict[str, GeneratedScaffold] = {}
        self._lock = threading.Lock()
        self._init_default_templates()

    def _init_default_templates(self) -> None:
        now = _utcnow()

        python_compute = ScaffoldTemplate(
            template_id="tmpl-python-compute",
            language="python",
            name="python_compute_module",
            description="Python compute module scaffold with long-polling template",
            file_templates=[
                ScaffoldFile(
                    filename="Dockerfile",
                    content='FROM --platform=linux/amd64 python:latest\nUSER 5000\nCOPY src/ /app/\nCMD ["python", "/app/app.py"]',
                ),
                ScaffoldFile(
                    filename="requirements.txt",
                    content="",
                ),
                ScaffoldFile(
                    filename="app.py",
                    content='import time\n\n\ndef main():\n    while True:\n        # long-polling loop\n        time.sleep(1)\n\n\nif __name__ == "__main__":\n    main()',
                ),
            ],
            created_at=now,
            updated_at=now,
        )

        ts_compute = ScaffoldTemplate(
            template_id="tmpl-typescript-compute",
            language="typescript",
            name="typescript_compute_module",
            description="TypeScript compute module scaffold",
            file_templates=[
                ScaffoldFile(
                    filename="package.json",
                    content='{\n  "name": "compute-module",\n  "version": "1.0.0",\n  "main": "dist/index.js",\n  "scripts": {\n    "build": "tsc",\n    "start": "node dist/index.js"\n  }\n}',
                ),
                ScaffoldFile(
                    filename="tsconfig.json",
                    content='{\n  "compilerOptions": {\n    "target": "ES2020",\n    "module": "commonjs",\n    "outDir": "./dist",\n    "rootDir": "./src",\n    "strict": true\n  }\n}',
                ),
                ScaffoldFile(
                    filename="src/index.ts",
                    content='async function main(): Promise<void> {\n  while (true) {\n    // long-polling loop\n    await new Promise((resolve) => setTimeout(resolve, 1000));\n  }\n}\n\nmain();',
                ),
            ],
            created_at=now,
            updated_at=now,
        )

        python_ml = ScaffoldTemplate(
            template_id="tmpl-python-ml",
            language="python",
            name="python_ml_module",
            description="Python ML module scaffold with sklearn template",
            file_templates=[
                ScaffoldFile(
                    filename="Dockerfile",
                    content='FROM --platform=linux/amd64 python:latest\nUSER 5000\nCOPY src/ /app/\nCMD ["python", "/app/app.py"]',
                ),
                ScaffoldFile(
                    filename="requirements.txt",
                    content="scikit-learn\nnumpy\npandas",
                ),
                ScaffoldFile(
                    filename="app.py",
                    content='from sklearn.ensemble import RandomForestClassifier\nimport numpy as np\n\n\ndef main():\n    while True:\n        # ML inference loop\n        pass\n\n\nif __name__ == "__main__":\n    main()',
                ),
            ],
            created_at=now,
            updated_at=now,
        )

        self._templates["tmpl-python-compute"] = python_compute
        self._templates["tmpl-typescript-compute"] = ts_compute
        self._templates["tmpl-python-ml"] = python_ml

    @classmethod
    def get_instance(cls) -> DevScaffoldEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_template(self, template: ScaffoldTemplate) -> ScaffoldTemplate:
        if not template.name or not template.name.strip():
            raise DevScaffoldError("MISSING_NAME", "name is required")
        if template.language not in _VALID_SCAFFOLD_LANGUAGES:
            raise DevScaffoldError(
                "INVALID_LANGUAGE",
                f"language must be one of {_VALID_SCAFFOLD_LANGUAGES}")

        now = _utcnow()
        tid = f"st-{uuid.uuid4().hex[:8]}"
        stored = template.model_copy(update={
            "template_id": tid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._templates) >= _MAX_SCAFFOLD_TEMPLATES:
                oldest = min(self._templates.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._templates[oldest.template_id]
            self._templates[tid] = stored
        return stored

    def get_template(self, template_id: str) -> ScaffoldTemplate:
        with self._lock:
            template = self._templates.get(template_id)
        if template is None:
            raise DevScaffoldError(
                "NOT_FOUND",
                f"template {template_id} not found")
        return template

    def list_templates(self,
                       language: str | None = None) -> list[ScaffoldTemplate]:
        with self._lock:
            results = list(self._templates.values())
        if language:
            results = [t for t in results if t.language == language]
        return sorted(results,
                      key=lambda t: t.created_at or datetime.min,
                      reverse=True)

    def update_template(self, template_id: str,
                        updates: dict) -> ScaffoldTemplate:
        if "language" in updates and updates["language"] not in _VALID_SCAFFOLD_LANGUAGES:
            raise DevScaffoldError(
                "INVALID_LANGUAGE",
                f"language must be one of {_VALID_SCAFFOLD_LANGUAGES}")

        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                raise DevScaffoldError(
                    "TEMPLATE_NOT_FOUND",
                    f"template {template_id} not found")
            data = template.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = ScaffoldTemplate(**data)
            self._templates[template_id] = updated
        return updated

    def delete_template(self, template_id: str) -> None:
        with self._lock:
            if template_id not in self._templates:
                raise DevScaffoldError(
                    "TEMPLATE_NOT_FOUND",
                    f"template {template_id} not found")
            del self._templates[template_id]

    def generate_scaffold(
        self,
        module_id: str,
        template_id: str,
        variables: dict | None = None,
    ) -> GeneratedScaffold:
        if not module_id or not module_id.strip():
            raise DevScaffoldError("MISSING_MODULE", "module_id is required")

        with self._lock:
            template = self._templates.get(template_id)
        if template is None:
            raise DevScaffoldError(
                "TEMPLATE_NOT_FOUND", f"template {template_id} not found")

        now = _utcnow()
        sid = f"gs-{uuid.uuid4().hex[:8]}"
        vars_dict = dict(variables) if variables else {}
        vars_dict.setdefault("module_id", module_id)
        rendered_files: list[ScaffoldFile] = []
        for ft in template.file_templates:
            content = ft.content
            for key, value in vars_dict.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            rendered_files.append(
                ScaffoldFile(filename=ft.filename, content=content))

        scaffold = GeneratedScaffold(
            scaffold_id=sid,
            module_id=module_id,
            template_id=template_id,
            rendered_files=rendered_files,
            status="generated",
            created_at=now,
        )
        with self._lock:
            if len(self._scaffolds) >= _MAX_GENERATED_SCAFFOLDS:
                oldest = min(self._scaffolds.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._scaffolds[oldest.scaffold_id]
            self._scaffolds[sid] = scaffold
        return scaffold

    def get_scaffold(self, scaffold_id: str) -> GeneratedScaffold:
        with self._lock:
            scaffold = self._scaffolds.get(scaffold_id)
        if scaffold is None:
            raise DevScaffoldError(
                "SCAFFOLD_NOT_FOUND",
                f"scaffold {scaffold_id} not found")
        return scaffold

    def list_scaffolds(
        self,
        module_id: str | None = None,
        status: str | None = None,
    ) -> list[GeneratedScaffold]:
        with self._lock:
            results = list(self._scaffolds.values())
        if module_id:
            results = [s for s in results if s.module_id == module_id]
        if status:
            results = [s for s in results if s.status == status]
        return sorted(results,
                      key=lambda s: s.created_at or datetime.min,
                      reverse=True)

    def apply_scaffold(self, scaffold_id: str) -> GeneratedScaffold:
        with self._lock:
            scaffold = self._scaffolds.get(scaffold_id)
            if scaffold is None:
                raise DevScaffoldError(
                    "NOT_FOUND",
                    f"scaffold {scaffold_id} not found")
            updated = scaffold.model_copy(update={"status": "applied"})
            self._scaffolds[scaffold_id] = updated
        return updated


_dev_scaffold_engine: DevScaffoldEngine | None = None
_dev_scaffold_engine_lock = threading.Lock()


def get_dev_scaffold_engine() -> DevScaffoldEngine:
    global _dev_scaffold_engine
    if _dev_scaffold_engine is None:
        with _dev_scaffold_engine_lock:
            if _dev_scaffold_engine is None:
                _dev_scaffold_engine = DevScaffoldEngine.get_instance()
    return _dev_scaffold_engine
