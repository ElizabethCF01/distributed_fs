FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./naming_server.py
ENV REDIS_HOST=redis
CMD ["uvicorn", "naming_server:app", "--host", "0.0.0.0", "--port", "8000"]
