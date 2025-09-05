#!/bin/bash
echo "Fixing import statements across all Python files..."

# Fix imports in src directory
find src/ -name "*.py" -type f -exec sed -i '' 's/from api\./from chatbot_ai_system.api./g' {} +
find src/ -name "*.py" -type f -exec sed -i '' 's/from app\./from chatbot_ai_system.app./g' {} +
find src/ -name "*.py" -type f -exec sed -i '' 's/^import api$/import chatbot_ai_system.api as api/g' {} +
find src/ -name "*.py" -type f -exec sed -i '' 's/^import app$/import chatbot_ai_system.app as app/g' {} +

# Fix imports in tests directory
find tests/ -name "*.py" -type f -exec sed -i '' 's/from api\./from chatbot_ai_system.api./g' {} +
find tests/ -name "*.py" -type f -exec sed -i '' 's/from app\./from chatbot_ai_system.app./g' {} +
find tests/ -name "*.py" -type f -exec sed -i '' 's/^import api$/import chatbot_ai_system.api as api/g' {} +
find tests/ -name "*.py" -type f -exec sed -i '' 's/^import app$/import chatbot_ai_system.app as app/g' {} +

# Fix any remaining imports in root level Python files
find . -maxdepth 1 -name "*.py" -type f -exec sed -i '' 's/from api\./from chatbot_ai_system.api./g' {} +
find . -maxdepth 1 -name "*.py" -type f -exec sed -i '' 's/from app\./from chatbot_ai_system.app./g' {} +

echo "Import statements fixed"