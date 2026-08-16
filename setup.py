"""Setup script for Ship Date Engine."""
from __future__ import annotations

from pathlib import Path
from setuptools import find_packages, setup


def read_requirements(path: str) -> list[str]:
    """Read requirements from file."""
    req_path = Path(__file__).parent / path
    with open(req_path, "r") as f:
        return [line.strip() for line in f if line and not line.startswith("#")]


# Read long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="ship-date-engine",
    version="2.0.0",
    author="Kaytheon LLC",
    description="A shipping-date analysis tool with web UI and REST API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/khurr/Ship-Date-Engine",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.10",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=24.0.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
        "ai": [
            "boto3>=1.34.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ship-date-engine=ship_date_engine.cli:main",
            "sde=ship_date_engine.cli:main",
        ],
    },
)
