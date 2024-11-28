# samuraizer/output/output_factory.py

from typing import Callable, Dict, Any

from ..formatters.json.json_output import output_to_json, output_to_json_stream
from ..formatters.yaml.yaml_output import output_to_yaml
from ..formatters.xml.xml_output import output_to_xml
from ..formatters.jsonl.ndjson_output import output_to_ndjson
from ..formatters.dot.dot_output import output_to_dot
from ..formatters.csv.csv_output import output_to_csv
from ..formatters.sexp.s_expression_output import output_to_sexp
from ..formatters.msgpack.msgpack_output import output_to_msgpack, output_to_msgpack_stream

class OutputFactory:
    """
    Factory class for creating output methods based on the desired format.
    """
    # Define which formats support pretty printing
    _pretty_print_formats = {'json', 'xml'}
    
    # Define which formats support compression
    _compression_formats = {'msgpack'}
    
    _output_methods: Dict[str, Callable[..., None]] = {
        "json": output_to_json,
        "json_stream": output_to_json_stream,
        "yaml": output_to_yaml,
        "xml": output_to_xml,
        "jsonl": output_to_ndjson,
        "dot": output_to_dot,
        "csv": output_to_csv,
        "sexp": output_to_sexp,
        "msgpack": output_to_msgpack,
        "msgpack_stream": output_to_msgpack_stream,
    }

    @classmethod
    def get_output(cls, format: str, streaming: bool = False, config: Dict[str, Any] = None) -> Callable[..., None]:
        """
        Get the appropriate output function for the specified format.
        
        Args:
            format: The desired output format
            streaming: Whether to use streaming mode
            config: Optional configuration dictionary containing formatting options
        
        Returns:
            A callable that takes data and output_file parameters
        """
        try:
            # Create a new config dictionary for format-specific options
            format_config = {} if config is None else config.copy()
            
            # Only pass pretty_print config if format supports it
            if format not in cls._pretty_print_formats:
                format_config.pop('pretty_print', None)
                
            # Only pass use_compression config if format supports it
            if format not in cls._compression_formats:
                format_config.pop('use_compression', None)
            
            if streaming:
                if format == "json":
                    return lambda data, output_file: cls._output_methods["json_stream"](data, output_file, format_config)
                elif format == "msgpack":
                    return lambda data, output_file: cls._output_methods["msgpack_stream"](data, output_file, format_config)
            
            # Return a lambda that includes the config parameter
            return lambda data, output_file: cls._output_methods[format](data, output_file, format_config)
            
        except KeyError:
            available = ', '.join(sorted(set(k for k in cls._output_methods.keys() 
                                       if not k.endswith('_stream'))))
            raise ValueError(
                f"Unknown output format: {format}. Available formats are: {available}."
            )
