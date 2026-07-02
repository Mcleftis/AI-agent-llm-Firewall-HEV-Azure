FROM python:3.10-slim
RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN g++ -shared -fPIC -o firewall.so firewall.cpp
RUN pip install --no-cache-dir fastapi uvicorn prometheus-fastapi-instrumentator torch numpy requests pydantic mlflow
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
