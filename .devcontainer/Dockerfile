FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash vscode
USER vscode
WORKDIR /workspace

# Install Claude Code globally
RUN curl -fsSL https://www.npmjs.com/install.sh | sh
RUN npm install -g @anthropic-ai/claude-code

# Set up Python environment
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy project files
COPY . .