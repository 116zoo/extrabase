#!/bin/bash
# SEO-GEO-AEO Skill Installer
set -e

SKILL_DIR="$HOME/.claude/skills/seo-geo-aeo"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing SEO-GEO-AEO skill..."
echo "Repo: $REPO_DIR"
echo ""

# Create skill directory symlink
mkdir -p "$HOME/.claude/skills"
if [ -L "$SKILL_DIR" ]; then
  rm "$SKILL_DIR"
fi
ln -sf "$REPO_DIR" "$SKILL_DIR"
echo "✓ Skill linked to $SKILL_DIR"

# Install Python dependencies
cd "$REPO_DIR"
if command -v uv &>/dev/null; then
  echo "Using uv for faster install..."
  uv venv .venv
  uv pip install -r requirements.txt --quiet
else
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt --quiet
fi
echo "✓ Python dependencies installed in .venv/"

# Create credentials directory
mkdir -p "$HOME/.config/seo-geo-aeo"
echo "✓ Credentials directory: ~/.config/seo-geo-aeo/"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SEO-GEO-AEO skill installed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Usage (in Claude Code):"
echo "  /seo-geo-aeo https://yoursite.com"
echo ""
echo "Credentials (optional):"
echo "  GSC:        cp your-gsc.json ~/.config/seo-geo-aeo/gsc.json"
echo "  GA4:        cp your-ga4.json ~/.config/seo-geo-aeo/ga4.json"
echo "  DataForSEO: export DATAFORSEO_LOGIN=... DATAFORSEO_PASSWORD=..."
echo ""
echo "Run tests:"
echo "  cd $REPO_DIR && .venv/bin/pytest tests/ -v"
echo ""
