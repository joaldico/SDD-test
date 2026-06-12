# syntax=docker/dockerfile:1
# Marketplace Conciliador — Web image (plan 3.8.1)
#
# Two stages:
#   builder  — node:22-alpine; installs deps with lockfile, type-checks, and
#              produces an optimised static bundle via Vite.
#   runtime  — nginx:alpine; serves the bundle and reverse-proxies /api.
#
# The final image contains NO Node.js, no source files, and no node_modules.

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
