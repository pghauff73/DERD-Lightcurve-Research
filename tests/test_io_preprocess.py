from pathlib import Path

import numpy as np
import pytest

from derd.io import read_ogle_photometry, read_target_manifest, sha256_file
from derd.preprocess import (
    clean_light_curve,
    fit_train_minmax,
    fold_phase,
    inverse_variance_weights,
)


def test_ogle_parser_reads_three_columns(tmp_path: Path):
    path = tmp_path / "x.dat"
    path.write_text("1 15.0 0.01\n2 15.1 0.02\n", encoding="utf-8")
    curve = read_ogle_photometry(path, star_id="X")
    assert curve.size == 2
    assert curve.metadata["time_system"] == "HJD-2450000"


def test_ogle_parser_rejects_wrong_column_count(tmp_path: Path):
    path = tmp_path / "x.dat"
    path.write_text("1 15.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_ogle_photometry(path, star_id="X")


def test_sha256_is_deterministic(tmp_path: Path):
    path = tmp_path / "x"
    path.write_bytes(b"abc")
    assert sha256_file(path) == sha256_file(path)


def test_cleaner_removes_only_large_error(tmp_path: Path):
    path = tmp_path / "x.dat"
    rows = [f"{i} {15 + (-1)**i * 0.4} {0.01 if i < 9 else 1.0}" for i in range(10)]
    path.write_text("\n".join(rows) + "\n")
    curve = read_ogle_photometry(path, star_id="X")
    cleaned, report = clean_light_curve(curve)
    assert cleaned.size == 9
    assert report.removed_count == 1
    assert np.ptp(cleaned.value) > 0.5  # brightness extrema were retained


def test_fold_phase_wraps_to_unit_interval():
    phase = fold_phase([0.0, 1.5, 2.0], 1.0)
    assert np.all((phase >= 0.0) & (phase < 1.0))
    assert phase.tolist() == [0.0, 0.5, 0.0]


def test_train_minmax_applies_train_bounds_to_test():
    scaler = fit_train_minmax([2.0, 4.0])
    transformed = scaler.transform_values([1.0, 2.0, 4.0, 5.0])
    assert transformed.tolist() == [-0.5, 0.0, 1.0, 1.5]


def test_inverse_variance_weights_have_median_one():
    weights = inverse_variance_weights([1.0, 2.0, 4.0])
    assert np.isclose(np.median(weights), 1.0)


def test_real_target_manifest_has_twenty_unique_stars():
    root = Path(__file__).resolve().parents[1]
    records = read_target_manifest(root / "data/manifests/phase02_targets.csv")
    assert len(records) == 20
    assert len({record.star_id for record in records}) == 20


def test_official_ogle_url_is_deterministic():
    from derd.ogle import official_photometry_url

    assert official_photometry_url("OGLE-LMC-CEP-0001") == (
        "https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/cep/phot/I/OGLE-LMC-CEP-0001.dat"
    )


def test_official_ogle_url_rejects_bad_identifier():
    from derd.ogle import official_photometry_url

    with pytest.raises(ValueError):
        official_photometry_url("CEP-1")
