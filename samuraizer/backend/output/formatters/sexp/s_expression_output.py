# samuraizer/output/s_expression_output.py

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union, List
from pathlib import Path
import re
from colorama import Fore, Style

class SExpError(Exception):
    """Custom exception for S-expression related errors."""
    pass

# Standard property order for consistent output
PROPERTY_ORDER = [
    "type",
    "size",
    "encoding",
    "permissions",
    "created",
    "modified",
    "file_hash",
    "content"
]

# Properties that should always be quoted
QUOTED_PROPERTIES = {
    "type",
    "encoding",
    "content",
    "error"
}

def escape_string(s: str) -> str:
    """
    Properly escapes special characters in strings for S-expression format.
    
    Args:
        s (str): The input string to escape.
    
    Returns:
        str: The properly escaped string.
    """
    return (s.replace('\\', '\\\\')
             .replace('"', '\\"')
             .replace('\n', '\\n')
             .replace('\r', '\\r')
             .replace('\t', '\\t'))

def needs_quoting(value: Any, property_name: Optional[str] = None) -> bool:
    """
    Determines whether a value needs to be quoted in S-expression format.
    
    Args:
        value: The value to check.
        property_name: The name of the property (used for enforcing quoting rules).
    
    Returns:
        bool: True if the value needs quoting, False otherwise.
    """
    if property_name in QUOTED_PROPERTIES:
        return True
    
    if value is None:
        return False
    
    if isinstance(value, (int, float)):
        return False
    
    if isinstance(value, str):
        # Don't quote octal permissions
        if property_name == "permissions" and value.startswith("0o"):
            return False
        
        # Quote if contains special characters or could be confused with other types
        return (
            any(c in value for c in ' ()"\\\';{}[]|\n\t') or
            value.lower() in ('nil', 't') or
            bool(re.match(r'^[0-9+-.]+', value))
        )
    
    return True

def format_atom(value: Any, property_name: Optional[str] = None) -> str:
    """
    Formats atomic values according to strict S-expression conventions.
    
    Args:
        value: The value to format.
        property_name: The name of the property (used for quoting rules).
    
    Returns:
        str: The properly formatted S-expression atom.
    """
    if value is None:
        return "nil"
    
    if isinstance(value, bool):
        return "t" if value else "nil"
    
    if isinstance(value, (int, float)):
        if property_name in ("created", "modified"):
            return str(value)  # Keep full precision for timestamps
        return str(int(value)) if value.is_integer() else str(value)
    
    if isinstance(value, str):
        if not value:
            return '""'
        
        if property_name == "permissions" and value.startswith("0o"):
            return value  # Don't quote octal permissions
            
        if needs_quoting(value, property_name):
            return f'"{escape_string(value)}"'
        return value
    
    # For any other type, convert to string and quote
    return f'"{escape_string(str(value))}"'

def format_properties(properties: Dict[str, Any], indent: str = "") -> List[str]:
    """
    Formats a dictionary of properties in keyword-style S-expression format.
    
    Args:
        properties: Dictionary of property names and values.
        indent: Indentation string for formatting.
    
    Returns:
        List[str]: List of formatted property lines.
    """
    lines = []
    
    # Sort properties according to standard order, with remaining properties alphabetically
    def property_sort_key(item):
        try:
            return (PROPERTY_ORDER.index(item[0]), item[0])
        except ValueError:
            return (len(PROPERTY_ORDER), item[0])
    
    for key, value in sorted(properties.items(), key=property_sort_key):
        if value is not None:  # Skip None values
            prop_name = key.replace('_', '-')  # Convert to kebab-case
            formatted_value = format_atom(value, key)
            lines.append(f"{indent}:{prop_name} {formatted_value}")
    
    return lines

