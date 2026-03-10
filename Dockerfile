FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port uvicorn runs on
EXPOSE 8080

# Run uvicorn Server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
