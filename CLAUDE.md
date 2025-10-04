# Python Docker Development

This repository is set up for Python development in Docker containers with automated code quality checks.

## Project Structure

- `src/` - Python application source code
- `tests/` - Pytest test suite
- `tools/` - Development and validation utilities
- `venv/` - Python virtual environment
- `.claude/` - Claude Code settings and hooks
  - `hooks/` - Automated quality check hooks
  - `settings.json` - Project configuration

## Available Commands

### Setup and Development
- `python3 -m venv venv && source venv/bin/activate` - Create and activate virtual environment
- `pip install -r requirements-dev.txt` - Install all development dependencies
- `docker build -t docker.odieserver.com/project:latest .` - Build Docker container
- `docker push docker.odieserver.com/project:latest` - Push to registry
- `docker run -it --rm -v $(pwd):/app docker.odieserver.com/project:latest` - Run in Docker

### Code Quality
- `ruff check .` - Run linting checks
- `ruff format .` - Format code automatically
- `ruff check --fix .` - Auto-fix linting issues
- `pytest` - Run test suite
- `pytest --cov=src` - Run tests with coverage
- `python tools/run_tests.py` - Run complete validation suite

## Validation System

This project includes automated code quality checks:

1. **Ruff - Linting & Formatting** - Fast Python linter and formatter (replaces Black, isort, flake8)
2. **Pylint - Static Analysis** - Additional code quality checks
3. **Pylance & mypy - Type Checking** - Static type analysis and IntelliSense
4. **Pytest - Testing** - Unit and integration tests with coverage
5. **AI Validation (Optional)** - Gemini-powered rule checking against CLAUDE.md

### Automated Validation Hooks

- **Pre-Tool-Use Hook**: Shows reminder about project rules before actions
- **Post-Edit Hooks**:
  - Runs Ruff formatting and linting after editing Python files
  - AI validation checks code against CLAUDE.md rules (if configured)
  - Optional automatic test runner (disabled by default)
- **Validation**: Ensures code quality standards are met

## Docker Development

- **Container**: Python application runs in isolated Docker containers
- **Volume Mounting**: Code is mounted for live development
- **Consistency**: Same environment across all machines
- **Registry**: All images pushed to `docker.odieserver.com`

### Docker Registry

All Docker images should be pushed to the local registry at `docker.odieserver.com`:

```bash
# Build and tag for registry
docker build -t docker.odieserver.com/project:latest .

# Push to registry
docker push docker.odieserver.com/project:latest

# Pull from registry
docker pull docker.odieserver.com/project:latest
```

## Development Workflow

1. **Activate Environment**: `source venv/bin/activate`
2. **Edit Code**: Make changes to Python files
3. **Auto-Validation**: Hooks automatically check code quality
4. **Test**: Run `pytest` to validate functionality
5. **Docker Test**: Build and run in container to verify

## Key Features

- ✅ **Automated Linting**: Ruff checks code on every edit
- ✅ **Type Safety**: Pylance validates type hints
- ✅ **Testing**: Pytest ensures functionality
- ✅ **Docker**: Containerized development and deployment
- ✅ **Fast**: Ruff is 10-100x faster than traditional tools

## Never Overcomplicate

- NEVER create custom event dispatching with complex workarounds
- Fix root causes, don't add complexity layers
- Use virtual environment when available
- Utilize Ruff for linting and formatting
- Address Pylance errors and warnings in Python

## Security Rules

- Hardcoded secrets OK for development - VERIFY removal before production
- ALWAYS validate user input
- Use environment variables for production config
- Never commit real secrets to version control

## Important Notes

- **Type Hints**: Always use type annotations for better tooling
- **Docstrings**: Document functions using Google or NumPy style
- **Testing**: Write tests alongside code
- **Docker**: Test in containers for consistency
- **Python venv**: All tools run from `venv/bin/activate`

## MCP Server Usage (Optional)

If MCP servers are configured in settings.json, Claude Code can use:

- **filesystem**: Local file system access and manipulation
- **github**: Repository management and CI/CD integration

## Troubleshooting

### Ruff Errors
1. Check errors: `ruff check .`
2. Auto-fix: `ruff check --fix .`
3. Format: `ruff format .`

### Docker Issues
1. Rebuild: `docker build --no-cache -t docker.odieserver.com/project:latest .`
2. Debug: `docker run -it --rm docker.odieserver.com/project:latest /bin/bash`
3. Registry access: Verify `curl -k https://docker.odieserver.com/v2/` returns `{}`

### Missing Dependencies
1. Activate venv: `source venv/bin/activate`
2. Update: `pip install --upgrade -r requirements-dev.txt`

## Best Practices

- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions small and focused
- Write tests for new functionality
- Run validation before commits
- Test in Docker containers regularly

This setup ensures high-quality Python code with minimal manual intervention.
