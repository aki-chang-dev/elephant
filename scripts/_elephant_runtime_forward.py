"""Load the plugin-shipped canonical runtime for checkout compatibility imports."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from types import ModuleType


_PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "elephant"


def _is_within_plugin_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(_PLUGIN_ROOT.resolve())
    except (OSError, ValueError):
        return False
    return True


def _validate_module_origin(name: str, module: ModuleType) -> None:
    origins: list[Path] = []
    module_file = getattr(module, "__file__", None)
    if isinstance(module_file, str):
        origins.append(Path(module_file))
    module_paths = getattr(module, "__path__", ())
    if module_paths is not None:
        origins.extend(Path(path) for path in module_paths if isinstance(path, str))
    if not origins or any(not _is_within_plugin_root(path) for path in origins):
        raise ImportError(
            f"preloaded module {name!r} is outside the checkout plugin root "
            f"{_PLUGIN_ROOT}"
        )


def _validate_preloaded_runtime(name: str) -> None:
    parts = name.split(".")
    for length in range(1, len(parts) + 1):
        prefix = ".".join(parts[:length])
        module = sys.modules.get(prefix)
        if module is not None:
            _validate_module_origin(prefix, module)


def canonical_module(name: str) -> ModuleType:
    _validate_preloaded_runtime(name)
    plugin_root = str(_PLUGIN_ROOT)
    if plugin_root not in sys.path:
        sys.path.insert(0, plugin_root)
    module = import_module(name)
    _validate_module_origin(name, module)
    return module


def alias_module(alias: str, canonical: str) -> ModuleType:
    module = canonical_module(canonical)
    sys.modules[alias] = module
    return module
