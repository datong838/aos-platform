"""Fixed current ecommerce profile: growth 1.8 and Niushop 1.22."""
from __future__ import annotations

import importlib.util
from pathlib import Path


OLD_NIUSHOP = (
    "platform.ecommerce.niushop/1.5.0",
    "platform.ecommerce.niushop",
    "1.5.0",
    "ecommerce_niushop",
)
CURRENT_NIUSHOP = (
    "platform.ecommerce.niushop/1.22.0",
    "platform.ecommerce.niushop",
    "1.22.0",
    "ecommerce_niushop",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("current ecommerce profile unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_builder():
    scripts = Path(__file__).resolve().parent
    ui_profile = _load(
        scripts / "build_ecommerce_ui_candidates.py",
        "current_ecommerce_ui_profile",
    )
    builder = ui_profile.load_builder()
    if (
        builder.RUNTIME_CASES.count(OLD_NIUSHOP) != 1
        or builder.ALL_CASES[: len(builder.RUNTIME_CASES)] != builder.RUNTIME_CASES
        or builder.EXPECTED_RUNTIME_OPERATION_COUNT != 13
    ):
        raise RuntimeError("growth 1.8 candidate profile drifted")
    builder.RUNTIME_CASES = tuple(
        CURRENT_NIUSHOP if item == OLD_NIUSHOP else item
        for item in builder.RUNTIME_CASES
    )
    builder.ALL_CASES = tuple(
        CURRENT_NIUSHOP if item == OLD_NIUSHOP else item
        for item in builder.ALL_CASES
    )
    return builder


if __name__ == "__main__":
    raise SystemExit(load_builder().main())
