# NeoBot-Net CLI

Local command-line interface for triggering reconnaissance scans via AWS ECS.

## Installation

```bash
# Install from the cli directory
cd cli
pip install -e .

# Verify installation
neobotnet --help
```

## Configuration

Set environment variables or create `~/.neobotnet/.env`:

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# ECS Configuration
ECS_CLUSTER=neobotnet-v2-dev-cluster
ECS_ORCHESTRATOR_TASK=neobotnet-v2-dev-orchestrator
ECS_SUBNETS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUP=sg-xxx

# Supabase Configuration
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

Check configuration:

```bash
neobotnet config
```

## Usage

### Programs (Assets)

```bash
# List all programs
neobotnet programs list

# Show program details
neobotnet programs show hackerone

# Add a new program with domains
neobotnet programs add hackerone --domains hackerone.com,api.hackerone.com

# Add program from file
neobotnet programs add bugcrowd --file domains.txt

# Delete a program
neobotnet programs delete old-program
```

### Scans

```bash
# Run a scan on an existing program
neobotnet scan run hackerone

# Run a scan with new domains
neobotnet scan run hackerone --domains new.hackerone.com

# Run a scan from a domains file
neobotnet scan run bugcrowd --file targets.txt

# Specify modules (default: subfinder,dnsx,httpx)
neobotnet scan run hackerone --modules subfinder,dnsx,httpx,katana

# Wait for scan to complete
neobotnet scan run hackerone --wait

# Check scan status
neobotnet scan status <task-id>

# List recent scans
neobotnet scan list
neobotnet scan list --status running
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LOCAL TERMINAL                    AWS VPC                       │
│  ──────────────                    ───────                       │
│                                                                  │
│  neobotnet scan run program        ┌──────────────────────────┐ │
│       │                            │  ORCHESTRATOR CONTAINER   │ │
│       │ aws ecs run-task           │                          │ │
│       └───────────────────────────▶│  • scan_pipeline.py      │ │
│                                    │  • Redis access ✅        │ │
│                                    │  • Launches containers    │ │
│                                    └───────────┬──────────────┘ │
│                                                │                 │
│                                                ▼                 │
│                                    ┌──────────────────────────┐ │
│                                    │  SCAN CONTAINERS         │ │
│                                    │  Subfinder → Redis       │ │
│                                    │  DNSx + HTTPx (parallel) │ │
│                                    │  Katana (sequential)     │ │
│                                    └──────────────────────────┘ │
│                                                │                 │
│                                                ▼                 │
│                                           Supabase               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Scan Pipeline

The CLI triggers a streaming scan pipeline:

1. **Subfinder**: Discovers subdomains, streams results to Redis
2. **DNSx + HTTPx**: Run in parallel, consume from Redis stream
3. **Katana** (optional): Runs after HTTPx completes, crawls discovered URLs

All results are stored in Supabase and viewable in the web UI.

## Viewing Logs

```bash
# Follow orchestrator logs
aws logs tail /aws/ecs/neobotnet-v2-dev --follow

# Filter by task ID
aws logs tail /aws/ecs/neobotnet-v2-dev --filter-pattern 'abc123'
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black neobotnet/
ruff check neobotnet/ --fix
```

