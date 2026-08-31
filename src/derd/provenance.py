"""Deterministic repository manifests for reproducible evidence capsules."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable, Iterator


_DEFAULT_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "build",
        "dist",
    }
)


@dataclass(frozen=True, slots=True)
class ManifestVerification:
    """Result of checking a SHA-256 manifest against a repository tree."""

    checked_count: int
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]
    malformed: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not (self.missing or self.mismatched or self.malformed)


def sha256_path(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_repository_files(
    root: str | Path,
    *,
    excluded_relative_paths: Iterable[str] = (),
    excluded_directory_names: Iterable[str] = _DEFAULT_EXCLUDED_DIRECTORY_NAMES,
) -> Iterator[Path]:
    """Yield regular files in stable path order.

    Exclusions are relative POSIX paths. Directory-name exclusions apply at any depth.
    Symlinks are rejected so a capsule cannot silently hash bytes outside its root.
    """

    root_path = Path(root).resolve()
    excluded_paths = {Path(value).as_posix().lstrip("./") for value in excluded_relative_paths}
    excluded_dirs = set(excluded_directory_names)
    files: list[Path] = []
    for path in root_path.rglob("*"):
        relative = path.relative_to(root_path)
        if any(part in excluded_dirs for part in relative.parts[:-1]):
            continue
        relative_text = relative.as_posix()
        if relative_text in excluded_paths:
            continue
        if path.is_symlink():
            raise ValueError(f"manifest refuses symlink: {relative_text}")
        if path.is_file():
            files.append(path)
    yield from sorted(files, key=lambda item: item.relative_to(root_path).as_posix())


def write_repository_manifest(
    root: str | Path,
    destination: str | Path,
    *,
    excluded_relative_paths: Iterable[str] = (),
) -> int:
    """Write a canonical ``SHA256  relative/path`` manifest and return its entry count."""

    root_path = Path(root).resolve()
    destination_path = Path(destination).resolve()
    try:
        destination_relative = destination_path.relative_to(root_path).as_posix()
    except ValueError:
        destination_relative = None
    exclusions = set(excluded_relative_paths)
    if destination_relative is not None:
        exclusions.add(destination_relative)

    entries = [
        (path.relative_to(root_path).as_posix(), sha256_path(path))
        for path in iter_repository_files(root_path, excluded_relative_paths=exclusions)
    ]
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(
        "".join(f"{digest}  {relative}\n" for relative, digest in entries),
        encoding="utf-8",
    )
    return len(entries)


def verify_repository_manifest(root: str | Path, manifest: str | Path) -> ManifestVerification:
    """Check every manifest entry without assuming the tree has no extra files."""

    root_path = Path(root).resolve()
    manifest_path = Path(manifest)
    missing: list[str] = []
    mismatched: list[str] = []
    malformed: list[str] = []
    checked = 0

    for line_number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        fields = raw_line.split("  ", maxsplit=1)
        if len(fields) != 2 or len(fields[0]) != 64:
            malformed.append(f"line {line_number}")
            continue
        expected, relative = fields
        if any(character not in "0123456789abcdef" for character in expected.lower()):
            malformed.append(f"line {line_number}")
            continue
        candidate = (root_path / relative).resolve()
        try:
            candidate.relative_to(root_path)
        except ValueError:
            malformed.append(f"line {line_number}")
            continue
        if not candidate.is_file():
            missing.append(relative)
            continue
        checked += 1
        if sha256_path(candidate) != expected.lower():
            mismatched.append(relative)

    return ManifestVerification(
        checked_count=checked,
        missing=tuple(missing),
        mismatched=tuple(mismatched),
        malformed=tuple(malformed),
    )
