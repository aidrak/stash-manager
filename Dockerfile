# --- Build Stage ---
FROM python:3.9-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Copy requirements and install Python packages
COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

# --- Final Stage ---
FROM python:3.9-slim

# Create a non-root user
RUN useradd --create-home appuser
WORKDIR /home/appuser

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y cron curl iputils-ping --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from the build stage
COPY --from=builder /usr/src/app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY src/ ./src/
COPY entrypoint.sh .

# Give the new user ownership of the application files
RUN chown -R appuser:appuser /home/appuser

# Switch to the non-root user
USER appuser

# Set execute permissions for the entrypoint script
RUN chmod +x /home/appuser/entrypoint.sh

# Expose the application port
EXPOSE 5001

# Set the entrypoint
ENTRYPOINT ["/home/appuser/entrypoint.sh"]
