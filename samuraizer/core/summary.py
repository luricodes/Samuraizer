# samuraizer/core/summary.py

from typing import Any, Dict


def create_summary(
    structure: Dict[str, Any],
    summary: Dict[str, Any],
    include_summary: bool,
    hashing_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Creates a summary of the directory structure.

    Args:
        structure (Dict[str, Any]): The directory structure.
        summary (Dict[str, Any]): The existing summary.
        include_summary (bool): Flag indicating whether to include the summary.
        hashing_enabled (bool, optional): Whether hashing/caching was enabled.

    Returns:
        Dict[str, Any]: The final data structure for output.
    """
    output_data: Dict[str, Any] = {}

    if include_summary and summary:
        output_data["summary"] = summary
        if hashing_enabled:
            output_data["hash_algorithm"] = "xxhash"

    output_data["structure"] = structure

    return output_data
