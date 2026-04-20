"""
Ombre SDK — setup.py
====================
Install via GitHub (no PyPI dependency):

    pip install git+https://github.com/Pypl0/Ombre.git

Or for a specific version:

    pip install git+https://github.com/ombre-ai/ombre-core.git@v1.0.0

Or from a local clone:

    git clone https://github.com/ombre-ai/ombre-core.git
    pip install ./ombre-core
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

try:
    with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "Ombre — The infrastructure layer that makes AI trustworthy."

version = {}
with open(os.path.join(here, "ombre", "__init__.py"), encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)
            break

setup(
    name="ombre-ai",
    version=version.get("__version__", "1.0.0"),
    description="The infrastructure layer that makes AI trustworthy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ombre Team",
    author_email="ombreaiq@gmail.com",
    url="https://github.com/ombre-ai/ombre-core",
    project_urls={
        "Documentation": "https://docs.ombre-ai.com",
        "Source": "https://github.com/ombre-ai/ombre-core",
        "Tracker": "https://github.com/ombre-ai/ombre-core/issues",
    },
    license="BUSL-1.1",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
    ],
    keywords=["ai", "llm", "openai", "anthropic", "groq", "hallucination", "audit", "compliance"],
    packages=find_packages(exclude=["tests*", "examples*", "docs*", "benchmarks*"]),
    python_requires=">=3.9",
    install_requires=[],  # Zero hard dependencies — customers bring their own providers
    extras_require={
        "openai": ["openai>=1.0.0"],
        "anthropic": ["anthropic>=0.20.0"],
        "groq": ["groq>=0.4.0"],
        "mistral": ["mistralai>=0.4.0"],
        "cohere": ["cohere>=5.0.0"],
        "all-providers": [
            "openai>=1.0.0",
            "anthropic>=0.20.0",
            "groq>=0.4.0",
            "mistralai>=0.4.0",
            "cohere>=5.0.0",
        ],
        "redis": ["redis>=5.0.0"],
        "postgres": ["psycopg2-binary>=2.9.0"],
        "server": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
            "ruff>=0.1.0",
            "httpx>=0.25.0",
        ],
        "full": [
            "openai>=1.0.0",
            "anthropic>=0.20.0",
            "groq>=0.4.0",
            "mistralai>=0.4.0",
            "cohere>=5.0.0",
            "redis>=5.0.0",
            "psycopg2-binary>=2.9.0",
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ombre=ombre.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
