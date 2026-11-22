"""Submission integrity check (pure Python + git). Writes a JSON report; exit 1 on any problem.

    python3 research/integrity_check.py <repo> <out.json>

Checks: release ZIP SHA-256 (dist/final/Techtonic.zip) equals the published value; tag submission-baseline-v1.0
resolves to the submitted commit; branch submission/final still points there; no file under the official paths
(wrapper/, scene.blend, submission/, packaging/, dist/, renders/, metadata.json, directions/, tools/) differs between
the baseline tag and the working tree of research/upgrade; the GitHub release asset is not touched (local check only).
"""
import hashlib, json, subprocess, sys
repo, out = sys.argv[1:3]
EXPECT_ZIP = "acccb548c270bfab4719c3f173eda544a1b818fd858f56b1fe2d67a07790a0dc"; EXPECT_COMMIT = "3155655"
def git(*a): return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout.strip()
r = {}
r["zip_sha256"] = hashlib.sha256(open(f"{repo}/dist/final/Techtonic.zip", "rb").read()).hexdigest(); r["zip_ok"] = r["zip_sha256"] == EXPECT_ZIP
r["tag_commit"] = git("rev-list", "-n1", "submission-baseline-v1.0"); r["tag_ok"] = r["tag_commit"].startswith(EXPECT_COMMIT)
r["submission_final_commit"] = git("rev-parse", "submission/final"); r["submission_final_ok"] = r["submission_final_commit"].startswith(EXPECT_COMMIT)
paths = ["wrapper", "scene.blend", "submission", "packaging", "dist", "renders", "metadata.json", "directions", "tools"]
r["official_paths_diff_vs_tag"] = git("diff", "--stat", "submission-baseline-v1.0", "--", *paths)
r["official_paths_untracked"] = git("ls-files", "--others", "--exclude-standard", "--", *paths)
r["official_paths_ok"] = r["official_paths_diff_vs_tag"] == "" and r["official_paths_untracked"] == ""
r["ok"] = all(r[k] for k in ("zip_ok", "tag_ok", "submission_final_ok", "official_paths_ok"))
json.dump(r, open(out, "w"), indent=1); print(json.dumps(r, indent=1)); sys.exit(0 if r["ok"] else 1)
