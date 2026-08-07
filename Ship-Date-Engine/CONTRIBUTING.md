# Ship Date Engine
# A Python shipping-date analysis tool

## Development Setup

### Prerequisites
- Python 3.10+ 
- pip >= 21.0

### Virtual Environment
```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install --upgrade pip
```

### Install Development Dependencies
```bash
# Core dependencies
pip install boto3
tweepapio (for Twitter API if needed)

# Development tools
pip install pytest
pip install pytest-cov  # Coverage reporting
pip install pyright  # Type checking
pip install black  # Code formatting
pip install flake8  # Linting
```

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=ship_date_engine --cov-report=html

# Run specific test file
pytest tests/test_engine.py -v

# Run slow tests only
pytest -m slow -v
```

### Type Checking
```bash
pyright ship_date_engine/
```

### Code Formatting
```bash
black ship_date_engine/ tests/
flake8 ship_date_engine/ tests/
```

## Security Guidelines

### File Upload Security
- Always validate file extensions against ALLOWED_EXTENSIONS
- Enforce MAX_UPLOAD_SIZE_MB limit
- Sanitize filenames using `sanitize_filename()`
- Prevent path traversal with `os.path.basename()`
- Use temporary directories that are cleaned up after use

### Input Validation
- Validate all user inputs against expected formats
- Use Pydantic models for structured data validation
- Check for SQL injection patterns in file content
- Sanitize HTML output to prevent XSS attacks

## API Endpoints (Web UI)

The web server provides the following endpoints:

- `GET /` - Main landing page
- `POST /upload` - Upload invoice files
- `POST /lookup/{shipping_id}` - Lookup by Shipping ID
- `POST /report/period` - Generate period-based reports

## Continuous Integration

CI/CD is configured via GitHub Actions (.github/workflows/ci.yml):

- ✅ Python version matrix testing
- ✅ All unit tests with coverage
- ✅ Type checking with pyright
- ✅ Security scanning for secrets
- ✅ Code formatting checks
