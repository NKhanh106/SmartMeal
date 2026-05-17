# ── Dependencies stage ─────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

# ── Builder stage ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci
COPY . .

# Build with production env
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy standalone build output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

EXPOSE 3000

CMD ["node", "server.js"]
