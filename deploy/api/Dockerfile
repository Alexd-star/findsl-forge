FROM python:3.11-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINDSL_REPO_ROOT=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-mysql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 findsl \
    && useradd --system --uid 10001 --gid findsl --create-home findsl

WORKDIR /app
COPY pyproject.toml README.md ./
COPY deploy/api/constraints.txt /tmp/constraints.txt
COPY src ./src
COPY configs ./configs
COPY data/samples ./data/samples
COPY grammar ./grammar
RUN python -m pip install -c /tmp/constraints.txt ".[service]"

RUN mkdir -p /var/log/findsl && chown -R findsl:findsl /var/log/findsl /app
USER 10001:10001

EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/v1/health/ready', timeout=2)"

CMD ["python", "-m", "findsl.cli", "serve-api", "--host", "0.0.0.0", "--port", "8766", "--log-level", "info"]
