"""Official OGLE retrieval helpers for completing the observational capsule."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import urllib.request


OGLE_LMC_CEPHEID_BASE = "https://www.astrouw.edu.pl/ogle/ogle4/OCVS/lmc/cep"
_STAR_PATTERN = re.compile(r"^OGLE-LMC-CEP-\d{4}$")


def official_photometry_url(star_id: str, *, band: str = "I") -> str:
    identifier = str(star_id).strip()
    active_band = str(band).strip().upper()
    if not _STAR_PATTERN.fullmatch(identifier):
        raise ValueError("star_id must match OGLE-LMC-CEP-NNNN")
    if active_band not in {"I", "V"}:
        raise ValueError("band must be I or V")
    return f"{OGLE_LMC_CEPHEID_BASE}/phot/{active_band}/{identifier}.dat"


def fetch_official_photometry(
    star_id: str,
    destination: str | Path,
    *,
    band: str = "I",
    timeout_seconds: float = 30.0,
    user_agent: str = "DERD-evidence-capsule/0.2 (+research reproducibility)",
) -> dict[str, object]:
    """Retrieve one official file and validate its three-column structure."""

    url = official_photometry_url(star_id, band=band)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
    text = data.decode("utf-8")
    count = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split()
        if len(fields) != 3:
            raise ValueError(f"official response line {line_number} does not have three columns")
        [float(field) for field in fields]
        count += 1
    if count < 8:
        raise ValueError("official response contains too few observations")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "star_id": star_id,
        "band": band.upper(),
        "url": url,
        "observation_count": count,
        "sha256": hashlib.sha256(data).hexdigest(),
        "destination": str(path),
    }
