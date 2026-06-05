# Mini E-commerce Distribuído — Guia de Execução

## Pré-requisitos

- Python 3.10+ **ou** Docker + Docker Compose
- Portas livres: **5001, 5002, 5003, 5012, 8000**

---

## Opção A — Docker Compose (Recomendado)

Todos os serviços foram movidos para a raiz do repositório (`mini-ecommerce-distribuido`) e os testes de integridade internos (`healthchecks`) foram corrigidos para utilizar comandos nativos de Python, eliminando a dependência do utilitário `curl` dentro dos containers `-slim`.

Para construir as imagens sem cache e subir todo o ecossistema integrado em segundo plano, execute:

```bash
# Na raiz do projeto (pasta mini-ecommerce-distribuido/)
docker compose build --no-cache
docker compose up -d
```

### Endpoints Disponíveis e Comportamento Esperado

> ⚠️ **Nota sobre Erros 404:** Acessar as URLs abaixo diretamente pela raiz (`/`) no navegador resultará em erro **404 Not Found**. Este é o comportamento normal e esperado, pois as rotas iniciais não foram programadas. Para testar a conectividade, adicione o caminho do endpoint específico (ex: `/status` ou `/health`).


| Serviço | URL de Entrada | Rota de Teste Válida |
| :--- | :--- | :--- |
| **API Gateway** | http://localhost:8000 | http://localhost:8000/status |
| **Dashboard Monitor** | http://localhost:8000/dashboard | Link Direto do Painel |
| **Usuários** | http://localhost:5001 | http://localhost:5001/health |
| **Produtos (primária)** | http://localhost:5002 | http://localhost:5002/health |
| **Produtos (réplica)** | http://localhost:5012 | http://localhost:5012/health |
| **Pedidos** | http://localhost:5003 | http://localhost:5003/health |

---

## Opção B — Execução Local (Sem Docker)

### 1. Instalar dependências
Certifique-se de que suas ferramentas não usem argumentos editáveis incorretos no instalador.
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

## Testando a Aplicação (PowerShell vs cURL)

Se você estiver executando os testes em ambiente Windows utilizando o **PowerShell**, utilize os comandos adaptados do `Invoke-RestMethod` para evitar falhas de aspas em dados JSON.

### 1. Registrar usuário admin
*   **Bash (Linux/Mac):**
    ```bash
    curl -X POST http://localhost:8000/users/register \
      -H "Content-Type: application/json" \
      -d '{"name":"Admin","email":"admin@loja.com","password":"senha123","role":"admin"}'
    ```
*   **PowerShell (Windows):**
    ```powershell
    Invoke-RestMethod -Uri "http://localhost:8000/users/register" -Method Post -ContentType "application/json" -Body '{"name":"Admin","email":"admin@loja.com","password":"senha123","role":"admin"}'
    ```

### 2. Login e obter token JWT
*   **Bash (Linux/Mac):**
    ```bash
    curl -X POST http://localhost:8000/users/login \
      -H "Content-Type: application/json" \
      -d '{"email":"admin@loja.com","password":"senha123"}'
    # Salve o "token" retornado. Exemplo: TOKEN=eyJ...
    ```
*   **PowerShell (Windows):**
    ```powershell
    Invoke-RestMethod -Uri "http://localhost:8000/users/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@loja.com","password":"senha123"}'
    ```

### 3. Criar produto (requer JWT de admin)
Substitua `$TOKEN` ou instancie a variável antes da chamada do comando.
*   **Bash (Linux/Mac):**
    ```bash
    curl -X POST http://localhost:8000/products \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer \$TOKEN" \
      -d '{"name":"Notebook Dell","price":3500.00,"stock":10,"description":"Notebook i7 16GB"}'
    ```
*   **PowerShell (Windows):**
    ```powershell
    Invoke-RestMethod -Uri "http://localhost:8000/products" -Method Post -Headers @{"Authorization"="Bearer \$TOKEN"} -ContentType "application/json" -Body '{"name":"Notebook Dell","price":3500.00,"stock":10,"description":"Notebook i7 16GB"}'
    ```

### 4. Listar produtos (sem autenticação)
*   **Bash / PowerShell:**
    ```bash
    curl http://localhost:8000/products
    ```

### 5. Criar pedido (requer JWT)
*   **Bash (Linux/Mac):**
    ```bash
    curl -X POST http://localhost:8000/orders \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer \$TOKEN" \
      -d '{"items":[{"productId":"1","name":"Notebook Dell","price":3500.00,"quantity":1}]}'
    ```
*   **PowerShell (Windows):**
    ```powershell
    Invoke-RestMethod -Uri "http://localhost:8000/orders" -Method Post -Headers @{"Authorization"="Bearer \$TOKEN"} -ContentType "application/json" -Body '{"items":[{"productId":"1","name":"Notebook Dell","price":3500.00,"quantity":1}]}'
    ```

### 6. Ver pedidos do usuário
Substitua o valor `1` pelo ID real gerado em sua base.
```bash
curl http://localhost:8000/orders/1 -H "Authorization: Bearer \$TOKEN"
```

### 7. Ver status dos serviços (heartbeat)
Retorna um relatório estruturado confirmando o status de comunicação ativa entre o gateway e as APIs.
```bash
curl http://localhost:8000/status
```

---

## Simulando Falhas no Ambiente

Para validar os mecanismos de tolerância a falhas e ver o monitoramento dinâmico em ação:

1.  Derrube um container específico via terminal (Ex: serviço de pedidos):
    ```bash
    docker compose stop orders
    ```
2.  Aguarde 10 segundos para a execução da janela de intervalo do heartbeat.
3.  Tente realizar uma requisição para a rota de pedidos pela porta do Gateway. O sistema retornará o status de erro tratado: **`503 Service Unavailable`**.
4.  Suba o serviço novamente para restabelecer a estabilidade automática:
    ```bash
    docker compose start orders
    ```

---

## Monitoramento Visual

Acesse **[http://localhost:8000/dashboard](http://localhost:8000/dashboard)** em qualquer navegador web para acompanhar o painel analítico com atualizações automáticas estruturadas a cada 5 segundos.
