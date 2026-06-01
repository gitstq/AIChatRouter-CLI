#!/usr/bin/env python
"""Setup script for AIChatRouter-CLI."""

from setuptools import setup, find_packages

setup(
    name="aichatrouter-cli",
    version="1.0.0",
    description="Intelligent AI Chat Router CLI - Route queries to the best AI model automatically",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="AIChatRouter Team",
    author_email="team@aichatrouter.dev",
    license="MIT",
    url="https://github.com/aichatrouter/aichatrouter-cli",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pyyaml>=5.4",
        "requests>=2.26",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aichatrouter=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Utilities",
    ],
    keywords="ai, chat, router, cli, openai, anthropic, llm",
)
