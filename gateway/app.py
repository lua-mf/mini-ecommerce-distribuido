"""
API Gateway - Porta 8000
- Repassa requisições para os microsserviços corretos
- Heartbeat a cada 5s para cada serviço (incluindo réplicas de produtos)
- Round-robin entre réplicas de produtos para leituras
- Dashboard HTML de monitoramento em GET /dashboard
"""
import os, time, logging, threading, requests
from flask import Flask, request, jsonify, Response
from datetime import datetime, timezone
from collections import deque

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USERS_URL    = os.environ.get("USERS_URL",    "http://localhost:5001")
PRODUCTS_URL = os.environ.get("PRODUCTS_URL", "http://localhost:5002")
PRODUCTS_REPLICA_URL = os.environ.get("PRODUCTS_REPLICA_URL", "http://localhost:5012")
ORDERS_URL   = os.environ.get("ORDERS_URL",   "http://localhost:5003")

SERVICES = {
    "users":            {"url": USERS_URL,    "healthy": True, "failures": 0, "last_check": None},
    "products":         {"url": PRODUCTS_URL, "healthy": True, "failures": 0, "last_check": None},
    "products_replica": {"url": PRODUCTS_REPLICA_URL, "healthy": True, "failures": 0, "last_check": None},
    "orders":           {"url": ORDERS_URL,   "healthy": True, "failures": 0, "last_check": None},
}

# Round-robin para leitura de produtos
_rr_counter = 0

# Log circular para dashboard
event_log = deque(maxlen=100)

def log_event(level, message):
    ts = datetime.now(timezone.utc).isoformat()
    entry = {"ts": ts, "level": level, "msg": message}
    event_log.appendleft(entry)
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)


def heartbeat_loop():
    while True:
        for name, svc in SERVICES.items():
            try:
                r = requests.get(f"{svc['url']}/health", timeout=2)
                if r.status_code == 200:
                    if not svc["healthy"]:
                        log_event("INFO", f"✅ Serviço '{name}' recuperado em {svc['url']}")
                    svc["healthy"] = True
                    svc["failures"] = 0
                else:
                    raise ValueError(f"status {r.status_code}")
            except Exception as e:
                svc["failures"] += 1
                if svc["failures"] >= 2 and svc["healthy"]:
                    svc["healthy"] = False
                    log_event("ERROR", f"❌ Serviço '{name}' FALHOU após {svc['failures']} tentativas: {e}")
            svc["last_check"] = datetime.now(timezone.utc).isoformat()
        time.sleep(5)


def get_products_read_url():
    """Round-robin entre primária e réplica para leituras."""
    global _rr_counter
    primary_ok  = SERVICES["products"]["healthy"]
    replica_ok  = SERVICES["products_replica"]["healthy"]
    if not primary_ok and not replica_ok:
        return None
    candidates = []
    if primary_ok:  candidates.append(PRODUCTS_URL)
    if replica_ok:  candidates.append(PRODUCTS_REPLICA_URL)
    url = candidates[_rr_counter % len(candidates)]
    _rr_counter += 1
    return url


def forward(target_url, path, method, headers=None, json_body=None, params=None):
    fwd_headers = {k: v for k, v in (request.headers or {}).items()
                   if k.lower() not in ("host", "content-length")}
    if headers:
        fwd_headers.update(headers)
    try:
        resp = requests.request(
            method, f"{target_url}{path}",
            headers=fwd_headers,
            json=json_body,
            params=params or request.args,
            timeout=10
        )
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("content-type", "application/json"))
    except Exception as e:
        return jsonify({"error": f"Erro ao contatar serviço: {str(e)}"}), 502


def require_healthy(service_name):
    """Decorator helper — retorna erro 503 se serviço estiver down."""
    svc = SERVICES.get(service_name)
    if not svc or not svc["healthy"]:
        return jsonify({"error": f"503 Service Unavailable — '{service_name}' está indisponível"}), 503
    return None


# ─────────────────────── USERS ROUTES ────────────────────────
@app.route("/users/register", methods=["POST"])
def proxy_register():
    err = require_healthy("users")
    if err: return err
    return forward(USERS_URL, "/users/register", "POST", json_body=request.get_json())


@app.route("/users/login", methods=["POST"])
def proxy_login():
    err = require_healthy("users")
    if err: return err
    return forward(USERS_URL, "/users/login", "POST", json_body=request.get_json())


@app.route("/users/<user_id>", methods=["GET"])
def proxy_get_user(user_id):
    err = require_healthy("users")
    if err: return err
    return forward(USERS_URL, f"/users/{user_id}", "GET")


# ─────────────────────── PRODUCTS ROUTES ──────────────────────
@app.route("/products", methods=["GET"])
def proxy_list_products():
    url = get_products_read_url()
    if not url:
        return jsonify({"error": "503 Service Unavailable — produtos indisponíveis"}), 503
    return forward(url, "/products", "GET")


@app.route("/products/<product_id>", methods=["GET"])
def proxy_get_product(product_id):
    url = get_products_read_url()
    if not url:
        return jsonify({"error": "503 Service Unavailable — produtos indisponíveis"}), 503
    return forward(url, f"/products/{product_id}", "GET")


