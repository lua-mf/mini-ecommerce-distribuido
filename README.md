# Mini E-commerce Distribuído — Guia de Execução

## Pré-requisitos

- Python 3.10+ **ou** Docker + Docker Compose
- Portas livres: **5001, 5002, 5003, 5012, 8000**

---

## Opção A — Docker Compose (recomendado)

```bash
# Na raiz do projeto 
docker-compose up --build
```

Todos os serviços sobem automaticamente. Acesse:

| Serviço           | URL                        |
|-------------------|----------------------------|
| API Gateway       | http://localhost:8000      |
| Dashboard Monitor | http://localhost:8000/dashboard |
| Usuários          | http://localhost:5001      |
| Produtos (primária)| http://localhost:5002     |
| Produtos (réplica) | http://localhost:5012     |
| Pedidos           | http://localhost:5003      |

---

## Opção B — Execução local (sem Docker)

### 1. Instalar dependências

```bash
pip install flask pyjwt bcrypt requests
```

### 2. Abrir 5 terminais e rodar cada serviço

**Terminal 1 — Usuários**
```bash
cd users/
JWT_SECRET=super-secret-ecommerce-key-2024 python app.py
```

**Terminal 2 — Produtos (primária)**
```bash
cd products/
JWT_SECRET=super-secret-ecommerce-key-2024 PORT=5002 IS_REPLICA=false REPLICA_URL=http://localhost:5012 DATA_FILE=products.json python app.py
```

**Terminal 3 — Produtos (réplica)**
```bash
cd products/
JWT_SECRET=super-secret-ecommerce-key-2024 PORT=5012 IS_REPLICA=true DATA_FILE=products_replica.json python app.py
```

**Terminal 4 — Pedidos**
```bash
cd orders/
JWT_SECRET=super-secret-ecommerce-key-2024 python app.py
```

**Terminal 5 — Gateway**
```bash
cd gateway/
USERS_URL=http://localhost:5001 PRODUCTS_URL=http://localhost:5002 PRODUCTS_REPLICA_URL=http://localhost:5012 ORDERS_URL=http://localhost:5003 python app.py
```

---

## Testando com curl

### 1. Registrar usuário admin
```bash
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Admin","email":"admin@loja.com","password":"senha123","role":"admin"}'
```

### 2. Login e obter token JWT
```bash
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@loja.com","password":"senha123"}'
# Salve o "token" retornado. Exemplo: TOKEN=eyJ...
```

### 3. Criar produto (requer JWT de admin)
```bash
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Notebook Dell","price":3500.00,"stock":10,"description":"Notebook i7 16GB"}'
```

### 4. Listar produtos (sem autenticação)
```bash
curl http://localhost:8000/products
```

### 5. Criar pedido (requer JWT)
```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items":[{"productId":"1","name":"Notebook Dell","price":3500.00,"quantity":1}]}'
```

### 6. Ver pedidos do usuário
```bash
# Substitua USER_ID pelo id retornado no login
curl http://localhost:8000/orders/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Ver status dos serviços (heartbeat)
```bash
curl http://localhost:8000/status
```

---

## Simulando falha

Para testar o heartbeat, derrube um serviço enquanto o gateway está rodando:

```bash
# Mata o serviço de pedidos (Ctrl+C no terminal 4)
# Aguarde ~10s e tente:
curl http://localhost:8000/orders -H "Authorization: Bearer $TOKEN" \
  -d '{"items":[]}' -H "Content-Type: application/json"
# Retornará: 503 Service Unavailable

# Verifique o log no terminal do gateway — verá a mensagem de falha com timestamp
# Ao reiniciar o serviço de pedidos, o gateway registra a recuperação automaticamente
```

---

## Monitoramento Visual

Acesse **http://localhost:8000/dashboard** no navegador para ver o painel de status em tempo real com auto-refresh a cada 5 segundos.
