#!/usr/bin/env python3
"""
Version Changelog Generator for Accredit Helper Pro
Analyzes git commits and file changes to generate version changelog summaries
"""

import os
import subprocess
import sys
from datetime import datetime
from collections import defaultdict

def run_git_command(command):
    """Run a git command and return the output"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Git command failed: {command}")
            print(f"Error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error running git command: {e}")
        return None

def analyze_file_changes(from_commit, to_commit='HEAD'):
    """Analyze file changes between two commits"""
    print(f"Analyzing changes between {from_commit} and {to_commit}...")
    
    # Get list of changed files
    files_cmd = f"git diff {from_commit}..{to_commit} --name-only"
    changed_files = run_git_command(files_cmd)
    
    if not changed_files:
        print("No file changes found.")
        return {}
    
    files_list = changed_files.split('\n')
    
    # Get statistics
    stats_cmd = f"git diff {from_commit}..{to_commit} --stat"
    stats = run_git_command(stats_cmd)
    
    # Categorize changes
    categories = {
        'models': [],
        'routes': [],
        'templates': [],
        'migrations': [],
        'documentation': [],
        'tests': [],
        'static': [],
        'config': [],
        'other': []
    }
    
    for file_path in files_list:
        if not file_path:
            continue
            
        if file_path.startswith('models.py') or '/models.py' in file_path:
            categories['models'].append(file_path)
        elif file_path.startswith('routes/') or '/routes/' in file_path:
            categories['routes'].append(file_path)
        elif file_path.startswith('templates/') or '/templates/' in file_path:
            categories['templates'].append(file_path)
        elif file_path.startswith('migrations/') or '/migrations/' in file_path:
            categories['migrations'].append(file_path)
        elif file_path.endswith('.md') or file_path.endswith('.txt'):
            categories['documentation'].append(file_path)
        elif file_path.startswith('test_') or '/test_' in file_path:
            categories['tests'].append(file_path)
        elif file_path.startswith('static/') or '/static/' in file_path:
            categories['static'].append(file_path)
        elif file_path in ['requirements.txt', '.gitignore', 'config.py']:
            categories['config'].append(file_path)
        else:
            categories['other'].append(file_path)
    
    return {
        'files': files_list,
        'categories': categories,
        'stats': stats,
        'total_files': len(files_list)
    }

def analyze_commits(from_commit, to_commit='HEAD'):
    """Analyze commit messages between two commits"""
    print(f"Analyzing commits between {from_commit} and {to_commit}...")
    
    # Get commit messages
    commits_cmd = f"git log {from_commit}..{to_commit} --oneline"
    commits = run_git_command(commits_cmd)
    
    if not commits:
        print("No commits found.")
        return {}
    
    commit_list = commits.split('\n')
    
    return {
        'commits': commit_list,
        'total_commits': len(commit_list)
    }

def generate_changelog_summary(from_commit, version_number, to_commit='HEAD'):
    """Generate a comprehensive changelog summary"""
    print(f"\n{'='*60}")
    print(f"GENERATING CHANGELOG FOR VERSION {version_number}")
    print(f"{'='*60}")
    
    # Get current date
    current_date = datetime.now().strftime('%d %B %Y')
    
    # Analyze changes
    file_analysis = analyze_file_changes(from_commit, to_commit)
    commit_analysis = analyze_commits(from_commit, to_commit)
    
    if not file_analysis or not commit_analysis:
        print("Could not analyze changes. Exiting.")
        return None
    
    # Generate summary
    changelog = []
    changelog.append(f"<!-- Version {version_number} Changelog -->")
    changelog.append(f"<div class=\"card mb-4\">")
    changelog.append(f"    <div class=\"card-header bg-primary text-white\">")
    changelog.append(f"        <h5 class=\"mb-0\">Version {version_number} <small class=\"ms-2\">- {current_date}</small></h5>")
    changelog.append(f"    </div>")
    changelog.append(f"    <div class=\"card-body\">")
    changelog.append(f"        <h6 class=\"mb-3\">🚀 Major Updates and Improvements:</h6>")
    changelog.append(f"        <ul>")
    
    # Add major features based on file changes
    categories = file_analysis['categories']
    
    if categories['migrations']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>🛠️ Database Schema Updates:</strong>")
        changelog.append(f"                <ul>")
        for migration in categories['migrations']:
            changelog.append(f"                    <li>New migration: {migration}</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    if categories['models']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>📊 Data Model Enhancements:</strong>")
        changelog.append(f"                <ul>")
        changelog.append(f"                    <li>Updated database models and relationships</li>")
        changelog.append(f"                    <li>Enhanced data integrity and performance</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    if categories['routes']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>⚡ Backend Functionality Updates:</strong>")
        changelog.append(f"                <ul>")
        for route in categories['routes'][:3]:  # Show first 3 route files
            changelog.append(f"                    <li>Enhanced {route.replace('routes/', '').replace('.py', '')} functionality</li>")
        if len(categories['routes']) > 3:
            changelog.append(f"                    <li>And {len(categories['routes']) - 3} other backend improvements</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    if categories['templates']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>🎨 User Interface Improvements:</strong>")
        changelog.append(f"                <ul>")
        changelog.append(f"                    <li>Updated {len(categories['templates'])} template(s) with enhanced UI/UX</li>")
        changelog.append(f"                    <li>Improved responsive design and accessibility</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    if categories['documentation']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>📚 Documentation Updates:</strong>")
        changelog.append(f"                <ul>")
        for doc in categories['documentation']:
            changelog.append(f"                    <li>Updated {doc}</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    if categories['tests']:
        changelog.append(f"            <li>")
        changelog.append(f"                <strong>🧪 Testing Improvements:</strong>")
        changelog.append(f"                <ul>")
        changelog.append(f"                    <li>Added {len(categories['tests'])} new test(s)</li>")
        changelog.append(f"                    <li>Enhanced test coverage and reliability</li>")
        changelog.append(f"                </ul>")
        changelog.append(f"            </li>")
    
    changelog.append(f"        </ul>")
    
    # Add statistics
    changelog.append(f"        <div class=\"alert alert-info mt-3\">")
    changelog.append(f"            <strong>📈 Change Statistics:</strong> ")
    changelog.append(f"            {file_analysis['total_files']} files modified, ")
    changelog.append(f"            {commit_analysis['total_commits']} commits")
    changelog.append(f"        </div>")
    
    changelog.append(f"    </div>")
    changelog.append(f"</div>")
    
    return '\n'.join(changelog)

def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("Usage: python generate_version_changelog.py <from_commit> <version_number> [to_commit]")
        print("Example: python generate_version_changelog.py ece47aa24dab6d881ae02452994f8c4f41e95eb7 48")
        sys.exit(1)
    
    from_commit = sys.argv[1]
    version_number = sys.argv[2]
    to_commit = sys.argv[3] if len(sys.argv) > 3 else 'HEAD'
    
    # Verify we're in a git repository
    if not os.path.exists('.git'):
        print("Error: Not in a git repository")
        sys.exit(1)
    
    # Generate changelog
    changelog = generate_changelog_summary(from_commit, version_number, to_commit)
    
    if changelog:
        print(f"\n{'='*60}")
        print("GENERATED CHANGELOG HTML:")
        print(f"{'='*60}")
        print(changelog)
        
        # Save to file
        output_file = f"changelog_v{version_number}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(changelog)
        
        print(f"\n{'='*60}")
        print(f"Changelog saved to: {output_file}")
        print("You can copy this HTML into your help.html template.")
        print(f"{'='*60}")

if __name__ == "__main__":
    main() 