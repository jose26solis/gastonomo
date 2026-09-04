# Imagen del backend (FastAPI/uvicorn). Build de un solo paso: no hay nada
# que compilar -psycopg/cryptography/bcrypt traen wheels prearmados para
# linux/amd64 y linux/arm64, no hace falta un toolchain de C en la imagen.
FROM python:3.13-slim

WORKDIR /app

# Copiar solo lo que pyproject.toml necesita para instalar (metadata +
# código) antes que el resto -así una capa de Docker con las dependencias
# ya instaladas se reutiliza entre builds mientras no cambien.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8000

# Sin curl en la imagen -slim no lo trae y no vale la pena instalarlo solo
# para esto-, así que el healthcheck usa la librería estándar de Python.
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/salud')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
