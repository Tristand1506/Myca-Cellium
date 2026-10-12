# Collection assignments inspected · 12 October 2026

The current main-branch organization and the running local Review Desk's public
state were inspected. Both report schema version 1, revision 21, and identical
collection, region and archive data. No public assignment import is needed.

## Storage and saved coverage

Memberships persist in tracked data/review-desk.json: image members use SHA-256
identities; virtual detail members use existing view IDs. Membership never moves
artwork. Private notes, Undo history and transaction recovery live in ignored
.review-desk/ and are not inputs to reference assignment or public output.

| Collection | Saved image memberships | Active | Archived |
|---|---:|---:|---:|
| Cap | 1 | 1 | 0 |
| Lichen | 1 | 1 | 0 |
| Face and eyes | 3 | 3 | 0 |
| Tissue and hyphae | 3 | 3 | 0 |
| Legs and contact | 4 | 4 | 0 |
| Membrane experiments | 45 | 45 | 0 |
| Legacy | 13 | 6 | 7 |
| Total | 70 | 63 | 7 |

There are 46 archived images overall and no saved virtual detail regions.
117 of the 187 original image assets have no direct collection membership;
78 of those are active. Unassigned does not mean missing, rejected or unusable.

The linked prior chat contains the request about collections but no assignment
attachment. No connected document-control session was available. The live editor's
public endpoint confirms saved state; unsaved browser drafts or selections could
not be inspected because browser tooling could not start in this session.

## Reference scope boundaries

- Cap contains C10, a head-to-cap relationship crop, not all-angle cap approval.
- Lichen contains C12; written colour and length rules continue to control it.
- Face and eyes contains C13, C02 and an unregistered original. C02 remains a
  compact-bob / lichen reference and explicitly excludes new facial anatomy.
- Tissue and hyphae contains C14, C07 and C15. C14 remains a comparison-only
  material attempt, not an approved finished tissue-depth target.
- Legs and contact contains C06, C04, C05 and C08. Their respective release,
  contact, low-origin correction and terrain caveats are retained.
- Membrane experiments retain experimental classifications and any existing
  R32–R34 records. No new R/C IDs or baseline-outfit approval are created.
- Legacy is organization-only. Its partly superseded and early reference statuses
  are not inferred anew from the collection's name or archival state.

The explicit topic map in data/collection-features.json affects navigation only.
Generated feature-references.json records every saved membership, including
archived history, with original reference records and crop-parent limitations.
Neither generated output nor membership is an approval ledger.

## Remaining gaps

No saved public collection data differs between the inspected running editor and
main. Browser-only unsaved state remains unverified. R24–R26 remain missing or
unmapped; eight Page-linked binaries (one MP4 and seven production ZIPs) remain
unavailable. No replacement artwork or identifiers are invented.

Original artwork, recovery manifest, checksums, current R/C IDs, written design
documents, canonical scopes, statuses and approval ledgers remain unchanged.
Pages publication remains manually dispatched; this change does not deploy.
