import json
import logging
from typing import Any, Dict, Generator
import os
import uuid
from datetime import datetime
import re

from samuraizer.utils.time_utils import format_timestamp
from colorama import Fore, Style

def output_to_jsonl(
    data_generator: Generator[Dict[str, Any], None, None],
    output_file: str,
    config: Dict[str, Any] = None
) -> None:
    """
    Writes data to a JSONL file with enhanced LLM fine-tuning support.

    Args:
        data_generator (Generator[Dict[str, Any], None, None]): Generator producing data dictionaries.
        output_file (str): Path to the output JSONL file.
        config (Dict[str, Any], optional): Configuration dictionary.
            - remove_empty_fields (bool): Whether to remove fields with empty values. Defaults to True.
            - llm_finetuning (bool): Whether to format data for LLM fine-tuning. Defaults to False.
            - include_metadata (bool): Whether to include metadata fields. Defaults to False.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as out_file:
            for data in data_generator:
                if not isinstance(data, dict):
                    logging.error(
                        f"Unexpected data type: {type(data)}. Expected: dict. Data: {data}"
                    )
                    continue

                # Initialize JSON payload
                json_payload = {}

                if config and config.get('llm_finetuning', False):
                    # Extract and process code content
                    code = data.get("content", "")
                    language = data.get("type", "")
                    file_path = data.get("path", "")

                    if not code or not language:
                        logging.error(
                            f"Missing 'content' or 'type' for LLM fine-tuning. Data: {data}"
                        )
                        continue

                    # Enhanced code preprocessing for LLM training
                    code = preprocess_code(code, language)
                    
                    # Core training fields
                    json_payload = {
                        "code": code,
                        "path": file_path,
                        "language": language,
                        "tokens": estimate_tokens(code),  # Estimate token count for LLM context
                        "code_structure": extract_code_structure(code, language),  # Extract high-level code structure
                    }

                    # Include metadata if configured
                    if config.get('include_metadata', False):
                        json_payload.update({
                            "id": str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat() + 'Z',
                            "source": config.get("source", "samuraizer"),
                            "file_size": data.get("info", {}).get("size", 0),
                            "last_modified": format_timestamp(data.get("info", {}).get("modified")),
                            "permissions": data.get("info", {}).get("permissions", ""),
                            "hash": data.get("info", {}).get("file_hash", ""),
                            "context": extract_context(file_path)  # Extract context from file path
                        })

                elif "summary" in data:
                    # Write the summary as a separate JSON object
                    summary_data = data.get("summary")
                    if not isinstance(summary_data, dict):
                        logging.error(
                            f"Unexpected type for 'summary': {type(summary_data)}. Expected: dict."
                        )
                        continue
                    json_payload = {"summary": summary_data}
                else:
                    parent = data.get("parent", "")
                    filename = data.get("filename", "")
                    info = data.get("info", {})

                    if not isinstance(info, dict):
                        logging.error(
                            f"Unexpected type for 'info': {type(info)}. Expected: dict. Data: {info}"
                        )
                        continue

                    file_path = os.path.join(parent, filename) if parent else filename
                    file_path = file_path.replace(os.sep, '/')

                    # Create the JSON payload
                    json_payload = {
                        "path": file_path,
                        "type": info.get("type", ""),
                        "size": info.get("size", ""),
                        "created": format_timestamp(info.get("created")),
                        "modified": format_timestamp(info.get("modified")),
                        "permissions": info.get("permissions", ""),
                        "hash": info.get("file_hash", ""),
                        "content": info.get("content", "")
                    }

                # Remove empty fields if specified in config
                if config and config.get('remove_empty_fields', True):
                    json_payload = {k: v for k, v in json_payload.items() if v}

                try:
                    json_line = json.dumps(json_payload, ensure_ascii=False)
                    out_file.write(json_line + '\n')
                    logging.debug(f"Writing entry: {json_payload}")
                except (TypeError, ValueError) as json_err:
                    logging.error(
                        f"Error serializing JSON data: {json_err}. Data: {json_payload}"
                    )
            logging.info(f"JSONL output successfully written to '{output_file}'.")
    except IOError as io_err:
        logging.error(f"IO error while writing the JSONL output file: {io_err}")
    except Exception as e:
        logging.error(f"Unexpected error while writing the JSONL output file: {e}")

def preprocess_code(code: str, language: str) -> str:
    """
    Preprocess code for better LLM training quality.
    
    Args:
        code (str): The source code to preprocess
        language (str): The programming language
        
    Returns:
        str: Preprocessed code
    """
    if not code:
        return code
        
    # Remove excessive blank lines
    code = re.sub(r'\n\s*\n\s*\n', '\n\n', code)
    
    # Normalize line endings
    code = code.replace('\r\n', '\n')
    
    # Language-specific preprocessing
    if language.lower() in ['python', 'py']:
        # Remove Python bytecode comments
        code = re.sub(r'#.*?coding[:=]\s*([-\w.]+)', '', code)
    elif language.lower() in ['javascript', 'js', 'typescript', 'ts']:
        # Remove sourcemap comments
        code = re.sub(r'//[@#]\s*sourceMappingURL=.*$', '', code, flags=re.MULTILINE)
    
    return code.strip()

def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in the text.
    This is a simple estimation - actual token count may vary by model.
    
    Args:
        text (str): The text to estimate tokens for
        
    Returns:
        int: Estimated token count
    """
    # Simple estimation: ~4 characters per token on average
    return len(text) // 4

