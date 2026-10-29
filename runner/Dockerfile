# 专用 Manager 镜像；与公网 API 镜像分离，只在可信宿主挂 Docker Socket。
FROM docker:cli AS cli
FROM python:3.12-slim
ARG PYPI_INDEX_URL=https://pypi.org/simple
WORKDIR /app
COPY --from=cli /usr/local/bin/docker /usr/local/bin/docker
COPY pyproject.toml ./
COPY backend ./backend
COPY runner ./runner
RUN pip install --no-cache-dir --index-url ${PYPI_INDEX_URL} '.[dev]'
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "runner.manager"]
