"""Mapping tables (data, not code): objects.yaml, attributes.yaml, values.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from enc2osm import yamlmini

HERE = Path(__file__).resolve().parent
KINDS = {"enum", "list", "text", "number", "int", "depth", "height", "siggrp", "meta"}
SCOPES = {"v1": ("v1",), "v2": ("v1", "v2"), "all": ("v1", "v2")}


@dataclass(frozen=True)
class Mapping:
    objects: dict
    attributes: dict
    values: dict
    rules: dict

    def classes(self, scope: str) -> list[str]:
        allowed = SCOPES[scope]
        return sorted(c for c, o in self.objects.items() if o["scope"] in allowed)

    def masters(self) -> set[str]:
        return {c for c, o in self.objects.items() if o["role"] == "master"}

    def slaves(self) -> set[str]:
        return {c for c, o in self.objects.items() if o["role"] == "slave"}

    def value(self, acronym: str, code) -> str | None:
        table = self.attributes[acronym].get("values", acronym)
        return self.values.get(table, {}).get(code)

    def all_types(self) -> set[str]:
        out = {o["type"] for o in self.objects.values() if o.get("type")}
        out |= {o["standalone"] for o in self.objects.values() if o.get("standalone")}
        out.discard("light")
        return out | {self.rules["light"]["major"], self.rules["light"]["minor"]}


def validate(m: Mapping) -> None:
    for cls, o in m.objects.items():
        if o.get("role") not in ("master", "slave", "feature"):
            raise ValueError(f"objects.yaml {cls}: bad role {o.get('role')!r}")
        if o["role"] == "slave" and not o.get("slave_key"):
            raise ValueError(f"objects.yaml {cls}: slave without slave_key")
        if o["role"] != "slave" and not o.get("type"):
            raise ValueError(f"objects.yaml {cls}: missing type")
        if o.get("scope") not in ("v1", "v2"):
            raise ValueError(f"objects.yaml {cls}: bad scope")
        if not set(o.get("geometry", [])) <= {"point", "line", "area"} or not o.get("geometry"):
            raise ValueError(f"objects.yaml {cls}: bad geometry")
    for acr, a in m.attributes.items():
        if a.get("kind") not in KINDS:
            raise ValueError(f"attributes.yaml {acr}: bad kind {a.get('kind')!r}")
        if a["kind"] != "meta" and not a.get("key"):
            raise ValueError(f"attributes.yaml {acr}: missing key")
        if a["kind"] in ("enum", "list") and a.get("values", acr) not in m.values:
            raise ValueError(f"attributes.yaml {acr}: no table in values.yaml")
    lr = m.rules.get("light") or {}
    if not isinstance(lr.get("major_min_range"), (int, float)) or not lr.get("major") \
            or not lr.get("minor"):
        raise ValueError("rules.yaml: light rule incomplete")
    for table, codes in m.values.items():
        for code, val in codes.items():
            if not isinstance(code, int) or not isinstance(val, str) or not val:
                raise ValueError(f"values.yaml {table}: bad entry {code!r}: {val!r}")


@cache
def load(directory: str | None = None) -> Mapping:
    d = Path(directory) if directory else HERE
    m = Mapping(yamlmini.load(d / "objects.yaml"), yamlmini.load(d / "attributes.yaml"),
                yamlmini.load(d / "values.yaml"), yamlmini.load(d / "rules.yaml"))
    validate(m)
    return m
