#!/usr/bin/env python3
"""
GitHub Good First Issue Finder

A tool to help open source beginners find suitable issues to contribute to.
Supports multiple languages, saves results to JSON/CSV, and provides detailed
issue information including repository health metrics.

Usage:
    python github_issue_finder.py --languages python javascript --output issues.json
    python github_issue_finder.py --languages cpp --stars-min 500 --limit 20
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from requests.exceptions import RequestException, ConnectionError, Timeout, TooManyRedirects
from tqdm import tqdm


class GitHubIssueFinder:
    """A tool to search for good-first-issues on GitHub"""
    
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "GoodFirstIssueFinder/1.0"
        })
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def search_issues(self, languages: List[str], stars_min: int = 100, 
                      limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for good-first-issues on GitHub
        
        Args:
            languages: List of programming languages to search for
            stars_min: Minimum repository stars (filter by popularity)
            limit: Maximum number of results to return
            
        Returns:
            List of issue dictionaries with detailed information
        """
        try:
            # Build language query
            language_query = ' '.join([f'language:{lang}' for lang in languages])
            
            # Build complete search query
            query = f'label:"good first issue" {language_query} state:open archived:false'
            
            params = {
                'q': query,
                'sort': 'updated',
                'order': 'desc',
                'per_page': min(limit, 100)
            }
            
            response = self.session.get(
                f"{self.base_url}/search/issues",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('items', [])
            
            # Filter and enrich issues
            enriched_issues = []
            for issue in tqdm(issues[:limit], desc="Analyzing issues"):
                enriched = self._enrich_issue(issue, stars_min)
                if enriched:
                    enriched_issues.append(enriched)
            
            return enriched_issues
            
        except Timeout:
            print('Error: The request timed out. Check your internet connection.')
        except ConnectionError:
            print('Error: Connection error! Please check your internet.')
        except TooManyRedirects:
            print('Error: Too many redirects.')
        except RequestException as err:
            print(f'Error: Request failed - {err}')
        except Exception as err:
            print(f'Error: Unexpected error - {err}')
        
        return []
    
    def _enrich_issue(self, issue: Dict[str, Any], stars_min: int) -> Optional[Dict[str, Any]]:
        """Enrich issue with additional repository information"""
        try:
            # Extract repository info
            repo_url = issue.get('repository_url', '')
            repo_name = repo_url.split('/')[-2] + '/' + repo_url.split('/')[-1] if repo_url else 'Unknown'
            
            # Get repository details (for stars count)
            if repo_url:
                repo_response = self.session.get(repo_url, timeout=10)
                if repo_response.status_code == 200:
                    repo_data = repo_response.json()
                    stars = repo_data.get('stargazers_count', 0)
                    
                    # Filter by minimum stars
                    if stars < stars_min:
                        return None
                else:
                    stars = 0
            else:
                stars = 0
            
            return {
                'repository': repo_name,
                'title': issue.get('title', 'No title'),
                'url': issue.get('html_url', ''),
                'stars': stars,
                'language': issue.get('repository', {}).get('language', 'Unknown'),
                'labels': [label.get('name', '') for label in issue.get('labels', [])],
                'created_at': issue.get('created_at', ''),
                'updated_at': issue.get('updated_at', ''),
                'comments_count': issue.get('comments', 0),
                'has_pull_request': 'pull_request' in issue
            }
            
        except Exception:
            return None
    
    def save_to_json(self, issues: List[Dict[str, Any]], filename: str) -> None:
        """Save issues to JSON file"""
        output = {
            'generated_at': datetime.now().isoformat(),
            'total_issues': len(issues),
            'issues': issues
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {len(issues)} issues to {filename}")
    
    def save_to_csv(self, issues: List[Dict[str, Any]], filename: str) -> None:
        """Save issues to CSV file"""
        if not issues:
            print("No issues to save")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=issues[0].keys())
            writer.writeheader()
            writer.writerows(issues)
        print(f"✓ Saved {len(issues)} issues to {filename}")
    
    def print_issues(self, issues: List[Dict[str, Any]]) -> None:
        """Pretty print issues to console"""
        if not issues:
            print("\n❌ No issues found. Try different languages or lower the stars threshold.")
            return
        
        print(f"\n{'='*60}")
        print(f"🔍 Found {len(issues)} good-first-issues")
        print(f"{'='*60}\n")
        
        for i, issue in enumerate(issues, 1):
            print(f"{i}. 📦 {issue['repository']}")
            print(f"   📝 {issue['title'][:80]}")
            print(f"   🔗 {issue['url']}")
            print(f"   ⭐ {issue['stars']:,} stars")
            print(f"   🏷️  Labels: {', '.join(issue['labels'][:3])}")
            print(f"   💬 Comments: {issue['comments_count']}")
            print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Find good-first-issues on GitHub for beginners',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --languages python --limit 10
  %(prog)s --languages cpp javascript --stars-min 500 --output issues.json
  %(prog)s --languages go --format csv --output beginner_issues.csv
        """
    )
    
    parser.add_argument(
        '--languages', '-l',
        required=True,
        nargs='+',
        help='Programming languages to search for (e.g., python cpp javascript)'
    )
    
    parser.add_argument(
        '--stars-min', '-s',
        type=int,
        default=100,
        help='Minimum repository stars (default: 100)'
    )
    
    parser.add_argument(
        '--limit', '-n',
        type=int,
        default=20,
        help='Maximum number of issues to return (default: 20)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='',
        help='Output filename (supports .json or .csv extension)'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'csv', 'console'],
        default='console',
        help='Output format (default: console)'
    )
    
    parser.add_argument(
        '--token', '-t',
        default=os.environ.get('GITHUB_TOKEN', ''),
        help='GitHub API token (or set GITHUB_TOKEN environment variable)'
    )
    
    args = parser.parse_args()
    
    # Create finder instance
    finder = GitHubIssueFinder(token=args.token)
    
    # Search for issues
    print(f"\n🔍 Searching for good-first-issues in: {', '.join(args.languages)}")
    print(f"⭐ Minimum stars: {args.stars_min}")
    print(f"📊 Maximum results: {args.limit}\n")
    
    issues = finder.search_issues(
        languages=args.languages,
        stars_min=args.stars_min,
        limit=args.limit
    )
    
    # Output results
    if args.output:
        if args.output.endswith('.json') or args.format == 'json':
            finder.save_to_json(issues, args.output)
        elif args.output.endswith('.csv') or args.format == 'csv':
            finder.save_to_csv(issues, args.output)
        else:
            finder.save_to_json(issues, args.output)
    
    if args.format == 'console' or not args.output:
        finder.print_issues(issues)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
