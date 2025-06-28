# Stash Manager

An automated bridge between Stash and Whisparr that intelligently processes and filters adult content based on configurable criteria.

## Overview

Stash Manager monitors your Stash instance for new scenes and automatically processes them through customizable filters before integrating with Whisparr for content management. It provides granular control over what content gets processed based on performers, studios, tags, and other metadata.

## Features

### Core Functionality
- **Automated Scene Processing** - Continuously monitors Stash for new content
- **Advanced Filtering System** - Multi-criteria filtering with granular controls
- **Whisparr Integration** - Seamless content management workflow
- **StashDB Support** - Enhanced metadata and performer information
- **Intelligent Scheduling** - Configurable processing intervals
- **Comprehensive Logging** - Detailed activity tracking and debugging

### Filtering Capabilities
- **Performer Filtering** - Whitelist/blacklist by performer names
- **Physical Attribute Filtering** - Ethnicity, breast size, and other measurements
- **Studio Management** - Include/exclude specific studios
- **Tag-Based Filtering** - Content categorization and filtering
- **Title Keyword Filtering** - Text-based scene title filtering
- **Configurable Controls** - Enable/disable individual filter types

### Technical Features
- **SQLite Database** - Local tracking of processed scenes and performers
- **GraphQL Integration** - Native Stash and StashDB API support
- **Docker Ready** - Containerized deployment with Unraid support
- **Error Recovery** - Automatic restart and error handling
- **Flexible Configuration** - YAML-based configuration management

## Quick Start

### Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/aidrak/stash-manager.git
   cd stash-manager
   ```

2. **Configure environment**
   ```bash
   cp .env.sample .env
   # Edit .env with your media path
   ```

3. **Setup configuration**
   ```bash
   mkdir -p /path/to/appdata/stash-manager/config
   cp config.yaml.sample /path/to/appdata/stash-manager/config/config.yaml
   # Edit config.yaml with your settings
   ```

4. **Deploy**
   ```bash
   docker-compose up -d
   ```

### Unraid Deployment

1. **Install from Community Applications** (if available)
   - Search for "Stash Manager" in Community Applications

2. **Manual Template Installation**
   - Copy the provided Unraid template XML
   - Add as new Docker container in Unraid
   - Configure paths and environment variables

## Configuration

### Required Configuration Files

#### 1. Environment Variables (`.env`)
```env
MEDIA_PATH=/path/to/your/media
```

#### 2. Main Configuration (`config/config.yaml`)

**Basic Setup:**
```yaml
# Stash connection
stash:
  url: http://stash:9999
  api_key: YOUR_STASH_API_KEY
  media_path: /media

# Whisparr connection  
whisparr:
  url: http://whisparr:6969
  api_key: YOUR_WHISPARR_API_KEY
  root_folder: /tv

# Processing schedule
cron:
  frequency: 60 # minutes between runs
```

**Advanced Filtering:**
```yaml
# Enable/disable filter types
filter_controls:
  enable_title_filters: true
  enable_performer_filters: true
  enable_studio_filters: false
  enable_ethnicity_filters: true
  enable_breast_size_filters: true
  enable_tag_filters: false

# Filter criteria
filters:
  # Performer management
  performer_whitelist: ["Performer One", "Performer Two"]
  performer_blacklist: ["Excluded Performer"]
  
  # Studio filtering
  include_studios: ["Studio A", "Studio B"]
  exclude_studios: ["Blocked Studio"]
  
  # Content filtering
  title_exclude_words: ["amateur", "homemade"]
  include_tags: ["Professional"]
  exclude_tags: ["Amateur"]
  
  # Physical attributes
  include_ethnicities: ["Caucasian", "Asian"]
  exclude_ethnicities: ["Other"]
  include_breast_sizes: ["C", "D", "DD"]
  exclude_breast_sizes: ["A", "B"]
