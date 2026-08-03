FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx
COPY relay.py .
ENV PORT=8080
CMD ["sh", "-c", "uvicorn relay:app --host 0.0.0.0 --port ${PORT}"]
