FROM python:3.12-slim

# git: lo necesita mcp_servers/django_project/tools.py (git_status) cuando
# corra como subproceso stdio dentro de este mismo contenedor.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# UID parametrizable (ver ADR-017, ADR-021) — nunca cableado a un número
# fijo, porque el UID real de fernando puede cambiar al migrar de servidor
# (ADR-002). El default acá es solo un fallback de build; docker-compose.yml
# lo pasa como build arg desde ORCHESTRATOR_UID.
ARG ORCHESTRATOR_UID=1001
RUN useradd --uid ${ORCHESTRATOR_UID} --create-home --shell /usr/sbin/nologin orchestrator \
    && mkdir -p /home/orchestrator/.claude \
    && chown orchestrator:orchestrator /home/orchestrator/.claude

WORKDIR /orchestrator

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator.py .

USER orchestrator
ENV HOME=/home/orchestrator

# Sin lógica de negocio ni disparador automático (ver ADR-021): este proceso
# solo mantiene el contenedor vivo para poder hacer `docker compose exec`.
CMD ["sleep", "infinity"]
