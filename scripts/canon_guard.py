#!/usr/bin/env python3
"""Myca Canon Automation v0.2. Read Git objects; never execute proposal code.

Decision and approval ledgers are append-only. A creator comment authenticates
an approval; a ledger entry alone can never grant approval.
"""
import argparse
from collections.abc import Mapping
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.error
import urllib.request

POLICY = "data/canon-policy.json"
DECISIONS = "data/design-decisions.json"
APPROVALS = "data/creator-approvals.json"
REGISTER = "data/canon-register.json"
STATUSES = {"canon", "provisional", "experimental", "unresolved", "superseded",
            "rejected", "style-specific"}
CHECK_NAME = "Myca canon approval"


class GuardError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GuardError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def document(tree, path):
    require(path in tree, f"Missing metadata: {path}")
    try:
        value = json.loads(tree[path], object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as exc:
        raise GuardError(f"Invalid JSON in {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path} must be an object")
    require(type(value.get("schema_version")) is int and value["schema_version"] == 1,
            f"Unsupported schema_version in {path}")
    return value


def text(value):
    return isinstance(value, str) and bool(value.strip())


def safe_path(value):
    return (text(value) and not value.startswith(("/", "-")) and
            "\\" not in value and "\x00" not in value and
            all(part not in ("", ".", "..") for part in value.split("/")) and
            PurePosixPath(value).parts[0] != ".git")


def string_list(value, label, nonempty=False):
    require(isinstance(value, list) and all(text(x) for x in value),
            f"{label} must be a list of nonempty strings")
    require(len(value) == len(set(value)), f"Duplicates in {label}")
    require(not nonempty or bool(value), f"{label} cannot be empty")


def policy_from(tree):
    policy = document(tree, POLICY)
    require(set(policy) == {"schema_version", "automation_version", "creator",
                            "protected_paths", "governance_paths"}, "Invalid policy fields")
    require(policy["automation_version"] == "0.2", "Unsupported automation version")
    creator = policy["creator"]
    require(isinstance(creator, dict) and set(creator) == {"login", "id"} and
            text(creator["login"]) and type(creator["id"]) is int and creator["id"] > 0,
            "Policy requires an explicit creator login and numeric GitHub ID")
    for field in ("protected_paths", "governance_paths"):
        string_list(policy[field], field, nonempty=True)
        require(all(safe_path(x) for x in policy[field]), f"Unsafe {field}")
    return policy


def records_from(tree):
    register = document(tree, REGISTER)
    require(text(register.get("baseline")), "Canon baseline is required")
    records = register.get("records")
    require(isinstance(records, list), "Canon records must be a list")
    result = {}
    references = set(re.findall(r"\b[RC]\d{2,}\b",
                               tree["docs/References/Reference Index.md"].decode("utf-8")))
    for record in records:
        require(isinstance(record, dict), "Canon record must be an object")
        identity = record.get("id")
        require(text(identity) and identity not in result, "Invalid or duplicate canon ID")
        require(isinstance(record.get("status"), str) and record["status"] in STATUSES,
                f"Invalid status for {identity}")
        authority = record.get("authority")
        require(safe_path(authority) and authority.startswith("docs/") and authority in tree,
                f"Missing or unsafe written authority for {identity}")
        section = record.get("section")
        require(text(section) and section.lower() in tree[authority].decode("utf-8").lower(),
                f"Missing authority section for {identity}")
        refs = record.get("references", [])
        string_list(refs, f"{identity} references")
        require(set(refs) <= references, f"Unknown reference ID for {identity}")
        result[identity] = record
    return register, result, references


def ledger(tree, path, key):
    value = document(tree, path)
    require(set(value) == {"schema_version", key} and isinstance(value[key], list),
            f"Invalid ledger: {path}")
    return value[key]


def validate(tree):
    """Validate schema and links without granting any creator approval."""
    policy_from(tree)
    _, records, references = records_from(tree)
    decisions = {}
    for decision in ledger(tree, DECISIONS, "decisions"):
        require(isinstance(decision, dict), "Decision must be an object")
        require(set(decision) == {"id", "status", "feature_ids", "summary", "rationale",
                                  "files", "references", "supersedes"}, "Invalid decision fields")
        identity = decision["id"]
        require(text(identity) and re.fullmatch(r"D-[0-9]{4,}", identity) and
                identity not in decisions, "Invalid or duplicate decision ID")
        require(isinstance(decision["status"], str) and decision["status"] in STATUSES,
                f"Invalid decision status: {identity}")
        require(text(decision["summary"]) and text(decision["rationale"]),
                f"{identity} requires a summary and rationale")
        for field in ("feature_ids", "files", "references"):
            string_list(decision[field], f"{identity} {field}")
        require(set(decision["feature_ids"]) <= records.keys(), f"Unknown feature in {identity}")
        require(set(decision["references"]) <= references, f"Unknown reference in {identity}")
        require(all(safe_path(p) and p not in (DECISIONS, APPROVALS) and
                    not any(c in p for c in "*?[") for p in decision["files"]),
                f"{identity} requires exact safe file paths, excluding the ledgers")
        require(decision["supersedes"] is None or
                (text(decision["supersedes"]) and decision["supersedes"] in decisions),
                f"{identity} supersedes an unknown or later decision")
        require(decision["status"] != "canon" or bool(decision["files"]),
                f"Canon decision {identity} must name its exact file scope")
        decisions[identity] = decision
    approvals = {}
    for approval in ledger(tree, APPROVALS, "approvals"):
        require(isinstance(approval, dict) and set(approval) ==
                {"id", "decision_id", "payload_sha256", "pr_number", "comment_id"},
                "Invalid approval fields")
        identity = approval["id"]
        require(text(identity) and re.fullmatch(r"A-[0-9]{4,}", identity) and
                identity not in approvals, "Invalid or duplicate approval ID")
        require(text(approval["decision_id"]) and approval["decision_id"] in decisions,
                f"Unknown decision for {identity}")
        require(decisions[approval["decision_id"]]["status"] == "canon",
                f"{identity} must approve a canon decision")
        require(text(approval["payload_sha256"]) and
                re.fullmatch(r"[0-9a-f]{64}", approval["payload_sha256"]),
                f"Invalid payload hash for {identity}")
        require(all(type(approval[k]) is int and approval[k] > 0
                    for k in ("pr_number", "comment_id")), f"Invalid GitHub evidence for {identity}")
        approvals[identity] = approval
    return decisions, approvals


def payload_digest(tree, decision):
    """Bind approval to the full decision and exact bytes (or deletion) of scoped files."""
    payload = {"decision": decision, "files": {
        path: hashlib.sha256(tree[path]).hexdigest() if path in tree else None
        for path in sorted(decision["files"])
    }}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def append_only(old, new, label):
    require(all(identity in new and new[identity] == item for identity, item in old.items()),
            f"{label} is append-only; add a successor instead of editing or deleting history")
    require(list(new)[:len(old)] == list(old), f"{label} history cannot be reordered")


def authenticated(approval, decision, tree, comments, creator, pr_number):
    digest = payload_digest(tree, decision)
    require(approval["pr_number"] == pr_number and approval["payload_sha256"] == digest,
            f"Stale or different-PR approval for {decision['id']}; expected payload {digest}")
    relevant = []
    for comment in comments:
        user = comment.get("user", {})
        if user.get("id") == creator["id"] and user.get("type") == "User":
            body = comment.get("body", "").strip()
            if body in (f"myca-approve {decision['id']} {digest}",
                        f"myca-revoke {decision['id']} {digest}"):
                require(type(comment.get("id")) is int and text(comment.get("updated_at")),
                        "Malformed GitHub comment evidence")
                relevant.append(comment)
    require(bool(relevant), f"No authenticated creator approval for {decision['id']} ({digest})")
    latest = max(relevant, key=lambda c: (c["updated_at"], c["id"]))
    require(latest["id"] == approval["comment_id"] and
            latest["body"].strip() == f"myca-approve {decision['id']} {digest}",
            f"Creator approval for {decision['id']} was revoked, edited, or superseded")


def check(base, head, comments=(), pr_number=None):
    decisions, approvals = validate(head)
    _, old_records, _ = records_from(base)
    _, records, _ = records_from(head)
    require(old_records.keys() <= records.keys(), "Existing feature IDs cannot be removed or renamed")
    bootstrap = POLICY not in base
    policy = policy_from(head if bootstrap else base)
    changed = {p for p in set(base) | set(head) if base.get(p) != head.get(p)}
    protected = {p for p in changed if matches(p, policy["protected_paths"])}
    if bootstrap:
        require(not protected and REGISTER not in changed,
                "Automation installation must preserve all existing canon and documentation")
        require(not approvals and not any(d["status"] == "canon" for d in decisions.values()),
                "Automation installation cannot invent creator approvals or canon decisions")
        return "Automation v0.2 installation: existing canon and documentation unchanged"
    old_decisions, old_approvals = validate(base)
    append_only(old_decisions, decisions, "Decision ledger")
    append_only(old_approvals, approvals, "Approval ledger")
    guarded = protected | {p for p in changed if matches(p, policy["governance_paths"])}
    changed_features = {identity for identity, record in records.items()
                        if record != old_records.get(identity) and
                        (record["status"] == "canon" or
                         old_records.get(identity, {}).get("status") == "canon")}
    proposed_features = {identity for identity, record in records.items()
                         if record != old_records.get(identity)}
    new_decisions = {i: d for i, d in decisions.items() if i not in old_decisions}
    for identity in proposed_features:
        require(any(identity in d["feature_ids"] and REGISTER in d["files"]
                    for d in new_decisions.values()),
                f"Version-controlled decision required for feature: {identity}")
    # Other record metadata can change only through a scoped approval; adding or
    # changing a non-canon status alone is a proposal, not a canon promotion.
    for identity in records.keys() & old_records.keys():
        before = {k: v for k, v in old_records[identity].items() if k != "status"}
        after = {k: v for k, v in records[identity].items() if k != "status"}
        if before != after:
            changed_features.add(identity)
    if changed_features or any(base.get(REGISTER) != head.get(REGISTER) and
                              document(base, REGISTER).get(k) != document(head, REGISTER).get(k)
                              for k in set(document(base, REGISTER)) | set(document(head, REGISTER))
                              if k != "records"):
        guarded.add(REGISTER)
    new_canon = {i: d for i, d in decisions.items()
                 if i not in old_decisions and d["status"] == "canon"}
    new_approvals = {i: a for i, a in approvals.items() if i not in old_approvals}
    approved = {}
    for approval in new_approvals.values():
        identity = approval["decision_id"]
        require(identity in new_canon, "New approvals must refer to a new canon decision")
        require(identity not in approved, f"Duplicate approval for {identity}")
        authenticated(approval, decisions[identity], head, comments, policy["creator"], pr_number)
        approved[identity] = decisions[identity]
    require(new_canon.keys() <= approved.keys(),
            "Every new canon decision needs an authenticated creator approval")
    covered = {p for d in approved.values() for p in d["files"]}
    require(guarded <= covered, f"Creator approval required for files: {', '.join(sorted(guarded - covered))}")
    for identity in changed_features:
        require(any(identity in d["feature_ids"] and REGISTER in d["files"]
                    for d in approved.values()), f"Creator approval required for feature: {identity}")
    return f"Canon gate passed: {len(guarded)} guarded files, {len(approved)} creator approvals"


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)


