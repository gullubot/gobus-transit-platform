# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage - just an alpine image to hold static files for volume sharing
FROM alpine:3.19

WORKDIR /usr/share/caddy
COPY --from=builder /app/dist .

# Keep the container alive to share the volume
CMD ["tail", "-f", "/dev/null"]
