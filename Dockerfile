FROM python:3.12-slim

WORKDIR /app

# install deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code
COPY . .

# DB lives in a mounted volume by default (see docker-compose.yml)
ENV DATABASE_URL=sqlite:////app/data/scholarpulse.db
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
