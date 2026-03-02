#!/usr/bin/env python3
"""
SchemaDiff - SQL Schema Diff & Migration Generator
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="schemadiff",
    version="0.1.0",
    author="NeverNet",
    author_email="contact@nevernet.com",
    description="SQL Schema Diff and Migration Generator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nevernet/SchemaDiff",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Databases",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "schemadiff=migration.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "migration": ["SQL/*.sql"],
    },
)
