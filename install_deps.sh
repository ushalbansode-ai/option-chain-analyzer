#!/bin/bash

# install_deps.sh
# Install dependencies for Option Chain Analyzer
# Run this script to install all required Python packages

echo "==========================================="
echo "📦 Option Chain Analyzer - Dependency Installer"
echo "==========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is installed
check_python() {
    print_status "Checking Python installation..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        print_success "Python found: $PYTHON_VERSION"
        return 0
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        print_success "Python found: $PYTHON_VERSION"
        return 0
    else
        print_error "Python is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
}

# Check if pip is installed
check_pip() {
    print_status "Checking pip installation..."
    if command -v pip3 &> /dev/null; then
        PIP_VERSION=$(pip3 --version 2>&1 | cut -d ' ' -f 2)
        print_success "pip found: version $PIP_VERSION"
        return 0
    elif command -v pip &> /dev/null; then
        PIP_VERSION=$(pip --version 2>&1 | cut -d ' ' -f 2)
        print_success "pip found: version $PIP_VERSION"
        return 0
    else
        print_error "pip is not installed. Please install pip."
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating Python virtual environment..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        if [ $? -eq 0 ]; then
            print_success "Virtual environment created successfully"
        else
            print_error "Failed to create virtual environment"
            exit 1
        fi
    else
        print_warning "Virtual environment already exists"
    fi
}

# Activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        print_success "Virtual environment activated"
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
        print_success "Virtual environment activated (Windows)"
    else
        print_error "Could not find virtual environment activation script"
        exit 1
    fi
}

# Upgrade pip
upgrade_pip() {
    print_status "Upgrading pip..."
    pip install --upgrade pip > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        PIP_VERSION=$(pip --version | cut -d ' ' -f 2)
        print_success "pip upgraded to version $PIP_VERSION"
    else
        print_warning "Failed to upgrade pip, but continuing..."
    fi
}

# Install dependencies from requirements.txt
install_requirements() {
    print_status "Installing dependencies from requirements.txt..."
    
    if [ -f "backend/requirements.txt" ]; then
        print_status "Found requirements.txt in backend directory"
        REQUIREMENTS_FILE="backend/requirements.txt"
    elif [ -f "requirements.txt" ]; then
        print_status "Found requirements.txt in root directory"
        REQUIREMENTS_FILE="requirements.txt"
    else
        print_error "requirements.txt not found!"
        echo "Creating a basic requirements.txt file..."
        cat > requirements.txt << 'EOF'
flask==2.3.3
flask-cors==4.0.0
requests==2.31.0
pandas==2.0.3
numpy==1.24.3
plotly==5.15.0
yfinance==0.2.18
websocket-client==1.6.1
apscheduler==3.10.1
python-dotenv==1.0.0
beautifulsoup4==4.12.2
lxml==4.9.3
EOF
        REQUIREMENTS_FILE="requirements.txt"
        print_success "Created basic requirements.txt"
    fi

    # Read and display requirements
    echo ""
    print_status "The following packages will be installed:"
    echo "----------------------------------------"
    cat $REQUIREMENTS_FILE
    echo "----------------------------------------"
    echo ""

    # Install requirements
    pip install -r $REQUIREMENTS_FILE
    
    if [ $? -eq 0 ]; then
        print_success "All dependencies installed successfully"
    else
        print_error "Failed to install some dependencies"
        echo "Trying alternative installation method..."
        pip install --no-cache-dir -r $REQUIREMENTS_FILE
        if [ $? -ne 0 ]; then
            print_error "Alternative installation also failed"
            print_warning "Some features might not work properly"
        fi
    fi
}

# Verify installations
verify_installations() {
    print_status "Verifying installations..."
    echo ""
    
    # List of packages to verify
    packages=("flask" "pandas" "requests" "plotly" "apscheduler")
    
    for package in "${packages[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            print_success "✓ $package imported successfully"
        else
            print_error "✗ $package failed to import"
        fi
    done
    
    # Additional checks for specific packages
    if python -c "import flask; print(f'  Flask version: {flask.__version__}')" 2>/dev/null; then
        :
    else
        print_warning "  Flask version check failed"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p logs
    mkdir -p data/historical
    mkdir -p data/cache
    print_success "Directories created: logs/, data/historical/, data/cache/"
}

# Set file permissions
set_permissions() {
    print_status "Setting file permissions..."
    if [ -f "backend/run.py" ]; then
        chmod +x backend/run.py
    fi
    if [ -f "backend/codespaces_app.py" ]; then
        chmod +x backend/codespaces_app.py
    fi
    if [ -f "start.sh" ]; then
        chmod +x start.sh
    fi
    print_success "File permissions set"
}

# Test NSE connectivity
test_connectivity() {
    print_status "Testing NSE website connectivity..."
    python3 -c "
import requests
import time
try:
    start_time = time.time()
    response = requests.get('https://www.nseindia.com', timeout=10)
    end_time = time.time()
    if response.status_code == 200:
        print('✅ NSE website is accessible (%.2f seconds)' % (end_time - start_time))
    else:
        print('⚠️  NSE website returned status code: %d' % response.status_code)
except Exception as e:
    print('❌ Cannot reach NSE website: %s' % e)
"
}

# Main installation function
main() {
    echo ""
    print_status "Starting dependency installation..."
    echo ""
    
    # Run all steps
    check_python
    check_pip
    create_venv
    activate_venv
    upgrade_pip
    install_requirements
    verify_installations
    create_directories
    set_permissions
    test_connectivity
    
    echo ""
    echo "==========================================="
    print_success "🎉 Dependency installation completed!"
    echo "==========================================="
    echo ""
    echo "📁 Project structure:"
    echo "   option-chain-analyzer/"
    echo "   ├── backend/           - Python backend"
    echo "   ├── frontend/          - Web dashboard"
    echo "   ├── venv/              - Virtual environment"
    echo "   ├── logs/              - Application logs"
    echo "   └── data/              - Data storage"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Activate virtual environment:"
    echo "      source venv/bin/activate"
    echo ""
    echo "   2. Start the application:"
    echo "      ./start.sh"
    echo "      OR"
    echo "      cd backend && python run.py"
    echo ""
    echo "   3. Access dashboard:"
    echo "      http://localhost:5000"
    echo ""
    echo "📖 For mobile access, check the README.md file"
    echo "==========================================="
}

# Run main function
main
