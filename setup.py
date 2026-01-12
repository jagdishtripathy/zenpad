from setuptools import setup, find_packages

setup(
    name="zenpad",
    version="1.4.1",
    description="A modern, lightweight text editor with features for coding and general use.",
    author="Zenpad Team",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "zenpad": ["themes/*.xml"],
    },
    entry_points={
        "console_scripts": [
            "zenpad=zenpad.main:main",
        ],
    },
    install_requires=[
        "PyGObject",
    ],
    data_files=[
        ("share/applications", ["data/zenpad.desktop"]),
    ],
)
