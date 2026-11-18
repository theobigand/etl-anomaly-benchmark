#!/usr/bin/env bash
# Generate one photographic asset with the Codex CLI built-in image_gen tool.
# Usage: gen-image.sh <theme-dir> <name> [reference-image ...]
#   Prompt = <theme>/prompts/_style.txt + <theme>/prompts/_subjects.txt (if present) + <theme>/prompts/<name>.txt
#   MODE=edit  -> the first reference image is the frame to edit (state change only).
# Output: <theme>/assets/source/<name>.png ; a previous file is moved to assets/rejected/.
# The output is collected from the Codex session folder named in this job's log (never "newest file").
set -euo pipefail
theme="$(cd "$1" && pwd)"; name="$2"; shift 2
mkdir -p "$theme/logs" "$theme/assets/source" "$theme/assets/rejected"
spec="$(cat "$theme/prompts/_style.txt"; [ -f "$theme/prompts/_subjects.txt" ] && cat "$theme/prompts/_subjects.txt"; cat "$theme/prompts/$name.txt")"
imgs=(); for r in "$@"; do imgs+=("--image=$r"); done
if [ "${MODE:-new}" = "edit" ]; then
  lead="Use your built-in image_gen tool exactly once to EDIT the first attached photograph. Keep camera position, lens, framing, geometry and every object identical; change ONLY what the spec below describes. Any further attached images are identity references. Do not copy, move or edit any files on disk; just produce the image and reply DONE."
else
  lead="Use your built-in image_gen tool exactly once to generate ONE photorealistic image from the spec below. Any attached images are REFERENCE images for subject identity (shape, proportions, materials, setting) only; generate a new photograph. Do not copy, move or edit any files on disk; just generate the image and reply DONE."
fi
log="$theme/logs/$name.$(date +%s).log"
codex exec --skip-git-repo-check -s read-only -C "$theme" ${imgs[@]+"${imgs[@]}"} "$lead

SPEC:
$spec" < /dev/null > "$log" 2>&1 || { echo "codex failed for $name, see $log" >&2; exit 1; }
sid=$(grep -m1 "session id:" "$log" | awk '{print $3}')
[ -n "$sid" ] || { echo "no session id in $log" >&2; exit 1; }
f=$(/bin/ls -t "$HOME/.codex/generated_images/$sid/"*.png 2>/dev/null | head -1 || true)
[ -n "$f" ] || { echo "no image produced for $name (session $sid), see $log" >&2; exit 1; }
if [ -f "$theme/assets/source/$name.png" ]; then mv "$theme/assets/source/$name.png" "$theme/assets/rejected/$name-$(date +%s).png"; fi
cp "$f" "$theme/assets/source/$name.png"
dims=$(magick identify -format '%wx%h' "$theme/assets/source/$name.png")
sha=$(shasum -a 256 "$theme/assets/source/$name.png" | awk '{print $1}')
refs="$*"; echo "$(date -u +%FT%TZ)	$name	mode=${MODE:-new}	session=$sid	src=$(basename "$f")	$dims	sha256=$sha	refs=${refs:-none}" >> "$theme/logs/provenance-map.tsv"
echo "$theme/assets/source/$name.png $dims"
