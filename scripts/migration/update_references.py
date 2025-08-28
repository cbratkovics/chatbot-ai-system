#!/usr/bin/env python3
"""Update all file references after reorganization"""

import re
from pathlib import Path


class ReferenceUpdater:
    def __init__(self):
        self.replacements = [
            # Docker compose files
            (r'(?<!config/docker/compose/)docker-compose\.yml', 'config/docker/compose/docker-compose.yml'),
            (r'(?<!config/docker/compose/)docker-compose\.test\.yml', 'config/docker/compose/docker-compose.test.yml'),
            (r'(?<!config/docker/compose/)docker-compose\.load\.yml', 'config/docker/compose/docker-compose.load.yml'),
            (r'(?<!config/docker/compose/)docker-compose\.tracing\.yml', 'config/docker/compose/docker-compose.tracing.yml'),
            
            # Dockerfile references
            (r'(?<!config/docker/dockerfiles/)Dockerfile\.multistage', 'config/docker/dockerfiles/Dockerfile.multistage'),
            
            # Requirements files
            (r'(?<!config/requirements/)requirements\.txt(?![a-z])', 'config/requirements/base.txt'),
            (r'(?<!config/requirements/)requirements-dev\.txt', 'config/requirements/dev.txt'),
            (r'(?<!config/requirements/)requirements-prod\.txt', 'config/requirements/prod.txt'),
            
            # Documentation - only update if not already in docs/
            (r'(?<!docs/architecture/)(?<!\/)ARCHITECTURE\.md', 'docs/architecture/ARCHITECTURE.md'),
            (r'(?<!docs/security/)(?<!\/)SECURITY\.md', 'docs/security/SECURITY.md'),
            (r'(?<!docs/performance/)(?<!\/)PERFORMANCE\.md', 'docs/performance/PERFORMANCE.md'),
            (r'(?<!docs/guides/)BRANCH_COMPARISON\.md', 'docs/guides/BRANCH_COMPARISON.md'),
            (r'(?<!docs/guides/)README_MAIN_BRANCH\.md', 'docs/guides/README_MAIN_BRANCH.md'),
            (r'(?<!docs/portfolio/)PORTFOLIO_SHOWCASE\.md', 'docs/portfolio/PORTFOLIO_SHOWCASE.md'),
            
            # Environment files
            (r'(?<!config/environments/)\.env\.example', 'config/environments/.env.example'),
            (r'(?<!config/environments/)render\.yaml', 'config/environments/render.yaml'),
            
            # Utility scripts
            (r'(?<!scripts/utils/)manage\.py', 'scripts/utils/manage.py'),
            (r'(?<!scripts/utils/)switch_version\.sh', 'scripts/utils/switch_version.sh'),
        ]
        
        self.updated_files = []
        
    def should_skip_file(self, filepath):
        """Check if file should be skipped"""
        skip_patterns = [
            '.git', 'node_modules', 'venv', '__pycache__', 
            '.pyc', '.pyo', '.pyd', '.so', '.egg',
            'main_branch_inventory.txt', 'update_references.py'
        ]
        return any(pattern in str(filepath) for pattern in skip_patterns)
        
    def update_file(self, filepath):
        """Update references in a single file"""
        if self.should_skip_file(filepath):
            return False
            
        try:
            with open(filepath, encoding='utf-8') as f:
                content = f.read()
            
            original = content
            changes_made = []
            
            for old, new in self.replacements:
                new_content = re.sub(old, new, content)
                if new_content != content:
                    changes_made.append(f"  {old} -> {new}")
                    content = new_content
            
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✓ Updated: {filepath}")
                for change in changes_made:
                    print(change)
                self.updated_files.append(str(filepath))
                return True
                
        except (UnicodeDecodeError, PermissionError):
            # Skip binary files and files without permission
            pass
        except Exception as e:
            print(f"Error updating {filepath}: {e}")
            
        return False
    
    def update_all(self):
        """Update references in all relevant files"""
        # File patterns to update
        patterns = ['*.yml', '*.yaml', '*.md', '*.sh', '*.py', 'Makefile', '*.json', '*.txt', '*.env*', '*.dockerfile', 'Dockerfile*']
        
        total_updated = 0
        
        print("Scanning for files to update...")
        for pattern in patterns:
            for filepath in Path('.').rglob(pattern):
                if self.update_file(filepath):
                    total_updated += 1
        
        print(f"\n📊 Summary: Updated {total_updated} files")
        return total_updated

if __name__ == "__main__":
    print("🔄 Starting reference update process...")
    print("=" * 50)
    
    updater = ReferenceUpdater()
    total = updater.update_all()
    
    print("=" * 50)
    if total > 0:
        print(f"✅ Successfully updated {total} files with new paths")
    else:
        print("ℹ️ No files needed updating")