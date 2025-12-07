FROM python:3.11-slim
WORKDIR /app
COPY . /app
ENV PYTHONPATH="${PYTHONPATH}:/app"
RUN pip install --no-cache-dir fastapi uvicorn aiosqlite pydantic pytest prometheus-client httpx
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
