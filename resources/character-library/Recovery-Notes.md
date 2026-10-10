# Recovery coverage and validation

[Reference index](Index.md) · [Original assets and aliases](Asset-Catalog.md) · [Membrane experiments](Experiments.md)

The initial recovery package was added at commit `ceea955729de66b515beea6b0bd11d083030db66`, on top of the existing canon-automation merge `0b32b5a02ea6e290381c90a1b766cbd9a4f8d12e`. Its 243 transferred files initially passed the independently supplied hashes. A subsequent authorized publication correction replaces two textual resources with clearly labeled sanitized derivatives and revises the public manifest, README, and checksums. The original nested `.gitignore` and every retained original asset remain unchanged. The enclosing ZIP and redundant nested archives are outside Git.

The current public package contains 239 distinct assets: 237 unchanged originals (421,076,824 bytes) and two sanitized metadata derivatives (2,579 bytes), totaling 421,079,403 bytes (401.6 MiB). The largest asset remains 16,303,464 bytes. All 242 entries in the revised `SHA256SUMS` pass. The validator pins the revised checksum-file and manifest hashes; `publication_revision` retains the prior independently verified hashes and records both replacements. The manifest records 290 current filename aliases: 288 for unchanged originals and two for derivatives. Retired source labels and hashes remain in derivative provenance and exclusion records. Different byte variants remain separate, even when their compositions or basenames resemble one another.

All 49 reference records remain present: 31 recovered source images, 15 recovered crops, and the three missing/unmapped source IDs R24–R26. The full entries for the 46 documented references match the unchanged current Reference Index. All 187 PNG, JPEG, and GIF files decode, including every GIF frame. C01–C15 match their recorded parent pixels and exclusive-edge rectangular bounds. These checks establish recovery integrity, not visual canon approval.

The recovered acting guide, model-sheet checklist, decision-log versions, S01–S03 previous documents, and other design snapshots are linked by original filename in the asset catalog. They retain their original bytes and prior-layout links. The two metadata derivatives are explicitly labeled separately. These resources do not replace the current authoritative files under `docs/`. Recovered scripts, workflow files, and production reports are historical resources; their location does not activate them.

## Explicit gaps and limits

- R24, R25, and R26 retain their earlier reserved identities. Similar titles or visual resemblance do not establish an exact mapping.
- Eight Page-linked binary records remain unavailable: **All animations MP4** and **Production files 1 of 7** through **Production files 7 of 7**. Their exact Page labels, MIME types, and reported sizes are preserved in [Missing-Resources.json](Missing-Resources.json), without private file references or invented original filenames. These metadata were independently confirmed from the accessible source Page; binary bytes were not transferred.
- The Page production group has 38 current records: 36 unchanged original assets and two sanitized derivatives. In 35 original records, `original_filename: null` is intentional because only a Page label was exposed; one shared original already had a documented filename. Derivatives are labeled as derivatives rather than treated as unknown original filenames. No original names are inferred from labels.
- Private conversation evidence, owner-specific metadata documents, unrelated images, and the identified blocked-output salvage are excluded from the public recovery. The unchanged owner archive remains the broader recovery deliverable.
- The seven registered membrane architectures and later unindexed lily/pencil-skirt exploration remain experiments. No baseline outfit replacement, R35 assignment, measurement system, patch map, or new creator approval is introduced.

## Publication correction

Two original textual resources contained metadata outside the public scope:

- `45_Creation_and_selection_verification.json`: Myca's service identifier in `pet.id`; an owner-specific Page identifier in `library.page_id`; and the unrelated `active_pet` block, including `id`, `name`, and `unchanged` selection status. The public replacement is `45_Myca_Production_Verification_SANITIZED.json`. Those fields are removed; Myca's production facts, sprite-sheet hash/dimensions, animation counts, and historical verification outcomes remain.
- `15_Confirmed_production_choices.md`: the Creation paragraph named another active pet and directed that its selection be retained. The public replacement is `15_Myca_Production_Choices_SANITIZED.md`. It removes that unrelated context and retains Myca's production choices, including the instruction not to activate Myca.

Both replacements declare themselves sanitized derivatives, with `original_bytes: false`, source hashes, retired source labels, and a reason in the manifest. The exact originals remain in the delivered owner recovery archive. No image bytes or canon were changed.

The exposed information was service/Page identifiers and pet-selection context. The examined textual resources contained no credential-token, private-key, or signed-download-URL patterns. The current public tree no longer contains those owner identifiers or unrelated active-pet values. **Earlier public Git commits still contain the original documents.** This correction does not erase historical exposure; no history rewrite, visibility change, or repository-setting change was authorized or performed.

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

`python scripts/resource_library.py build-indexes` regenerates only `Index.md`, `Asset-Catalog.md`, and `Experiments.md`. It does not write image bytes or alter the current manifest, checksum file, README, design-history supplement, or stored assets. The authorized publication revision is recorded separately in the manifest; future recovery batches should retain their own provenance.

The original documentation-site build remains unchanged and does not publish this resource directory. This addition provides repository navigation; it does not deploy a website or alter repository settings. The current canon gate still controls protected written-authority changes and approval receipts. No historical approval is invented.
