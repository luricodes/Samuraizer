import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import QWidget

from ...visualizations import JsonTreeView, TextResultView, GraphResultView

logger = logging.getLogger(__name__)

class ResultProcessor:
    def __init__(self):
        self.current_config = None

    def setConfiguration(self, config: Dict[str, Any]) -> None:
        if not config:
            logger.error("Attempted to set empty configuration")
            return
        
        try:
            if 'output' not in config:
                raise ValueError("Configuration missing 'output' section")
            if 'format' not in config['output']:
                raise ValueError("Output configuration missing 'format' field")
                
            self.current_config = config
            logger.debug("Configuration successfully set in ResultProcessor")
            
        except Exception as e:
            logger.error(f"Error setting configuration: {e}", exc_info=True)
            raise ValueError(f"Invalid configuration format: {str(e)}")

    def hasConfiguration(self) -> bool:
        return self.current_config is not None

    def getOutputFormat(self) -> str:
        try:
            if not self.current_config:
                logger.warning("No configuration available, using default format")
                return 'json'
                
            return self.current_config.get('output', {}).get('format', 'json').lower()
            
        except Exception as e:
            logger.error(f"Error getting output format: {e}", exc_info=True)
            return 'json'

    def createView(self, results: Dict[str, Any]) -> Optional[QWidget]:
        try:
            if not results:
                raise ValueError("No results provided to display")
            
            if not self.hasConfiguration():
                raise ValueError("No configuration available for creating result view")
            
            output_format = self.getOutputFormat()
            logger.debug(f"Creating result view with format: {output_format}")
            
            view: QWidget
            if output_format in ['json', 'yaml', 'messagepack']:
                view = JsonTreeView(results)
            elif output_format == 'dot':
                view = GraphResultView(results)
            else:
                view = TextResultView(results)
            
            view.results_data = results
            return view
            
        except Exception as e:
            logger.error(f"Error creating view: {e}", exc_info=True)
            return None