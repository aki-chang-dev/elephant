#!/usr/bin/env python3
"""Copy exactly the marketplace artifact and run its setup smoke in isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def _artifact_digest(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        body = path.read_bytes()
        hasher.update(len(relative).to_bytes(8, "big"))
        hasher.update(relative)
        hasher.update(len(body).to_bytes(8, "big"))
        hasher.update(body)
    return hasher.hexdigest()


def run(root: Path) -> dict[str, object]:
    marketplace_path = root / ".agents/plugins/marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    source = marketplace["plugins"][0]["source"]
    if source.get("source") != "local" or not isinstance(source.get("path"), str):
        raise ValueError("marketplace smoke requires one local plugin source")
    artifact_source = (root / source["path"]).resolve()
    artifact_source.relative_to(root.resolve())
    digest = _artifact_digest(artifact_source)
    with tempfile.TemporaryDirectory() as directory:
        temporary_root = Path(directory)
        artifact = temporary_root / "artifact"
        repository = temporary_root / "repository"
        shutil.copytree(artifact_source, artifact)
        repository.mkdir()
        program = (
            "import json,pathlib,sys; "
            "artifact=pathlib.Path(sys.argv[1]).resolve(); "
            "repository=pathlib.Path(sys.argv[2]).resolve(); "
            "sys.path.insert(0,str(artifact)); "
            "from elephant_runtime.installed_smoke import run_installed_smoke; "
            "print(json.dumps(run_installed_smoke(repository),sort_keys=True))"
        )
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-I", "-c", program, str(artifact), str(repository)],
            cwd=temporary_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "isolated artifact smoke failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        result = json.loads(completed.stdout)
    result.update(
        {
            "artifact_digest": digest,
            "artifact_source": source["path"],
            "isolated_command": "python -I -c <artifact public-pipeline smoke>",
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    result = run(arguments.root.resolve())
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
