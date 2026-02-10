FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --without dev,rag --no-root

COPY schema/ schema/
COPY src/ src/
RUN poetry install --no-interaction --no-ansi --without dev,rag

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "ondc_mcp.server"]
