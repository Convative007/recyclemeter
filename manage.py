#!/usr/bin/env python
"""Project commands:  python manage.py build | serve [--port N] | test"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="render the static site into dist/")
    s = sub.add_parser("serve", help="build, then serve dist/ locally")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-watch", action="store_true", help="do not rebuild on file changes")
    sub.add_parser("test", help="run the test suite")
    args = ap.parse_args()

    if args.cmd == "build":
        from recyclemeter.build import build
        print(f"Built {build()}")
    elif args.cmd == "serve":
        from recyclemeter.server import serve
        serve(args.host, args.port, watch=not args.no_watch)
    elif args.cmd == "test":
        return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