def format_file_entry(name: str, data: Dict[str, Any], indent: str = "", include_content: bool = True) -> str:
    """
    Formats a file entry in S-expression format.
    
    Args:
        name: File name.
        data: File metadata and content.
        indent: Indentation string.
        include_content: Whether to include file content in output.
    
    Returns:
        str: Formatted file entry.
    """
    result = [f"{indent}(file {format_atom(name, 'name')}"]
    
    # Filter out content if not included
    if not include_content:
        data = {k: v for k, v in data.items() if k != 'content'}
        
    properties = format_properties(data, indent + "  ")
    if properties:
        result.extend(properties)
    result.append(f"{indent})")
    
    return '\n'.join(result)

def format_directory(data: Dict[str, Any], indent: str = "", include_content: bool = True) -> str:
    """
    Formats a directory structure in S-expression format.
    
    Args:
        data: The directory structure to format.
        indent: Indentation string.
        include_content: Whether to include file content in output.
    
    Returns:
        str: Formatted directory structure.
    """
    result = []
    next_indent = indent + "  "
    
    for name, value in sorted(data.items()):
        if isinstance(value, dict):
            if "type" in value:  # File entry
                result.append(format_file_entry(name, value, next_indent, include_content))
            else:  # Directory entry
                result.append(f"{indent}(directory {format_atom(name, 'name')}")
                subdir = format_directory(value, next_indent, include_content)
                if subdir:
                    result.append(subdir)
                result.append(f"{indent})")
    
    return '\n'.join(result)

def format_summary(summary: Dict[str, Any], indent: str = "") -> str:
    """
    Formats the summary section in S-expression format.
    
    Args:
        summary: The summary data to format.
        indent: Indentation string.
    
    Returns:
        str: Formatted summary section.
    """
    next_indent = indent + "  "
    result = [f"{indent}(summary"]
    
    # Handle regular summary fields
    regular_fields = {k: v for k, v in summary.items() if k != "failed_files"}
    if regular_fields:
        result.extend(format_properties(regular_fields, next_indent))
    
    # Handle failed files separately
    if "failed_files" in summary and summary["failed_files"]:
        result.append(f"{next_indent}(failed-files")
        for file_info in summary["failed_files"]:
            result.append(f"{next_indent}  (failure")
            result.extend(format_properties({
                "path": file_info["file"],
                "error": file_info["error"]
            }, next_indent + "    "))
            result.append(f"{next_indent}  )")
        result.append(f"{next_indent})")
    
    result.append(f"{indent})")
    return '\n'.join(result)

def output_to_sexp(data: Dict[str, Any], output_file: str, config: Dict[str, Any] = None) -> None:
    """
    Writes repository structure data to a file in S-expression format.
    
    Args:
        data: The repository data to write.
        output_file: The path to the output file.
        config: Optional configuration dictionary containing formatting options.
            - include_content: Whether to include file content in output (default: True)
            - indent_size: Number of spaces for each indentation level (default: 2)
        
    Raises:
        SExpError: If there's an error during S-expression generation.
        IOError: If there's an error writing to the file.
    """
    if config is None:
        config = {}

    include_content = config.get('include_content', True)
    indent_size = config.get('indent_size', 2)
    base_indent = " " * indent_size

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Start the repository expression
            f.write("(repository\n")
            
            # Write structure
            f.write(f"{base_indent}(structure\n")
            structure = data.get("structure", data)
            formatted_structure = format_directory(structure, base_indent * 2, include_content)
            f.write(formatted_structure)
            f.write(f"\n{base_indent})\n")
            
            # Write summary if present
            if "summary" in data:
                formatted_summary = format_summary(data["summary"], base_indent)
                f.write(formatted_summary)
                f.write("\n")
            
            # Close repository expression
            f.write(")\n")
            
        logging.info(f"S-expression output successfully written to '{output_file}'")
        
    except IOError as e:
        error_msg = f"IO error while writing S-expression output: {e}"
        logging.error(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        raise SExpError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error while writing S-expression output: {e}"
        logging.error(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        raise SExpError(error_msg) from e
