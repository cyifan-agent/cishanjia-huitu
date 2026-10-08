"""Load only configured local dependency directories; never download packages."""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path


def dependency_roots() -> list[Path]:
    skill_root = Path(__file__).resolve().parent.parent
    configured = []
    config_path = skill_root / "runtime.local.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        configured = config.get("package_roots", [])
        if not isinstance(configured, list):
            raise ValueError("runtime.local.json package_roots must be a list")
    raw_paths = list(filter(None, os.environ.get("HUITU_DEPENDENCIES", "").split(os.pathsep)))
    raw_paths += [str(skill_root / ".deps")] + configured
    roots = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = skill_root / path
        path = path.resolve()
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def bootstrap() -> list[Path]:
    roots = dependency_roots()
    for path in reversed(roots):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return roots


def audit() -> dict:
    roots = bootstrap()
    modules = {}
    for name in ("cv2", "numpy", "fontTools", "vtracer", "resvg_py", "PIL"):
        try:
            module = importlib.import_module(name)
            modules[name] = {"status": "ready", "file": str(module.__file__)}
        except Exception as exc:
            modules[name] = {"status": "missing", "error": str(exc)}
    return {
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "package_roots": [str(path) for path in roots],
        "modules": modules,
        "status": "PASS" if all(item["status"] == "ready" for item in modules.values()) else "FAIL",
        "downloads_performed": False,
        "local_vision_model_installed_by_this_update": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--print-paths", action="store_true")
    parser.add_argument("--paths-json", type=Path, help="UTF-8 path exchange for Windows PowerShell")
    args = parser.parse_args()
    if args.paths_json:
        args.paths_json.parent.mkdir(parents=True, exist_ok=True)
        args.paths_json.write_text(json.dumps([str(path) for path in dependency_roots()], ensure_ascii=False), encoding="utf-8")
        raise SystemExit(0)
    if args.print_paths:
        print(os.pathsep.join(str(path) for path in dependency_roots()))
        raise SystemExit(0)
    report = audit()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
