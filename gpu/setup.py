from setuptools import setup, find_packages

setup(
    name="gpu",
    version="0.1.0",
    description="GPU Simulator and Tools",
    author="",
    author_email="",
    packages=["gpu", "gpu.common"],
    package_dir={"gpu": "."},
    install_requires=[
        "bitstring>=4.0.0",
        "pandas>=2.0.0",
        "aenum>=3.1.0",
    ],
    python_requires=">=3.8",
)
