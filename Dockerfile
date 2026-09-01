FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home anton && mkdir -p /app/data /app/reports \
    && chown -R anton:anton /app
USER anton

CMD ["anton", "run"]
