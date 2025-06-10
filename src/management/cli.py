#!/usr/bin/env python3
"""
Management CLI for Online Cinema API.

Usage:
    python -m src.management.cli init-data
    python -m src.management.cli init-data --prod
    python -m src.management.cli --help
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.management.commands.init_default_data import init_default_data


def print_help():
    """Print help information."""
    print("🎬 Online Cinema API Management CLI")
    print()
    print("Available commands:")
    print("  init-data        Initialize default data (user groups, etc.)")
    print("  init-data --prod Initialize default data using production environment")
    print("  help             Show this help message")
    print()
    print("Usage:")
    print("  python -m src.management.cli <command>")
    print("  python src/management/cli.py <command>")
    print()
    print("Examples:")
    print("  python -m src.management.cli init-data")
    print("  python -m src.management.cli init-data --prod")


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("❌ Error: No command specified!")
        print()
        print_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command in ["help", "--help", "-h"]:
        print_help()
        return
    
    elif command == "init-data":
        await init_default_data()
    
    else:
        print(f"❌ Error: Unknown command '{command}'")
        print()
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 