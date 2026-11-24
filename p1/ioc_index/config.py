
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__",
})

MAX_FILE_BYTES = 512 * 1024   # 512 Ko


@dataclass(frozen=True)
class Settings:
    target: Path              
    chroma_path: Path           
    collection: str = "code_chunks"
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_cache: Path = REPO_ROOT / ".models"

    @classmethod
    def from_env(cls, target=None, chroma_path=None) -> "Settings":
        """Create an instance of settings from provided arguments or environment variables."""
        target = target or os.environ.get("IOC_TARGET")
        if not target:
            raise ValueError("no target: pass one or set IOC_TARGET")
        target = Path(target).expanduser().resolve()
        if not target.is_dir():
            raise ValueError("IOC_TARGET must be a valid directory")
        chroma_path = chroma_path or os.environ.get("CHROMA_PATH") or REPO_ROOT / "./data/chroma"
        collection = os.environ.get("IOC_COLLECTION") or cls.collection
        embed_model = os.environ.get("IOC_EMBED_MODEL") or cls.embed_model
        model_cache = os.environ.get("IOC_MODEL_CACHE") or cls.model_cache
        return cls(target=target,
            chroma_path=Path(chroma_path).expanduser().resolve(),
            collection=collection, embed_model=embed_model,
            model_cache=Path(model_cache).expanduser().resolve())