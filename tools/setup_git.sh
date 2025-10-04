#!/bin/bash
# Setup git repository and gitdoc for automatic commits

set -e

echo "🔧 Git and GitDoc Setup"
echo "======================="

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is not installed"
    echo "Please install git: sudo apt-get install git"
    exit 1
fi

echo "✅ Git is installed"

# Initialize git repository if not already initialized
if [ ! -d .git ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
else
    echo "✅ Git repository already exists"
fi

# Check if gitdoc is installed
GITDOC_CMD="gitdoc"
if ! command -v gitdoc &> /dev/null; then
    echo "📥 Installing gitdoc..."
    if sudo -n true 2>/dev/null; then
        sudo npm install -g gitdoc
    else
        echo "⚠️  Attempting local install (use 'sudo npm install -g gitdoc' for global install)..."
        npm install -g gitdoc --prefix ~/.local
        export PATH="$HOME/.local/bin:$PATH"
        GITDOC_CMD="$HOME/.local/bin/gitdoc"
    fi
    echo "✅ GitDoc installed"
else
    echo "✅ GitDoc already installed"
fi

# Check if gitdoc is running
if $GITDOC_CMD status &> /dev/null; then
    echo "✅ GitDoc is already running"
else
    echo "🚀 Enabling GitDoc for automatic commits..."
    $GITDOC_CMD enable
    echo "✅ GitDoc enabled"
fi

# Create initial commit if no commits exist
if ! git rev-parse HEAD &> /dev/null; then
    echo "📝 Creating initial commit..."
    git add .
    git commit -m "Initial commit - Python Docker development setup"
    echo "✅ Initial commit created"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "GitDoc is now watching this repository and will automatically commit changes."
echo "To check status: gitdoc status"
echo "To disable: gitdoc disable"
