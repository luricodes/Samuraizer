# Samuraizer 🗡️

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt-6.0%2B-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A powerful Python-based analysis and processing tool with both command-line (CLI) and graphical (GUI) interfaces. Samuraizer provides comprehensive insights into your data structure, with advanced features for large-scale analysis and visualization. Samuraizer analyses files from local folder structures or Git repositories and saves them in structured data formats of your choice. With the help of an intelligent caching system and file validation using hashing, scans of any size are processed in seconds.

## 🌟 Features

### Core Features
- **Multi-Interface Support**: Both CLI and GUI interfaces for maximum flexibility
- **Advanced File Analysis**: Intelligent file type detection and content analysis
- **Caching System**: SQLite-based caching with automatic path management
- **Multi-threaded Processing**: Parallel processing for faster analysis
- **Smart File Handling**: Automatic encoding detection and binary file processing
- **Signal Handling**: Graceful shutdown and resource cleanup
- **Initialization System**: Robust application startup and configuration

### GitHub Integration
- **Repository Management**: Clone and analyze GitHub repositories
- **Authentication**: Secure token-based GitHub authentication
- **Branch Selection**: Support for selecting specific repository branches
- **Multi-Repository**: Manage and analyze multiple repositories
- **Progress Tracking**: Real-time clone and analysis progress
- **URL Support**: Both HTTPS and SSH repository URLs
- **Error Recovery**: Robust error handling and recovery

### LLM Features
- **Fine-tuning Support**: Enhanced code preprocessing for LLM training
- **Token Estimation**: Intelligent token count estimation
- **Code Structure Analysis**: Extract high-level code structures
- **Context Extraction**: Smart context derivation from file paths
- **Language Support**: Language-specific preprocessing
- **Metadata Enhancement**: Rich metadata for training
- **Code Pattern Recognition**: Advanced code pattern analysis

### Output Formats
- **JSON**: Standard hierarchical format with optional pretty printing
- **JSONL**: LLM-optimized format with code structure analysis
- **YAML**: Human-readable structured format with validation
- **XML**: Markup-based structured format
- **DOT**: GraphViz format for visual representation
- **CSV**: Tabular format for spreadsheet compatibility
- **S-Expression**: LISP-style structured format
- **MessagePack**: Compact binary format with compression
- **Format Validation**: Data validation for all output formats
- **Error Handling**: Robust error handling per format
- **Configuration**: Format-specific output options

### GUI Features
- **Dark/Light Theme**: Built-in theme switching support
- **Interactive Visualizations**: 
  - Structure visualization
  - SVG-based graph rendering
  - Interactive network graphs with real-time updates
  - Dynamic graph manipulation
  - Event-driven graph interactions
  - Custom graph layouts and styling
- **Real-time Progress**: Live progress tracking with ETA
- **Multi-tab Interface**: Multiple analyses in parallel
- **Configurable Settings**: Persistent user preferences
- **Drag & Drop**: File and folder drag-and-drop support
- **Repository Browser**: Integrated GitHub repository browser

### Analysis Capabilities
- **File Type Detection**: Using python-magic for accurate type identification
- **Encoding Detection**: Smart character encoding detection and handling
- **Size Analysis**: File and directory size analysis
- **Binary Detection**: Intelligent binary file handling with size limits
- **Hash Computation**: Fastest file validation with xxHash
- **Metadata Extraction**: Comprehensive file metadata analysis
- **Content Analysis**: Deep file content inspection and processing
- **Binary Processing**: Specialized binary file handling and analysis
- **Text Processing**: Advanced text file analysis with encoding detection
- **Symlink Handling**: Optional symbolic link following
- **Error Recovery**: Robust error handling and reporting
- **Code Analysis**: Advanced code structure and pattern analysis

## 🛠️ Installation

### Prerequisites
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.9 python3-pip python3-venv
sudo apt-get install qt6-base-dev qt6-webengine-dev
sudo apt-get install graphviz graphviz-dev

# macOS
brew install python@3.9
brew install qt@6
brew install graphviz

# Windows
# Install Python 3.9+ from python.org
# Install GraphViz from graphviz.org
```

### Installation Methods

#### 1. Using pip (Recommended)
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install the package
pip install samuraizer
```

#### 2. From Source
```bash
# Clone repository
git clone https://github.com/yourusername/samuraizer
cd samuraizer

# Install dependencies
pip install -r requirements.txt

# Development dependencies (optional)
pip install -r requirements-dev.txt

# Install package
pip install -e .
```

## 📊 Usage

### GUI Mode
```bash
# Launch GUI application
samuraizer_gui

# The GUI provides:
# - File/folder selection via browse or drag-drop
# - Output format selection
# - Analysis configuration
# - Real-time progress monitoring
# - Interactive visualizations
# - Results export
```

