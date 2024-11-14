# samuraizer/core/summary.py

from typing import Any, Dict, Optional


def create_summary(
    structure: Dict[str, Any],
    summary: Dict[str, Any],
    include_summary: bool,
    hash_algorithm: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a summary of the directory structure.

    Args:
        structure (Dict[str, Any]): The directory structure.
        summary (Dict[str, Any]): The existing summary.
        include_summary (bool): Flag indicating whether to include the summary.
        hash_algorithm (Optional[str], optional): The hash algorithm used or None.

    Returns:
        Dict[str, Any]: The final data structure for output.
    """
    output_data: Dict[str, Any] = {}

    if include_summary and summary:
        output_data["summary"] = summary
        if hash_algorithm:
            output_data["hash_algorithm"] = hash_algorithm

    output_data["structure"] = structure

    return output_data
