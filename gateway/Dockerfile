# 1. Escolhe a imagem oficial do Python como base
FROM python:3.11-slim

# 2. Define a pasta dentro do container onde o código vai ficar
WORKDIR /app

# 3. Copia a lista de dependências para o container
COPY requirements.txt .

# 4. Instala as dependências listadas no arquivo
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o restante dos arquivos do seu projeto local para o container
COPY app.py .

# 6. Define o comando para rodar a aplicação Flask quando o container for iniciado
CMD ["python", "app.py"]
