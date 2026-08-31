import json

from derd.iurm import SweepSpec, run_sweep, write_sweep
from derd.parameters import DERDParameters


def test_iurm_sweep_changes_only_the_active_dimension(tmp_path) -> None:
    base = DERDParameters(0.2, 0.7, 0.5, 0.3)
    spec = SweepSpec(
        experiment_id="IURM-TEST-E1",
        active_dimension="e1",
        values=(0.1, 0.2, 0.3),
        frozen_parameters=base,
        samples=128,
    )
    rows = run_sweep(spec)
    assert [row["e1"] for row in rows] == [0.1, 0.2, 0.3]
    assert all(row["e2"] == base.e2 for row in rows)
    assert all(row["amplitude_ratio"] == base.amplitude_ratio for row in rows)
    assert all(row["phase_ratio"] == base.phase_ratio for row in rows)

    csv_path, json_path = write_sweep(spec, tmp_path)
    assert csv_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["spec"]["active_dimension"] == "e1"
    assert len(payload["rows"]) == 3
