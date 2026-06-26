# rag-trust-lab API 컨테이너.
# 빌드:  docker build -t rag-trust-lab .
# 실행:  docker run -p 8000:8000 rag-trust-lab   ->  http://localhost:8000/docs
FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 복사해 레이어 캐시를 활용한다.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY . .

# Render 등 클라우드는 $PORT를 주입한다. 로컬 기본값은 8000.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
