"""Regression tests use synthetic features and never rewrite Myca's documents."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import canon_guard as guard


def put(tree, path, value):
    tree[path] = json.dumps(value, sort_keys=True).encode()


def fixture():
    tree = {
        "docs/brief.md": b"Synthetic feature specification\n",
        "docs/References/Reference Index.md": b"R01 supports only feature.a\n",
        "scripts/canon_guard.py": b"trusted checker",
    }
    put(tree, guard.POLICY, {
        "schema_version": 1, "automation_version": "0.2",
        "creator": {"login": "creator", "id": 123},
        "protected_paths": ["docs/**"],
        "governance_paths": [guard.POLICY, "scripts/canon_guard.py", ".github/workflows/**"],
    })
    put(tree, guard.REGISTER, {"schema_version": 1, "baseline": "1.0", "records": [{
        "id": "feature.a", "status": "experimental", "authority": "docs/brief.md",
        "section": "Synthetic feature", "references": ["R01"],
    }]})
    put(tree, guard.DECISIONS, {"schema_version": 1, "decisions": []})
    put(tree, guard.APPROVALS, {"schema_version": 1, "approvals": []})
    return tree


def decision(status="canon", files=None, features=None, identity="D-0001", supersedes=None):
    return {"id": identity, "status": status, "feature_ids": features if features is not None else ["feature.a"],
            "summary": "Synthetic scoped decision", "rationale": "Synthetic evidence",
            "files": files if files is not None else [guard.REGISTER],
            "references": ["R01"], "supersedes": supersedes}


def add_decision(tree, item):
    value = json.loads(tree[guard.DECISIONS])
    value["decisions"].append(item)
    put(tree, guard.DECISIONS, value)


def approve(tree, item, user_id=123, pr_number=7, comment_id=10):
    digest = guard.payload_digest(tree, item)
    approval = {"id": "A-0001", "decision_id": item["id"], "payload_sha256": digest,
                "pr_number": pr_number, "comment_id": comment_id}
    put(tree, guard.APPROVALS, {"schema_version": 1, "approvals": [approval]})
    return [{"id": comment_id, "user": {"id": user_id, "login": "creator", "type": "User"},
             "body": f"myca-approve {item['id']} {digest}", "updated_at": "2026-10-10T12:00:00Z"}]


class CanonGuardTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        self.head = copy.deepcopy(self.base)

    def promote(self):
        register = json.loads(self.head[guard.REGISTER])
        register["records"][0]["status"] = "canon"
        put(self.head, guard.REGISTER, register)
        item = decision()
        add_decision(self.head, item)
        return item

    def blocked(self, pattern, comments=(), number=7):
        with self.assertRaisesRegex(guard.GuardError, pattern):
            guard.check(self.base, self.head, comments, number)

    def test_unchanged_baseline_passes(self):
        self.assertIn("passed", guard.check(self.base, self.head))

    def test_experimental_decision_requires_no_approval(self):
        add_decision(self.head, decision(status="experimental"))
        self.assertIn("0 creator approvals", guard.check(self.base, self.head))

    def test_promotion_without_a_decision_fails(self):
        register = json.loads(self.head[guard.REGISTER])
        register["records"][0]["status"] = "canon"
        put(self.head, guard.REGISTER, register)
        self.blocked("decision required")

    def test_promotion_without_approval_fails(self):
        self.promote()
        self.blocked("authenticated creator approval")

    def test_approved_promotion_passes(self):
        item = self.promote()
        self.assertIn("1 creator approvals", guard.check(self.base, self.head, approve(self.head, item), 7))

    def test_ledger_claim_without_live_evidence_fails(self):
        approve(self.head, self.promote())
        self.blocked("No authenticated")

    def test_spoofed_login_cannot_approve(self):
        comments = approve(self.head, self.promote(), user_id=456)
        self.blocked("No authenticated", comments)

    def test_creator_bot_cannot_approve(self):
        comments = approve(self.head, self.promote())
        comments[0]["user"]["type"] = "Bot"
        self.blocked("No authenticated", comments)

    def test_general_praise_cannot_approve(self):
        comments = approve(self.head, self.promote())
        comments[0]["body"] = "Looks good; approve everything!"
        self.blocked("No authenticated", comments)

    def test_wrong_pr_cannot_replay_approval(self):
        comments = approve(self.head, self.promote(), pr_number=8)
        self.blocked("different-PR", comments)

    def test_wrong_comment_id_fails(self):
        comments = approve(self.head, self.promote())
        comments[0]["id"] = 11
        self.blocked("superseded", comments)

    def test_file_edit_invalidates_approval(self):
        item = self.promote()
        comments = approve(self.head, item)
        register = json.loads(self.head[guard.REGISTER])
        register["baseline"] = "changed"
        put(self.head, guard.REGISTER, register)
        self.blocked("Stale", comments)

    def test_decision_edit_invalidates_approval(self):
        item = self.promote()
        comments = approve(self.head, item)
        item["rationale"] = "Different evidence"
        put(self.head, guard.DECISIONS, {"schema_version": 1, "decisions": [item]})
        self.blocked("Stale", comments)

    def test_revocation_overrides_approval(self):
        item = self.promote()
        comments = approve(self.head, item)
        revoke = copy.deepcopy(comments[0])
        revoke.update(id=11, body=revoke["body"].replace("approve", "revoke"),
                      updated_at="2026-10-10T12:01:00Z")
        self.blocked("revoked", comments + [revoke])

    def test_edit_of_older_comment_can_revoke(self):
        comments = approve(self.head, self.promote())
        revoke = copy.deepcopy(comments[0])
        revoke.update(id=9, body=revoke["body"].replace("approve", "revoke"),
                      updated_at="2026-10-10T12:02:00Z")
        self.blocked("revoked", [revoke] + comments)

    def test_unrelated_comment_does_not_revoke(self):
        item = self.promote()
        comments = approve(self.head, item)
        extra = copy.deepcopy(comments[0])
        extra.update(id=11, body="Thank you", updated_at="2026-10-10T12:01:00Z")
        guard.check(self.base, self.head, comments + [extra], 7)

    def test_approval_file_addition_does_not_change_payload(self):
        item = self.promote()
        digest = guard.payload_digest(self.head, item)
        approve(self.head, item)
        self.assertEqual(digest, guard.payload_digest(self.head, item))

    def test_each_promoted_feature_requires_scope(self):
        item = self.promote()
        item["feature_ids"] = []
        put(self.head, guard.DECISIONS, {"schema_version": 1, "decisions": [item]})
        self.blocked("decision required", approve(self.head, item))

    def test_protected_document_change_requires_approval(self):
        self.head["docs/brief.md"] += b"Changed text\n"
        self.blocked("approval required for files")

    def test_new_document_requires_approval(self):
        self.head["docs/new.md"] = b"New authority"
        self.blocked("approval required for files")

    def test_deletion_is_bound_in_approval(self):
        self.base["docs/extra.md"] = self.head["docs/extra.md"] = b"Old text"
        del self.head["docs/extra.md"]
        item = decision(files=["docs/extra.md"], features=[])
        add_decision(self.head, item)
        guard.check(self.base, self.head, approve(self.head, item), 7)

    def test_uncovered_second_document_fails(self):
        item = self.promote()
        comments = approve(self.head, item)
        self.head["docs/brief.md"] += b"Unapproved drift"
        self.blocked("docs/brief.md", comments)

    def test_unrelated_code_can_change_without_design_approval(self):
        self.head["scripts/build_site.py"] = b"Renderer change"
        guard.check(self.base, self.head)

    def test_policy_and_checker_changes_require_approval(self):
        for path in (guard.POLICY, "scripts/canon_guard.py", ".github/workflows/validate.yml"):
            with self.subTest(path=path):
                self.head = copy.deepcopy(self.base)
                if path == guard.POLICY:
                    value = json.loads(self.head[path])
                    value["creator"]["id"] = 456
                    put(self.head, path, value)
                else:
                    self.head[path] = b"Changed checker"
                self.blocked("approval required for files")

    def test_head_policy_cannot_grant_creator_permission(self):
        item = self.promote()
        item["files"].append(guard.POLICY)
        put(self.head, guard.DECISIONS, {"schema_version": 1, "decisions": [item]})
        policy = json.loads(self.head[guard.POLICY])
        policy["creator"]["id"] = 456
        put(self.head, guard.POLICY, policy)
        self.blocked("No authenticated", approve(self.head, item, user_id=456))

    def test_existing_feature_id_cannot_be_removed(self):
        register = json.loads(self.head[guard.REGISTER])
        register["records"] = []
        put(self.head, guard.REGISTER, register)
        self.blocked("cannot be removed")

    def test_decision_history_is_append_only(self):
        add_decision(self.base, decision(status="experimental"))
        self.head = copy.deepcopy(self.base)
        value = json.loads(self.head[guard.DECISIONS])
        value["decisions"][0]["summary"] = "Rewritten history"
        put(self.head, guard.DECISIONS, value)
        self.blocked("append-only")

    def test_approval_history_is_append_only(self):
        item = self.promote()
        approve(self.head, item)
        self.base = copy.deepcopy(self.head)
        put(self.head, guard.APPROVALS, {"schema_version": 1, "approvals": []})
        self.blocked("append-only")

    def test_successor_decision_preserves_history(self):
        add_decision(self.base, decision(status="experimental"))
        self.head = copy.deepcopy(self.base)
        item = decision(identity="D-0002", supersedes="D-0001")
        add_decision(self.head, item)
        guard.check(self.base, self.head, approve(self.head, item), 7)

    def test_noncanon_status_transition_requires_a_decision(self):
        register = json.loads(self.head[guard.REGISTER])
        register["records"][0]["status"] = "provisional"
        put(self.head, guard.REGISTER, register)
        self.blocked("decision required")
        add_decision(self.head, decision(status="provisional"))
        guard.check(self.base, self.head)

    def test_baseline_version_change_requires_approval(self):
        register = json.loads(self.head[guard.REGISTER])
        register["baseline"] = "2.0"
        put(self.head, guard.REGISTER, register)
        self.blocked("approval required for files")

    def test_existing_canon_demotion_requires_approval(self):
        register = json.loads(self.base[guard.REGISTER])
        register["records"][0]["status"] = "canon"
        put(self.base, guard.REGISTER, register)
        add_decision(self.head, decision(status="experimental"))
        self.blocked("approval required for files")

    def test_existing_metadata_retarget_requires_approval(self):
        register = json.loads(self.head[guard.REGISTER])
        register["records"][0]["section"] = "specification"
        put(self.head, guard.REGISTER, register)
        add_decision(self.head, decision(status="experimental"))
        self.blocked("approval required for files")

    def test_missing_written_authority_fails(self):
        del self.head["docs/brief.md"]
        self.blocked("written authority")

    def test_github_check_publishes_failure_on_actual_pr_head(self):
        self.promote()
        self.run_github_check(expected_failure=True)

    def test_github_check_publishes_success_on_actual_pr_head(self):
        self.run_github_check(expected_failure=False)

    def run_github_check(self, expected_failure):
        base_sha, head_sha = "b" * 40, "c" * 40
        calls = []
        pr = {"state": "open", "head": {"sha": head_sha}, "base": {"sha": base_sha}}
        def request(path, payload=None, method=None):
            calls.append((path, payload, method))
            if path == "/pulls/7":
                return pr
            if path == "/check-runs":
                return {"id": 999}
            if path.startswith("/issues/7/comments"):
                return []
            return {}
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            event_path.write_text(json.dumps({"issue": {"number": 7}}))
            env = {"GITHUB_EVENT_PATH": str(event_path), "GITHUB_REPOSITORY": "owner/repo",
                   "GITHUB_TOKEN": "test-only-token"}
            with patch.dict(guard.os.environ, env), \
                 patch.object(guard.GitHub, "request", side_effect=request), \
                 patch.object(guard, "git", return_value=head_sha.encode()), \
                 patch.object(guard, "GitTree", side_effect=lambda sha: self.base if sha == base_sha else self.head), \
                 patch("builtins.print"):
                self.assertEqual(bool(guard.github_check()), expected_failure)
        creation = next(payload for path, payload, _ in calls if path == "/check-runs")
        self.assertEqual(creation["head_sha"], head_sha)
        self.assertEqual(calls[-1][0], "/check-runs/999")
        self.assertEqual(calls[-1][2], "PATCH")
        self.assertEqual(calls[-1][1]["conclusion"], "failure" if expected_failure else "success")

    def test_schema_rejects_duplicate_ids_unknown_refs_and_unsafe_paths(self):
        for mutation in (lambda d: d.update(references=["R99"]),
                         lambda d: d.update(feature_ids=["missing"]),
                         lambda d: d.update(files=["../secret"]),
                         lambda d: d.update(files=["docs/**"]),
                         lambda d: d.update(files=[guard.APPROVALS]),
                         lambda d: d.update(status="approved"),
                         lambda d: d.update(supersedes=[])):
            with self.subTest(mutation=mutation):
                tree = fixture()
                item = decision()
                mutation(item)
                add_decision(tree, item)
                with self.assertRaises(guard.GuardError):
                    guard.validate(tree)
        add_decision(self.head, decision())
        add_decision(self.head, decision())
        self.blocked("duplicate decision ID")

    def test_duplicate_json_keys_are_rejected(self):
        self.head[guard.DECISIONS] = b'{"schema_version":1,"decisions":[],"decisions":[]}'
        self.blocked("Duplicate JSON key")

    def test_installation_preserves_existing_canon(self):
        for path in (guard.POLICY, guard.DECISIONS, guard.APPROVALS):
            del self.base[path]
        self.assertIn("installation", guard.check(self.base, self.head))
        self.head["docs/brief.md"] += b"Hidden change"
        self.blocked("installation must preserve")

    def test_installation_cannot_invent_approval(self):
        for path in (guard.POLICY, guard.DECISIONS, guard.APPROVALS):
            del self.base[path]
        add_decision(self.head, decision())
        approve(self.head, decision())
        self.blocked("cannot invent")

    def test_github_comment_pagination(self):
        api = guard.GitHub("owner/repo", "test-only-token")
        with patch.object(api, "request", side_effect=[[{}] * 100, [{"id": 101}]]) as request:
            self.assertEqual(len(api.comments(7)), 101)
            self.assertTrue(request.call_args.args[0].endswith("page=2"))

    def test_git_reads_committed_bytes_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "file").write_bytes(b"committed")
            (root / "link").symlink_to("file")
            subprocess.run(["git", "-C", directory, "add", "."], check=True)
            subprocess.run(["git", "-C", directory, "-c", "user.name=Test", "-c",
                            "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
            (root / "file").write_bytes(b"untrusted worktree")
            original = guard.git
            with patch.object(guard, "git", side_effect=lambda *args: original("-C", directory, *args)):
                tree = guard.GitTree("HEAD")
                self.assertEqual(tree["file"], b"committed")
                with self.assertRaisesRegex(guard.GuardError, "Symlinks"):
                    tree["link"]


if __name__ == "__main__":
    unittest.main()
