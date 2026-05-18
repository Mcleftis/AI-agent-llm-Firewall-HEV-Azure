FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*
RUN addgroup --system hevgroup && adduser --system --group hevuser
WORKDIR /app
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*
COPY . .
RUN g++ -shared -fPIC -o testing/unit/physics.so cpp_core/physics_solver.cpp || true
RUN g++ -shared -fPIC -o cpp_core/cpp_firewall/firewall.so cpp_core/cpp_firewall/firewall.cpp || true
RUN chown -R hevuser:hevgroup /app
USER hevuser
EXPOSE 8501 8502

