# --- Build Stage ---
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

# --- Final Stage ---
FROM python:3.11-slim

# Use Unraid standard: nobody (UID 99) and users (GID 100)
# The nobody user and users group should already exist, but let's ensure they do
RUN groupadd -f -g 100 users && \
    useradd -r -u 99 -g 100 -d /home/nobody -s /bin/bash nobody || true && \
    mkdir -p /home/nobody
WORKDIR /home/nobody

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y cron curl iputils-ping gosu --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from the build stage
COPY --from=builder /usr/src/app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY src/ ./src/
COPY entrypoint.sh .

# Give the nobody user ownership of the application files
RUN chown -R nobody:users /home/nobody

# Set execute permissions for the entrypoint script
RUN chmod +x /home/nobody/entrypoint.sh


# Expose the application port
EXPOSE 5001

# Set the entrypoint
ENTRYPOINT ["/home/nobody/entrypoint.sh"]
