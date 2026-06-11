#!/bin/bash
# Start SEO Dashboard locally on http://localhost:3000
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"

# Build client if public/ is empty or missing
if [ ! -f "$SERVER_DIR/public/index.html" ]; then
  echo "Building client..."
  cd "$SCRIPT_DIR" && npm run build
fi

# Create DB directory if needed
mkdir -p "$SERVER_DIR/db"

# Load .env if present
if [ -f "$SERVER_DIR/.env" ]; then
  export $(grep -v '^#' "$SERVER_DIR/.env" | xargs)
fi

# Override DATABASE_URL to absolute path
export DATABASE_URL="$SERVER_DIR/db/seo.db"

echo "Starting SEO Dashboard on http://localhost:${PORT:-3000}"
cd "$SERVER_DIR" && npx ts-node src/index.ts
