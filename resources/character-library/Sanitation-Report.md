# PR #2 sanitation report

## Result and audit scope

This replacement imports verified public assets onto `main` at `0b32b5a02ea6e290381c90a1b766cbd9a4f8d12e`. No recovery-branch commit is a parent. The old PR, branches and history remain unchanged. Nothing is merged, force-pushed, deleted or deployed.

The audited source is PR #2 at `8e97da9420458cb35ccb55c9f583e11e0a512cef`: 21 locally reachable commits including its head/merge refs, 276 unique blobs, 89 distinct UTF-8 text blobs, manifests, filenames, commit author/committer headers, PR description/comments and metadata of 187 image blobs. Broad searches were reviewed for false positives; an apparent unrelated name inside embedded base64 was random payload text. Public creator attribution in canon governance and GitHub noreply commit addresses is retained. No credential-token, private-key or signed-download-URL patterns were found in examined text; this does not prove every possible secret format is absent.

## Findings and treatment

| Affected original | Exposure category | Public treatment |
|---|---|---|
| `10_Production_brief.json` | Owner paths, private project identifier, unrelated selection instruction | Private original archived; report omitted from public import |
| `29_Atlas_validation.json` | Owner path and private project identifier | Private original archived; report omitted from public import |
| `30_Pet_quality_check.json` | Owner path and private project identifier | Private original archived; report omitted from public import |
| `36_Transparency_edge_cleanup.json` | Owner input/output paths and private project identifier | Private original archived; report omitted from public import |
| `37_Standard_frame_review.json` | Owner frame paths and private project identifier | Private original archived; report omitted from public import |
| `45_Creation_and_selection_verification.json` | Service IDs, unrelated selection context, private Page inventory | Re-reviewed derivative omits service/account state and Page inventory; sprite/animation facts retained |
| `15_Confirmed_production_choices.md` | Unrelated active-pet name/selection context | Existing labeled derivative reviewed and retained |

Exact affected originals, every distinct reachable text-blob version, manifests, commit headers and private audit evidence are preserved in a separate owner-controlled private archive outside Git. All 104 archived entries passed SHA-256 verification. Private archive identifiers and locations are not published. The archive does not claim inaccessible excluded files or missing artwork.

The package contains **234 assets: 232 unchanged originals and two labeled metadata derivatives**, totaling 421,015,862 bytes with 285 current aliases. Source hashes remain in provenance. Five production reports with private paths are omitted in full and retained privately. Three runtime-UUID artwork labels were replaced with neutral SHA-derived labels, including aliases in the manifest/catalog. Their exact original names and files are archived privately; bytes, hashes and classifications are unchanged. No missing original filename is inferred. Counts, checksum pins, manifest revision and navigation were updated. The history supplement omits unrelated personal-conversation and private recovery-archive context while preserving Myca decisions and limitations.

## Preservation and checks

All 187 artwork files retain identical SHA-256 hashes and exact bytes, including GIFs and image metadata. All frames decode. Metadata contains format/colour-profile data; no owner-path, service-ID or private-URL patterns were found. This is not visual canon approval.

All 49 R01–R34/C01–C15 identifiers, mappings, use limitations, defects and statuses are unchanged. Duplicate source-context prose and source-document provenance fields are omitted from the public manifest; crop parent/bounds/size data are retained explicitly. All 15 crops retain exact parent pixels, bounds and dimensions. R24–R26 remain missing/unmapped; eight unavailable binaries retain labels, MIME types and sizes without guessed filenames. R32–R34 and all other experimental classifications remain experimental. No artwork generation, new reference ID or canon approval is introduced.

Validation covers 237 checksums, pinned manifest/checksum hashes, decoding, crop comparisons, generated navigation and privacy patterns. Historical snapshots retain prior-layout links and are accessed through the catalog; those old links are not claimed repaired. `docs/`, project instructions, canon register, approval policy, ledgers, governance workflows and site renderer remain byte-identical to main. Existing metadata/ledger validation, 42 tests, local site build, whitespace check and committed canon gate are run. Whitespace checking treats preserved CRLF endings as intentional (`git -c core.whitespace=cr-at-eol diff --check`), without normalizing original files. Zero guarded-file approvals are required for this resource import. See [Recovery-Notes.md](Recovery-Notes.md) for repeatable commands.

## Residual exposure and GitHub Support

**Clean replacement lineage does not erase old public exposure.** The recovery branch remains reachable: its head contains five owner-path reports and earlier commits retain the two previously removed originals. Both `refs/pull/2/head` and `refs/pull/2/merge` were fetched successfully. Commit/blob URLs and PR diffs can still expose the originals. Closing a PR or removing working-tree files does not erase them.

Affected reports first entered commits `7b8d89cf2d26bfc18aa7cad9926e0c05745f4b51`, `2460c2ab755e73b5d59957389a15ffcd255f0907`, `96dc0d84a39bc3b62ad9adedd914e4786d2c5970`, and `ccaa0e7cf972b38256b90a9481018b183b78f4f7`. These are evidence references, not replacement parents.

The public API reported **zero forks and zero Actions caches** at audit time; the 20 old-branch workflow runs had zero current downloadable artifacts. This cannot exclude prior downloads, deleted forks, clones, external caches or screenshots. Old Actions runs/logs remain. Cached GitHub commit/diff views and external indexing were not purged or comprehensively enumerable. Previously delivered recovery ZIPs and local clones remain owner-held copies and must stay private.

GitHub's [sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) states PR refs are read-only. Dereferencing affected PRs, clearing cached views and garbage-collecting otherwise unreferenced sensitive objects requires **GitHub Support**, subject to eligibility. Support ordinarily requires other refs and fork refs to be cleaned first. The intentionally retained old branch means that prerequisite is not met. Later branch deletion/history rewriting needs separate authorization. Fork/clone owners control their copies; Support cannot erase downloads. No Support request was submitted or removal promised.
