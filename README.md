# Samuraizer 🗡️

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt-6.0%2B-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Samuraizer is a Python-based data analysis and processing tool with both command-line (CLI) and graphical (GUI) interfaces. It is designed to provide deep insights into local file systems and Git repositories, with fast, scalable processing powered by caching, streaming, and parallelism. The project emphasizes a modular architecture, allowing easy extension of analysis, output formats, and user interfaces.

Known caveat: there are a few minor bugs mentioned by maintainers; these are tracked and resolved as time allows.

## 🤖 What Samuraizer does

- Analyzes files from local folders or Git repositories
- Detects file types, encodings, and metadata
- Hash-based caching for fast re-analysis
- Streaming and non-streaming processing modes
- Output to a variety of structured formats
- GUI with visualizations and configuration options
- GitHub integration for repository cloning and analysis

## 🧭 Features

- Core Features
  - Multi-Interface Support: CLI and GUI
  - Advanced File Analysis: Smart type detection, encoding handling, and metadata extraction
  - Caching System: SQLite-based, with path management and optional disabling
  - Multi-threaded Processing: Parallel traversal and analysis
  - Signal Handling: Clean shutdown and resource cleanup
  - Initialization System: Robust startup/configuration

- GitHub Integration
  - Repository Management: Clone and analyze GitHub repositories
  - Authentication: Token-based access
  - Branch Selection: Per-repo branch control
  - Multi-Repository: Manage and analyze several repos
  - Progress Tracking: Real-time clone/analysis updates
  - URL Support: HTTPS and SSH
  - Error Recovery: Robust handling and recovery

- Output Formats
  - JSON, JSONL, YAML, XML, DOT (GraphViz), CSV, S-Expression, MessagePack
  - Format Validation and Robust Error Handling
  - Per-format configuration options

- GUI Features
  - Dark/Light Theme with persistent preferences
  - Interactive Visualizations: tree, graph, and network representations
  - Real-time Progress with ETA
  - Multi-tab analyses and configurable settings
  - Drag & Drop for file/folder input
  - Integrated GitHub repository browser

- Analysis Capabilities
  - File Type Detection (python-magic)
  - Encoding Detection and Handling
  - Size Analysis, Binary Detection, and Hash Computation (xxHash)
  - Metadata Extraction and Content Analysis
  - Binary and Text Processing
  - Symlink Handling (configurable)
  - Code Analysis and Problem Reporting

- Architecture Overview
  - Core Engine: Traversal, content analysis, caching, event handling
  - GUI Layer: PyQt6-based interface, visualizations, settings, progress
  - Analysis Pipeline: Type detection, processing, metadata, cache interaction
  - Output Generation: Format conversion, streaming, compression, export

## 🧰 Tech Stack

- Python 3.9+ (core logic, CLI, and scripting)
- PyQt6 (GUI)
- SQLite (cache)
- GraphViz (DOT output)
- xxHash (fast hashing)
- python-magic (file type detection)
- NetworkX / PyVis (visualizations)
- Colorama / tqdm (CLI UX)

## 🛠️ Installation

Prerequisites
- Python 3.9+ (virtual environments recommended)
- Qt 6 (for GUI)
- Graphviz (for DOT/visualization)

Windows:
- Install Python 3.9+
- Install Graphviz
- Install dependencies in a virtual environment

Linux/macOS:
- Install Python 3.9+
- Install Qt 6 and Graphviz
- Create and activate a virtual environment, then install dependencies

Installation Methods

1) Using pip (Recommended)
```bash
# Create and activate virtual environment
python -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

# Install the package
pip install samuraizer
```

2) From Source
```bash
# Clone repository
git clone https://github.com/luricodes/Samuraizer.git
cd Samuraizer

# Install dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt

# Install package in editable mode
pip install -e .
```

## 🚀 Quick Start

CLI mode
- Analyze a directory and output to a file
```bash
samuraizer /path/to/analyze -o output.json
```

- Choose a format
```bash
samuraizer /path/to/analyze -o output.yaml -f yaml
```

- Streaming mode for large datasets
```bash
samuraizer /path/to/analyze -o output.jsonl -f jsonl --stream
```

- Include binaries
```bash
samuraizer /path/to/analyze -o output.json --include-binary
```

- Advanced options
```bash
samuraizer /path/to/analyze -o output.json \
  --threads 8 \
  --max-size 100 \
  --follow-symlinks \
  --hash-algorithm xxhash \
  --encoding utf-8
```

