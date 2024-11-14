# samuraizer_gui/ui/widgets/results_display/graph_utils.py

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def check_graphviz_installation() -> bool:
    """Überprüft die Installation von Graphviz und ob es im PATH verfügbar ist."""
    try:
        path = os.environ.get('PATH', '')
        logger.debug(f"Aktueller PATH: {path}")
        
        # Übliche Installationspfade für Graphviz
        graphviz_paths = [
            r"C:\Program Files\Graphviz\bin",
            r"C:\Graphviz\bin",
        ]
        
        # Füge Graphviz zum PATH hinzu, wenn gefunden aber nicht bereits enthalten
        for graphviz_path in graphviz_paths:
            if os.path.exists(graphviz_path) and graphviz_path not in path:
                os.environ['PATH'] = graphviz_path + os.pathsep + path
                logger.debug(f"Graphviz-Pfad zum PATH hinzugefügt: {graphviz_path}")
                break
        
        # Versuche, die Version von dot auszuführen
        result = subprocess.run(['dot', '-V'], capture_output=True, text=True)
        logger.debug(f"Graphviz-Version: {result.stdout}")
        return True
            
    except FileNotFoundError:
        logger.error("dot ausführbare Datei nicht im PATH gefunden")
        return False
    except Exception as e:
        logger.error(f"Fehler bei der Überprüfung von Graphviz: {e}")
        return False