class GitTree(Mapping):
    """Read-only, lazy view of committed files; symlink metadata is rejected."""
    def __init__(self, ref):
        self.sha = git("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
        self.entries = {}
        self.cache = {}
        for entry in git("ls-tree", "-rz", self.sha).split(b"\0"):
            if entry:
                metadata, path = entry.split(b"\t", 1)
                mode, kind, sha = metadata.decode().split()
                self.entries[path.decode("utf-8")] = (mode, kind, sha)

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, path):
        mode, kind, sha = self.entries[path]
        require(kind == "blob" and mode in ("100644", "100755"),
                f"Symlinks and submodules are not accepted by canon automation: {path}")
        if path not in self.cache:
            self.cache[path] = git("cat-file", "blob", sha)
        return self.cache[path]


class GitHub:
    def __init__(self, repository, token):
        require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)),
                "Invalid GitHub repository")
        require(bool(token), "GITHUB_TOKEN is required for authenticated approval checks")
        self.root = f"https://api.github.com/repos/{repository}"
        self.token = token

    def request(self, path, payload=None, method=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.root + path, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
            "User-Agent": "myca-canon-automation/0.2"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def comments(self, number):
        result = []
        page = 1
        while True:
            batch = self.request(f"/issues/{number}/comments?per_page=100&page={page}")
            require(isinstance(batch, list), "Invalid GitHub comments response")
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1


def github_check():
    """Called only from trusted base code by pull_request_target/issue_comment."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    api = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_TOKEN"))
    number = event.get("pull_request", event.get("issue", {})).get("number")
    require(type(number) is int and number > 0, "Missing pull request number")
    pr = api.request(f"/pulls/{number}")
    require(pr["state"] == "open", "Pull request is closed")
    head_sha, base_sha = pr["head"]["sha"], pr["base"]["sha"]
    require(all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (head_sha, base_sha)),
            "Invalid GitHub commit SHA")
    # Fetch Git objects, never checkout or execute the proposal. Forks use the
    # base repository's pull ref. Ref text comes from a validated numeric ID.
    git("fetch", "--no-tags", "origin", base_sha,
        f"+refs/pull/{number}/head:refs/canon-guard/head")
    require(git("rev-parse", "refs/canon-guard/head").decode().strip() == head_sha,
            "Pull request changed during evaluation; rerun the gate")
    run = api.request("/check-runs", {"name": CHECK_NAME, "head_sha": head_sha, "status": "in_progress"})
    conclusion = "success"
    try:
        summary = check(GitTree(base_sha), GitTree(head_sha), api.comments(number), number)
    except (GuardError, KeyError, ValueError, UnicodeError, subprocess.CalledProcessError,
            urllib.error.URLError) as exc:
        conclusion, summary = "failure", str(exc)
    # Publish to the actual PR head, including when triggered by a creator comment.
    api.request(f"/check-runs/{run['id']}", {"status": "completed", "conclusion": conclusion,
        "output": {"title": CHECK_NAME, "summary": summary[:60000]}}, method="PATCH")
    print(summary)
    return conclusion != "success"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "digests", "check", "github-check"))
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        if args.command == "github-check":
            return github_check()
        head = GitTree(args.head)
        if args.command == "validate":
            validate(head)
            print("Decision and approval schemas valid; approval authenticity is checked by the canon gate")
        elif args.command == "digests":
            decisions, _ = validate(head)
            for decision in decisions.values():
                print(f"{decision['id']}: myca-approve {decision['id']} {payload_digest(head, decision)}")
        else:
            require(args.base is not None, "check requires an explicit --base; it cannot approve a snapshot alone")
            print(check(GitTree(args.base), head))
        return 0
    except (GuardError, KeyError, ValueError, UnicodeError, subprocess.CalledProcessError,
            urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
