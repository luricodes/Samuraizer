# samuraizer_gui/ui/widgets/results_display/svg_loader.py

import logging
from pathlib import Path
import tempfile
from io import BytesIO

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)

def load_svg_data(scene, view, svg_data: str):
    """
    Loads and displays SVG data directly in the given scene and view.
    
    Args:
        scene (QGraphicsScene): The scene where the SVG will be displayed.
        view (QGraphicsView): The view that displays the scene.
        svg_data (str): The SVG content as a string.
    """
    try:
        logger.debug("Loading SVG from data")
        
        # Clear existing elements
        scene.clear()
        
        # Convert SVG string data to bytes
        svg_bytes = QByteArray(svg_data.encode('utf-8'))
        
        # Create SVG renderer from bytes
        renderer = QSvgRenderer(svg_bytes)
        
        if not renderer.isValid():
            raise ValueError("Invalid SVG content")
        
        # Create SVG item with the renderer
        svg_item = QGraphicsSvgItem()
        svg_item.setSharedRenderer(renderer)
        
        # Add SVG item to scene
        scene.addItem(svg_item)
        
        # Set scene rect to SVG bounds
        scene.setSceneRect(svg_item.boundingRect())
        
        # Reset view transformation before fitting
        view.resetTransform()
        
        # Fit view to content
        view.fitInView(
            scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio
        )
        
        # Initialize zoom factor based on the current transform
        if hasattr(view, 'zoom_factor'):
            view.zoom_factor = view.transform().m11()
        
        logger.debug("SVG successfully loaded")
        
    except Exception as e:
        logger.error(f"Error loading SVG: {e}", exc_info=True)
        show_error(scene, view, f"Error loading graph: {str(e)}")

def load_svg(scene, view, svg_path: Path):
    """
    Loads and displays an SVG file in the given scene and view.
    
    Args:
        scene (QGraphicsScene): The scene where the SVG will be displayed.
        view (QGraphicsView): The view that displays the scene.
        svg_path (Path): The path to the SVG file.
    """
    try:
        logger.debug(f"Loading SVG from path: {svg_path}")
        
        if not svg_path.exists():
            raise FileNotFoundError(f"SVG file not found: {svg_path}")
        
        # Read SVG file content
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_data = f.read()
        
        # Use load_svg_data to handle the actual rendering
        load_svg_data(scene, view, svg_data)
        
    except Exception as e:
        logger.error(f"Error loading SVG file: {e}", exc_info=True)
        show_error(scene, view, f"Error loading graph: {str(e)}")

def show_error(scene, view, message: str):
    """
    Shows an error message in the scene and adjusts the view.
    
    Args:
        scene (QGraphicsScene): The scene where the error will be displayed.
        view (QGraphicsView): The view that displays the scene.
        message (str): The error message.
    """
    scene.clear()
    error_text = scene.addText(message)
    error_text.setDefaultTextColor(QColor(Qt.GlobalColor.red))
    # Ensure error message is visible
    scene.setSceneRect(error_text.boundingRect())
    # Reset view transformation before fitting
    view.resetTransform()
    view.fitInView(
        scene.sceneRect(),
        Qt.AspectRatioMode.KeepAspectRatio
    )
    # Initialize zoom factor if available
    if hasattr(view, 'zoom_factor'):
        view.zoom_factor = view.transform().m11()
