"""Surveillance du disque : événements natifs + polling de secours."""
from __future__ import annotations

from .indexer import Indexer

import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class _Handler(FileSystemEventHandler):
    """Reçoit les événements de watchdog et les transmet au Watcher."""

    def __init__(self, watcher: "Watcher") -> None:
        self.watcher = watcher

    def on_any_event(self, event) -> None:
        if event.is_directory:
            return 
        self.watcher._handle(event.src_path)
        dest = getattr(event, "dest_path", None)
        if dest:
            self.watcher._handle(dest)


class Watcher:
    def __init__(self, indexer: Indexer, interval: float = 2.0) -> None:
        self.indexer = indexer
        self.interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._observer = None
        self._thread = None

    def _handle(self, abs_path: str) -> None:
        """Réindexe ou supprime UN fichier signalé par un événement."""
        rel = os.path.relpath(abs_path, self.indexer.settings.target)
        if self.indexer.files.is_excluded(rel):
            return
        with self._lock:
            if (self.indexer.settings.target / rel).is_file():
                self.indexer.index_file(rel)
            else:
                self.indexer.remove_file(rel)
        return

    def _poll(self) -> None:
        """Boucle de secours : sync() toutes les `interval` secondes, jusqu'à stop()."""
        while (self._stop.wait(self.interval) is False):
            with self._lock:
                self.indexer.sync()
        return

    def start(self) -> "Watcher":
        """Démarre les événements natifs + le thread de polling."""
        self._observer = Observer()
        self._observer.schedule(_Handler(self), str(self.indexer.settings.target), recursive=True)
        self._observer.start()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Arrête proprement les deux mécanismes."""
        self._stop.set()
        self._observer.stop()
        self._observer.join()
        self._thread.join()
