from setuptools import setup, find_packages

# Basic platform-independent requirements
install_requires = [
    # Core analyzer requirements
    "colorama>=0.4.6",
    "dicttoxml>=1.7.16",
    "tqdm>=4.65.0",
    "charset-normalizer>=3.2.0",
    "msgpack>=1.0.5",
    "typing-extensions>=4.7.1",
    "pathspec>=0.11.2",
    "rich>=13.5.2",
    "click>=8.1.7",
    "jsonschema>=4.19.0",
    "tomli>=2.0.1",
    "xxhash>=3.5.0",
    "python-magic-bin>=0.4.14; platform_system == 'Windows'",
    "python-magic>=0.4.27; platform_system != 'Windows'",
    
    # GUI requirements
    "PyQt6>=6.4.0",
]

# Development dependencies
extras_require = {
    'dev': [
        'pytest>=7.4.0',
        'pytest-cov>=4.1.0',
        'black>=23.7.0',
        'isort>=5.12.0',
        'mypy>=1.4.1',
        'flake8>=6.1.0',
    ]
}

setup(
    name="samuraizer",
    version="1.0.0",
    author="Lucas Richert",
    license='GNU GPLv3',
    author_email="info@lucasrichert.tech",
    description="A versatile analysis and processing tool with GUI support",
    packages=find_packages(include=["samuraizer", "samuraizer.*"]),
    python_requires='>=3.9',
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "samuraizer=samuraizer.main:run",
            "samuraizer_gui=samuraizer.gui.main:main"
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.9",
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        "Operating System :: OS Independent",
        "Environment :: X11 Applications :: Qt",
    ],
)
