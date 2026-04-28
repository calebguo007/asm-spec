# ASM Protocol - Multi-stage Docker Build

# Stage 1: Build TypeScript
FROM node:22-slim AS ts-build
WORKDIR /app
COPY registry/package*.json registry/tsconfig.json registry/
RUN cd registry && npm ci --ignore-scripts
COPY registry/src registry/src
COPY payments/package*.json payments/tsconfig.json payments/
RUN cd payments && npm ci --ignore-scripts
COPY payments/src payments/src

# Stage 2: Python crawler deps
FROM python:3.12-slim AS py-build
WORKDIR /build
COPY crawler/requirements.txt .
RUN pip install --no-cache-dir --target=/deps -r requirements.txt

# Stage 3: Runtime
FROM node:22-slim AS runtime
RUN apt-get update && apt-get install -y python3 python3-pip curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY manifests/ manifests/
COPY schema/ schema/
COPY --from=ts-build /app/registry registry
COPY --from=ts-build /app/payments payments
COPY crawler/ crawler/
COPY scorer/ scorer/
COPY --from=py-build /deps /usr/local/lib/python3/dist-packages
ENV NODE_ENV=production ASM_MODE=mock PORT=3456 PAYMENT_PORT=3457
EXPOSE 3456 3457
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:3456/health || exit 1
CMD ["sh", "-c", "cd /app/registry && npx tsx src/http.ts & cd /app/payments && npx tsx src/seller.ts & wait"]
