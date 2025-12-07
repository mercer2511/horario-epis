# Usamos Python 3.13 (versión ligera)
FROM python:3.13-slim

# Variables de entorno para optimización
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Copiamos requirements e instalamos dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código fuente
COPY . .

# IMPORTANTE: Cloud Run inyecta la variable PORT (por defecto 8080)
# Usamos uvicorn para levantar la API en ese puerto.
CMD exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}