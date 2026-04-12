#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# docprep CLI Quickstart
#
# Demonstrates the CLI workflow step by step.
# Run: bash examples/cli_quickstart.sh
# ──────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_DOCS="$SCRIPT_DIR/sample_docs"

echo "============================================"
echo "  docprep CLI Quickstart"
echo "============================================"
echo ""

# ── Step 1: Preview document structure ──
echo "── Step 1: Preview document structure ──"
echo "Command: docprep preview $SAMPLE_DOCS"
echo ""
python3 -m docprep preview "$SAMPLE_DOCS"
echo ""

# ── Step 2: Ingest into SQLite ──
DB_DIR=$(mktemp -d)
DB_PATH="$DB_DIR/docs.db"
echo "── Step 2: Ingest into SQLite ──"
echo "Command: docprep ingest $SAMPLE_DOCS --db sqlite:///$DB_PATH"
echo ""
python3 -m docprep ingest "$SAMPLE_DOCS" --db "sqlite:///$DB_PATH"
echo ""

# ── Step 3: Export as JSONL ──
OUTPUT_DIR=$(mktemp -d)
OUTPUT="$OUTPUT_DIR/records.jsonl"
echo "── Step 3: Export as JSONL ──"
echo "Command: docprep export $SAMPLE_DOCS -o $OUTPUT"
echo ""
python3 -m docprep export "$SAMPLE_DOCS" -o "$OUTPUT"
echo ""
echo "Exported records (first 3 lines):"
head -3 "$OUTPUT"
echo "..."
echo ""
LINES=$(wc -l < "$OUTPUT")
echo "Total: $LINES records in $OUTPUT"
echo ""

# ── Step 4: Check what changed (diff) ──
echo "── Step 4: Check for changes ──"
echo "Command: docprep diff $SAMPLE_DOCS --db sqlite:///$DB_PATH"
echo ""
python3 -m docprep diff "$SAMPLE_DOCS" --db "sqlite:///$DB_PATH"
echo ""

# ── Step 5: Use a config file ──
echo "── Step 5: Using a config file ──"
echo "Instead of passing flags, create a docprep.toml:"
echo ""
echo '  source = "docs/"'
echo '  '
echo '  [sink]'
echo '  database_url = "sqlite:///docs.db"'
echo '  create_tables = true'
echo '  '
echo '  [[chunkers]]'
echo '  type = "heading"'
echo '  '
echo '  [[chunkers]]'
echo '  type = "token"'
echo '  max_tokens = 512'
echo ""
echo "Then just run: docprep ingest"
echo ""

# Cleanup
rm -rf "$DB_DIR" "$OUTPUT_DIR"

echo "============================================"
echo "  Done! See 'docprep --help' for all commands"
echo "============================================"
