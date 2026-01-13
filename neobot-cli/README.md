# NeoBot-Net CLI

A command-line interface for the NeoBot-Net reconnaissance API. Designed for bug bounty hunters and security researchers who prefer terminal workflows.

## Features

- 🚀 **Zero dependencies** - Just `curl` and `jq` (pre-installed on most systems)
- 📦 **Single file** - Easy to install and distribute
- 🔗 **Pipe-friendly** - Works seamlessly with your existing toolchain
- 🔐 **Secure** - API key stored with proper file permissions
- ⚡ **Auto-pagination** - Automatically fetches all pages of results

## Installation

### Quick Install (Recommended)

```bash
curl -sSL https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli/install.sh | bash
```

### Manual Install

```bash
# Download the script
curl -sSL https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli/neobot -o ~/.local/bin/neobot

# Make it executable
chmod +x ~/.local/bin/neobot

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
neobot config --key nb_live_xxxxxxxxxxxxx

# Or use environment variable
export NEOBOT_API_KEY=nb_live_xxxxxxxxxxxxx
```

## Usage

### List Programs

```bash
# List all programs (name + ID)
neobot programs

# Just program names
neobot programs | cut -f1

# Get program IDs only
neobot programs --id

# JSON output
neobot programs --json

# Count programs
neobot programs --count
```

### Get Subdomains

```bash
# Get all subdomains for a program (by name)
neobot subdomains verisign

# Or by UUID
neobot subdomains ad9a8a21-6611-4846-bc39-ae803d4053a5

# Search for specific subdomains
neobot subdomains verisign --search api

# JSON output with full metadata
neobot subdomains verisign --json

# Count subdomains
neobot subdomains verisign --count
```

### Get DNS Records

```bash
# Get all DNS records
neobot dns verisign

# Filter by record type
neobot dns verisign --type CNAME
neobot dns verisign --type A

# JSON output
neobot dns verisign --json
```

### Get HTTP Probes (Servers)

```bash
# Get all probed URLs
neobot probes verisign

# Only live servers (200 OK)
neobot probes verisign --live

# Filter by status code
neobot probes verisign --status 403

# JSON output
neobot probes verisign --json
```

### Get URLs

```bash
# Get all URLs
neobot urls verisign

# Only alive URLs
neobot urls verisign --alive

# Only URLs with parameters
neobot urls verisign --params

# Filter by status code
neobot urls verisign --status 200

# Search URLs
neobot urls verisign --search api

# Combine filters
neobot urls verisign --alive --params

# JSON output
neobot urls verisign --json
```

### Get Statistics

```bash
# Show program statistics
neobot stats verisign
```

## Integration Examples

### Subdomain Takeover Analysis

```bash
# Find CNAME records pointing to potentially vulnerable services
neobot dns verisign --type CNAME | grep -E "(s3|cloudfront|herokuapp|azure)"
```

### Live Server Discovery

```bash
# Get subdomains and probe with httpx
neobot subdomains verisign | httpx -silent -status-code

# Or use pre-probed results
neobot probes verisign --live
```

### Vulnerability Scanning with Nuclei

```bash
# Scan live URLs
neobot urls verisign --alive | nuclei -t cves/

# Scan servers with specific status codes
neobot probes verisign --status 200 | nuclei -t technologies/
```

### Parameter Discovery for Fuzzing

```bash
# Get URLs with parameters for parameter fuzzing
neobot urls verisign --params | gf xss
neobot urls verisign --params | gf sqli
```

### Export Data

```bash
# Export subdomains to file
neobot subdomains verisign > verisign_subdomains.txt

# Export as JSON
neobot subdomains verisign --json > verisign_subdomains.json

# Export multiple programs
for prog in verisign tesla cloudflare; do
    neobot subdomains "$prog" > "${prog}_subdomains.txt"
done
```

### Combine with Other Tools

```bash
# Check for subdomain takeover with subjack
neobot subdomains verisign | subjack -w - -t 100

# Fuzzing with ffuf
neobot urls verisign --alive | ffuf -w - -u FUZZ -mc 200,403

# Screenshot with gowitness
neobot probes verisign --live | gowitness file -f -
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
neobot config --show

# The config file format
api_key=nb_live_xxxxxxxxxxxxx
```

## Troubleshooting

### "Command not found: neobot"

Add `~/.local/bin` to your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "No API key configured"

Configure your API key:

```bash
neobot config --key YOUR_API_KEY
```

### "Authentication failed"

1. Check your API key is correct
2. Ensure it starts with `nb_live_`
3. Regenerate a new key at [neobotnet.com/api-docs](https://neobotnet.com/api-docs)

### "Program not found"

- Check the program name spelling
- Use `neobot programs` to list available programs
- Try using the program UUID instead of name

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Support

- Documentation: [neobotnet.com/api-docs](https://neobotnet.com/api-docs)
- Issues: [GitHub Issues](https://github.com/caffeinedoom/neobotnet_scan_mvp/issues)
- Support: [neobotnet.com/support](https://neobotnet.com/support)
