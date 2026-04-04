from setuptools import setup, find_packages

setup(
    name="gpu-simulator",
    version="0.1.0",
    description="GPU Cycle-Accurate Simulator",
    author="",
    author_email="",
    packages=["simulator"] + ["simulator." + pkg for pkg in find_packages(where="src")],
    package_dir={"simulator": "src"},
    install_requires=[
        "bitstring>=4.0.0",
        "pandas>=2.0.0",
        "aenum>=3.1.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            # Add any command-line scripts here if needed
        ],
    },
)
