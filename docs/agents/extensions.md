# Extension Support

agent-sync supports agent extensions that create subdirectories with their own skills.

## Example: Opencode Superpowers

```
~/.config/opencode/
├── superpowers/
│   └── skills/              # 14 skills from Superpowers extension
│       ├── skill-1/
│       └── skill-2/
└── skills/
    └── superpowers  →  symlink → ../superpowers/skills/
```

## What agent-sync Does

1. ✅ **Detects** extension subdirectories automatically (`superpowers/skills/`)
2. ✅ **Preserves** symlinks that point to internal extension directories
3. ✅ **Backs up** both the skills and symlink structure
4. ✅ **Restores** everything correctly on `pull` (skills + symlinks)
5. ✅ **Uses manifest** (`.agent-sync-manifest.json`) to track extension metadata

## Supported Patterns

| Pattern | Example | Handled |
|---------|---------|---------|
| Extension subdirectory | `~/.config/opencode/superpowers/skills/` | ✅ Yes |
| Internal symlink | `skills/superpowers → ../superpowers/skills/` | ✅ Preserved |
| External symlink | `skills/my-skill → ~/.agents/skills/my-skill/` | ✅ Removed |
| Multiple extensions | `superpowers/`, `my-ext/`, etc. | ✅ Yes |
| Skills with `__` in name | `my__custom-skill/` | ✅ Yes (no parsing issues) |

## How It Works

### On `push` (backup)

```
1. Scan ~/.agents/skills/ → global skills
2. Scan ~/.config/opencode/superpowers/skills/ → extension skills
3. Detect symlinks in ~/.config/opencode/skills/
   - Internal (../superpowers/skills/) → backup symlink
   - External (~/.agents/skills/) → skip (will be removed)
4. Copy all skills to repo with real names
5. Create .agent-sync-manifest.json with extension metadata
```

### On `pull` (restore)

```
1. Read .agent-sync-manifest.json
2. Restore extension skills to ~/.config/opencode/superpowers/skills/
3. Restore symlinks to ~/.config/opencode/skills/superpowers
4. Restore global skills to ~/.agents/skills/
```

## Repository Structure

```
agent-sync-private-configs/
├── skills/
│   ├── minha-skill/              # Global skill
│   └── opencode-superpowers/     # Extension skills
│       ├── skill-1/
│       └── skill-2/
├── configs/
│   └── opencode/
│       ├── opencode.json
│       └── skills/
│           └── superpowers  →    # Symlink backup
└── .agent-sync-manifest.json     # Extension metadata
```

## Example Manifest

```json
{
  "version": 1,
  "extensions": {
    "opencode-superpowers": {
      "agent": "opencode",
      "extension_dir": "superpowers",
      "skills_dir": "~/.config/opencode/superpowers/skills/",
      "symlink": {
        "from": "~/.config/opencode/skills/superpowers",
        "to": "../superpowers/skills/"
      }
    }
  },
  "global_skills": ["minha-skill", "outra-skill"]
}
```

## Supported Extensions

| Extension | Agent | Structure |
|-----------|-------|-----------|
| Opencode Superpowers | opencode | `~/.config/opencode/superpowers/skills/` |
| Cursor Extensions | cursor | `~/.cursor/extensions/<name>/skills/` |
| Custom plugins | any | `<config_dir>/<extension>/skills/` |
