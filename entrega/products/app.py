"""
Serviço de Produtos - Porta 5002 (réplica primária) / 5012 (réplica secundária)
Implementa replicação síncrona (consistência forte):
- Toda escrita é propagada para ambas as réplicas antes de confirmar.
- Leituras distribuídas em round-robin entre as réplicas.
"""
import os, json, requests
from flask import Flask, request, jsonify
import jwt
from datetime import datetime, timezone

app = Flask(__name__)
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-ecommerce-key-2024")
PORT = int(os.environ.get("PORT", 5002))
IS_REPLICA = os.environ.get("IS_REPLICA", "false").lower() == "true"
REPLICA_URL = os.environ.get("REPLICA_URL", "http://localhost:5012")
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(os.path.dirname(__file__), "products.json"))


def load_products():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def save_products(products):
    with open(DATA_FILE, "w") as f:
        json.dump(products, f, indent=2)


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
    return jsonify({"status": "ok", "service": "products", "port": PORT, "replica": IS_REPLICA})


@app.route("/products", methods=["GET"])
def list_products():
    products = load_products()
    return jsonify(products)


@app.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return jsonify({"error": "Produto não encontrado"}), 404
    return jsonify(product)


@app.route("/products", methods=["POST"])
def create_product():
    payload = get_auth_payload()
    if not payload:
        return jsonify({"error": "Token inválido ou ausente"}), 401
    if payload.get("role") != "admin":
        return jsonify({"error": "Apenas administradores podem criar produtos"}), 403

    data = request.get_json()
    if not data or not all(k in data for k in ("name", "price")):
        return jsonify({"error": "name e price são obrigatórios"}), 400

    products = load_products()
    product = {
        "id": str(len(products) + 1),
        "name": data["name"],
        "description": data.get("description", ""),
        "price": float(data["price"]),
        "stock": int(data.get("stock", 0)),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    products.append(product)
    save_products(products)

    # Se não é réplica, propaga para a réplica (consistência forte)
    if not IS_REPLICA:
        try:
            resp = requests.post(
                f"{REPLICA_URL}/products",
                json=data,
                headers={"Authorization": request.headers.get("Authorization", ""), "X-Internal": "true"},
                timeout=5
            )
            if resp.status_code not in (200, 201):
                # Rollback local se réplica falhar
                products = [p for p in products if p["id"] != product["id"]]
                save_products(products)
                return jsonify({"error": "Falha ao replicar. Operação cancelada."}), 503
        except Exception as e:
            products = [p for p in products if p["id"] != product["id"]]
            save_products(products)
            return jsonify({"error": f"Réplica indisponível: {str(e)}"}), 503

    return jsonify({"message": "Produto criado", "product": product}), 201


# Endpoint interno para replicação direta (sem verificação de role)
@app.route("/internal/sync", methods=["POST"])
def sync():
    if request.headers.get("X-Internal") != "true":
        return jsonify({"error": "Acesso não autorizado"}), 403
    data = request.get_json()
    products = load_products()
    product = {
        "id": str(len(products) + 1),
        "name": data["name"],
        "description": data.get("description", ""),
        "price": float(data["price"]),
        "stock": int(data.get("stock", 0)),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    products.append(product)
    save_products(products)
    return jsonify({"synced": True, "product": product}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
