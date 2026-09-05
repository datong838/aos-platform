"""Image-internal launcher. This module must never run in the platform process."""
import importlib
import json
import keyword
import sys
from pathlib import Path

from .client import serve_registration
from .session import serve_session


def main():
    if sys.argv[1:] not in ([], ["--serve"]):
        raise ValueError("unsupported runtime mode")
    persistent = sys.argv[1:] == ["--serve"]
    root = Path("/aos/bundle").resolve(strict=True)
    config = json.loads(Path("/aos/runtime.json").read_bytes())
    entry = config["entrypoint"]
    if (not isinstance(entry, str) or not entry.startswith("backend/")
            or not entry.endswith(".py:register") or len(entry) > 1024
            or any(part in {"", ".", ".."} for part in entry.split("/"))
            or any(char in entry for char in "\\%?#")):
        raise ValueError("invalid image entrypoint")
    path = (root / entry.removesuffix(":register")).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("entrypoint escapes bundle")
    package = config["pythonPackage"]
    if not isinstance(package, str) or not package or any(
            not part.isidentifier() or keyword.iskeyword(part) for part in package.split(".")):
        raise ValueError("invalid Python package")
    parts = list(path.relative_to(root / "backend").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    module_name = ".".join(parts)
    if module_name != package and not module_name.startswith(package + "."):
        raise ValueError("entrypoint is outside declared Python package")
    # This path is inside the isolated image, never the platform interpreter.
    sys.path.insert(0, str(root / "backend"))
    module = importlib.import_module(module_name)
    if Path(module.__file__).resolve(strict=True) != path:
        raise ValueError("loaded module does not match entrypoint")
    if persistent:
        serve_session(module.register, module.handle)
    else:
        serve_registration(module.register)


if __name__ == "__main__":
    main()
