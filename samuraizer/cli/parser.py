# samuraizer/cli/parser.py

import argparse
import os
from pathlib import Path
import logging
from zoneinfo import available_timezones
from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.backend.services.config_services import DEFAULT_MAX_FILE_SIZE_MB

# Initialize logging with default settings
setup_logging(verbose=False)
logger = logging.getLogger(__name__)

def get_default_cache_path() -> str:
    return str(Path.cwd() / ".cache")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Lists a repository into a JSON, YAML, XML, NDJSON, DOT, "
            "S-Expressions, MessagePack or CSV file."
        ),
        epilog=(
            "Examples:\\n"
            "  samuraizer /path/to/repo -o output.json\\n"
            "  samuraizer --exclude-folders build dist --include-binary --format yaml\\n"
            "  samuraizer /path/to/repo -o output.ndjson --format ndjson\\n"
            "  samuraizer /path/to/repo -o output.dot --format dot\\n"
            "  samuraizer /path/to/repo -o output.csv --format csv\\n"
            "  samuraizer /path/to/repo -o output.sexp --format sexp\\n"
            "  samuraizer /path/to/repo -o output.xml --format xml\\n"
            "  samuraizer /path/to/repo -o output.msgpack --format msgpack\\n"
            "  samuraizer /path/to/repo -o output.json --use-utc\\n"
            "  samuraizer /path/to/repo -o output.json --repository-timezone America/New_York\\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "root_directory",
        type=str,
        help="The root directory of the repository to be analyzed."
    )
    
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Path to the output file."
    )
    
    # Add timezone-related arguments
    parser.add_argument(
        "--use-utc",
        action="store_true",
        help="Use UTC for all timestamps (recommended for consistency)."
    )
    
    parser.add_argument(
        "--repository-timezone",
        type=str,
        choices=list(available_timezones()),
        help="Specify the repository's timezone (e.g., 'America/New_York', 'Asia/Shanghai')."
    )
    
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "yaml", "xml", "ndjson", "dot", "csv", "sexp", "msgpack"],
        default="json",
        help="Output file format (default: json).",
    )
    
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enables streaming mode for JSON output (automatically enabled for NDJSON and MessagePack).",
    )

    parser.add_argument(
        "--hash-algorithm",
        type=str,
        choices=["md5", "sha1", "sha256", "sha512"],
        default="md5",
        help="Hash algorithm for verification (default: md5)."
    )
    
    parser.add_argument(
        "--include-binary",
        action="store_true",
        help="Includes binary files and image files in the analysis."
    )
    
    parser.add_argument(
        "--exclude-folders",
        nargs='*',
        default=[],
        help="List of folder names to be excluded from the analysis."
    )
    
    parser.add_argument(
        "--exclude-files",
        nargs='*',
        default=[],
        help="List of file names to be excluded from the analysis."
    )
    
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follows symbolic links during traversal."
    )
    
    parser.add_argument(
        "--image-extensions",
        nargs='*',
        default=[],
        help="Additional image file extensions to be considered as binary."
    )
    
    parser.add_argument(
        "--exclude-patterns",
        nargs='*',
        default=[],
        help="Glob or regex patterns to exclude files and folders."
    )
    
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Number of threads for parallel processing (default: CPU cores * 2)."
    )
    
    parser.add_argument(
        "--encoding",
        type=str,
        default=None,
        help="Default encoding for text files (default: auto detection)."
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enables verbose logging."
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to the log file."
    )
    
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Disables hash verification."
    )
    
    parser.add_argument(
        "--max-size",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_MB,
        help=f"Maximum file size to read in MB (default: {DEFAULT_MAX_FILE_SIZE_MB})."
    )
    
    parser.add_argument(
        "--pool-size",
        type=int,
        default=5,
        help="Size of the database connection pool (default: 5)."
    )
    
    parser.add_argument(
        "--include-summary",
        action="store_true",
        help="Adds a summary of the analysis to the output file."
    )
    
    parser.add_argument(
        "--cache-path",
        type=str,
        default=get_default_cache_path(),
        help="Path to the cache directory (default: ./.cache)."
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable file caching (slower but uses less disk space)"
    )
    
    args = parser.parse_args()

    # Validate and fix output extension
    format_extensions = {
        "json": ".json",
        "yaml": ".yaml",
        "xml": ".xml",
        "ndjson": ".ndjson",
        "dot": ".dot",
        "csv": ".csv",
        "sexp": ".sexp",
        "msgpack": ".msgpack"
    }
    
    expected_extension = format_extensions[args.format]
    output_path = Path(args.output)
    
    if output_path.suffix.lower() != expected_extension:
        args.output = str(output_path.with_suffix(expected_extension))
        logger.info(f"Adjusted output filename to use correct extension: {args.output}")

    # Automatically enable streaming for NDJSON and MessagePack
    if args.format in ["ndjson", "msgpack"]:
        args.stream = True
        if args.format == "ndjson":
            logger.debug("Streaming automatically enabled for NDJSON format")
        else:
            logger.debug("Streaming automatically enabled for MessagePack format")

    # Validate streaming mode is only used with supported formats
    if args.stream and args.format not in ["json", "ndjson", "msgpack"]:
        parser.error("--stream is only available for JSON, NDJSON, and MessagePack formats.")

    # Handle timezone settings
    if args.use_utc and args.repository_timezone:
        parser.error("Cannot use both --use-utc and --repository-timezone")

    return args
