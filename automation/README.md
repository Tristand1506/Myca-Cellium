# Myca Canon Automation v0.2

This automation records feature-scoped decisions and checks creator approval.
The existing written design rules remain authoritative. Installation does not
change Myca's design, the 1.0 baseline, reference IDs, or source documentation.
The decision and approval ledgers start empty: the missing legacy decision log
has not been imported, and historical approvals have not been invented.

## Files and checks

| File | Purpose |
| --- | --- |
| `data/design-decisions.json` | Append-only decisions, including experimental proposals, rationale, references, and exact file/feature scope. |
| `data/creator-approvals.json` | Append-only approval receipts linking a decision and content digest to a GitHub PR comment. |
| `data/canon-policy.json` | Creator identity and paths requiring scoped approval. The base-branch policy controls a PR. |
| `scripts/canon_guard.py` | Schema/link validation, deterministic approval digests, change detection, and live GitHub evidence verification. |
| `.github/workflows/canon-approval.yml` | Runs trusted base code and publishes `Myca canon approval` on the actual PR head commit. |
| `.github/workflows/validate.yml` | Runs the original integrity validator, ledger validation, and regression tests without write permissions. |

The creator is identified by the repository owner's stable GitHub account ID
`56117578` (currently `Tristand1506`). A matching display name or login alone
cannot grant approval. Any future identity or policy change requires approval
from the creator identified in the existing base policy.

## Installation and merge enforcement

1. Review and merge this infrastructure PR. Run the checks below against its base
   commit to verify that existing documentation and the canon register are unchanged.
2. In GitHub branch protection or a branch ruleset for `main`, require pull requests
   and the `Myca canon approval` check from GitHub Actions, together with the existing
   validation job. Apply the rules to administrators and remove bypass allowances
   if creator approval must be mandatory for everyone. Disable direct pushes.
3. Open a test PR to confirm the gate runs and blocks an unapproved canon change.

The privileged workflow uses `pull_request_target`, so it becomes active only
after installation on the trusted base branch. It cannot authenticate its own
initial installation PR. Do not require the new check before that workflow has
been installed and produced its first check run. Repository settings are external
to this PR; committing a workflow alone does not make a check mandatory for merging.

Users who can alter repository rules or publish arbitrary workflows with write
tokens remain trusted administrators. For repositories with untrusted write
contributors, also use organization rulesets with a required trusted workflow or
equivalent controls on workflow changes; a check name alone is not a security
boundary against another workflow impersonating that name.

## Record a proposal

Append a decision to `data/design-decisions.json`, using an unused `D-` ID:

```json
{
  "id": "D-0001",
  "status": "experimental",
  "feature_ids": ["outfit.membrane.layered-petal"],
  "summary": "Evaluate the layered-petal candidate",
  "rationale": "Proposal for review; no creator selection recorded",
  "files": ["data/canon-register.json"],
  "references": ["R32"],
  "supersedes": null
}
```

This is a format example, not an imported decision or an approval. Decision statuses
are `canon`, `provisional`, `experimental`, `unresolved`, `superseded`, `rejected`,
and `style-specific`, matching the existing project vocabulary. Feature and reference
IDs must already exist in the current register/index. Register changes must have a
new decision naming the affected features and `data/canon-register.json`.

To revise a recorded decision, append a successor with a new ID and `supersedes`
pointing to the earlier decision. Never edit, reorder, or delete prior ledger entries.
Proposal-only decisions and non-canon status transitions do not require approval.
Changing existing record metadata, changing an existing canon feature, or adding a
canon feature does. Existing feature IDs cannot be removed or renamed.

## Request and record scoped creator approval

1. Prepare the exact proposed written-rule and register changes in a PR. Preserve
   original sources and reference identifiers. A future design change should follow
   the existing project's authoritative-document-first protocol.
2. Append a successor decision with `status: "canon"`. Name every affected feature
   in `feature_ids` and every affected protected file in `files`, using exact repository
   paths. This status records an approved decision; it does not automatically set
   the statuses of all associated features. Governance-only decisions may use an
   empty `feature_ids` list. Commit the proposal before calculating its digest.
3. Run `python scripts/canon_guard.py digests`. The creator must review the decision
   and scoped diff, then post the emitted command as the entire body of a PR
   conversation comment:

   ```text
   myca-approve D-0002 <64-character-payload-sha256>
   ```

4. Append an approval receipt with an unused `A-` ID to `data/creator-approvals.json`:

   ```json
   {
     "id": "A-0001",
     "decision_id": "D-0002",
     "payload_sha256": "<64-character-payload-sha256>",
     "pr_number": 123,
     "comment_id": 456789
   }
   ```

5. Push the receipt. The gate fetches live comments from that PR and verifies the
   numeric creator ID, exact command, comment ID, digest, and latest approval/revocation.
   A creator can approve their own PR with this comment protocol; no self-review
   workaround or second identity is necessary.

The hash covers the entire decision and exact bytes of every scoped file, including
deletions. Adding the approval receipt does not alter that hash. Editing the decision
or a scoped file invalidates its approval. Unrelated code edits do not. Approval
receipts and decision ledgers cannot be listed as scoped files, avoiding circular
hashes. Another PR cannot replay the receipt, and one feature's approval cannot
cover a different feature. Captions, attractive images, general praise, labels, and
unverified JSON claims do not grant approval.

To revoke a pending approval, the creator posts `myca-revoke D-0002 <digest>`.
The latest matching creator command, ordered by GitHub update time and comment ID,
controls approval. Edits and deletions of comments also rerun the check. Reapproval
requires updating the unmerged receipt to refer to the latest approval comment.
Once a receipt is merged it is immutable history; a subsequent design reversal is
a new scoped decision and approval, not deletion of the old receipt.

All changes anywhere under `docs/`, changes to `PROJECT_INSTRUCTIONS.md`, and
changes to the checker, validator, policy, or workflows require explicit scoped
approval. The gate reads these rules from the base commit, so the proposal cannot
weaken its own checks. It reads proposal files as Git objects and never executes
proposal code with its GitHub write token. The token is used only to read repository
data/comments and publish the check result. It cannot approve, merge, or publish Pages.

## Local validation

```sh
python scripts/validate.py
python -m unittest discover -s tests -v
# These commands inspect committed Git objects, not uncommitted edits:
python scripts/canon_guard.py validate
python scripts/canon_guard.py digests
python scripts/canon_guard.py check --base <base-commit-sha> --head HEAD
```

The offline `check` has no authenticated comment evidence and therefore fails closed
when a new creator approval is required. Only the trusted GitHub workflow fetches
live approval evidence. `validate` checks schema and links only; it never asserts that
a decision has been approved. The workflow checks new approvals against the current
PR. Merged receipts are retained as historical evidence without re-fetching old PRs.
Changes to current canon still need a new decision and a new approval.

The existing Pages workflow remains manually invoked and unchanged. This automation
does not restore missing image files or the unavailable legacy decision log.
