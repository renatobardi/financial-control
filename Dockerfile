# syntax=docker/dockerfile:1
# Imagem de runtime do controle financeiro.
#
# Stage tailwind: gera financeiro/web/static/app.css com o binário standalone (ADR-0001,
# sem Node), pinado por versão e SHA256, os mesmos do Dockerfile do Kubo. Arquitetura
# padrão linux-arm64 (oute-server é aarch64); em x86_64 passe TAILWIND_ARCH=linux-x64 e o
# TAILWIND_SHA256 correspondente.
FROM python:3.12-slim AS tailwind
ARG TAILWIND_VERSION=v4.3.2
ARG TAILWIND_ARCH=linux-arm64
ARG TAILWIND_SHA256=394ddccc2402cfa3abd97dfba56f3587781a3d6e6ce66e65ceada14beb7664b8
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSL -o tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-${TAILWIND_ARCH}" \
    && echo "${TAILWIND_SHA256}  tailwindcss" | sha256sum -c - \
    && chmod +x tailwindcss
COPY financeiro/web/styles ./financeiro/web/styles
COPY financeiro/web/templates ./financeiro/web/templates
RUN ./tailwindcss -i financeiro/web/styles/input.css -o /build/app.css --minify

# Stage runtime
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FINANCEIRO_BD=/data/financeiro.db
ARG FINANCEIRO_COMMIT=desconhecido
ENV FINANCEIRO_COMMIT=${FINANCEIRO_COMMIT}
WORKDIR /app
# Camada de dependências primeiro: não invalida o cache a cada mudança de código.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY financeiro ./financeiro
COPY --from=tailwind /build/app.css ./financeiro/web/static/app.css
RUN useradd --create-home --uid 10001 app && mkdir /data && chown app /data
USER app
VOLUME /data
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "financeiro", "servir", "--host", "0.0.0.0"]
