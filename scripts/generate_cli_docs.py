#!/usr/bin/env python3
"""Generate CLI documentation from Click application.

Usage: python scripts/generate_cli_docs.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_sync.cli import main


def get_param_info(param):
    """Extract parameter info from a Click parameter."""
    # Get names
    if hasattr(param, 'opts') and param.opts:
        names = param.opts
    elif hasattr(param, 'name'):
        names = [f"--{param.name}"]
    else:
        names = []
    
    # Get help text
    if hasattr(param, 'help') and param.help:
        help_text = param.help
    elif hasattr(param, 'secondary_opts') and param.secondary_opts:
        # Boolean flag
        help_text = "Boolean flag"
    else:
        help_text = ""
    
    # Get default
    default = ""
    if hasattr(param, 'default') and param.default is not None:
        if hasattr(param.default, '__call__'):
            default = f" [flag]"
        elif param.default:
            default = f" [default: {param.default}]"
    
    # Get type hint
    if hasattr(param, 'type') and param.type:
        type_hint = str(param.type).split("'")[1] if "'" in str(param.type) else str(param.type)
    else:
        type_hint = ""
    
    return names, help_text, default, type_hint


def format_command(cmd, parent_path="", depth=0):
    """Recursively format a command and its subcommands."""
    lines = []
    
    if not hasattr(cmd, 'commands'):
        # It's a single command (not a group)
        path = parent_path
        short_help = getattr(cmd, 'short_help', '') or ""
        help_text = getattr(cmd, 'help', '') or ""
        
        lines.append(f"### `agent-sync {path}`\n")
        if help_text:
            lines.append(f"{help_text}\n\n")
        elif short_help:
            lines.append(f"{short_help}\n\n")
        
        # Add usage line
        if hasattr(cmd, 'usage'):
            lines.append(f"**Usage:** `{cmd.usage}`\n\n")
        
        # Add options
        if hasattr(cmd, 'params') and cmd.params:
            options = []
            for param in cmd.params:
                if isinstance(param, type) and "Argument" in str(type(param)):
                    continue
                    
                names, help_t, default, type_hint = get_param_info(param)
                if names:
                    opt_str = ", ".join(names)
                    if type_hint and "bool" not in type_hint.lower():
                        opt_str += f" <{type_hint}>"
                    opt_str += default
                    if help_t:
                        opt_str += f" — {help_t}"
                    options.append(opt_str)
            
            if options:
                lines.append("**Options:**\n")
                for opt in options:
                    lines.append(f"- `{opt}`\n")
                lines.append("\n")
        
        lines.append("---\n\n")
        return lines
    
    # It's a group - process subcommands
    for name, subcmd in cmd.commands.items():
        path = f"{parent_path} {name}".strip()
        short_help = getattr(subcmd, 'short_help', '') or ""
        help_text = getattr(subcmd, 'help', '') or ""
        
        lines.append(f"### `agent-sync {path}`\n")
        
        if help_text:
            lines.append(f"{help_text}\n\n")
        elif short_help:
            lines.append(f"{short_help}\n\n")
        
        # Add options
        if hasattr(subcmd, 'params') and subcmd.params:
            options = []
            for param in subcmd.params:
                names, help_t, default, type_hint = get_param_info(param)
                if names:
                    opt_str = ", ".join(names)
                    if type_hint and "bool" not in type_hint.lower():
                        opt_str += f" <{type_hint}>"
                    opt_str += default
                    if help_t:
                        opt_str += f" — {help_t}"
                    options.append(opt_str)
            
            if options:
                lines.append("**Options:**\n")
                for opt in options:
                    lines.append(f"- `{opt}`\n")
                lines.append("\n")
        
        lines.append("---\n\n")
        
        # Recurse for subcommands
        if hasattr(subcmd, 'commands') and subcmd.commands:
            lines.extend(format_command(subcmd, path, depth + 1))
    
    return lines


def generate_docs():
    """Generate comprehensive CLI documentation."""
    
    output = """# CLI Reference

Complete reference for all agent-sync commands.

## Overview

agent-sync is a unified CLI tool to sync, centralize, and share AI agent configurations and skills.

"""
    
    # Group commands by category
    categories = {
        "Sync & Backup": ["push", "pull", "link", "status"],
        "Configuration": ["init", "setup", "config", "generate-config"],
        "Skills": ["skills"],
        "Publishing": ["publish"],
        "Agents": ["agents", "enable", "disable", "custom-agents"],
        "System": ["update", "version", "mcp", "secrets"],
    }
    
    if hasattr(main, 'commands'):
        for category, cmd_names in categories.items():
            output += f"## {category}\n\n"
            
            for cmd_name in cmd_names:
                if cmd_name in main.commands:
                    cmd = main.commands[cmd_name]
                    
                    # Get description
                    short_help = getattr(cmd, 'short_help', '') or ""
                    help_text = getattr(cmd, 'help', '') or ""
                    
                    output += f"### `agent-sync {cmd_name}`\n"
                    if help_text:
                        output += f"{help_text}\n\n"
                    elif short_help:
                        output += f"{short_help}\n\n"
                    
                    # Add subcommands if it's a group
                    if hasattr(cmd, 'commands') and cmd.commands:
                        output += "**Subcommands:**\n"
                        for subname, subcmd in cmd.commands.items():
                            sub_help = getattr(subcmd, 'short_help', '') or ""
                            if sub_help:
                                output += f"- `{subname}`: {sub_help}\n"
                            else:
                                output += f"- `{subname}`\n"
                        output += "\n"
                    
                    # Add main options
                    if hasattr(cmd, 'params') and cmd.params:
                        options = []
                        for param in cmd.params:
                            names, help_t, default, type_hint = get_param_info(param)
                            if names:
                                opt_str = ", ".join(names)
                                if type_hint and "bool" not in type_hint.lower():
                                    opt_str += f" <{type_hint}>"
                                opt_str += default
                                if help_t:
                                    opt_str += f" — {help_t}"
                                options.append(opt_str)
                        
                        if options:
                            output += "**Options:**\n"
                            for opt in options:
                                output += f"- `{opt}`\n"
                            output += "\n"
                    
                    output += "---\n\n"
    
    return output


if __name__ == "__main__":
    docs = generate_docs()
    
    # Write to docs/cli.md
    output_path = Path(__file__).parent.parent / "docs" / "cli.md"
    output_path.write_text(docs)
    
    print(f"Generated CLI documentation at: {output_path}")
    print(f"Length: {len(docs)} characters")