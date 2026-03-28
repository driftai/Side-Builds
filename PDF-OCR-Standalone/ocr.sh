#!/usr/bin/env bash
set -euo pipefail
START_TIME=$(date +%s)

# Get PDF path: first argument
if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/document.pdf"
  exit 1
fi
PDF_IN="$1"

# Resolve absolute path
PDF_ABS="$(readlink -f "$PDF_IN")"
if [ ! -f "$PDF_ABS" ]; then
  echo "Error: file not found: $PDF_ABS"
  exit 1
fi

# Create working directory
WORKDIR="$(mktemp -d)"
IMAGES_DIR="$WORKDIR/images"
mkdir -p "$IMAGES_DIR"

# Output locations (final output stays in package root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FINAL_OUTPUT="$SCRIPT_DIR/full_output.txt"
> "$FINAL_OUTPUT"  # truncate
START_TIME=$(date +%s)

echo "Converting PDF to images..."
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -png -r 150 "$PDF_ABS" "$IMAGES_DIR/page"
elif command -v convert >/dev/null 2>&1; then
  convert -density 150 "$PDF_ABS[0-9]*" "$IMAGES_DIR/page-%d.png" 2>/dev/null || true
  # If the above fails (non-zero because no matches?), try alternative
  if [ "$(ls -A "$IMAGES_DIR" 2>/dev/null | wc -l)" -eq 0 ]; then
    convert -density 150 "$PDF_ABS" "$IMAGES_DIR/page-%d.png"
  fi
else
  echo "Error: Neither pdftoppm nor convert (ImageMagick) is installed."
  rm -rf "$WORKDIR"
  exit 1
fi

# Count images
PAGE_COUNT=$(ls "$IMAGES_DIR"/*.png 2>/dev/null | wc -l)
if [ "$PAGE_COUNT" -eq 0 ]; then
  echo "Error: No images generated from PDF."
  rm -rf "$WORKDIR"
  exit 1
fi

echo "Generated $PAGE_COUNT images. Running OCR... (approx. 30-90s per page depending on network and model)"

# Process each image in order
TOTAL_PAGES=$PAGE_COUNT
CURRENT=0
for img in $(ls -1v "$IMAGES_DIR"/*.png); do
  CURRENT=$((CURRENT+1))
  PAGE_NUM=$(basename "$img" | sed -E 's/.*-([0-9]+)\.png/\1/')
  echo "[$CURRENT/$TOTAL_PAGES] OCR page $PAGE_NUM started at $(date +%H:%M:%S)"
  OUT_TXT="$WORKDIR/ocr_page-${PAGE_NUM}.txt"
  START_PAGE=$(date +%s)
  if python3 "$SCRIPT_DIR/analyze-screenshot-v2.py" "$img" "Extract all text verbatim with paragraph structure." > "$OUT_TXT"; then
    echo "=== PAGE $PAGE_NUM ===" >> "$FINAL_OUTPUT"
    cat "$OUT_TXT" >> "$FINAL_OUTPUT"
    echo "" >> "$FINAL_OUTPUT"
    STATUS="OK"
  else
    echo "=== PAGE $PAGE_NUM ===" >> "$FINAL_OUTPUT"
    echo "[OCR failed for this page]" >> "$FINAL_OUTPUT"
    echo "" >> "$FINAL_OUTPUT"
    STATUS="FAILED"
  fi
  END_PAGE=$(date +%s)
  DURATION=$((END_PAGE-START_PAGE))
  # Rough estimate for remaining
  if [ $CURRENT -lt $TOTAL_PAGES ]; then
    REMAINING_SEC=$(( (TOTAL_PAGES-CURRENT) * (DURATION<60?60:DURATION) ))
    REMAINING_MIN=$((REMAINING_SEC/60))
    echo "    Page $PAGE_NUM $STATUS. Est. ${REMAINING_MIN} min remaining."
  else
    echo "    Page $PAGE_NUM $STATUS. Completed in ${DURATION}s."
  fi
done
ELAPSED=$(( $(date +%s) - START_TIME ))
echo "All done in ${ELAPSED}s. Final output: $FINAL_OUTPUT"
echo "Work files (images, per-page outputs) are in $WORKDIR and will be deleted in 8 minutes."



# Schedule cleanup after 8 minutes (480 seconds)
(
  sleep 480
  rm -rf "$WORKDIR" 2>/dev/null || true
) &

