#!/usr/bin/env bash
# seo-geo-aeo — Codex + Claude Code skill installer
# Usage:
#   bash install.sh                    (from cloned repo)
#   curl -fsSL https://raw.githubusercontent.com/116zoo/extrabase/main/install.sh | bash
set -e

REPO="116zoo/extrabase"
REF="main"
SKILL_NAME="seo-geo-aeo"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SKILL_DIR_CODEX="$CODEX_HOME/skills/$SKILL_NAME"
SKILL_DIR_CLAUDE="$CLAUDE_HOME/skills/$SKILL_NAME"
WORK_DIR="$HOME/seo-auto/seo-geo-aeo"

# Colors
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  seo-geo-aeo — Skill Installer${NC}"
echo -e "${BOLD}  Codex + Claude Code${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── 1. Clone or update the skill repo ────────────────────────────────────────
INSTALL_FROM_SCRIPT_DIR=false
if [ -f "$(dirname "$0")/SKILL.md" ]; then
    # Running from inside the cloned repo
    REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
    INSTALL_FROM_SCRIPT_DIR=true
    echo "→ Installing from local directory: $REPO_DIR"
else
    # Download from GitHub
    echo "→ Cloning from GitHub (github.com/$REPO)..."
    REPO_DIR="$WORK_DIR"
    mkdir -p "$REPO_DIR"
    if [ -d "$REPO_DIR/.git" ]; then
        cd "$REPO_DIR" && git pull origin "$REF" -q
        ok "Skill updated from GitHub"
    else
        git clone --depth 1 --branch "$REF" "https://github.com/$REPO.git" "$REPO_DIR" -q
        ok "Skill cloned to $REPO_DIR"
    fi
fi

# ── 2. Work directory structure ───────────────────────────────────────────────
echo "→ Setting up work directories..."
mkdir -p "$WORK_DIR/profiles" "$WORK_DIR/runs" "$WORK_DIR/schedule"
ok "Work directories ready: $WORK_DIR"

# ── 3. Install for Codex ──────────────────────────────────────────────────────
if [ -d "$CODEX_HOME" ]; then
    echo "→ Installing for Codex..."
    mkdir -p "$CODEX_HOME/skills"

    if [ "$INSTALL_FROM_SCRIPT_DIR" = true ]; then
        # Symlink from codex skills to this repo
        rm -f "$SKILL_DIR_CODEX"
        ln -sf "$REPO_DIR" "$SKILL_DIR_CODEX"
    else
        rm -f "$SKILL_DIR_CODEX"
        ln -sf "$WORK_DIR" "$SKILL_DIR_CODEX"
    fi

    # Symlink data dirs
    for dir in profiles runs schedule; do
        link="$SKILL_DIR_CODEX/$dir"
        target="$WORK_DIR/$dir"
        [ ! -e "$link" ] && ln -sf "$target" "$link" 2>/dev/null || true
    done

    # Add trust to Codex config
    CONFIG="$CODEX_HOME/config.toml"
    if [ -f "$CONFIG" ]; then
        python3 - <<PYEOF
import os
config = "$CONFIG"
with open(config) as f: content = f.read()
paths = ["$WORK_DIR", "$SKILL_DIR_CODEX"]
added = []
for path in paths:
    entry = f'\n[projects."{path}"]\ntrust_level = "trusted"\n'
    if f'"{path}"' not in content:
        content += entry
        added.append(os.path.basename(path))
if added:
    with open(config, 'w') as f: f.write(content)
    print(f"Trust added for: {', '.join(added)}")
PYEOF
    fi
    ok "Codex: $SKILL_DIR_CODEX"
else
    warn "Codex not found — skipping Codex install"
fi

# ── 4. Install for Claude Code ────────────────────────────────────────────────
if [ -d "$CLAUDE_HOME" ]; then
    echo "→ Installing for Claude Code..."
    mkdir -p "$CLAUDE_HOME/skills"
    rm -f "$SKILL_DIR_CLAUDE"
    if [ "$INSTALL_FROM_SCRIPT_DIR" = true ]; then
        ln -sf "$REPO_DIR" "$SKILL_DIR_CLAUDE"
    else
        ln -sf "$WORK_DIR" "$SKILL_DIR_CLAUDE"
    fi
    ok "Claude Code: $SKILL_DIR_CLAUDE"
else
    warn "Claude Code not found — skipping"
fi

# ── 5. Python dependencies ────────────────────────────────────────────────────
echo "→ Installing Python dependencies..."
REQS="${REPO_DIR:-$WORK_DIR}/requirements.txt"
if [ -f "$REQS" ]; then
    if command -v uv &>/dev/null; then
        uv pip install -r "$REQS" --system -q 2>/dev/null && ok "Dependencies installed (uv)" || {
            pip3 install -r "$REQS" -q --break-system-packages 2>/dev/null && ok "Dependencies installed (pip3)" || \
            warn "Install manually: pip install reportlab requests beautifulsoup4"
        }
    elif command -v pip3 &>/dev/null; then
        pip3 install -r "$REQS" -q --break-system-packages 2>/dev/null && ok "Dependencies installed" || \
        warn "Install manually: pip install reportlab requests beautifulsoup4"
    else
        warn "pip3 not found — install manually: pip install reportlab requests beautifulsoup4"
    fi
fi

# ── 6. Credentials directory ──────────────────────────────────────────────────
mkdir -p "$HOME/.config/seo-geo-aeo"
ok "Credentials directory: ~/.config/seo-geo-aeo/"

# ── 7. Verify ─────────────────────────────────────────────────────────────────
echo ""
echo "→ Verifying..."
TARGET="${REPO_DIR:-$WORK_DIR}"
[ -f "$TARGET/SKILL.md" ]          && ok "SKILL.md" || err "SKILL.md missing"
[ -d "$TARGET/agents" ]            && ok "agents/ ($(ls $TARGET/agents/*.md 2>/dev/null | wc -l) agents)" || err "agents/ missing"
[ -f "$TARGET/scripts/pdf_report.py" ] && ok "scripts/pdf_report.py" || err "scripts missing"
python3 -c "import reportlab" 2>/dev/null && ok "reportlab importable" || warn "reportlab not installed"

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo ""
echo "  In Codex:       /seo-geo-aeo https://monsite.fr"
echo "  In Claude Code: /seo-geo-aeo https://monsite.fr"
echo ""
echo "  Commands:"
echo "    /seo-geo-aeo run --full"
echo "    /seo-geo-aeo apply"
echo "    /seo-geo-aeo report"
echo ""
echo "  Work directory: $WORK_DIR"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
