import argparse
import logging
from typing import Optional

from samuraizer.backend.services.logging.logging_service import setup_logging
from samuraizer.config.timezone_config import TimezoneConfigManager

setup_logging(verbose=False)
logger = logging.getLogger(__name__)


HASH_ALGORITHMS = ["md5", "sha1", "sha256", "sha512", "xxhash"]
SUPPORTED_FORMATS = ["json", "yaml", "xml", "jsonl", "dot", "csv", "sexp", "msgpack"]


def parse_arguments(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(
        description=(
            "Lists a repository into a JSON, YAML, XML, JSONL, DOT, "
            "S-Expressions, MessagePack or CSV file."
        ),
        epilog=(
            "Examples:\n"
            "  samuraizer /path/to/repo -o output.json\n"
            "  samuraizer --exclude-folders build dist --include-binary --format yaml\n"
            "  samuraizer /path/to/repo -o output.jsonl --format jsonl\n"
            "  samuraizer /path/to/repo -o output.dot --format dot\n"
            "  samuraizer /path/to/repo -o output.csv --format csv\n"
            "  samuraizer /path/to/repo -o output.sexp --format sexp\n"
            "  samuraizer /path/to/repo -o output.xml --format xml\n"
            "  samuraizer /path/to/repo -o output.msgpack --format msgpack\n"
            "  samuraizer /path/to/repo -o output.json --use-utc\n"
            "  samuraizer /path/to/repo -o output.json --repository-timezone America/New_York\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("root_directory", type=str, nargs="?", help="Repository root directory")
    parser.add_argument("-o", "--output", type=str, help="Path to the output file.")

    # Configuration controls
    parser.add_argument("--config", type=str, default=None, help="Path to the configuration file")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Name of the configuration profile to use (default profile when omitted)",
    )
    parser.add_argument(
        "--config-validate",
        action="store_true",
        help="Validate the configuration file and exit.",
    )
    parser.add_argument(
        "--config-migrate",
        action="store_true",
        help="Attempt to migrate legacy configuration files into the unified format and exit.",
    )

    # Timezone
    timezone_config = TimezoneConfigManager()
    timezone_choices = timezone_config.list_timezones()

    parser.add_argument(
        "--use-utc",
        action="store_true",
        default=None,
        help="Use UTC for all timestamps (recommended for consistency).",
    )
    parser.add_argument(
        "--repository-timezone",
        type=str,
        choices=timezone_choices,
        default=None,
        help="Specify the repository's timezone (e.g., 'America/New_York').",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=SUPPORTED_FORMATS,
        default=None,
        help="Output file format.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        default=None,
        help="Enables streaming mode for supported formats.",
    )
    parser.add_argument(
        "--hash-algorithm",
        type=str,
        choices=HASH_ALGORITHMS,
        default=None,
        help="Hash algorithm for verification (default from configuration).",
    )
    parser.add_argument(
        "--include-binary",
        action="store_true",
        default=None,
        help="Includes binary files and image files in the analysis.",
    )
    parser.add_argument(
        "--exclude-folders",
        nargs="*",
        default=None,
        help="List of folder names to be excluded from the analysis.",
    )
    parser.add_argument(
        "--exclude-files",
        nargs="*",
        default=None,
        help="List of file names to be excluded from the analysis.",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        default=None,
        help="Follows symbolic links during traversal.",
    )
    parser.add_argument(
        "--image-extensions",
        nargs="*",
        default=None,
        help="Additional image file extensions to be considered as binary.",
    )
    parser.add_argument(
        "--exclude-patterns",
        nargs="*",
        default=None,
        help="Glob or regex patterns to exclude files and folders.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Number of threads for parallel processing (default from configuration).",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=None,
        help="Default encoding for text files (default from configuration).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enables verbose logging.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to the log file.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Disables hash verification.",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=None,
        help="Maximum file size to read in MB (default from configuration).",
    )
    parser.add_argument(
        "--pool-size",
        type=int,
        default=5,
        help="Size of the database connection pool (default: 5).",
    )
    parser.add_argument(
        "--include-summary",
        action="store_true",
        default=None,
        help="Adds a summary of the analysis to the output file.",
    )
    parser.add_argument(
        "--cache-path",
        type=str,
        default=None,
        help="Path to the cache directory (default from configuration).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable file caching (slower but uses less disk space)",
    )

    args = parser.parse_args(argv)

    if args.use_utc and args.repository_timezone:
        parser.error("Cannot use both --use-utc and --repository-timezone")

    if not args.config_validate and not args.config_migrate:
        if not args.root_directory:
            parser.error("root_directory is required unless running a configuration command.")
        if not args.output:
            parser.error("--output is required unless running a configuration command.")

    return args
