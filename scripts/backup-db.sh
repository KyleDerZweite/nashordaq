#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
DB_PATH="./data/nashordaq.db"

if [ ! -f "$DB_PATH" ]; then
    echo "Error: $DB_PATH not found" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/nashordaq-${TIMESTAMP}.db"

cp "$DB_PATH" "$DEST"
echo "Backed up to $DEST"