```

### Network Configuration

**For Docker Compose:**
- Ensure your Stash and Whisparr containers are on the `media_net` network
- Create the network if it doesn't exist:
  ```bash
  docker network create media_net
  ```

**For Unraid:**
- Use bridge networking or custom bridge
- Ensure containers can communicate via hostnames or IP addresses

## API Requirements

### Stash API
- **Endpoint**: Your Stash GraphQL endpoint (typically `http://stash:9999/graphql`)
- **Authentication**: API key from Stash settings
- **Permissions**: Read access to scenes, performers, studios, and tags

### Whisparr API  
- **Endpoint**: Your Whisparr API endpoint (typically `http://whisparr:6969/api/v3/`)
- **Authentication**: API key from Whisparr settings
- **Permissions**: Full access for series management

### StashDB API (Optional)
- **Endpoint**: `https://stashdb.org/graphql`
- **Authentication**: StashDB API key (optional, for enhanced metadata)

## Directory Structure

```
stash-manager/
├── src/                    # Python application code
│   ├── main.py            # Application entry point
│   ├── config.py          # Configuration management
│   ├── processor.py       # Main processing logic
│   ├── filter.py          # Scene filtering engine
│   ├── stash_api.py       # Stash GraphQL client
│   ├── whisparr.py        # Whisparr API client
│   └── stashdb.py         # StashDB API client
├── config/                # Configuration directory
│   └── config.yaml        # Main configuration file
├── Dockerfile             # Docker build instructions
├── docker-compose.yml     # Docker Compose definition
├── entrypoint.sh          # Container startup script
├── loop-runner.sh         # Application runner script
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables
```

## Logging and Monitoring

### Log Levels
- **DEBUG**: Detailed processing information
- **INFO**: General operational messages  
- **WARNING**: Non-critical issues
- **ERROR**: Critical errors requiring attention

### Log Configuration
```yaml
logs:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
```

### Database Monitoring
The application maintains a SQLite database at `/config/stash_manager.db` containing:
- **scenes** table: Processed scene information
- **performers** table: Performer metadata and processing history

## Troubleshooting

### Common Issues

**Container won't start:**
- Check that config.yaml exists and is valid YAML
- Verify API keys are correct
- Ensure network connectivity between containers

**No scenes being processed:**
- Check Stash API connectivity and authentication
- Verify filter settings aren't too restrictive
- Review logs for filtering reasons

**Whisparr integration failing:**
- Confirm Whisparr API key and endpoint
- Check network connectivity
- Verify root folder path is correct

### Debug Mode
Enable debug logging for detailed troubleshooting:
```yaml
logs:
  level: DEBUG
```

### Manual Testing
Test API connectivity:
```bash
# Test Stash connection
curl -H "ApiKey: YOUR_API_KEY" -X POST -H "Content-Type: application/json" \
  -d '{"query":"query { version { build_time } }"}' \
  http://stash:9999/graphql

# Test Whisparr connection  
curl -H "X-Api-Key: YOUR_API_KEY" \
  http://whisparr:6969/api/v3/system/status
```

## Security Considerations

- **API Keys**: Store securely and rotate regularly
- **Network Isolation**: Use Docker networks to isolate traffic
- **File Permissions**: Ensure config directory has appropriate permissions
- **Updates**: Keep container updated for security patches

## Performance Tuning

### Processing Limits
```yaml
processing:
  scene_limit: 1000        # Max scenes per processing run
  performer_limit: 500     # Max performers to process
  delay_seconds: 10        # Delay between API calls
  job_timeout: 1800        # Maximum job runtime (seconds)
```

### Schedule Optimization
- **High Activity**: 15-30 minute intervals
- **Normal Usage**: 60 minute intervals  
- **Low Activity**: 2-4 hour intervals

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -am 'Add new feature'`)
6. Push to the branch (`git push origin feature/new-feature`)
7. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: Check the wiki for additional guides
- **Community**: Join discussions in GitHub Discussions

## Changelog

### v1.0.0
- Initial release
- Core Stash and Whisparr integration
- Advanced filtering system
- Docker and Unraid support
- SQLite database tracking
- Comprehensive configuration options