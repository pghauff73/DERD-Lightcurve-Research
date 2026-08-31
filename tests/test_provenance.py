from pathlib import Path

import pytest

from derd.provenance import (
    iter_repository_files,
    verify_repository_manifest,
    write_repository_manifest,
)


def test_manifest_round_trip(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "nested/b.txt").write_text("beta\n", encoding="utf-8")
    manifest = tmp_path / "MANIFEST_SHA256.txt"
    assert write_repository_manifest(tmp_path, manifest) == 2
    result = verify_repository_manifest(tmp_path, manifest)
    assert result.valid
    assert result.checked_count == 2


def test_manifest_detects_changed_file(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_text("alpha\n", encoding="utf-8")
    manifest = tmp_path / "MANIFEST_SHA256.txt"
    write_repository_manifest(tmp_path, manifest)
    target.write_text("changed\n", encoding="utf-8")
    result = verify_repository_manifest(tmp_path, manifest)
    assert not result.valid
    assert result.mismatched == ("a.txt",)


def test_repository_iterator_rejects_symlink(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        list(iter_repository_files(tmp_path))