@app.route("/products", methods=["POST"])
def proxy_create_product():
    # Escrita sempre vai para a primária (que propaga para réplica)
    err = require_healthy("products")
    if err: return err
    return forward(PRODUCTS_URL, "/products", "POST", json_body=request.get_json())


# ─────────────────────── ORDERS ROUTES ───────────────────────
@app.route("/orders", methods=["POST"])
def proxy_create_order():
    err = require_healthy("orders")
    if err: return err
    return forward(ORDERS_URL, "/orders", "POST", json_body=request.get_json())


@app.route("/orders/<user_id>", methods=["GET"])
def proxy_get_orders(user_id):
    err = require_healthy("orders")
    if err: return err
    return forward(ORDERS_URL, f"/orders/{user_id}", "GET")


# ─────────────────────── HEALTH & DASHBOARD ──────────────────
@app.route("/health", methods=["GET"])
def gw_health():
    return jsonify({"status": "ok", "service": "gateway", "port": 8000})


@app.route("/status", methods=["GET"])
def gw_status():
    return jsonify({name: {
        "url": s["url"],
        "healthy": s["healthy"],
        "failures": s["failures"],
        "last_check": s["last_check"]
    } for name, s in SERVICES.items()})


@app.route("/dashboard", methods=["GET"])
def dashboard():
    return DASHBOARD_HTML


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="5">
<title>E-commerce Monitor</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@700;800&display=swap');
  :root {
    --bg: #0a0a0f; --panel: #12121a; --border: #1e1e2e;
    --green: #00ff9d; --red: #ff4757; --amber: #ffa502;
    --blue: #00b4ff; --text: #c8d0e0; --muted: #555566;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; min-height: 100vh; padding: 2rem; }
  h1 { font-family: 'Syne', sans-serif; font-size: 2rem; color: var(--green); letter-spacing: -1px; margin-bottom: .25rem; }
  .subtitle { color: var(--muted); font-size: .75rem; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; position: relative; overflow: hidden; }
  .card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; }
  .card.ok::before { background: var(--green); }
  .card.fail::before { background: var(--red); }
  .card-name { font-family: 'Syne', sans-serif; font-size: .85rem; font-weight: 800; color: var(--blue); text-transform: uppercase; letter-spacing: 1px; }
  .card-status { font-size: 1.5rem; font-weight: 700; margin: .5rem 0; }
  .card.ok .card-status { color: var(--green); }
  .card.fail .card-status { color: var(--red); }
  .card-url { font-size: .7rem; color: var(--muted); }
  .card-meta { font-size: .7rem; color: var(--muted); margin-top: .5rem; }
  .log-section h2 { font-family: 'Syne', sans-serif; font-size: 1rem; color: var(--amber); margin-bottom: .75rem; }
  .log { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; max-height: 320px; overflow-y: auto; }
  .log-entry { display: flex; gap: 1rem; padding: .3rem 0; border-bottom: 1px solid var(--border); font-size: .72rem; }
  .log-entry:last-child { border-bottom: none; }
  .log-ts { color: var(--muted); white-space: nowrap; }
  .log-ok { color: var(--green); }
  .log-err { color: var(--red); }
  .badge { display: inline-block; padding: .15rem .5rem; border-radius: 4px; font-size: .65rem; font-weight: 700; text-transform: uppercase; }
  .badge-ok { background: #00ff9d22; color: var(--green); border: 1px solid var(--green); }
  .badge-fail { background: #ff475722; color: var(--red); border: 1px solid var(--red); }
  .refresh-note { font-size: .65rem; color: var(--muted); margin-top: 1.5rem; }
</style>
</head>
<body>
<h1>⚡ E-commerce Distribuído</h1>
<p class="subtitle">Auto-refresh a cada 5s • API Gateway :8000</p>
<div class="grid" id="cards">Carregando...</div>
<div class="log-section">
  <h2>📋 Log de Eventos</h2>
  <div class="log" id="log">Carregando...</div>
</div>
<p class="refresh-note">Página atualiza automaticamente a cada 5 segundos via meta refresh.</p>
<script>
async function refresh() {
  const r = await fetch('/status');
  const data = await r.json();
  const cards = document.getElementById('cards');
  cards.innerHTML = Object.entries(data).map(([name, s]) => `
    <div class="card ${s.healthy ? 'ok' : 'fail'}">
      <div class="card-name">${name}</div>
      <div class="card-status">${s.healthy ? '● ONLINE' : '● OFFLINE'}</div>
      <div class="card-url">${s.url}</div>
      <div class="card-meta">Falhas: ${s.failures} | Último check: ${s.last_check ? s.last_check.slice(11,19)+'Z' : 'N/A'}</div>
    </div>`).join('');

  const logR = await fetch('/log');
  const logData = await logR.json();
  const logEl = document.getElementById('log');
  logEl.innerHTML = logData.events.map(e => `
    <div class="log-entry">
      <span class="log-ts">${e.ts.slice(11,19)}Z</span>
      <span class="${e.level==='ERROR' ? 'log-err' : 'log-ok'}">${e.msg}</span>
    </div>`).join('') || '<div style="color:var(--muted);font-size:.75rem">Nenhum evento ainda.</div>';
}
refresh();
</script>
</body>
</html>"""


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"events": list(event_log)})


if __name__ == "__main__":
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    log_event("INFO", "🚀 API Gateway iniciado na porta 8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
