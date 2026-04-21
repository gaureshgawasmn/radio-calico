FROM python:3.12-slim
WORKDIR /app
COPY api.py .
EXPOSE 8089
CMD ["python3", "api.py"]
