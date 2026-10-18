FROM falkordb/falkordb:latest

# Install Python 3, pip, venv, git, and curl
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Create virtual environment to isolate Python dependencies
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure entrypoint is executable and uses LF line endings
RUN chmod +x docker-entrypoint.sh

# Render sets PORT dynamically (defaults to 8080)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
