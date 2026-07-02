FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn transformers torch numpy
EXPOSE 8001
CMD ["uvicorn", "llm_operator:app", "--host", "0.0.0.0", "--port", "8001"]
