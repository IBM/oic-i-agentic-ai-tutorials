# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CVE-2026-81726 mitigation: pre-download NLTK data at build time so the app
# never calls nltk.download() at runtime (the vulnerable code path).
RUN python -c "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('stopwords', quiet=True)"

# Copy app code
COPY main.py .

# Expose FastAPI port
EXPOSE 8000

# Run the app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]