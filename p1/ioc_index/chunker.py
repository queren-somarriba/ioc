"""Découpage d'un fichier en blocs logiques (fonction, classe, bloc de config).

Schéma imposé par le contrat P1/P2 (voir metadatas Chroma).
"""
from __future__ import annotations

from dataclasses import dataclass

import ast

from pathlib import Path, PurePosixPath



@dataclass(frozen=True)
class Chunk:
    path: str          # chemin relatif à la cible            -> metadata "path"
    name: str          # "search", "NoteService", nom du fichier pour un bloc global
    kind: str          # "function" | "async_function" | "class" | "module" | "config"
    start_line: int    # 1-based, inclus                       -> id = f"{path}:{start_line}"
    end_line: int      # 1-based, inclus
    text: str          # code source brut (décorateurs + docstrings inclus) -> document


def chunk_file(path: str, source: str) -> list[Chunk]:
    """Découpe `source` selon sa structure logique."""
    filename = PurePosixPath(path).name
    if not filename.endswith(".py"):
        return _build_chunks(path, source, [(1, "config", filename)])
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return _build_chunks(path, source, [(1, "module", filename)])
    return _build_chunks(path, source, _python_marks(tree, path))

def _start_line(node) -> int:
    """1-based, inclus"""
    return min([node.lineno] + [d.lineno for d in node.decorator_list])

def _python_marks(tree : ast.Module, path) -> list[tuple[int, str, str]]:
    """crete a list of tuples that categorize the different nodes of the AST tree"""
    filename = PurePosixPath(path).name
    mark = [(1, "module", filename)]
    after_def = False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            mark.append((_start_line(node), _kind(node), node.name))
            after_def = True
        elif isinstance(node, ast.ClassDef):
            after_def = True
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) or isinstance(sub, ast.AsyncFunctionDef):
                    mark.append((_start_line(sub), _kind(sub), sub.name))
            mark.append((_start_line(node), "class", node.name))
        elif after_def:
            mark.append((node.lineno, "module", filename))
            after_def = False
    return mark

def _build_chunks(path: str, source: str, marks: list) -> list[Chunk]:
    """Construit les chunks à partir des noeuds AST."""
    lines = source.split("\n")

    # 1. trier sur la ligne uniquement
    marks = sorted(marks, key=lambda m: m[0])

    # 2. dédoublonner : à ligne égale, garder la dernière
    unique = []
    for mark in marks:
        if unique and unique[-1][0] == mark[0]:
            unique[-1] = mark
        else:
            unique.append(mark)
    marks = unique
    result = []
    for i, (start, kind, name) in enumerate(marks):
        if i + 1 < len(marks):
            end = marks[i + 1][0] - 1
        else:
            end = len(lines)
        while end >= start and lines[end -1].strip() == "":
            end -= 1
        if start > end:
            continue

        text = "\n".join(lines[start - 1:end])
        result.append(Chunk(path=path, name=name, kind=kind, start_line=start, end_line=end, text=text))
    return result

def _kind(node) -> str:
    return "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
