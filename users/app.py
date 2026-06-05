"""
Serviço de Usuários - Porta 5001
Responsável por registro, login e consulta de usuários.
Senhas armazenadas com bcrypt. JWT gerado no login.
"""
import os, json, hashlib
from flask import Flask, request, jsonify
import jwt, bcrypt
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-ecommerce-key-2024")
DATA_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def load_users():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def save_users(users):
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)


def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "users", "port": 5001})


@app.route("/users/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ("name", "email", "password")):
        return jsonify({"error": "name, email e password são obrigatórios"}), 400

    users = load_users()
    if any(u["email"] == data["email"] for u in users):
        return jsonify({"error": "E-mail já cadastrado"}), 409

    hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    user = {
        "id": str(len(users) + 1),
        "name": data["name"],
        "email": data["email"],
        "password": hashed,
        "role": data.get("role", "user"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    users.append(user)
    save_users(users)

    return jsonify({"message": "Usuário criado com sucesso", "userId": user["id"]}), 201


@app.route("/users/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ("email", "password")):
        return jsonify({"error": "email e password são obrigatórios"}), 400

    users = load_users()
    user = next((u for u in users if u["email"] == data["email"]), None)
    if not user:
        return jsonify({"error": "Credenciais inválidas"}), 401

    if not bcrypt.checkpw(data["password"].encode(), user["password"].encode()):
        return jsonify({"error": "Credenciais inválidas"}), 401

    payload = {
        "userId": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return jsonify({"token": token, "userId": user["id"], "role": user["role"]}), 200


@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    payload = verify_token(token)
    if not payload:
        return jsonify({"error": "Token inválido ou expirado"}), 401

    users = load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    return jsonify({"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
