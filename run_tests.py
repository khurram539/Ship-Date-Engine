"""Run Ship Date Engine tests."""
from __future__ import annotations

import argparse
import subprocess
import sys


def run_pytest():
    """Run pytest with default configuration."""
    command = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
    
    print("Running tests...")
    result = subprocess.run(command)
    
    return result.returncode == 0


def run_linting():
    """Run flake8 linting."""
    try:
        import flake8
    except ImportError:
        print("flake8 not installed. Skipping lint check.")
        return True
    
    command = [sys.executable, "-m", "flake8", "ship_date_engine/", "tests/", "--max-line-length=120"]
    
    print("Running linter...")
    result = subprocess.run(command)
    
    return result.returncode == 0


def run_formatting_check():
    """Check if code is properly formatted with black."""
    try:
        import black
    except ImportError:
        print("black not installed. Skipping format check.")
        return True
    
    command = [sys.executable, "-m", "black", "--check", "ship_date_engine/", "tests/"]
    
    print("Running formatter check...")
    result = subprocess.run(command)
    
    return result.returncode == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Ship Date Engine tests and checks")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run all tests")
    test_parser.set_defaults(func=lambda: run_pytest())
    
    # Lint command
    lint_parser = subparsers.add_parser("lint", help="Run flake8 linting")
    lint_parser.set_defaults(func=lambda: run_linting())
    
    # Format check command
    fmt_parser = subparsers.add_parser("format", help="Check code formatting with black")
    fmt_parser.set_defaults(func=lambda: run_formatting_check())
    
    # All checks command
    all_parser = subparsers.add_parser("all", help="Run all checks (test, lint, format)")
    all_parser.set_defaults(func=lambda: None)
    
    args = parser.parse_args()
    
    if args.command == "all":
        print("=" * 60)
        print("Running ALL checks...")
        print("=" * 60)
        
        results = []
        tests_passed, status_msg = run_pytest(), "✅ Tests"
        if tests_passed:
            print(f"  {status_msg}: PASSED\n")
        else:
            print(f"  {status_msg}: FAILED\n")
            results.append(False)
        
        lints_passed, status_msg = run_linting(), "✅ Linting"
        if lints_passed:
            print(f"  {status_msg}: PASSED\n")
        else:
            print(f"  {status_msg}: FAILED\n")
            results.append(False)
        
        formats_passed, status_msg = run_formatting_check(), "✅ Formatting"
        if formats_passed:
            print(f"  {status_msg}: PASSED\n")
        else:
            print(f"  {status_msg}: FAILED\n")
            results.append(False)
        
        return all(results)
    else:
        success = args.func()
        exit(0 if success else 1)


if __name__ == "__main__":
    main()
