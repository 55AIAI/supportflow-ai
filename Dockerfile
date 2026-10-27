FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-worker.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/backend/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn","supportflow.server:app","--host","0.0.0.0","--port","8000","--no-access-log"]
