from setuptools import setup, find_packages
from pathlib import Path

readme = Path(__file__).parent / "README.md"
long_desc = readme.read_text(encoding="utf-8") if readme.exists() else ""

setup(
    name="prompt-forge",
    version="1.0.0",
    description="Raw text → god-mode prompt compiler. No LLM API required.",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="AwZ",
    python_requires=">=3.8",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    package_data={
        "": ["../data/*.json", "../data/*.yaml"],
    },
    install_requires=[
        "requests>=2.28",
        "beautifulsoup4>=4.11",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "forge=forge:main",
        ],
    },
    py_modules=["forge"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
    ],
)
