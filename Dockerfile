FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SHA del commit horneado en la imagen (ADR-037, endpoint /salud/), como
# variable de entorno y no como archivo bajo /app: `web` monta `.:/app`
# como volumen (ver docker-compose.yml), así que cualquier archivo escrito
# bajo /app en este build quedaría tapado por el bind mount del host en
# tiempo de ejecución — verificado en vivo el 2026-08-08, un primer intento
# con /app/.git_sha dio "No such file or directory" pese a estar en la
# imagen. Una variable de entorno no tiene ese problema: sobrevive al mount.
# "desconocido" es el default a propósito: un build que no pase
# --build-arg GIT_SHA tiene que quedar detectable como tal, no
# silenciosamente vacío ni heredar el SHA de un build anterior.
ARG GIT_SHA=desconocido
ENV GIT_SHA=${GIT_SHA}

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
