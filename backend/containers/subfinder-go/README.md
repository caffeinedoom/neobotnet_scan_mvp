# Subfinder-Go Container

## Overview

A high-performance Go-based container for multi-domain subdomain enumeration using the ProjectDiscovery Subfinder SDK. This container replaces the inefficient Python-based subprocess approach with native Go performance and built-in multi-domain support.

## Key Features

- **Multi-Domain Support**: Scan multiple domains in a single container execution
- **Native Go Performance**: Direct SDK integration eliminates subprocess overhead
- **Redis Coordination**: Real-time progress tracking and job coordination
- **Supabase Integration**: Efficient batch storage of discovered subdomains
- **Graceful Shutdown**: Proper signal handling for container orchestration
- **Rate Limiting**: Built-in API rate limiting to respect provider limits
- **Worker Pool**: Configurable concurrent domain processing

## Usage

### Command Line Interface

```bash
# Scan single domain
./subfinder-go <job_id> <domain>

# Scan multiple domains
./subfinder-go <job_id> <domain1,domain2,domain3>

# Example
./subfinder-go asset_123_abc epicgames.com,unrealengine.com,fortnite.com
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis server hostname | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |
| `SUPABASE_URL` | Supabase project URL | Required |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | Required |
| `SCAN_TIMEOUT` | Overall scan timeout in minutes | `10` |
| `WORKERS` | Number of concurrent workers | `10` |

## Architecture

### Multi-Domain Processing Flow

1. **Parse Arguments**: Extract job ID and domain list from command line
2. **Initialize Resources**: Setup Redis, Supabase, and logging
3. **Progress Tracking**: Initialize asset-level scan progress in Redis
4. **Worker Pool**: Process domains concurrently with configurable limits
5. **Rate Limiting**: Respect API provider rate limits (15 req/sec)
6. **Result Aggregation**: Collect and batch-store discovered subdomains
7. **Status Updates**: Real-time progress updates via Redis

### Data Flow

```
Asset Scan Request
├── Domain 1 (epicgames.com) ─┐
├── Domain 2 (unrealengine.com) ─┤ → Subfinder SDK → Results → Supabase
└── Domain 3 (fortnite.com) ─┘

Progress Updates ↓
Redis Job Tracking
```

## Performance Improvements

### Before (Python Container)
- **Process Overhead**: Python → subprocess → subfinder CLI
- **Memory Inefficiency**: Multiple data marshaling steps
- **Single Domain**: One container per domain
- **Error Handling**: Complex CLI output parsing

### After (Go Container)
- **Direct SDK Access**: Native Go subfinder integration
- **Memory Efficient**: Direct memory access to results
- **Multi-Domain**: Multiple domains per container
- **Structured Errors**: Proper Go error handling

## Integration with ECS Orchestrator

### Container Configuration
```python
# In workflow_orchestrator.py
"containerOverrides": [{
    "name": "subfinder-go",
    "command": [job_id, ",".join(domains)],
    "environment": [
        {"name": "REDIS_HOST", "value": redis_host},
        {"name": "SUPABASE_URL", "value": supabase_url},
        # ... other env vars
    ]
}]
```

### Resource Scaling
- **CPU**: Scales with domain count (512 * domains, max 4096)
- **Memory**: Scales for result processing (1024 * domains, max 8192)
- **Timeout**: Increases with domain count (5 min * domains)

## Redis Job Tracking

### Asset Scan Progress
```json
{
  "job_id": "asset_123_abc",
  "status": "running",
  "total_domains": 3,
  "completed_domains": 1,
  "total_subdomains": 247,
  "domain_progress": {
    "epicgames.com": {
      "status": "completed",
      "subdomains_found": 89
    },
    "unrealengine.com": {
      "status": "running",
      "subdomains_found": 23
    },
    "fortnite.com": {
      "status": "pending"
    }
  }
}
```

## Database Schema

### Subdomain Records
```sql
INSERT INTO subdomains (
  subdomain,
  ip_addresses,
  source_module,
  discovered_at,
  scan_job_id,
  parent_domain
) VALUES (
  'store.epicgames.com',
  '{}',
  'subfinder',
  '2025-01-09T12:34:56Z',
  'asset_123_abc',
  'epicgames.com'
);
```

## Building and Testing

### Build Container
```bash
cd backend/containers/subfinder-go
docker build -t subfinder-go:latest .
```

### Local Testing
```bash
# Set environment variables
export REDIS_HOST=localhost
export SUPABASE_URL=your_supabase_url
export SUPABASE_SERVICE_ROLE_KEY=your_service_key

# Test single domain
./subfinder-go test_job_123 example.com

# Test multiple domains
./subfinder-go test_job_456 "example.com,test.com"
```

## Migration Path

### Phase 1: Parallel Testing
- Deploy subfinder-go alongside existing Python container
- Test with small domain sets
- Compare performance and accuracy

### Phase 2: Gradual Migration
- Update workflow orchestrator to use subfinder-go
- Migrate asset-level scans first
- Keep Python container for single-domain scans

### Phase 3: Full Migration
- Replace all subfinder usage with Go container
- Remove Python container and dependencies
- Update frontend to use new progress format

## Monitoring and Debugging

### Container Logs
```bash
# View container logs
docker logs <container_id>

# Follow real-time logs
docker logs -f <container_id>
```

### Redis Debugging
```bash
# Check job progress
redis-cli GET job:asset_123_abc

# List all active jobs
redis-cli KEYS "job:*"
```

### Health Checks
- Container includes basic health check via process monitoring
- Logs provide detailed progress and error information
- Redis stores real-time scan progress

## Future Enhancements

- **IP Resolution**: Add IP address resolution for discovered subdomains
- **HTTP Probing**: Integrate HTTP status code checking
- **SSL Analysis**: Add SSL certificate information gathering
- **Custom Wordlists**: Support for custom subdomain wordlists
- **Performance Metrics**: Detailed timing and performance analytics
