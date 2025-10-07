"""Flask application powering the Telegram CNC cutting mode assistant."""
from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from api.admin import (
    add_user,
    append_history,
    delete_user,
    get_history,
    get_users,
    is_user_authorised,
    verify_admin_password,
)
from api.calc_modes import calculate_cutting_modes
from api.gpt_materials import analyse_material, load_materials

load_dotenv()


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "tg-cnc-secret")


@app.route("/")
def index() -> str:
    """Render the Telegram Mini App interface."""
    user_id = request.args.get("user_id", "")
    return render_template("index.html", user_id=user_id)


@app.route("/admin")
def admin_panel() -> str:
    if session.get("admin_authenticated"):
        return render_template("admin.html", admin_logged=True)
    return render_template("admin.html", admin_logged=False)


@app.post("/api/check_access")
def check_access():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"allowed": False, "message": "user_id отсутствует"}), 400

    allowed = is_user_authorised(int(user_id))
    if not allowed:
        return (
            jsonify({"allowed": False, "message": "⛔ Доступ запрещён. Обратитесь к администратору."}),
            403,
        )
    return jsonify({"allowed": True})


@app.get("/api/materials")
def list_materials():
    materials = load_materials()
    return jsonify({"materials": list(materials.values())})


@app.post("/api/materials/analyze")
def analyze_material():
    payload = request.get_json(force=True)
    user_id = payload.get("user_id")
    material_name = payload.get("material")

    if not user_id or not material_name:
        return jsonify({"error": "Недостаточно данных"}), 400

    if not is_user_authorised(int(user_id)):
        return (
            jsonify({"error": "⛔ Доступ запрещён. Обратитесь к администратору."}),
            403,
        )

    properties = analyse_material(material_name)
    return jsonify({"material": properties})


@app.post("/api/calc")
def calc_modes():
    payload: Dict[str, Any] = request.get_json(force=True)

    required_fields = [
        "user_id",
        "tool_type",
        "tool_material",
        "diameter",
        "teeth",
        "material_properties",
    ]

    missing = [f for f in required_fields if f not in payload]
    if missing:
        return jsonify({"error": f"Отсутствуют поля: {', '.join(missing)}"}), 400

    user_id = int(payload["user_id"])
    if not is_user_authorised(user_id):
        return (
            jsonify({"error": "⛔ Доступ запрещён. Обратитесь к администратору."}),
            403,
        )

    tool_type = payload["tool_type"]
    tool_material = payload["tool_material"]
    diameter = float(payload.get("diameter", 0))
    teeth = int(payload.get("teeth", 0))
    material_props: Dict[str, Any] = payload.get("material_properties", {})

    calculations = calculate_cutting_modes(tool_type, tool_material, material_props, diameter, teeth)

    recommendations = _build_recommendations(material_props, tool_type, tool_material)

    append_history(
        {
            "timestamp": dt.datetime.utcnow().isoformat(),
            "user_id": str(user_id),
            "tool_type": tool_type,
            "tool_material": tool_material,
            "diameter": diameter,
            "teeth": teeth,
            "material": material_props.get("name"),
            "vc": calculations["vc"],
            "n": calculations["n"],
            "fz": calculations["fz"],
            "feed": calculations["feed"],
        }
    )

    return jsonify({
        "calculation": calculations,
        "recommendations": recommendations,
    })


def _build_recommendations(material_props: Dict[str, Any], tool_type: str, tool_material: str) -> Dict[str, Any]:
    risks = material_props.get("risks", [])
    notes = material_props.get("notes", [])

    extra_notes = []
    temperature_risk = str(material_props.get("temperature_risk", "средний")).lower()
    if "выс" in temperature_risk:
        extra_notes.append("Сократите время резания, применяйте активное охлаждение.")
    if tool_type == "mill" and tool_material.lower() == "carbide":
        extra_notes.append("Используйте динамическую стратегию обработки для снижения вибраций.")
    if tool_type == "drill":
        extra_notes.append("Проверяйте удаление стружки, применяйте прерывистое сверление при глубине >3D.")

    return {
        "risks": risks,
        "notes": notes + extra_notes,
        "coolant": material_props.get("coolant", ""),
        "temperature_risk": material_props.get("temperature_risk", ""),
        "work_hardening": material_props.get("work_hardening", ""),
    }


@app.post("/api/admin/login")
def admin_login():
    payload = request.get_json(force=True)
    password = payload.get("password", "")
    if verify_admin_password(password):
        session["admin_authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Неверный пароль"}), 403


@app.post("/api/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return jsonify({"success": True})


@app.get("/api/admin/users")
def admin_users():
    if not session.get("admin_authenticated"):
        return jsonify({"error": "Требуется вход"}), 401
    return jsonify({"users": get_users()})


@app.post("/api/admin/users")
def admin_add_user():
    if not session.get("admin_authenticated"):
        return jsonify({"error": "Требуется вход"}), 401
    payload = request.get_json(force=True)
    try:
        entry = add_user(int(payload.get("user_id")), payload.get("name", ""))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"user": entry})


@app.delete("/api/admin/users/<user_id>")
def admin_delete_user(user_id: str):
    if not session.get("admin_authenticated"):
        return jsonify({"error": "Требуется вход"}), 401
    delete_user(int(user_id))
    return jsonify({"success": True})


@app.get("/api/admin/history")
def admin_history():
    if not session.get("admin_authenticated"):
        return jsonify({"error": "Требуется вход"}), 401
    return jsonify({"history": get_history()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
