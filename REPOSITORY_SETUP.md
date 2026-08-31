# GitHub repository setup

Intended repository:

```text
pghauff73/DERD-Lightcurve-Research
```

Recommended initial visibility: **private**.

## Route A: create from the source ZIP

```bash
unzip DERD-Lightcurve-Research-v2.1.0-source.zip
cd DERD-Lightcurve-Research

git init -b main
git add -A
git commit -m "chore: publish DERD v2.1 Phase 21 research capsule"

gh auth status
gh repo create pghauff73/DERD-Lightcurve-Research \
  --private \
  --description "Reproducible DERD waveform-model research and evidence gates for Cepheid, RR Lyrae, and Delta Scuti light curves" \
  --source . \
  --remote origin \
  --push
```

## Route B: preserve the prepared commit with the Git bundle

```bash
git clone DERD-Lightcurve-Research-v2.1.0.git.bundle DERD-Lightcurve-Research
cd DERD-Lightcurve-Research

# Cloning a bundle records the local bundle as origin; replace it during creation.
git remote remove origin

gh auth status
gh repo create pghauff73/DERD-Lightcurve-Research \
  --private \
  --description "Reproducible DERD waveform-model research and evidence gates for Cepheid, RR Lyrae, and Delta Scuti light curves" \
  --source . \
  --remote origin \
  --push
```

## Suggested repository topics

```text
astrophysics variable-stars light-curves cepheids rr-lyrae delta-scuti reproducible-research python
```

## After creation

1. Confirm GitHub Actions completes on Python 3.10, 3.11, and 3.12.
2. Keep the repository private until the license and publication boundary are chosen.
3. Do not upload locally acquired raw photometry excluded by `.gitignore`.
4. Create a `v2.1.0` release only after the repository commit and release bundle hashes are frozen.
