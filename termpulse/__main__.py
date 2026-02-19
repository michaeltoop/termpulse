"""Entry point for termpulse."""

import argparse
import os
import sys

from termpulse.app import TermPulseApp


def main():
    parser = argparse.ArgumentParser(description="termpulse — ambient developer intelligence")
    parser.add_argument("--cwd", "-C", help="Directory to monitor (default: current)")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    args = parser.parse_args()

    if args.version:
        from termpulse import __version__
        print(f"termpulse {__version__}")
        sys.exit(0)

    if args.cwd:
        target = os.path.expanduser(args.cwd)
        if os.path.isdir(target):
            os.chdir(target)
        else:
            print(f"termpulse: directory not found: {target}", file=sys.stderr)
            sys.exit(1)

    app = TermPulseApp()
    app.run()


if __name__ == "__main__":
    main()
