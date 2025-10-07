"""Utilities for analyzing materials via OpenAI GPT models.

This module wraps interactions with OpenAI's API and keeps a local cache
of analysed materials in a JSON file. The cache is used both to minimise
API calls and to serve previously analysed materials immediately.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency for local tests
    OpenAI = None  # type: ignore


MATERIALS_PATH = Path("db/materials.json")


def _load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return an empty structure on failure."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_materials() -> Dict[str, Dict[str, Any]]:
    """Return the material cache indexed by normalised material name."""
    data = _load_json(MATERIALS_PATH)
    if not isinstance(data, dict):
        return {}
    return data  # type: ignore[return-value]


def save_material(name: str, properties: Dict[str, Any]) -> None:
    """Persist a material entry using a case-insensitive key."""
    materials = load_materials()
    key = name.strip().lower()
    materials[key] = properties
    _save_json(MATERIALS_PATH, materials)


def analyse_with_gpt(material_name: str) -> Dict[str, Any]:
    """Call OpenAI's API to analyse material properties.

    If the API key is not configured the function falls back to a local
    heuristic generator so that the application can still operate in
    offline/demo environments.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return _fallback_material(material_name)

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Ты технолог-металлург. Анализируешь материал и возвращаешь JSON "
        "со структурированными свойствами. Говори кратко и по-деловому."
    )

    user_prompt = f"""
Проанализируй материал "{material_name}" для обработки на ЧПУ.

Верни JSON со следующими полями:
- name: нормализованное название материала
- hardness_hb: твердость по Бринеллю (строка)
- structure: краткое описание структуры
- machinability_index: число от 0 до 1 (1 — легко обрабатывается)
- temperature_risk: низкий/средний/высокий
- work_hardening: низкая/средняя/высокая склонность к наклепу
- coolant: рекомендации по СОЖ
- notes: список из 3–5 технологических советов
- risks: список возможных проблем при обработке
- recommended_vc_hss: рекомендуемый диапазон Vc в м/мин для HSS
- recommended_vc_carbide: диапазон Vc для твердосплавного инструмента
- recommended_fz: диапазон подачи на зуб для фрез
"""

    response = client.responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_output_tokens=600,
    )

    content = response.output_text

    try:
        parsed: Dict[str, Any] = json.loads(content)
    except json.JSONDecodeError:
        return _fallback_material(material_name)

    return parsed


def _fallback_material(material_name: str) -> Dict[str, Any]:
    """Generate deterministic pseudo properties when GPT is unavailable."""
    name = material_name.strip()
    lowered = name.lower()

    if "алю" in lowered:
        hardness = "70-90 HB"
        machinability = 0.85
        temperature_risk = "низкий"
        work_hardening = "низкая"
        coolant = "Эмульсия или минимально-воздушное охлаждение"
        notes = [
            "Используйте острый инструмент с большим передним углом",
            "Высокие подачи допустимы, но следите за вибрациями",
            "Удаляйте стружку продувкой"
        ]
        risks = ["Залипание стружки", "Вибрации при больших вылетах"]
        vc_hss = "60-90"
        vc_carbide = "180-280"
        fz = "0.06-0.12"
    elif "титан" in lowered:
        hardness = "200-320 HB"
        machinability = 0.35
        temperature_risk = "высокий"
        work_hardening = "высокая"
        coolant = "Высоконапорная СОЖ, охлаждение через инструмент"
        notes = [
            "Минимизируйте контакт инструмента с материалом",
            "Используйте жёсткую оснастку и короткий вылет",
            "Контролируйте износ по задней поверхности"
        ]
        risks = ["Перегрев", "Наклёп", "Быстрый износ инструмента"]
        vc_hss = "15-20"
        vc_carbide = "40-70"
        fz = "0.04-0.08"
    else:
        hardness = "120-200 HB"
        machinability = 0.6
        temperature_risk = "средний"
        work_hardening = "средняя"
        coolant = "Эмульсия или синтетическая СОЖ"
        notes = [
            "Контролируйте температурный режим",
            "Используйте жёсткую фиксацию заготовки",
            "Следите за эвакуацией стружки"
        ]
        risks = ["Перегрев", "Вибрации"]
        vc_hss = "25-35"
        vc_carbide = "120-180"
        fz = "0.05-0.1"

    return {
        "name": name.title(),
        "hardness_hb": hardness,
        "structure": "См. справочные данные",
        "machinability_index": machinability,
        "temperature_risk": temperature_risk,
        "work_hardening": work_hardening,
        "coolant": coolant,
        "notes": notes,
        "risks": risks,
        "recommended_vc_hss": vc_hss,
        "recommended_vc_carbide": vc_carbide,
        "recommended_fz": fz,
    }


def analyse_material(material_name: str) -> Dict[str, Any]:
    """Return cached material data or fetch via GPT if not present."""
    materials = load_materials()
    key = material_name.strip().lower()
    if key in materials:
        return materials[key]

    properties = analyse_with_gpt(material_name)
    save_material(material_name, properties)
    return properties
