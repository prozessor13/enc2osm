"""Phase 4: master/slave aggregation within one cell (before clipping).

A structure (master: buoy, beacon, landmark, ...) collects its slaves (lights, topmarks,
daymarks, fog signals, racons):

1. via LNAM_REFS with FFPT_RIND = 2 (slave) on the master, or FFPT_RIND = 1 (master) on the slave;
2. fallback: an unreferenced slave at exactly the position of exactly one point master;
3. slaves still without a master are grouped per position into standalone objects.

The aggregated object has exactly one position: its master's.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from enc2osm.extract import Feature
from enc2osm.mapping import Mapping

RIND_MASTER, RIND_SLAVE = 1, 2
# Which slave class names a standalone group, first match wins.
STANDALONE_PRECEDENCE = ("LIGHTS", "FOGSIG", "RTPBCN", "DAYMAR", "TOPMAR")
QUANT = 1e7  # 1e-7 degree position key


@dataclass
class Aggregate:
    master: Feature | None
    slaves: list[Feature] = field(default_factory=list)
    standalone_cls: str | None = None  # slave class naming a master-less group

    @property
    def primary(self) -> Feature:
        return self.master if self.master is not None else self.slaves[0]

    @property
    def kind(self) -> str:
        return self.primary.kind

    @property
    def cls(self) -> str:
        return self.master.cls if self.master is not None else self.standalone_cls

    @property
    def lnam(self) -> str:
        return self.primary.lnam


def pos_key(f: Feature) -> tuple[int, int]:
    return round(f.x * QUANT), round(f.y * QUANT)


def light_sort_key(f: Feature) -> tuple:
    """Lights on one structure: SECTR1 ascending (unsectored first), then colour, then LNAM."""
    s1 = f.attrs.get("SECTR1")
    colour = f.attrs.get("COLOUR") or []
    return (s1 is not None, float(s1) if s1 is not None else 0.0,
            [int(c) if str(c).isdigit() else 99 for c in colour], f.lnam)


def slave_sort_key(f: Feature) -> tuple:
    order = STANDALONE_PRECEDENCE.index(f.cls) if f.cls in STANDALONE_PRECEDENCE else 99
    return (order, light_sort_key(f) if f.cls == "LIGHTS" else (), f.lnam)


def aggregate(features: list[Feature], mapping: Mapping, stats: Counter) -> list[Aggregate]:
    masters_cls, slaves_cls = mapping.masters(), mapping.slaves()
    masters = [f for f in features if f.cls in masters_cls]
    slaves = {f.lnam: f for f in features if f.cls in slaves_cls}
    by_lnam = {f.lnam: f for f in masters}
    owner: dict[str, str] = {}  # slave LNAM -> master LNAM

    def attach(slave_lnam: str, master_lnam: str, how: str) -> None:
        if slave_lnam in owner:
            if owner[slave_lnam] != master_lnam:
                stats["slave_multiple_masters"] += 1
            return
        owner[slave_lnam] = master_lnam
        stats[f"slave_attached_{how}"] += 1

    for m in sorted(masters, key=lambda f: (f.cls, f.lnam)):
        for ref, rind in m.refs:
            if rind == RIND_SLAVE:
                if ref in slaves:
                    attach(ref, m.lnam, "lnam")
                elif ref not in by_lnam:
                    stats["ref_unresolved"] += 1  # slave class out of scope (RDOSTA, RADRFL, ...)
    for s in sorted(slaves.values(), key=lambda f: f.lnam):
        for ref, rind in s.refs:
            if rind == RIND_MASTER and ref in by_lnam:
                attach(s.lnam, ref, "lnam")

    # slaves of non-point masters cannot share the master's position -> standalone
    for s_lnam, m_lnam in list(owner.items()):
        if by_lnam[m_lnam].kind != "point":
            del owner[s_lnam]
            stats["slave_attached_lnam"] -= 1
            stats["slave_of_nonpoint_master"] += 1

    point_masters = defaultdict(list)
    for m in masters:
        if m.kind == "point":
            point_masters[pos_key(m)].append(m)
    for s in sorted(slaves.values(), key=lambda f: f.lnam):
        if s.lnam in owner:
            continue
        cands = point_masters.get(pos_key(s), [])
        if len(cands) == 1:
            attach(s.lnam, cands[0].lnam, "position")
        elif len(cands) > 1:
            stats["slave_position_ambiguous"] += 1

    grouped: dict[str, list[Feature]] = defaultdict(list)
    for s_lnam, m_lnam in owner.items():
        grouped[m_lnam].append(slaves[s_lnam])
    out = [Aggregate(m, sorted(grouped.get(m.lnam, []), key=slave_sort_key))
           for m in masters]
    out += [Aggregate(f) for f in features if f.cls not in masters_cls | slaves_cls]

    loose: dict[tuple[int, int], list[Feature]] = defaultdict(list)
    for s in slaves.values():
        if s.lnam not in owner:
            loose[pos_key(s)].append(s)
    for group in loose.values():
        group.sort(key=slave_sort_key)
        out.append(Aggregate(None, group, standalone_cls=group[0].cls))
        stats["standalone_objects"] += 1
        for s in group:
            stats[f"slave_standalone:{s.cls}"] += 1
    out.sort(key=lambda a: (a.cls, a.lnam))
    return out
