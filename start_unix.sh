#!/usr/bin/env bash
echo "Starting EssaIDE Setup..."

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    echo "Please install Python 3.10 or newer."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and run
source venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo "Launching IDE..."
python main.py
