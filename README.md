# Mini E-commerce Distribuído — Guia de Execução

## Pré-requisitos

- Python 3.10+ **ou** Docker + Docker Compose
- Terminal: **PowerShell** (Windows) ou Bash (Linux/Mac)
- Portas livres: **5001, 5002, 5003, 5012, 8000**

---

## Opção A — Docker Compose (Recomendado)

Todos os serviços operam de forma isolada na raiz do repositório (`mini-ecommerce-distribuido`). Os testes de integridade internos (`healthchecks`) utilizam comandos nativos de Python, eliminando dependências externas como o utilitário `curl` de dentro dos containers `-slim`.

Para construir as imagens e subir todo o ecossistema integrado em segundo plano, execute no PowerShell:

```powershell
# Na raiz do projeto (pasta mini-ecommerce-distribuido/)
docker compose build --no-cache
docker compose up -d
```

### Endpoints Disponíveis e Comportamento Esperado

> ⚠️ **Nota sobre Erros 404:** Acessar as URLs abaixo diretamente pela raiz (`/`) no navegador ou via requisição resultará em erro **404 Not Found**. Este é o comportamento normal e esperado do framework quando a rota inicial não foi programada. Para testar a conectividade, adicione o caminho do endpoint específico (ex: `/status` ou `/health`).


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
Certifique-se de que os pacotes não utilizem argumentos editáveis inválidos (evite o prefixo `-e`).
```powershell
pip install flask pyjwt bcrypt requests
```

### 2. Abrir 5 janelas do PowerShell e rodar cada serviço

**Terminal 1 — Usuários**
```powershell
cd users
\$env:JWT_SECRET="super-secret-ecommerce-key-2024"; python app.py
```

**Terminal 2 — Produtos (primária)**
```powershell
cd products
\$env:JWT_SECRET="super-secret-ecommerce-key-2024"; env:PORT="5002"; env:IS_REPLICA="false"; \(env:REPLICA_URL="http://localhost:5012"; \)env:DATA_FILE="products.json"; python app.py
```

**Terminal 3 — Produtos (réplica)**
```powershell
cd products
\(env:JWT_SECRET="super-secret-ecommerce-key-2024"; \)env:PORT="5012"; \(env:IS_REPLICA="true"; \)env:DATA_FILE="products_replica.json"; python app.py
```

**Terminal 4 — Pedidos**
```powershell
cd orders
\$env:JWT_SECRET="super-secret-ecommerce-key-2024"; python app.py
```

**Terminal 5 — Gateway**
```powershell
cd gateway
\(env:USERS_URL="http://localhost:5001"; \)env:PRODUCTS_URL="http://localhost:5002"; \(env:PRODUCTS_REPLICA_URL="http://localhost:5012"; \)env:ORDERS_URL="http://localhost:5003"; python app.py
```

---

## Testando a Aplicação via PowerShell (Windows)

No Windows PowerShell, requisições HTTP REST devem utilizar o cmdlet `Invoke-RestMethod` passando os cabeçalhos autenticados no formato de tabela estruturada (`@{"Authorization"="Bearer ..."}`).

### 1. Registrar usuário admin
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/users/register" -Method Post -ContentType "application/json" -Body '{"name":"Admin","email":"admin@loja.com","password":"senha123","role":"admin"}'
```

### 2. Login e armazenamento automatizado do Token JWT
Para evitar truncamento de texto ou cópia incompleta de strings longas com reticências (`...`), execute o bloco abaixo para autenticar e salvar o token real diretamente na variável de sessão `$TOKEN`:
```powershell
\$RESPOSTA = Invoke-RestMethod -Uri "http://localhost:8000/users/login" -Method Post -ContentType "application/json" -Body '{"email":"admin@loja.com","password":"senha123"}'
TOKEN = RESPOSTA.token
```

### 3. Criar produto (requer JWT de admin)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/products" -Method Post -Headers @{"Authorization"="Bearer \$TOKEN"} -ContentType "application/json" -Body '{"name":"Notebook Dell","price":3500.00,"stock":10,"description":"Notebook i7 16GB"}'
```

### 4. Listar produtos (sem autenticação)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/products" -Method Get
```

### 5. Criar pedido (requer JWT)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/orders" -Method Post -Headers @{"Authorization"="Bearer \$TOKEN"} -ContentType "application/json" -Body '{"items":[{"productId":"1","name":"Notebook Dell","price":3500.00,"quantity":1}]}'
```

### 6. Ver pedidos específicos do usuário
Substitua o número final pelo ID do pedido gerado pelo sistema.
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/orders/1" -Method Get -Headers @{"Authorization"="Bearer \$TOKEN"}
```

### 7. Ver status global de integração (heartbeat)
Retorna o relatório estruturado em formato JSON confirmando o estado de comunicação ativa entre o API Gateway e as aplicações internas.
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/status" -Method Get
```

---

## Persistência de Dados

Os microserviços utilizam persistência em arquivos planos locais. Ao executar o ambiente via Docker Compose, volumes nomeados isolados gerenciam e salvam essas alterações em tempo real. Você pode inspecionar os registros brutos em formato de texto no diretório local do projeto avaliando a criação automatizada dos arquivos:
*   `users.json`
*   `products.json`
*   `products_replica.json`

---

## Simulando Falhas no Ambiente

Para validar os mecanismos de resiliência e tolerância a falhas do sistema:

1.  Derrube um container específico via PowerShell (Ex: serviço de pedidos):
    ```powershell
    docker compose stop orders
    ```
2.  Aguarde 10 segundos para a execução do intervalo programado do monitoramento.
3.  Efetue uma nova requisição para a rota de criação ou listagem de pedidos. O sistema tratará a indisponibilidade retornando o erro: **`503 Service Unavailable`**.
4.  Reinicie o serviço para restabelecer a estabilidade e sincronia automática:
    ```powershell
    docker compose start orders
    ```

---

## Monitoramento Visual

Acesse **[http://localhost:8000/dashboard](http://localhost:8000/dashboard)** em qualquer navegador web para acompanhar o painel gráfico analítico estruturado com atualizações automáticas de disponibilidade a cada 5 segundos.