GUI mode
- Launch GUI
```bash
samuraizer_gui
```

- The GUI offers file/folder selection, output settings, analysis configuration, real-time progress, and rich visualizations.
- The included usage GIF demonstrates drag-and-drop, graphs, and export workflows.

Note: The CLI and GUI share the same core analysis engine and output pipeline, but expose different configuration surfaces.

## 📐 Configuration

CLI Options (highlights)
- root_directory: Directory to analyze
- -o, --output: Output file path
- -f, --format: Output format (json|yaml|xml|jsonl|dot|csv|sexp|msgpack)
- --stream: Enable streaming mode
- --include-binary: Include binary files
- --exclude-folders, --exclude-files, --exclude-patterns: Exclusion controls
- --image-extensions: Additional image extensions
- --follow-symlinks: Follow symbolic links
- --threads: Number of processing threads
- --max-size: Maximum file size (MB)
- --encoding: Text encoding
- --hash-algorithm: Hash algorithm (default xxhash)
- --cache-path: Cache directory location
- --no-cache: Disable caching
- --verbose, --log-file: Logging controls

GUI Settings
- Theme (Dark/Light)
- Caching controls
- Performance: thread count, batch size
- Output format and compression
- Filters: exclusion patterns
- Visualization: graph display options

Unified configuration is stored in a single TOML file managed by the unified configuration manager.  
Default location: `~/.config/samurai/config.toml` on Linux/macOS or `%APPDATA%\samurai\config.toml` on Windows.  
Both CLI (`--config`, `--profile`) and GUI share this file, including support for configuration profiles.

Configuration File (TOML example)
```toml
config_version = "1.0"

[analysis]
default_format = "json"
max_file_size_mb = 50
threads = 4
follow_symlinks = false
include_binary = false
encoding = "auto"
cache_enabled = true
include_summary = true

[cache]
path = "~/.cache/samurai"
size_limit_mb = 1000
cleanup_days = 30

[exclusions.folders]
exclude = ["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]

[exclusions.patterns]
exclude = ["*.pyc", "test_*", "*.tmp", ".DS_Store", "Thumbs.db"]

[output]
compression = false
streaming = false
pretty_print = true

[theme]
name = "dark"

[timezone]
use_utc = false
```

Cache System
- SQLite-based cache in a .cache folder
- Path management, pooling, and automatic cleanup
- Optional disable via --no-cache

Visualization
- Tree, Graph, and Network views
- Interactive layouts, export options (DOT/SVG)

Advanced Features
- Streaming mode for memory-efficient processing
- Binary file handling with size limits
- Error recovery and partial result preservation

## 🏗️ Architecture and Data Flow

- Core Engine
  - Traversal and analysis of file trees
  - Cache management and invalidation
  - Event-driven architecture for status updates

- GUI Layer
  - PyQt6-based interface
  - Real-time progress, plots, and configuration panels

- Analysis Pipeline
  - File type detection (python-magic)
  - Encoding and binary handling
  - Metadata extraction and content analysis
  - Symlink handling and error reporting

- Output Generation
  - Format conversion and streaming
  - Output writers for multiple formats
  - Validation and compression controls

Data Flow Outline
1) User provides root_directory and options via CLI or GUI
2) Cache is initialized or connected (xxHash pathway)
3) Directory structure is traversed (or streamed) by traversal modules
4) Analysis pipeline extracts metadata, content, and structure
5) Output is formatted by OutputFactory into the chosen format
6) Results saved to disk with progress updates and error handling
7) Cleanup and resource finalization

## 🧪 Testing and Development

Development setup
- Install development dependencies
```bash
pip install -r requirements-dev.txt
```

Testing
```bash
pytest
```

Code quality
- Black, isort, mypy, flake8
```bash
black .
isort .
mypy .
flake8
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (git checkout -b feature/awesome-feature)
3. Implement changes
4. Run tests (pytest)
5. Commit with a descriptive message
6. Push and open a Pull Request

Development notes
- Follow the repository’s code style
- Add tests for new features
- Update documentation as needed

## 📝 License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See LICENSE for details.

## 🙏 Acknowledgments

Samuraizer leverages a number of open-source libraries:
- PyQt6, python-magic, charset-normalizer, xxhash, SQLite, GraphViz, NetworkX, PyVis, Colorama, tqdm

## 📫 Contact

- GitHub Issues: https://github.com/luricodes/Samuraizer/issues
- Email: info@lucasrichert.tech
