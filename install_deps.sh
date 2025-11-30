#!/bin/bash
# install_deps.sh - Install dependencies only

echo "📦 Installing dependencies..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt
    echo "✅ Dependencies installed successfully"
else
    echo "❌ requirements.txt not found"
    exit 1
fi

echo ""
echo "💡 Next steps:"
echo "   Run: ./start.sh to start the application"
