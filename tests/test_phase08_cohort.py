from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from derd.harmonic_extraction import git_blob_sha1_file
from derd.model import waveform
from derd.parameters import DERDParameters
from derd.validation_phase07 import Phase07Config, run_phase07_target
from derd.validation_phase08 import (
    Phase08Config,
    Phase08Target,
    assess_cohort,
    target_specific_config,
)


def _write_synthetic_magnitude_curve(path: Path, *, seed: int, n: int = 260) -> None:
    rng = np.random.default_rng(seed)
    phase = np.sort(rng.random(n))
    period = 1.0
    flux = 1.0 + 0.25 * waveform(
        phase,
        DERDParameters(0.27, 0.73, 0.62, 0.29),
        time_law="geometric",
        output_normalization="canonical",
    )
    magnitude = -2.5 * np.log10(flux)
    rows = [f"{time:.8f} {value:.8f} 0.00200000" for time, value in zip(phase, magnitude)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _target(path: Path, *, object_id: str, family: str, grade: str = "EXTERNAL_CATALOG") -> Phase08Target:
    data = path.read_bytes()
    return Phase08Target(
        object_id=object_id,
        family=family,
        mode="synthetic",
        catalog_period_days=1.0,
        period_evidence_grade=grade,
        source_relative_path=path.name,
        source_repository_path=path.name,
        source_git_blob_sha1=git_blob_sha1_file(path),
        source_sha256=hashlib.sha256(data).hexdigest(),
        source_byte_count=len(data),
        source_repository="synthetic/repository",
        source_commit="1" * 40,
        period_source="synthetic exact",
    )


def test_target_specific_seeds_are_deterministic_and_distinct() -> None:
    base = Phase07Config(synthetic_samples_per_class=8, propagation_draws=128)
    first = target_specific_config(base, "STAR-A")
    replay = target_specific_config(base, "STAR-A")
    other = target_specific_config(base, "STAR-B")
    assert first.calibration_seed == replay.calibration_seed
    assert first.draw_seed == replay.draw_seed
    assert first.calibration_seed != other.calibration_seed
    assert first.draw_seed != other.draw_seed


def test_source_completeness_is_not_confused_with_cleaning(tmp_path: Path) -> None:
    path = tmp_path / "curve.dat"
    _write_synthetic_magnitude_curve(path, seed=3)
    lines = path.read_text(encoding="utf-8").splitlines()
    fields = lines[-1].split()
    fields[-1] = "1.00000000"
    lines[-1] = " ".join(fields)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = run_phase07_target(
        source_path=path,
        object_id="SYNTH-CLEAN",
        mode="synthetic",
        catalog_period=1.0,
        expected_git_blob_sha1=git_blob_sha1_file(path),
        source_locator="synthetic:test",
        config=Phase07Config(
            synthetic_samples_per_class=8,
            propagation_draws=128,
            observation_sweep_counts=(),
            minimum_observations=240,
        ),
    )
    assert result.observation_count == 259
    assert result.gate.checks["source_complete"]


def test_small_multifamily_cohort_runs_and_stays_development_only(tmp_path: Path) -> None:
    targets = []
    for index, family in enumerate(("classical_cepheid", "rr_lyrae", "delta_scuti")):
        path = tmp_path / f"star-{index}.dat"
        _write_synthetic_magnitude_curve(path, seed=10 + index)
        targets.append(_target(path, object_id=f"SYNTH-{index}", family=family))
    assessment = assess_cohort(
        targets,
        root=tmp_path,
        config=Phase08Config(
            target_config=Phase07Config(
                synthetic_samples_per_class=8,
                propagation_draws=128,
                observation_sweep_counts=(),
                minimum_observations=240,
                period_grid_count=21,
            )
        ),
    )
    assert len(assessment.targets) == 3
    assert len(assessment.family_summary) == 3
    assert not assessment.population_inference_ready
    assert not assessment.c17_promoted
    assert "NOT_READY" in assessment.decision


def test_legacy_period_grade_blocks_claim_evidence(tmp_path: Path) -> None:
    path = tmp_path / "legacy.dat"
    _write_synthetic_magnitude_curve(path, seed=22)
    target = _target(
        path,
        object_id="SYNTH-LEGACY",
        family="delta_scuti",
        grade="LEGACY_FEATURE_TABLE_DIAGNOSTIC",
    )
    assessment = assess_cohort(
        [target],
        root=tmp_path,
        config=Phase08Config(
            target_config=Phase07Config(
                synthetic_samples_per_class=8,
                propagation_draws=128,
                observation_sweep_counts=(),
                minimum_observations=240,
                period_grid_count=21,
            )
        ),
    )
    item = assessment.targets[0]
    assert not item.checks["period_evidence_grade"]
    assert item.stage_reached == "PERIOD_PROVENANCE"
    assert item.disposition == "ENGINEERING_ONLY_PERIOD_NOT_CLAIM_GRADE"
