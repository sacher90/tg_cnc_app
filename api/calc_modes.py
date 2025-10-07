"""Cutting mode calculations for CNC drilling and milling tools."""
from __future__ import annotations

import math
from typing import Dict


def _select_vc(tool_type: str, tool_material: str, material_props: Dict[str, any]) -> float:
    """Return a recommended cutting speed based on heuristics."""
    machinability = float(material_props.get("machinability_index", 0.6))

    if tool_material.lower() == "hss":
        base = 40
        multiplier = 1.1 if tool_type == "drill" else 1.0
    elif tool_material.lower() == "carbide":
        base = 140
        multiplier = 1.3 if tool_type == "mill" else 1.2
    else:  # indexable or other plates
        base = 110
        multiplier = 1.25 if tool_type == "mill" else 1.0

    hardness_penalty = 1.0
    temperature_risk = str(material_props.get("temperature_risk", "средний")).lower()
    if "выс" in temperature_risk:
        hardness_penalty -= 0.25
    elif "низ" in temperature_risk:
        hardness_penalty += 0.1

    work_hardening = str(material_props.get("work_hardening", "средняя")).lower()
    if "выс" in work_hardening:
        hardness_penalty -= 0.1
    elif "низ" in work_hardening:
        hardness_penalty += 0.05

    vc = base * machinability * multiplier * hardness_penalty
    return max(vc, 8.0)


def _select_fz(tool_type: str, tool_material: str, material_props: Dict[str, any], diameter: float) -> float:
    """Return feed per tooth based on diameter and machinability."""
    machinability = float(material_props.get("machinability_index", 0.6))

    if tool_type == "drill":
        # Equivalent f per revolution converted to per tooth for 2 flutes assumption
        base = 0.12 if diameter > 10 else 0.08
        return max(base * machinability, 0.04)

    tool_factor = 1.0
    if tool_material.lower() == "carbide":
        tool_factor = 1.2
    elif tool_material.lower() == "hss":
        tool_factor = 0.9

    dia_factor = 0.045 + (diameter / 100.0)
    return max(dia_factor * machinability * tool_factor, 0.02)


def calculate_cutting_modes(
    tool_type: str,
    tool_material: str,
    material_props: Dict[str, any],
    diameter: float,
    teeth: int,
) -> Dict[str, float]:
    """Calculate CNC cutting parameters and return a comprehensive dict."""
    tool_type = tool_type.lower()
    tool_material = tool_material.lower()

    vc = _select_vc(tool_type, tool_material, material_props)
    fz = _select_fz(tool_type, tool_material, material_props, diameter)

    n = (1000 * vc) / (math.pi * diameter) if diameter > 0 else 0
    n = max(n, 1.0)

    total_teeth = teeth if teeth > 0 else (2 if tool_type == "drill" else 4)
    feed = fz * total_teeth * n

    if tool_type == "drill":
        ap = diameter * 2.0  # depth of drilling in mm (per pass)
        ae = diameter * 0.95
    else:
        ap = max(diameter * 0.2, 0.5)
        ae = max(diameter * 0.6, 0.5)

    return {
        "vc": round(vc, 2),
        "n": round(n, 0),
        "fz": round(fz, 4),
        "feed": round(feed, 1),
        "ap": round(ap, 2),
        "ae": round(ae, 2),
    }
