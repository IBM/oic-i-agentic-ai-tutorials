FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir beeai-framework[a2a,search]
CMD ["python", "__main__.py"]
