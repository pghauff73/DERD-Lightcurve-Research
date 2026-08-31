#!/usr/bin/env python3
"""Build a stable SHA-256 manifest for code, tests, and frozen protocols only."""
from __future__ import annotations

import argparse
from pathlib import Path

from derd.provenance import sha256_path


DEFAULT_PATHS = (
    ".github",
    "src",
    "tests",
    "experiments",
    "docs",
    "data/manifests",
    "data/evidence",
    "data/schemas",
    "research/preregistration",
    "research/claims",
    "pyproject.toml",
    "README_IMPLEMENTATION.md",
    "CHANGELOG.md",
)


def selected_files(root: Path, selections: tuple[str, ...], destination: Path):
    files: list[Path] = []
    excluded_directory_names = {"__pycache__", ".pytest_cache", ".git", ".venv", "build", "dist"}
    for selection in selections:
        candidate = root / selection
        if candidate.is_dir():
            files.extend(
                path
                for path in candidate.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and path.suffix != ".pyc"
                and not any(part in excluded_directory_names for part in path.relative_to(root).parts)
            )
        elif candidate.is_file():
            if candidate.suffix != ".pyc":
                files.append(candidate)
        else:
            raise FileNotFoundError(candidate)
    destination_resolved = destination.resolve()
    unique = {path.resolve() for path in files if path.resolve() != destination_resolved}
    return sorted(unique, key=lambda path: path.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, default=Path("research/CODE_MANIFEST_SHA256.txt"))
    parser.add_argument("--path", action="append", dest="paths")
    args = parser.parse_args()
    root = args.root.resolve()
    destination = args.destination if args.destination.is_absolute() else root / args.destination
    selections = tuple(args.paths) if args.paths else DEFAULT_PATHS
    files = selected_files(root, selections, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(f"{sha256_path(path)}  {path.relative_to(root).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    print(f"wrote {len(files)} entries to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
