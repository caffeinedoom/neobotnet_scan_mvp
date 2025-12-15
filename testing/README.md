# Testing Directory

This directory contains organized testing utilities for the Web Reconnaissance Framework.

## Structure

```
testing/
├── api/           # API testing utilities (future)
├── data/          # Test payloads and data files
├── scripts/       # Test automation scripts
└── README.md      # This file
```

## Quick Start

1. **Run all tests:**
   ```bash
   cd testing/scripts
   ./run-all-tests.sh
   ```

2. **Individual tests:**
   ```bash
   ./test-auth.sh                    # Test authentication
   ./test-recon.sh                   # Test reconnaissance (default payload)
   ./test-recon.sh scan-example.json # Test with specific payload
   ./check-logs.sh 10                # Check logs (last 10 minutes)
   ```

## Test Data Files

- `login.json` - User authentication payload
- `scan-debug.json` - Debug domain for testing
- `scan-example.json` - Example.com for realistic testing

## Test Scripts

- `test-auth.sh` - Authentication flow testing
- `test-recon.sh` - Reconnaissance functionality testing
- `check-logs.sh` - CloudWatch logs analysis
- `run-all-tests.sh` - Master test runner

## Results

Test results are saved to `/tmp/`:
- `/tmp/login_response.json` - Authentication response
- `/tmp/scan_response.json` - Scan request response
- `/tmp/jwt_token.txt` - Current JWT token

## Notes

- Scripts are designed for zsh compatibility
- No complex quoting issues
- Clean, organized, and reusable
- Can be safely removed or kept for ongoing testing
