# samuraizer/output/xml_output.py

import logging
import re
from typing import Any, Dict, Optional
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from colorama import Fore, Style

def sanitize_tag(tag: str) -> str:
    """
    Sanitizes a string to be used as an XML tag.
    """
    # Replace spaces and invalid characters with underscores
    tag = re.sub(r'\s+', '_', tag)
    tag = re.sub(r'[^\w\-\.]', '', tag)
    # Ensure the tag doesn't start with a number
    if re.match(r'^\d', tag):
        tag = f'item_{tag}'
    return tag

def dict_to_xml(parent: Element, data: Any) -> None:
    """
    Recursively converts a dictionary to XML elements, distinguishing between directories and files.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and 'type' in value:
                # File
                file_element = SubElement(parent, 'file', name=key)
                for file_key, file_value in value.items():
                    if file_key != 'name' and file_key != 'type':
                        child = SubElement(file_element, sanitize_tag(file_key))
                        if isinstance(file_value, dict) or isinstance(file_value, list):
                            dict_to_xml(child, file_value)
                        else:
                            child.text = str(file_value)
                    elif file_key == 'type':
                        child = SubElement(file_element, sanitize_tag(file_key))
                        child.text = str(file_value)
            elif isinstance(value, dict):
                # Directory
                dir_element = SubElement(parent, 'directory', name=key)
                dict_to_xml(dir_element, value)
            elif isinstance(value, list):
                # If a list is present, e.g., for multiple files or directories
                for item in value:
                    if isinstance(item, dict):
                        dict_to_xml(parent, item)
            else:
                # Other types can be added as text
                child = SubElement(parent, sanitize_tag(key))
                child.text = str(value)
    elif isinstance(data, list):
        for item in data:
            dict_to_xml(parent, item)
    else:
        parent.text = str(data)

def format_xml(element: Element, pretty_print: bool = True) -> str:
    """
    Returns an XML string for the Element, optionally pretty-printed.
    
    Args:
        element: The XML element to format
        pretty_print: Whether to pretty print the output
    """
    rough_string = tostring(element, 'utf-8')
    if pretty_print:
        try:
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        except Exception as e:
            logging.error(f"{Fore.RED}Error formatting XML: {e}{Style.RESET_ALL}")
            return rough_string.decode('utf-8')
    return rough_string.decode('utf-8')

def output_to_xml(
    data: Dict[str, Any],
    output_file: str,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Writes the data to an XML file with improved structure and readability.
    
    Args:
        data: The data to write
        output_file: The output file path
        config: Optional configuration dictionary containing formatting options
    """
    try:
        logging.debug(f"Starting XML conversion with data: {data}")
        root = Element('repository')
        dict_to_xml(root, data)

        pretty_print = config.get('pretty_print', True) if config else True
        xml_content = format_xml(root, pretty_print=pretty_print)
        logging.debug(f"XML structure after conversion: {xml_content[:200]}...")

        with open(output_file, 'w', encoding='utf-8') as xml_file:
            xml_file.write(xml_content)
        
        logging.info(f"XML output successfully written to '{output_file}'.")
    except Exception as e:
        logging.error(
            f"{Fore.RED}Error converting data to XML: {e}{Style.RESET_ALL}"
        )
