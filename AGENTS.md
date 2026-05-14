# LLM Foundation & Project Mandates

This file provides critical instructions for AI models (like Gemini, Claude, etc.) working on the `agent-sync` project.

## 🚀 Automatic Versioning (Hatch-VCS)

This project uses `hatch-vcs` for dynamic versioning based on Git Tags.

**Rules for LLMs:**
1.  **NEVER** hardcode version strings in `pyproject.toml` or `__init__.py`. 
2.  The `__init__.py` should use `importlib.metadata.version("agent-sync")` to read its version.
3.  **To Release a New Version**:
    -   Perform your code changes and commit.
    -   Determine the next semantic version (e.g., `v0.8.1`).
    -   Execute: `git tag vX.X.X`
    -   Execute: `git push origin vX.X.X`
    -   Create a GitHub Release using `gh release create`.

## 🏗️ Architecture Mandates

-   **Agent Registry**: New agent CLI support must be added to `src/agent_sync/agent_registry.yaml`, not hardcoded in Python.
-   **No Symlinks**: Always prefer `Native`, `Config`, or `Copy` methods. Do not re-introduce symlink fallbacks.
-   **UX/DX First**: CLI outputs must be categorized, visual (using Rich panels/tables), and provide clear guidance on errors.
-   **VS Code Extensions & IDEs**: Support for RooCode, Cline, Cursor, and Windsurf uses specialized handlers in `src/agent_sync/agents/` with transform support (e.g., Cursor's flatten transform).

## 📦 Distribution

-   Users update via `agent-sync update`. Ensure this command remains bulletproof and supports both `pipx` and `pip` (with `--break-system-packages` for macOS).

## 🔗 DotAgents Protocol Alignment

This project follows the [DotAgents Protocol](https://dotagentsprotocol.com/) conventions for AI agent configuration.

**What we follow:**
- `~/.agents/skills/` as the canonical skills hub (vendor-neutral, shared across all agents)
- `.agents/` directory structure for centralized configuration
- Git-friendly, version-controllable agent configurations

**Why vendor-specific paths still exist:**
Some agents (Claude Code, Gemini CLI, etc.) don't natively read from `~/.agents/`. agent-sync bridges this by:
1.  Using `~/.agents/skills/` as the **source of truth**
2.  Copying/syncing to vendor-specific paths when needed
3.  Supporting multiple sync methods: `native`, `config`, and `copy`

**Not implemented (yet):**
- `./.agents/` workspace overrides
- `~/.agents/mcp.json` unified MCP configuration
- `.dotagents` bundles from hub.dotagentsprotocol.com

- Gemini CLI: AI contributor overseeing architectural mandates.