FROM registry.access.redhat.com/ubi9

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Set writable config dir so fastapi-cli doesn't try to use /.config
ENV XDG_CONFIG_HOME=/app/.config
RUN mkdir -p /app/.config && chmod -R 777 /app/.config

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /bin/uv

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy


ENV PYTHONPATH=/app

COPY ./scripts /app/scripts

COPY ./pyproject.toml ./uv.lock ./alembic.ini /app/

COPY ./app /app/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv uv sync

RUN if [ -f /app/scripts/prestart.sh ]; then chmod +x /app/scripts/prestart.sh; fi

USER root

COPY ./scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]