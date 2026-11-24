from __future__ import annotations

from dataclasses import dataclass

import ast

import re

from pathlib import Path, PurePosixPath



@dataclass(frozen=True)
class Chunk:
    path: str
    name: str         
    kind: str          
    start_line: int    
    end_line: int      
    text: str        
    


def chunk_file(path: str, source: str) -> list[Chunk]:
    """Chunk the file into logical blocks (functions, classes, config blocks) based on the AST."""
    filename = PurePosixPath(path).name
    if filename.endswith((".yaml", ".yml")):
        return _build_chunks(path, source, _yaml_marks(source, path))
    if filename.endswith((".md", ".markdown")):
        return _build_chunks(path, source, _markdown_marks(source, path))
    if not filename.endswith(".py"):
        return _build_chunks(path, source, [(1, "config", filename)])
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return _build_chunks(path, source, _python_regex_marks(source, path))
    return _build_chunks(path, source, _python_marks(tree, path))

def _start_line(node) -> int:
    """Return the line number of the first line of the node"""
    return min([node.lineno] + [d.lineno for d in node.decorator_list])

def _yaml_marks(source : str, path) -> list[tuple[int, str, str]]:
    """Create a list of tuples that categorize the different nodes of the YAML file."""
    filename = PurePosixPath(path).name
    marks = [(1, "config", filename)]
    for number, line in enumerate(source.split("\n"), start=1):
        if not line:
            continue
        if line.startswith(("#", "-", " ", "\t")):
            continue
        if ":" not in line:
            continue
        key = line.split(":", 1)[0]
        if not key:
            continue
        key = key.strip()
        marks.append((number, "config", key))
    return marks

def _markdown_marks(source : str, path) -> list[tuple[int, str, str]]:
    """Create a list of tuples that categorize the different nodes of the markdown file."""
    filename = PurePosixPath(path).name
    marks = [(1, "markdown", filename)]
    in_code = False
    for number, line in enumerate(source.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.match(r"#{1,6} ", line):
            marks.append((number, "markdown", line.strip()))
    return marks


def _python_regex_marks(source : str, path) -> list[tuple[int, str, str]]:
    """Create a list of tuples that categorize the different nodes of the Python file using regex."""
    filename = PurePosixPath(path).name
    marks = [(1, "module", filename)]
    in_class = False
    method_indent = None
    lines = source.split("\n")
    for number, line in enumerate(lines, start=1):
        m = re.match(r"(\s*)(async\s+)?(def|class)\s+(\w+)", line)
        if m is None:
            continue
        indent = len(m.group(1))
        kind = "class" if m.group(3) == "class" else "async_function" if m.group(2) else "function"
        name = m.group(4)
        start = number
        while (start > 1 and lines[start - 2].strip().startswith("@")):
            start -= 1
        if indent == 0:
            marks.append((start, kind, name))
            in_class = (kind == "class")
            method_indent = None
        elif in_class:
            if method_indent is None:
                method_indent = indent
            if indent == method_indent:
                marks.append((start, kind, name))

    return marks

def _python_marks(tree : ast.Module, path) -> list[tuple[int, str, str]]:
    """Create a list of tuples that categorize the different nodes of the AST tree"""
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
    """Create a list of chunks based on the marks and the source code."""
    lines = source.split("\n")
    marks = sorted(marks, key=lambda m: m[0])
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
