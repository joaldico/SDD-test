# syntax=docker/dockerfile:1
# Marketplace Conciliador — Web image (plan 3.8.1)
#
# Three stages:
#   dev      — node:22-alpine; Vite dev server with HMR (docker-compose.dev.yml).
#   builder  — node:22-alpine; installs deps with lockfile, type-checks, and
#              produces an optimised static bundle via Vite.
#   runtime  — nginx:alpine; serves the bundle and reverse-proxies /api.
#
# The runtime image contains NO Node.js, no source files, and no node_modules.

# ── Stage 0: local development (Vite + HMR) ──────────────────────────────────
FROM node:22-alpine AS dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host 0.0.0.0: bind on all interfaces so the port mapping works from the host
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ── Stage 1: build the React bundle ──────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies with strict lockfile enforcement (plan 3.8.1: npm ci).
# Copied before source so Docker caches this layer until package files change.
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build: tsc --noEmit (type check) + vite build
COPY . .
RUN npm run build

# ── Stage 2: serve with nginx (~25 MB final image, no Node) ──────────────────
FROM nginx:alpine AS runtime

# Remove the default welcome page configuration
RUN rm /etc/nginx/conf.d/default.conf

# Our configuration: SPA fallback + /api reverse proxy (see nginx.conf)
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Static bundle produced by Vite
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
