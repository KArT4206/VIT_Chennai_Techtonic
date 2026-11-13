#!/usr/bin/env bash
# Build the evaluator ZIP in a fresh staging folder, using the brief's exact Track 1 layout:
#   scene.blend  wrapper/eyes.py  renders/  metadata.json  README.md   (at the ZIP root)
#
#   tools/build_package.sh <staging_dir> [team_name]
#
# Copies only those files (README from packaging/README.md). It refuses to reuse an existing
# staging folder and never writes inside the repository.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
stage="${1:?usage: build_package.sh <staging_dir> [team_name]}"
team="${2:-Techtonic}"

[ -e "$stage" ] && { echo "refusing: $stage already exists" >&2; exit 1; }
case "$(cd "$(dirname "$stage")" && pwd)/" in "$repo"/*) echo "refusing: staging inside repo" >&2; exit 1;; esac

mkdir -p "$stage/$team/wrapper" "$stage/$team/renders"
cp "$repo/scene.blend" "$repo/metadata.json" "$stage/$team/"
cp "$repo/packaging/README.md" "$stage/$team/README.md"
cp "$repo/wrapper/eyes.py" "$stage/$team/wrapper/"
cp "$repo"/renders/frame_0[0-9].png "$stage/$team/renders/"

# Files at the ZIP root, stored without macOS extras (-X drops resource forks/extended attrs).
(cd "$stage/$team" && zip -qrX "../$team.zip" scene.blend wrapper renders metadata.json README.md)
echo "$stage/$team.zip"
