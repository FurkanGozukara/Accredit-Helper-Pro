import subprocess
import re
from collections import defaultdict

def run_git_command(command):
    """Run a git command and return the output"""
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout.strip()

def get_changed_files():
    """Get list of changed files since last commit"""
    return run_git_command("git diff --name-only").split('\n')

def get_file_changes(file_path):
    """Get the changes for a specific file"""
    return run_git_command(f"git diff {file_path}")

def analyze_changes():
    """Analyze git changes and extract new features/changes"""
    changed_files = get_changed_files()
    new_features = []
    changes = defaultdict(list)
    
    print(f"Changed files: {changed_files}")
    
    # Look for new features in code files
    for file_path in changed_files:
        if not file_path:
            continue
            
        if file_path.endswith(('.py', '.html', '.js')):
            diff = get_file_changes(file_path)
            
            # Look for added lines with function definitions or route definitions
            added_lines = [line[1:] for line in diff.split('\n') if line.startswith('+') and not line.startswith('+++')]
            
            for line in added_lines:
                # Check for new routes, functions, or features
                if 'def ' in line and not line.strip().startswith('#'):
                    function_name = line.split('def ')[1].split('(')[0].strip()
                    changes['New Functions'].append(f"{function_name} in {file_path}")
                
                if 'route(' in line:
                    route_path = re.search(r"route\(['\"](.+?)['\"]", line)
                    if route_path:
                        changes['New Routes'].append(f"{route_path.group(1)} in {file_path}")
                
                # Check for comments that might indicate new features
                if line.strip().startswith('# New feature:'):
                    feature = line.strip()[len('# New feature:'):].strip()
                    new_features.append(feature)
                
                # Look for significant UI changes
                if '<div' in line and 'class=' in line:
                    class_match = re.search(r"class=['\"](.+?)['\"]", line)
                    if class_match and 'new-feature' in class_match.group(1):
                        changes['UI Changes'].append(f"New UI element in {file_path}")
    
    # Look for untracked files that might indicate new features
    untracked_files = run_git_command("git ls-files --others --exclude-standard").split('\n')
    for file_path in untracked_files:
        if not file_path:
            continue
        changes['New Files'].append(file_path)
        
        # New templates likely indicate new features
        if file_path.startswith('templates/') and file_path.endswith('.html'):
            feature_name = file_path.replace('templates/', '').replace('.html', '').replace('/', ' - ')
            new_features.append(f"New page for {feature_name}")
    
    # Extract key changes and features
    key_changes = []
    for category, items in changes.items():
        if items:
            key_changes.append(f"{category}:")
            for item in items:
                key_changes.append(f"  - {item}")
    
    return {
        'new_features': new_features,
        'key_changes': key_changes,
        'changed_files': changed_files,
        'changes_by_category': dict(changes)
    }

def suggest_version_history_update():
    """Suggest content for version history update based on changes"""
    changes = analyze_changes()
    
    # Format version history entry
    version_history = [
        "Version 28.0 (April 2025):",
    ]
    
    # Add new features
    if changes['new_features']:
        version_history.append("- New features:")
        for feature in changes['new_features']:
            version_history.append(f"  * {feature}")
    
    # Add significant changes from each category
    for category, items in changes['changes_by_category'].items():
        if items and category not in ['New Files']:  # Skip listing all new files
            version_history.append(f"- {category}:")
            for item in items[:5]:  # Limit to 5 items per category
                version_history.append(f"  * {item}")
    
    # Add changed files summary
    file_categories = defaultdict(list)
    for file in changes['changed_files']:
        if not file:
            continue
        if file.endswith('.py'):
            file_categories['Python'].append(file)
        elif file.endswith('.html'):
            file_categories['Templates'].append(file)
        elif file.endswith('.js'):
            file_categories['JavaScript'].append(file)
        else:
            file_categories['Other'].append(file)
    
    version_history.append("- Updated files by category:")
    for category, files in file_categories.items():
        if files:
            version_history.append(f"  * {category}: {len(files)} files")
    
    return "\n".join(version_history)

def main():
    """Main function to run the analysis and print results"""
    print("Analyzing git changes...")
    changes = analyze_changes()
    
    print("\nNew Features:")
    for feature in changes['new_features']:
        print(f"- {feature}")
    
    print("\nKey Changes:")
    for change in changes['key_changes']:
        print(change)
    
    print("\nSuggested Version History Update:")
    print(suggest_version_history_update())

if __name__ == "__main__":
    main() 