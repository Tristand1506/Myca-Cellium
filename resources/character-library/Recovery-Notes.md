# Recovery coverage and validation

[Reference index](Index.md) · [Original assets and aliases](Asset-Catalog.md) · [Membrane experiments](Experiments.md)

The reviewed recovery package was added at commit `ceea955729de66b515beea6b0bd11d083030db66`, on top of the existing canon-automation merge `0b32b5a02ea6e290381c90a1b766cbd9a4f8d12e`. Its 243 transferred files are preserved unchanged, including the original nested `.gitignore`. The enclosing ZIP and redundant nested archives are outside Git.

The package contains 239 distinct original assets totaling 421,078,476 bytes (401.6 MiB). The largest asset is 16,303,464 bytes. All 242 entries in `SHA256SUMS` pass; the checksum file and manifest also match independently supplied SHA-256 values. The manifest records 290 filename aliases. Different byte variants are preserved separately, even when the compositions or basenames resemble one another.

All 49 reference records remain present: 31 recovered source images, 15 recovered crops, and the three missing/unmapped source IDs R24–R26. The full entries for the 46 documented references match the unchanged current Reference Index. All 187 PNG, JPEG, and GIF files decode, including every GIF frame. C01–C15 match their recorded parent pixels and exclusive-edge rectangular bounds. These checks establish recovery integrity, not visual canon approval.

The recovered acting guide, model-sheet checklist, decision-log versions, S01–S03 previous documents, and other design snapshots are linked by original filename in the asset catalog. They retain their original bytes and prior-layout links. They do not replace the current authoritative files under `docs/`. Recovered scripts, workflow files, and production reports are historical resources; their location does not activate them.

## Explicit gaps and limits

- R24, R25, and R26 retain their earlier reserved identities. Similar titles or visual resemblance do not establish an exact mapping.
- Eight Page-linked binary records remain unavailable: **All animations MP4** and **Production files 1 of 7** through **Production files 7 of 7**. Their exact Page labels, MIME types, and reported sizes are preserved in [Missing-Resources.json](Missing-Resources.json), without private file references or invented original filenames. These metadata were independently confirmed from the accessible source Page; binary bytes were not transferred.
- The Page-only production material includes 38 asset records. In 37 records, `original_filename: null` is intentional: only a Page label was exposed. The remaining shared asset already had a documented filename. No original names are inferred from the labels.
- Private conversation evidence, owner-specific metadata documents, unrelated images, and the identified blocked-output salvage are excluded from the public recovery. The unchanged owner archive remains the broader recovery deliverable.
- The seven registered membrane architectures and later unindexed lily/pencil-skirt exploration remain experiments. No baseline outfit replacement, R35 assignment, measurement system, patch map, or new creator approval is introduced.

Publication review: the unchanged historical `45_Creation_and_selection_verification.json` report contains non-secret Page/pet IDs and an unrelated active-pet status. These metadata were already present in the supplied reviewed transfer. Its exact bytes are retained for review in this draft; no identifier values are reproduced in the new navigation or gap records.

## Repeat the checks

```sh
cd resources/character-library
sha256sum -c SHA256SUMS
cd ../..
python scripts/resource_library.py validate
# Optional full decoding and crop comparisons; requires Pillow:
python scripts/resource_library.py validate --images
python scripts/validate.py
python scripts/canon_guard.py validate
python -m unittest discover -s tests -v
python scripts/build_site.py
git diff --check
```

`python scripts/resource_library.py build-indexes` regenerates only `Index.md`, `Asset-Catalog.md`, and `Experiments.md`. It does not write image bytes or alter the reviewed manifest, checksum file, original README, original design-history supplement, or historical resources. Future recovery batches should retain their own manifests instead of rewriting this snapshot.

The original documentation-site build remains unchanged and does not publish this resource directory. This addition provides repository navigation; it does not deploy a website or alter repository settings. The current canon gate still controls protected written-authority changes and approval receipts. No historical approval is invented.
