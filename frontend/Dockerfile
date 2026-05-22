FROM node:18-alpine

WORKDIR /app

# Accept build arguments for API URLs
ARG REACT_APP_ANALYTICS_API_URL=http://localhost:8000
ARG REACT_APP_INGEST_API_URL=http://localhost:8001
ARG REACT_APP_API_URL=http://localhost:8000

# Set environment variables for build
ENV REACT_APP_ANALYTICS_API_URL=${REACT_APP_ANALYTICS_API_URL}
ENV REACT_APP_INGEST_API_URL=${REACT_APP_INGEST_API_URL}
ENV REACT_APP_API_URL=${REACT_APP_API_URL}

# Copy package lock files FIRST for better caching
COPY package.json package-lock.json* ./

# Install dependencies with fix for ajv-keywords
RUN npm install --legacy-peer-deps --no-audit && npm install ajv --legacy-peer-deps --save-optional

# Copy source code
COPY . .

# Create non-root user for security (use different gid to avoid conflicts)
RUN addgroup -g 1001 appuser && \
    adduser -D -u 1001 -G appuser appuser

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

# Start application
CMD ["npm", "start"]
