from setuptools import setup
import os

# Read the contents of the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="essaide",
    version="1.0.0",
    author="Jeswin Sunny",
    author_email="jeswin@example.com",
    description="A powerful, highly-optimized terminal IDE built with Textual.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["main", "lsp_client", "pdb_client"],
    install_requires=[
        "textual[syntax]>=0.81.0",
        "rich==13.7.1",
        "requests==2.32.3",
        "python-lsp-server>=1.11.0",
        "black>=24.0.0"
    ],
    entry_points={
        "console_scripts": [
            "essa-ide=main:run",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Build Tools",
        "Environment :: Console",
    ],
    python_requires=">=3.10",
)
