#!/bin/bash
# Quick setup script for LangFlow + watsonx Orchestrate RAG tutorial

set -e  # Exit on error

echo "🚀 Setting up LangFlow + watsonx Orchestrate RAG Tutorial"
echo ""

# Check Python version
echo "1️⃣  Checking Python version..."
python3 --version || { echo "❌ Python 3 not found. Please install Python 3.11+"; exit 1; }
echo "✅ Python found"
echo ""

# Create virtual environment
echo "2️⃣  Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "⚠️  Virtual environment already exists. Skipping..."
else
    python3 -m venv .venv
    echo "✅ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "3️⃣  Activating virtual environment..."
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "4️⃣  Upgrading pip..."
pip install --upgrade pip --quiet
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "5️⃣  Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "✅ All dependencies installed"
echo ""

# Check Docker
echo "6️⃣  Checking Docker..."
docker --version || { echo "⚠️  Docker not found. Please install Docker Desktop"; }
echo ""

# Copy .env if needed
echo "7️⃣  Setting up environment variables..."
if [ -f ".env" ]; then
    echo "⚠️  .env file already exists. Skipping..."
else
    cp .env.example .env
    echo "✅ .env file created from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and add your API credentials!"
    echo "   Either:"
    echo "   - WATSONX_API_KEY + WATSONX_PROJECT_ID"
    echo "   - OPENAI_API_KEY"
fi
echo ""

# Start Docker containers
echo "8️⃣  Starting pgvector database..."
if docker ps | grep -q rag-pgvector; then
    echo "⚠️  pgvector container already running. Skipping..."
else
    docker-compose up -d
    echo "✅ pgvector database started"
fi
echo ""

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env file with your API credentials:"
echo "      nano .env  # or use your preferred editor"
echo "   2. Activate venv (if not already active):"
echo "      source .venv/bin/activate"
echo "   3. Load sample documents:"
echo "      python scripts/load-documents.py"
echo "   4. Follow the complete tutorial:"
echo "      open docs/tutorial.md"
echo ""
echo "Need help? See docs/TROUBLESHOOTING.md"
