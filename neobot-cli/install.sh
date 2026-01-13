#!/usr/bin/env bash
#
# NeoBot-Net CLI Installer
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli/install.sh | bash
#
# Or with a specific version:
#   curl -sSL ... | bash -s -- --version v1.0.0

set -euo pipefail

# Configuration
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
REPO_URL="https://raw.githubusercontent.com/caffeinedoom/neobotnet_scan_mvp/main/neobot-cli"
VERSION="${1:-latest}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}${CYAN}"
echo "  _   _            ____        _   "
echo " | \ | | ___  ___ | __ )  ___ | |_ "
echo " |  \| |/ _ \/ _ \|  _ \ / _ \| __|"
echo " | |\  |  __/ (_) | |_) | (_) | |_ "
echo " |_| \_|\___|\___/|____/ \___/ \__|"
echo ""
echo -e "${NC}${BOLD}NeoBot-Net CLI Installer${NC}"
echo ""

# Check dependencies
echo -e "${CYAN}→${NC} Checking dependencies..."

missing=()
for cmd in curl jq; do
    if ! command -v "$cmd" &> /dev/null; then
        missing+=("$cmd")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo -e "${RED}Error:${NC} Missing required dependencies: ${missing[*]}"
    echo ""
    echo "Install them with:"
    echo "  Debian/Ubuntu: sudo apt install ${missing[*]}"
    echo "  macOS:         brew install ${missing[*]}"
    echo "  Arch:          sudo pacman -S ${missing[*]}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Dependencies OK (curl, jq)"

# Create install directory
echo -e "${CYAN}→${NC} Creating install directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Download the script
echo -e "${CYAN}→${NC} Downloading neobotnet CLI..."
curl -sSL "${REPO_URL}/neobotnet" -o "${INSTALL_DIR}/neobotnet"

# Make executable
chmod +x "${INSTALL_DIR}/neobotnet"

echo -e "${GREEN}✓${NC} Installed to ${INSTALL_DIR}/neobotnet"

# Check if in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo -e "${YELLOW}Warning:${NC} $INSTALL_DIR is not in your PATH."
    echo ""
    echo "Add it to your shell configuration:"
    echo ""
    echo "  # For bash (~/.bashrc):"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "  # For zsh (~/.zshrc):"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then reload your shell: source ~/.bashrc (or ~/.zshrc)"
fi

echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Configure your API key:"
echo "     neobotnet config --key YOUR_API_KEY"
echo ""
echo "  2. List your programs:"
echo "     neobotnet programs"
echo ""
echo "  3. Get subdomains:"
echo "     neobotnet subdomains <program-name>"
echo ""
echo "For help: neobotnet help"
echo "Documentation: https://neobotnet.com/api-docs"
