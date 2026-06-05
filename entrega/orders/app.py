"""
Serviço de Pedidos - Porta 5003
Criação e listagem de pedidos por usuário autenticado.
"""
import os, json
from flask import Flask, request, jsonify
import jwt
from datetime import datetime, timezone

app = Flask(__name__)
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-ecommerce-key-2024")
DATA_FILE = os.path.join(os.path.dirname(__file__), "orders.json")


def load_orders():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def save_orders(orders):
    with open(DATA_FILE, "w") as f:
        json.dump(orders, f, indent=2)


def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def get_auth_payload():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    return verify_token(token)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "orders", "port": 5003})


@app.route("/orders", methods=["POST"])
def create_order():
    payload = get_auth_payload()
    if not payload:
        return jsonify({"error": "Token inválido ou ausente"}), 401

    data = request.get_json()
    if not data or "items" not in data or not data["items"]:
        return jsonify({"error": "items é obrigatório e não pode ser vazio"}), 400

    orders = load_orders()
    total = sum(item.get("price", 0) * item.get("quantity", 1) for item in data["items"])

    order = {
        "id": str(len(orders) + 1),
        "userId": payload["userId"],
        "items": data["items"],
        "total": round(total, 2),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    orders.append(order)
    save_orders(orders)

    return jsonify({"message": "Pedido criado", "order": order}), 201


@app.route("/orders/<user_id>", methods=["GET"])
def get_user_orders(user_id):
    payload = get_auth_payload()
    if not payload:
        return jsonify({"error": "Token inválido ou ausente"}), 401

    # Usuário só pode ver seus próprios pedidos; admin pode ver qualquer um
    if payload["userId"] != user_id and payload.get("role") != "admin":
        return jsonify({"error": "Acesso negado"}), 403

    orders = load_orders()
    user_orders = [o for o in orders if o["userId"] == user_id]
    return jsonify(user_orders)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    app.run(host="0.0.0.0", port=port, debug=False)
