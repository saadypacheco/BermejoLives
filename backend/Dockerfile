FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
# timeouts/retries altos: PyPI a veces va lento y corta la descarga
ENV PIP_DEFAULT_TIMEOUT=120 UV_HTTP_TIMEOUT=120
RUN pip install --no-cache-dir --timeout 120 --retries 8 uv \
 && uv pip install --system .

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
