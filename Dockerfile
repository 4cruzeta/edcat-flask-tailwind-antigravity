# Stage 1: Build Tailwind CSS (V4)
FROM node:22-alpine AS tailwind_builder

WORKDIR /app

# First, copy only the files needed for npm install to leverage Docker cache
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the CSS inputs and HTML templates (Tailwind V4 doesn't need external JS configs)
COPY edcat_root/ ./edcat_root/

# Build Tailwind CSS V4 explicitly pointing the input
RUN npx @tailwindcss/cli \
  -i ./edcat_root/static/css/input.css \
  -o ./edcat_root/static/css/output.css \
  --minify

# Stage 2: Build the final Python application using UV
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Inject latest UV binary directly into the Docker layer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Cache initialization: Copy only the requirement locks
COPY pyproject.toml uv.lock ./

# Sync Python packages optimally (creating a .venv internally)
RUN uv sync --frozen --no-dev

# Copy the actual backend code, our main entrypoint AND the RAG Vectors!
COPY edcat_root/ ./edcat_root/
COPY main.py ./

# Copy the compiled production-ready CSS from the builder stage
COPY --from=tailwind_builder /app/edcat_root/static/css/output.css ./edcat_root/static/css/output.css

EXPOSE 8080

# Run the app flawlessly via UV leveraging Gunicorn worker management
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "main:app"]