def extract_code_structure(code: str, language: str) -> Dict[str, Any]:
    """
    Extract high-level code structure information.
    
    Args:
        code (str): The source code
        language (str): The programming language
        
    Returns:
        Dict[str, Any]: Structure information
    """
    structure = {
        "imports": [],
        "functions": [],
        "classes": []
    }
    
    try:
        # Basic pattern matching for common structures
        if language.lower() in ['python', 'py']:
            # Find imports
            imports = re.findall(r'^(?:from\s+\S+\s+)?import\s+\S+', code, re.MULTILINE)
            structure["imports"] = [imp.strip() for imp in imports]
            
            # Find function definitions
            functions = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', code)
            structure["functions"] = functions
            
            # Find class definitions
            classes = re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]', code)
            structure["classes"] = classes
            
        elif language.lower() in ['javascript', 'js', 'typescript', 'ts']:
            # Find imports
            imports = re.findall(r'^(?:import|export)\s+.*?[;\n]', code, re.MULTILINE)
            structure["imports"] = [imp.strip() for imp in imports]
            
            # Find function definitions (including arrow functions)
            functions = re.findall(r'(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)|(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s+)?\(.*?\)\s*=>)', code)
            structure["functions"] = [f[0] or f[1] for f in functions if f[0] or f[1]]
            
            # Find class definitions
            classes = re.findall(r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)', code)
            structure["classes"] = classes
    except Exception as e:
        logging.error(f"Error extracting code structure: {e}")
    
    return structure

def extract_context(file_path: str) -> Dict[str, str]:
    """
    Extract contextual information from the file path.
    
    Args:
        file_path (str): The file path
        
    Returns:
        Dict[str, str]: Contextual information
    """
    parts = file_path.split('/')
    return {
        "filename": parts[-1] if parts else "",
        "directory": '/'.join(parts[:-1]) if len(parts) > 1 else "",
        "project_context": extract_project_context(parts)
    }

def extract_project_context(path_parts: list) -> str:
    """
    Extract project context from path parts.
    
    Args:
        path_parts (list): List of path components
        
    Returns:
        str: Project context description
    """
    context_indicators = {
        'src': 'source code',
        'test': 'test code',
        'lib': 'library code',
        'docs': 'documentation',
        'examples': 'example code',
        'utils': 'utility code',
        'core': 'core functionality',
        'components': 'component code',
        'models': 'data models',
        'controllers': 'controller logic',
        'views': 'view logic',
        'services': 'service logic',
        'api': 'API code',
        'config': 'configuration',
        'scripts': 'scripts',
        'vendor': 'third-party code'
    }
    
    for part in path_parts:
        part_lower = part.lower()
        if part_lower in context_indicators:
            return context_indicators[part_lower]
    
    return "general code"
