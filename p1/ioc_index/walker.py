"""Parcours de la cible : quels fichiers sont indexables ?"""
from __future__ import annotations

from .config import Settings

from .config import EXCLUDED_DIRS

from pathlib import Path

from .config import MAX_FILE_BYTES

import os


class FileFilter:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.target
        self.chroma_path = settings.chroma_path
        self.model_cache = settings.model_cache

    def is_excluded(self, rel_path: str) -> bool:
        """Vrai si le chemin (relatif à la cible) doit être ignoré."""
        for i in Path(rel_path).parts:
            if i in EXCLUDED_DIRS:
                return True
            if i.startswith("."):
                return True
            if (i.endswith(".ioc.tmp")):
                return True
        absolute = self.root / rel_path
        if absolute.is_relative_to(self.chroma_path) or absolute.is_relative_to(self.model_cache):
            return True
        return False

    def read_text(self, rel_path: str) -> str | None:
        """Contenu texte du fichier, ou None s'il n'est pas indexable (binaire...)."""
        if self.is_excluded(rel_path):
            return None
        path = self.root / rel_path 
        try:
            if not path.is_file():
                return None
            if path.stat().st_size > MAX_FILE_BYTES:
                return None
            data = path.read_bytes()
        except OSError:
            return None
        if b"\x00" in data:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def scan(self) -> list[str]:
        """Liste des fichiers indexables de la cible (chemins relatifs)."""
        result = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not self.is_excluded(
                    os.path.relpath(os.path.join(dirpath, d), self.root))]
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), self.root)
                if not self.is_excluded(rel):
                    result.append(rel)
        result.sort()
        return result

