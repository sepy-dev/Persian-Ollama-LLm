# Base image سبک
FROM python:3.11-slim

WORKDIR /app

# کپی سورس
COPY ./app /app

# نصب وابستگی‌ها
RUN pip install --no-cache-dir fastapi uvicorn httpx jinja2 python-multipart requests ctranslate2 sentencepiece ollama


EXPOSE 8000

# اجرای FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
