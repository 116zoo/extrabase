# Codex Setup — seo-geo-aeo

## Installation

The skill is pre-installed at `~/.codex/skills/seo-geo-aeo/` with symlinks pointing to the working data directories.

```bash
# Verify installation
ls ~/.codex/skills/seo-geo-aeo/

# Manual setup if needed
SKILL_SRC="$HOME/seo-auto/agent opti seo geo aeo/seo-geo-aeo"
SKILL_DST="$HOME/.codex/skills/seo-geo-aeo"
mkdir -p "$SKILL_DST/references"
cp "$SKILL_SRC/docs/codex-skill.md" "$SKILL_DST/SKILL.md"
ln -sf "$SKILL_SRC/agents"   "$SKILL_DST/agents"
ln -sf "$SKILL_SRC/scripts"  "$SKILL_DST/scripts"
ln -sf "$SKILL_SRC/schema"   "$SKILL_DST/schema"
ln -sf "$SKILL_SRC/profiles" "$SKILL_DST/profiles"
ln -sf "$SKILL_SRC/runs"     "$SKILL_DST/runs"
ln -sf "$SKILL_SRC/schedule" "$SKILL_DST/schedule"
```

## Usage in Codex

```
/seo-geo-aeo https://monsite.fr
/seo-geo-aeo run --full
/seo-geo-aeo apply
/seo-geo-aeo report
```

## Key Differences vs Claude Code

| Feature | Claude Code | Codex |
|---------|-------------|-------|
| Parallel agents | ✅ | ❌ Sequential |
| Agent dispatch | `Agent()` tool | Not available |
| File tools | Read/Write/Edit | Shell commands |
| Trigger | `Skill(seo-geo-aeo)` | `/seo-geo-aeo` |

## Working Directory

```
~/seo-auto/agent opti seo geo aeo/seo-geo-aeo/
```

All profiles, runs, and reports are shared between Claude Code and Codex — same data directory.

## Trust Config

Add to `~/.codex/config.toml`:
```toml
[projects."/home/ropie/.codex/skills/seo-geo-aeo"]
trust_level = "trusted"

[projects."/home/ropie/seo-auto/agent opti seo geo aeo"]
trust_level = "trusted"
```
