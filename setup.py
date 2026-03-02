#!/usr/bin/env python3
"""
SchemaDiff - SQL Schema Diff & Migration Generator
"""

from setuptools import setup, find_packages

setup(
    name="nevernet-sql-diff",
    version="0.1.0",
    author="NeverNet",
    author_email="contact@nevernet.com",
    description="SQL Schema Diff and Migration Generator",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/nevernet/SchemaDiff",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "sqlglat>=20.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nevernet-sql-diff=main:main",
        ],
    },
    include_package_data=True,
)
