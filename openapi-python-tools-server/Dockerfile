FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

COPY requirements.txt requirements-fastapi.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-fastapi.txt

COPY app ./app
COPY tools ./tools
COPY openapi ./openapi

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
