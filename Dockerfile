FROM python:3.12-slim
RUN pip install --no-cache-dir psycopg2-binary
WORKDIR /app
COPY api.py .
EXPOSE 8089
CMD ["python3", "api.py"]
