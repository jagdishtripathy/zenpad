from setuptools import setup, find_packages

setup(
    name="zenpad",
    version="1.5.0",
    description="A lightweight, keyboard-driven text editor for the Linux desktop",
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
