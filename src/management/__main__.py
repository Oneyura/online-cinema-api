#!/usr/bin/env python3
"""
Entry point for running management commands as a module.

Usage:
    python -m src.management init-data
    python -m src.management help
"""

from src.management.cli import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main()) 