"""Final-round package audit -> research/demo/final_round_audit.json (pure Python + git/gh).

    python3 research/demo/source/final_audit.py <deck_text.md>

<deck_text.md> is the pptx skill's slide_text.py output for final_round_presentation.pptx.
Checks: README relative links/anchors resolve; GitHub links resolve (tag, release); README commands reference existing
files (Blender commands are labelled 'not executed here'); the pure-Python commands are executed; deck wording keeps
the required qualifiers; deck and video use the same agreed figures; the silent video is unchanged since its QC;
original submission files and refs are untouched.
"""
import hashlib, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); DEMO = os.path.dirname(HERE); REPO = os.path.dirname(os.path.dirname(DEMO))
sh = lambda *c: subprocess.run(c, capture_output=True, text=True, cwd=REPO)
sha = lambda p: hashlib.sha256(open(os.path.join(REPO, p), "rb").read()).hexdigest()
R = {}; readme = open(os.path.join(REPO, "README.md")).read()
anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-") for h in re.findall(r"^#+ (.+)$", readme, re.M)}
tracked = set(sh("git", "ls-files").stdout.split())
links = []
for text, url in re.findall(r"\[([^\]]+)\]\(([^)\s]+)\)", readme):
    if url.startswith("http"):
        if "/releases/tag/v1.0" in url: ok = sh("gh", "release", "view", "v1.0", "-R", "KArT4206/VIT_Chennai_Techtonic", "--json", "tagName").returncode == 0
        elif "submission-baseline-v1.0" in url: ok = "refs/tags/submission-baseline-v1.0" in sh("git", "ls-remote", "--tags", "origin").stdout
        else: ok = None
        links.append(dict(link=url, kind="external", resolves=ok))
    elif url.startswith("#"):
        links.append(dict(link=url, kind="anchor", resolves=url[1:] in anchors))
    else:
        p = url.rstrip("/"); ex = os.path.exists(os.path.join(REPO, p))
        tr = p in tracked or any(t.startswith(p + "/") for t in tracked)
        links.append(dict(link=url, kind="relative", resolves=ex, tracked_in_git=tr, note=None if tr else "new file in this change (uncommitted)"))
R["readme_links"] = dict(total=len(links), unresolved=[l for l in links if l["resolves"] is False], links=links)
cmds = []
for block in re.findall(r"```bash\n(.*?)```", readme, re.S):
    for line in block.strip().splitlines():
        c = line.split("#")[0].strip()
        refs = [r for r in re.findall(r"(?:research|tools|wrapper)/[\w./-]+", c)]
        missing = [r for r in refs if not os.path.exists(os.path.join(REPO, r))]
        kind = "blender: syntax and referenced files checked, not executed here" if c.startswith(("blender", "PYTHON=")) else "python: executed"
        rec = dict(command=c, referenced_files=refs, missing=missing, kind=kind)
        if kind == "python: executed":
            r = sh(*[sys.executable if x == "python3" else x for x in c.split()]); rec["exit_code"] = r.returncode
        cmds.append(rec)
for c in re.findall(r"`(blender -b --factory-startup[^`]+|python3 research/[^`]+)`", readme):
    refs = re.findall(r"(?:research|tools)/[\w./-]+", c); cmds.append(dict(command=c, referenced_files=refs, missing=[r for r in refs if not os.path.exists(os.path.join(REPO, r))], kind="inline: referenced files checked, not executed"))
R["readme_commands"] = cmds
deck = open(sys.argv[1]).read()
need = {"effective fitted label": "EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS", "ROI rejected": "NOT ADOPTED", "segmentation provisional": "provisional",
        "legacy verifier": "51 PASS / 20 FAIL", "research suite": "research compliance checks passed", "held-out": "held-out", "glitch": "8.09 px detector glitch",
        "dataset vs detector": "Generation success is not detector accuracy", "condition-specific": "condition-specific", "not human": "not for other eyes or human subjects"}
R["deck_wording"] = {k: (v in deck) for k, v in need.items()}
vm = json.load(open(os.path.join(DEMO, "asset_manifest.json")))["checks"]; dm = json.load(open(os.path.join(DEMO, "presentation_numbers.json")))["checks"]
agreed_v = sorted(round(c["agreed"], 4) for c in vm); agreed_d = sorted(round(c["agreed"], 4) for c in dm)
R["deck_video_same_figures"] = dict(video_checks=len(vm), deck_checks=len(dm), video_pass=all(abs(c["value"] - c["agreed"]) <= c["tol"] for c in vm),
                                    deck_pass=all(abs(c["value"] - c["agreed"]) <= c["tol"] for c in dm), shared_figures=len(set(agreed_v) & set(agreed_d)),
                                    deck_only=sorted(set(agreed_d) - set(agreed_v)), video_only=sorted(set(agreed_v) - set(agreed_d)))
q = json.load(open(os.path.join(DEMO, "final_quality_check.json")))
R["video_unchanged_since_qc"] = sha("research/demo/final_round_silent.mp4") == q["video_sha256"]
R["protection"] = dict(branch=sh("git", "branch", "--show-current").stdout.strip(),
    submission_final=sh("git", "rev-parse", "--short", "submission/final").stdout.strip(), origin_submission_final=sh("git", "rev-parse", "--short", "origin/submission/final").stdout.strip(),
    baseline_tag=sh("git", "rev-parse", "--short", "submission-baseline-v1.0^{commit}").stdout.strip(),
    zip_ok=sha("dist/final/Techtonic.zip").startswith("acccb548"), original_video_ok=sha("submission/VIT_Chennai_Techtonic.mp4").startswith("a7cf7e5b"),
    original_pptx_ok=sha("submission/VIT_Chennai_Techtonic.pptx").startswith("9ef3f011"),
    tracked_changes_outside_scope=[l for l in sh("git", "status", "--porcelain").stdout.splitlines() if not re.match(r"^.. (README\.md|research/)", l)],
    release_v1_assets=sh("gh", "release", "view", "v1.0", "-R", "KArT4206/VIT_Chennai_Techtonic", "--json", "assets", "-q", "[.assets[].name]").stdout.strip())
P = R["protection"]
R["all_pass"] = (not R["readme_links"]["unresolved"] and all(not c["missing"] for c in cmds) and all(c.get("exit_code", 0) == 0 for c in cmds)
                 and all(R["deck_wording"].values()) and R["deck_video_same_figures"]["video_pass"] and R["deck_video_same_figures"]["deck_pass"] and R["video_unchanged_since_qc"]
                 and P["branch"] == "research/upgrade" and P["submission_final"] == P["origin_submission_final"] == P["baseline_tag"] == "3155655"
                 and P["zip_ok"] and P["original_video_ok"] and P["original_pptx_ok"] and not P["tracked_changes_outside_scope"])
json.dump(R, open(os.path.join(DEMO, "final_round_audit.json"), "w"), indent=1)
print(json.dumps({k: R[k] for k in ("deck_wording", "deck_video_same_figures", "video_unchanged_since_qc", "protection", "all_pass")}, indent=1))
print("links", R["readme_links"]["total"], "unresolved", R["readme_links"]["unresolved"]); print("commands", [(c["command"][:60], c.get("exit_code"), c["missing"]) for c in cmds])
