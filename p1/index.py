#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import sys
from ioc_index import Indexer, Settings, Watcher


def main() -> int:
    parser = argparse.ArgumentParser(description="Index a directory in ChromaDB.")
    parser.add_argument("target", nargs="?", help="Directory to index (default: IOC_TARGET)")
    parser.add_argument("--watch", action="store_true", help="Watch the directory for changes after indexation")
    args = parser.parse_args()
    try:
        settings = Settings.from_env(target=args.target)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    indexer = Indexer(settings)
    indexer.sync()
    print(settings.target, " nbr files:", len(indexer.store.indexed_path()), "nbr chunks:", indexer.store.count())
    if not args.watch:
        return 0
    watcher = Watcher(indexer).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
