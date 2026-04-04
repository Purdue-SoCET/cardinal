#!/bin/bash

# Script to set up development environment for GPU simulator
# This creates a virtual environment and installs packages in editable mode

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up GPU Simulator Development Environment${NC}"

# Define virtual environment directory
VENV_DIR="venv"

# Check if virtual environment already exists
if [ -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Virtual environment already exists at $VENV_DIR${NC}"
    read -p "Do you want to remove it and create a new one? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    else
        echo "Using existing virtual environment..."
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip

# Install gpu package (includes common) in editable mode
echo -e "${BLUE}Installing gpu package (includes common) in editable mode...${NC}"
pip install -e gpu/

# Install simulator package in editable mode
echo -e "${BLUE}Installing simulator package in editable mode...${NC}"
pip install -e gpu/simulator/

echo -e "${GREEN}✓ Development environment setup complete!${NC}"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate, run:"
echo "  deactivate"
