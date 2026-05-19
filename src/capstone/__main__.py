"""Allow running capstone as a module: python -m capstone."""

from capstone.cli import cli

if __name__ == "__main__":
    cli()
