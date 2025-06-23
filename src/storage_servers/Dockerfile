FROM python:3.11-slim
WORKDIR /app
COPY main.py requirements.txt ./
COPY storage ./storage
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p storage
EXPOSE 5001

CMD ["python", "main.py", "--port", "5001"]
