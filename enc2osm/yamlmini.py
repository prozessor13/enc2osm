"""A strict loader for the YAML subset used by the mapping tables (stdlib only).

Runtime dependencies are limited to GDAL + pyosmium, so PyYAML is not available.
Supported: block mappings nested by indentation, `# comments`, plain / single- /
double-quoted scalars, flow lists `[a, b]` and flow mappings `{k: v, k2: [a, b]}` (one level
of nesting inside a flow mapping). Scalars: int, float, null/~, true/false,
everything else is a string. Anything outside this subset raises ValueError.
"""

from __future__ import annotations

import re

_KEY = re.compile(r"^(?P<key>'[^']*'|\"[^\"]*\"|[^:#'\"\[\]{}]+?)\s*:(?:\s+(?P<val>.*))?$")


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(tok: str):
    tok = tok.strip()
    if tok == "":
        return None
    if tok[0] == tok[-1] and tok[0] in "'\"" and len(tok) >= 2:
        return tok[1:-1]
    if tok in ("null", "~", "Null", "NULL"):
        return None
    if tok in ("true", "True"):
        return True
    if tok in ("false", "False"):
        return False
    if re.fullmatch(r"[-+]?\d+", tok):
        return int(tok)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", tok):
        return float(tok)
    if tok[0] in "[{&*!|>%@`":
        raise ValueError(f"unsupported YAML construct: {tok!r}")
    return tok


def _value(tok: str, depth: int = 0):
    tok = tok.strip()
    if tok.startswith("["):
        if not tok.endswith("]"):
            raise ValueError(f"unterminated flow list: {tok!r}")
        inner = tok[1:-1].strip()
        return [] if not inner else [_scalar(t) for t in _split_flow(inner, nested=False)]
    if tok.startswith("{"):
        if not tok.endswith("}") or depth > 0:
            raise ValueError(f"unsupported flow mapping: {tok!r}")
        out: dict = {}
        inner = tok[1:-1].strip()
        for item in (_split_flow(inner, nested=True) if inner else []):
            k, sep, v = item.partition(":")
            if not sep:
                raise ValueError(f"expected 'key: value' in flow mapping, got {item!r}")
            key = _scalar(k)
            if key in out:
                raise ValueError(f"duplicate key {key!r} in flow mapping")
            out[key] = _value(v, depth + 1)
        return out
    return _scalar(tok)


def _split_flow(s: str, nested: bool) -> list[str]:
    parts, cur, quote, level = [], [], None, 0
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "," and level == 0:
            parts.append("".join(cur))
            cur = []
        elif ch in "[]{}":
            if not nested or ch in "{}":
                raise ValueError("nested flow collections are not supported")
            level += 1 if ch == "[" else -1
            cur.append(ch)
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def loads(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    pending: tuple[int, dict, object] | None = None  # (indent, parent, key) awaiting a block
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError(f"line {lineno}: tabs are not allowed for indentation")
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = _KEY.match(line.strip())
        if not m:
            raise ValueError(f"line {lineno}: expected 'key: value', got {line.strip()!r}")
        key = _scalar(m.group("key"))
        if pending is not None:
            p_indent, p_parent, p_key = pending
            pending = None
            if indent > p_indent:
                child: dict = {}
                p_parent[p_key] = child
                stack.append((p_indent, child))
            else:
                p_parent[p_key] = None
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"line {lineno}: bad indentation")
        parent = stack[-1][1]
        if key in parent:
            raise ValueError(f"line {lineno}: duplicate key {key!r}")
        val = m.group("val")
        if val is None or val.strip() == "":
            parent[key] = None
            pending = (indent, parent, key)
        else:
            parent[key] = _value(val)
    return root


def load(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return loads(f.read())
