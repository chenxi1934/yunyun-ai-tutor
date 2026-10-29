ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${NODE_IMAGE} AS frontend
WORKDIR /ui
COPY frontend/package.json ./
RUN npm install --package-lock=false --registry=https://registry.npmjs.org
COPY frontend/ ./
RUN npm run build

FROM ${PYTHON_IMAGE}
ARG PYPI_INDEX_URL=https://pypi.org/simple
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir --timeout 30 --retries 2 --index-url ${PYPI_INDEX_URL} . && useradd -u 10001 -m app && mkdir /data && chown app /data
COPY --from=frontend /ui/dist ./frontend/dist/
ENV YUNYUN_PROJECT_ROOT=/app YUNYUN_MODE=web YUNYUN_DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
