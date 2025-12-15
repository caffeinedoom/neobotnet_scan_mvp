#!/usr/bin/env python3
"""
Setup script for Web Reconnaissance Framework Backend.
"""
import os
import sys
import subprocess
from pathlib import Path


def run_command(command, check=True):
    """Run a shell command."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, check=check)
    return result.returncode == 0


def setup_environment():
    """Set up the development environment."""
    print("🚀 Setting up Web Reconnaissance Framework Backend...")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Not running in a virtual environment!")
        print("   Please activate your virtual environment first:")
        print("   source .venv/bin/activate")
        return False
    
    # Install dependencies
    print("\n📦 Installing dependencies...")
    if not run_command("pip install -r requirements.txt"):
        print("❌ Failed to install dependencies")
        return False
    
    print("\n✅ Setup completed successfully!")
    print("\n🔧 Next steps:")
    print("1. Copy backend/env.example to backend/.env and fill in your Supabase credentials")
    print("2. Run: python setup.py dev")
    
    return True


def run_dev_server():
    """Run the development server."""
    print("🌟 Starting development server...")
    
    # Check if .env file exists
    if not Path(".env.dev").exists():
        print("⚠️  .env file not found!")
        print("   Please create .env file with your configuration.")
        print("   See env.example for reference.")
        return False
    
    # Run the server
    run_command("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000", check=False)


def run_tests():
    """Run tests."""
    print("🧪 Running tests...")
    run_command("pytest -v", check=False)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python setup.py [setup|dev|test]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "setup":
        setup_environment()
    elif command == "dev":
        run_dev_server()
    elif command == "test":
        run_tests()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: setup, dev, test")
        sys.exit(1)


if __name__ == "__main__":
    main() 