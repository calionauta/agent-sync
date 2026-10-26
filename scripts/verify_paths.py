#!/usr/bin/env python3
"""
Script to verify agent CLI paths on the current system.

Usage:
    python verify_paths.py
"""

from pathlib import Path

from agent_sync.agents import get_all_agents


def check_path(path: Path, label: str = "") -> str:
    """Check if a path exists and return status icon."""
    if path.exists():
        return f"✓ {path} {label}"
    else:
        return f"✗ {path} {label}"


def main():
    """Verify all agent paths."""
    print("=" * 60)
    print("Agent CLI Paths Verification")
    print("=" * 60)
    print()

    agents = get_all_agents()

    for agent in agents:
        print(f"\n🤖 {agent.name}")
        print("-" * 40)

        # Config path (skip for global-skills)
        if agent.name != "global-skills" and agent.config_path:
            status = check_path(agent.config_path)
            print(f"  Config: {status}")

        # Skills path
        if agent.name != "global-skills":
            status = check_path(agent.skills_path, "(primary)")
            print(f"  Skills: {status}")

        # Additional skills paths
        if hasattr(agent, "get_all_skills_paths") and agent.name != "global-skills":
            all_paths = agent.get_all_skills_paths()
            for path in all_paths:
                if path != agent.skills_path:
                    status = check_path(path, "(additional)")
                    print(f"         {status}")

        # Global skills (only for global-skills agent)
        if agent.name == "global-skills":
            status = check_path(agent.skills_path)
            print(f"  Skills: {status}")

        # Availability
        available = agent.is_available()
        print(f"\n  Status: {'✅ Available' if available else '❌ Not configured'}")
        print(f"  Sync: {'🟢 Enabled' if agent.is_enabled() else '🔴 Disabled'}")

    print()
    print("=" * 60)
    print("Global Paths")
    print("=" * 60)

    # Check global skills directory
    global_skills = Path.home() / ".agents" / "skills"
    print(f"\n📁 Global Skills: {global_skills}")
    if global_skills.exists():
        skills = list(global_skills.glob("*"))
        print(f"  ✓ Exists ({len(skills)} items)")
        for skill in skills[:5]:  # Show first 5
            print(f"    - {skill.name}")
        if len(skills) > 5:
            print(f"    ... and {len(skills) - 5} more")
    else:
        print("  ✗ Does not exist")

    print()
    print("=" * 60)
    print("Verification Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
