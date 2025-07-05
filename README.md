# Stash Manager

An automated bridge between Stash and Whisparr that intelligently processes and filters adult content based on a powerful, rule-based engine.

## Overview

Stash Manager monitors your Stash instance for new scenes and automatically processes them through a customizable, sequential rule engine before integrating with Whisparr for content management. It provides granular, priority-based control over what content gets processed.

## Features

### Core Functionality
- **Automated Scene Processing** - Continuously monitors Stash for new content.
- **Rule-Based Filtering Engine** - Define a sequence of rules to accept or reject scenes with ultimate control over priority.
- **Dry Run Mode** - Safely test your rules without making any actual changes.
- **Whisparr Integration** - Seamless content management workflow.
- **StashDB Support** - Trigger identification jobs to enhance metadata.
- **Intelligent Scheduling** - Configurable processing intervals.
- **Comprehensive Logging** - Detailed activity tracking and debugging.

### Technical Features
- **SQLite Database** - Local tracking of processed scenes and performers.
- **GraphQL Integration** - Native Stash and StashDB API support.
- **Docker Ready** - Containerized deployment with Unraid and standard Docker support.
- **Error Recovery** - Automatic restart and error handling.
- **Flexible Configuration** - YAML-based configuration for rules and settings.

## Quick Start

### Docker Compose (Recommended for most platforms)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/aidrak/stash-manager.git
    cd stash-manager
    ```

2.  **Create your environment file:**
    ```bash
    cp .env.sample .env
    ```
    Now, edit the `.env` file with your Stash URL, API keys, and media path.

3.  **Deploy:**
    ```bash
    docker-compose up -d
    ```

### Unraid Deployment

1.  **Install from Community Applications** (if available).
2.  Or, **install manually** by adding the template from this repository to your Docker tab.
3.  Configure your Stash/Whisparr details and paths in the Unraid template UI.

## Configuration

Configuration is managed through environment variables (`.env` file) and the web interface.

#### Environment Variables (`.env` file)
This file is for secrets and environment-specific paths. It is read by `docker-compose` for standard Docker setups. For Unraid, these values are set in the container template UI.

Create this file by copying `.env.sample`:
```bash
cp .env.sample .env
```

## Directory Structure

```
stash-manager/
├── src/                    # Python application code
│   ├── app.py             # Application entry point
│   ├── config.py          # Configuration management
│   ├── processor.py       # Main processing logic
│   ├── filter.py          # Rule-based filtering engine
│   ├── stash_api.py       # Stash GraphQL client
│   └── ...
├── Dockerfile             # Docker build instructions
├── docker-compose.yml     # Docker Compose definition
├── entrypoint.sh          # Container startup script
├── requirements.txt       # Python dependencies
└── .env.sample            # Sample environment file
```

## Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/new-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add new feature'`).
5.  Push to the branch (`git push origin feature/new-feature`).
6.  Create a Pull Request.

## License

This project is licensed under the MIT License.
