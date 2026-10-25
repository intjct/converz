# Entry point used to build Converz.exe with PyInstaller.
import sys

from converz.app import main

if __name__ == "__main__":
    sys.exit(main())
