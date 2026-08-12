FROM python:3.11-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINDSL_REPO_ROOT=/app \
    PYTHONPATH=/app/src

RUN groupadd --system --gid 10001 findsl \
    && useradd --system --uid 10001 --gid findsl --create-home findsl

WORKDIR /app
COPY pyproject.toml README.md ./
COPY deploy/api/constraints.txt /tmp/constraints.txt
RUN python -m pip install -c /tmp/constraints.txt \
    "setuptools>=61" wheel antlr4-python3-runtime==4.13.2 sqlglot==28.5.0
COPY src ./src
COPY configs ./configs
COPY data/samples ./data/samples
COPY data/hero ./data/hero
COPY data/real_samples ./data/real_samples
COPY grammar ./grammar
RUN python -m pip install --no-deps --no-build-isolation .

USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=2)"

CMD ["python", "-m", "findsl.cli", "serve-demo", "--host", "0.0.0.0", "--port", "8765"]
