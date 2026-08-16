from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent.resolve()


def read_requirements(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


setup(
    name="ship-date-engine",
    version="1.0.0",
    description="Ship Date Engine with REST API and validation utilities.",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "python-multipart>=0.0.9",
        *read_requirements(ROOT / "ship_date_engine" / "requirements.txt"),
    ],
)
