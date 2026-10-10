# Recovery coverage and validation

[Reference index](Index.md) · [Asset catalog](Asset-Catalog.md) · [Membrane experiments](Experiments.md) · [Sanitation report](Sanitation-Report.md)

234 assets: 232 unchanged originals and two labeled sanitized metadata derivatives. All 187 artwork files remain byte-identical. All 49 reference records remain present; R24–R26 stay missing/unmapped. C01–C15 remain exact crops. Eight unavailable binary records retain labels, MIME types and sizes in [Missing-Resources.json](Missing-Resources.json). Missing assets are not invented.

Derivatives omit owner paths, service/account metadata and unrelated selection context. Exact original text versions and manifests are retained privately outside Git; source SHA-256 hashes remain public. Historical text snapshots preserve prior-layout links; use the catalog for repository navigation.

The baseline outfit, membrane experimental classifications, written authority, governance and approval records remain unchanged. No new reference ID or approval is introduced.

## Repeat the checks

```sh
python scripts/resource_library.py validate --images
python scripts/validate.py
python scripts/canon_guard.py validate
python -m unittest discover -s tests -v
python scripts/build_site.py
git -c core.whitespace=cr-at-eol diff --check
python scripts/canon_guard.py check --base origin/main --head HEAD
```

`python scripts/resource_library.py build-indexes` rebuilds only three navigation indexes. It does not write artwork or change the manifest. The manifest and 237-entry checksum ledger are pinned. No hosting or deployment change is made. Old public exposure remains as detailed in the sanitation report.
