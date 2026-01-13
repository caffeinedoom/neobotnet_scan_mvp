# neobotnet simple CLI

A command-line interface for the [neobotnet](www.neobotnet.com) reconnaissance API. Designed for bug bounty hunters and security researchers who prefer terminal workflows.

## Features

- **Zero dependencies** - Just `curl` and `jq` (pre-installed on most systems)
-  **Single file** - Easy to install and distribute
-  **Pipe-friendly** - Works seamlessly with your existing toolchain
-  **Secure** - API key stored with proper file permissions
-  **Auto-pagination** - Automatically fetches all pages of results

## Installation

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli/install.sh | bash
```

### Manual Install

```bash
# Download the script
curl -sSL https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli/neobotnet -o ~/.local/bin/neobotnet

# Make it executable
chmod +x ~/.local/bin/neobotnet

# Ensure ~/.local/bin is in your PATH
export PATH="$HOME/.local/bin:$PATH"
```

## Getting Your API Key

1. **Sign in** to [neobotnet.com](https://neobotnet.com) using Google or X (Twitter)
2. Navigate to **API Docs** in the sidebar (or go directly to [neobotnet.com/api-docs](https://neobotnet.com/api-docs))
3. Click **"Generate API Key"** button
4. Click the **eye icon** to reveal your key
5. **Copy** your API key (it starts with `nb_live_`)

> ⚠️ **Keep your API key secret!** Don't share it or commit it to public repositories.

## Configuration

Once you have your API key, configure the CLI:

```bash
# Configure your API key
neobotnet config --key nb_live_xxxxxxxxxxxxx

# Or use environment variable
export NEOBOT_API_KEY=nb_live_xxxxxxxxxxxxx
```

## Usage

### List Programs

```bash
# List all programs (name + ID)
neobotnet programs

# Just program names
neobotnet programs | cut -f1

# Get program IDs only
neobotnet programs --id

# JSON output
neobotnet programs --json

# Count programs
neobotnet programs --count
```

### Get Subdomains

```bash
# Get all subdomains for a program (by name)
neobotnet subdomains verisign

# Or by UUID
neobotnet subdomains ad9a8a21-6611-4846-bc39-ae803d4053a5

# Search for specific subdomains
neobotnet subdomains verisign --search api

# JSON output with full metadata
neobotnet subdomains verisign --json

# Count subdomains
neobotnet subdomains verisign --count
```

### Get DNS Records

```bash
# Get all DNS records
neobotnet dns verisign

# Filter by record type
neobotnet dns verisign --type CNAME
neobotnet dns verisign --type A

# JSON output
neobotnet dns verisign --json
```

### Get HTTP Probes (Servers)

```bash
# Get all probed URLs
neobotnet probes verisign

# Only live servers (200 OK)
neobotnet probes verisign --live

# Filter by status code
neobotnet probes verisign --status 403

# JSON output
neobotnet probes verisign --json
```

### Get URLs

```bash
# Get all URLs
neobotnet urls verisign

# Only alive URLs
neobotnet urls verisign --alive

# Only URLs with parameters
neobotnet urls verisign --params

# Filter by status code
neobotnet urls verisign --status 200

# Search URLs
neobotnet urls verisign --search api

# Combine filters
neobotnet urls verisign --alive --params

# JSON output
neobotnet urls verisign --json
```

### Get Statistics

```bash
# Show program statistics
neobotnet stats verisign
```

## Integration Examples

### Subdomain Takeover Analysis

```bash
# Find CNAME records pointing to potentially vulnerable services
neobotnet dns verisign --type CNAME | grep -E "(s3|cloudfront|herokuapp|azure)"
```

### Live Server Discovery

```bash
# Get subdomains and probe with httpx
neobotnet subdomains verisign | httpx -silent -status-code

# Or use pre-probed results
neobotnet probes verisign --live
```

### Vulnerability Scanning with Nuclei

```bash
# Scan live URLs
neobotnet urls verisign --alive | nuclei -t cves/

# Scan servers with specific status codes
neobotnet probes verisign --status 200 | nuclei -t technologies/
```

### Parameter Discovery for Fuzzing

```bash
# Get URLs with parameters for parameter fuzzing
neobotnet urls verisign --params | gf xss
neobotnet urls verisign --params | gf sqli
```

### Export Data

```bash
# Export subdomains to file
neobotnet subdomains verisign > verisign_subdomains.txt

# Export as JSON
neobotnet subdomains verisign --json > verisign_subdomains.json

# Export multiple programs
for prog in verisign tesla cloudflare; do
    neobotnet subdomains "$prog" > "${prog}_subdomains.txt"
done
```

### Combine with Other Tools

```bash
# Check for subdomain takeover with subjack
neobotnet subdomains verisign | subjack -w - -t 100

# Fuzzing with ffuf
neobotnet urls verisign --alive | ffuf -w - -u FUZZ -mc 200,403

# Screenshot with gowitness
neobotnet probes verisign --live | gowitness file -f -
```

## Output Formats

| Flag | Description |
|------|-------------|
| (default) | Plain text, one item per line (pipe-friendly) |
| `--json` or `-j` | Full JSON output with metadata |
| `--count` or `-c` | Just the count of results |
| `--id` or `-i` | IDs only (for programs command) |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEOBOT_API_KEY` | API key (alternative to config file) | - |
| `NEOBOT_API_URL` | Custom API URL | `https://aldous-api.neobotnet.com` |

## Config File

The API key is stored in `~/.neobot/config`:

```bash
# View current config
neobotnet config --show

# The config file format
api_key=nb_live_xxxxxxxxxxxxx
```
