"""PyInstaller entry point. Kept separate from the package so the frozen binary has a
single, unambiguous start script."""

from ludex.cli import main

if __name__ == "__main__":
    main()