### CLI Mode
```bash
# Basic usage
samuraizer /path/to/analyze -o output.json

# Specify format
samuraizer /path/to/analyze -o output.yaml -f yaml

# Enable streaming for large datasets
samuraizer /path/to/analyze -o output.jsonl -f jsonl --stream --llm-finetuning

# Include binary files
samuraizer /path/to/analyze -o output.json --include-binary

# Custom exclusions
samuraizer /path/to/analyze -o output.json \
    --exclude-folders node_modules dist \
    --exclude-files "*.pyc" "*.log" \
    --exclude-patterns "test_*" "*.tmp"

# Advanced options
samuraizer /path/to/analyze -o output.json \
    --threads 8 \
    --max-size 100 \
    --follow-symlinks \
    --hash-algorithm xxhash \
    --encoding utf-8
```

## ⚙️ Configuration

### CLI Options
```
Arguments:
  root_directory           Directory to analyze

Options:
  -o, --output            Output file path
  -f, --format            Output format (json|yaml|xml|jsonl|dot|csv|sexp|msgpack)
  --stream                Enable streaming mode
  --include-binary        Include binary files
  --exclude-folders       Folders to exclude
  --exclude-files         Files to exclude
  --exclude-patterns      Glob/regex patterns to exclude
  --image-extensions      Additional image extensions
  --follow-symlinks       Follow symbolic links
  --threads               Number of processing threads
  --max-size             Maximum file size (MB)
  --encoding             Default text encoding
  --hash-algorithm       Hash algorithm xxhash
  --cache-path           Cache directory location
  --no-cache             Disable caching
  --verbose              Enable verbose logging
  --log-file            Log file path
```

### GUI Settings
- **Theme**: Dark/Light mode selection
- **Caching**: Enable/disable and configure caching
- **Performance**: Thread count and batch size
- **Output**: Format and compression options
- **Filters**: File/folder exclusion patterns
- **Visualization**: Graph and display options

### Configuration File
```yaml
# config.yaml
analysis:
  max_file_size: 50  # MB
  include_binary: false
  follow_symlinks: false
  thread_count: 4
  hash_algorithm: "xxhash"
  encoding: "auto"

filters:
  excluded_folders:
    - node_modules
    - .git
    - venv
  excluded_files:
    - "*.pyc"
    - "*.pyo"
    - ".DS_Store"
  exclude_patterns:
    - "test_*"
    - "*.tmp"

output:
  format: "json"
  streaming: false
  pretty_print: true
  include_summary: true
  use_compression: false
```

## 🔄 Cache System

The analyzer uses SQLite for caching to improve performance:

- **Location**: Default `.cache` directory in working directory
- **Strategy**: File hash and metadata-based caching
- **Pooling**: Connection pooling for concurrent access
- **Maintenance**: Automatic cleanup of outdated entries
- **Control**: Can be disabled via --no-cache flag

## 🎨 Visualization

The GUI provides multiple visualization options:

### Tree View
- Hierarchical structure visualization
- File metadata display
- Expandable/collapsible nodes
- Search and filter capabilities

### Graph View
- Interactive node-based visualization
- Zoom and pan controls
- Node filtering and highlighting
- Export to DOT/SVG formats

### Network View
- Force-directed graph layout
- Interactive node manipulation
- Relationship visualization
- Custom node styling

## 🔍 Advanced Features

### Streaming Mode
- Memory-efficient processing
- Real-time output generation
- Progress tracking
- Suitable for large datasets

### Binary File Handling
- Automatic binary detection
- Configurable size limits
- Optional base64 encoding
- Image file detection

### Error Recovery
- Graceful error handling
- Detailed error reporting
- Partial results preservation
- Recovery suggestions

## 🏗️ Architecture

### Components
1. **Core Engine**
   - File traversal
   - Content analysis
   - Cache management
   - Event handling

2. **GUI Layer**
   - PyQt6-based interface
   - Visualization components
   - Settings management
   - Progress tracking

3. **Analysis Pipeline**
   - File type detection
   - Content processing
   - Metadata extraction
   - Cache interaction

4. **Output Generation**
   - Format conversion
   - Stream processing
   - Compression handling
   - Export management

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Create Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Code formatting
black .
isort .

# Type checking
mypy .

# Linting
flake8
```

## 📝 License

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## 🙏 Acknowledgments

Built with these amazing libraries:
- PyQt6 - GUI framework
- python-magic - File type detection
- charset-normalizer - Encoding detection
- xxhash - Fast hashing
- SQLite - Caching system
- GraphViz - Graph visualization
- NetworkX - Graph processing
- PyVis - Interactive visualization
- Colorama - Terminal colors
- tqdm - Progress bars

## 📫 Contact

For questions and support:
- GitHub Issues: [Create an issue](https://github.com/yourusername/samuraizer/issues)
- Email: info@lucasrichert.tech
