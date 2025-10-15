# samuraizer_gui/ui/widgets/results_display/graph_result_view.py

import json
import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGraphicsView,
    QGraphicsScene, QApplication, QHBoxLayout, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QWheelEvent, QKeyEvent, QTransform

from ..utils.graph_processor import prepare_dot_content
from ..utils.graph_renderer import check_graphviz_installation
from ..utils.svg_renderer import load_svg_data, show_error

logger = logging.getLogger(__name__)

class ZoomableGraphicsView(QGraphicsView):
    """Custom QGraphicsView with zoom functionality"""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        
        # Enable antialiasing for smoother rendering
        self.setRenderHints(QPainter.RenderHint.Antialiasing | 
                           QPainter.RenderHint.SmoothPixmapTransform |
                           QPainter.RenderHint.TextAntialiasing)
        
        # Set viewport update mode
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        # Enable scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        # Set scene alignment
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Set drag mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # Set transformation anchor
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Initialize view state
        self.setInteractive(True)
        self.setEnabled(True)

    @property
    def zoom_factor(self):
        return self._zoom_factor

    @zoom_factor.setter
    def zoom_factor(self, value):
        self._zoom_factor = max(self.min_zoom, min(self.max_zoom, value))

    def initialize_view(self):
        """Initialize the view with proper transform"""
        # Reset any existing transform
        self.resetTransform()
        # Set initial transform
        self.setTransform(QTransform().scale(1.0, 1.0))
        self._zoom_factor = 1.0
        # Ensure the view is enabled and interactive
        self.setInteractive(True)
        self.setEnabled(True)
        # Update the viewport
        self.viewport().update()

    def wheelEvent(self, event: Optional[QWheelEvent]) -> None:
        """Handle mouse wheel events for zooming"""
        if event is None:
            super().wheelEvent(event)
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Calculate zoom factor
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor
            
            # Determine zoom direction
            if event.angleDelta().y() > 0:
                factor = zoom_in_factor
            else:
                factor = zoom_out_factor
            
            # Calculate new zoom
            new_zoom = self.zoom_factor * factor
            
            # Apply zoom if within limits
            if self.min_zoom <= new_zoom <= self.max_zoom:
                self.zoom_factor = new_zoom
                
                viewport = self.viewport()
                if viewport is None:
                    return

                # Store center point
                center_point = self.mapToScene(viewport.rect().center())

                # Apply new transform
                self.setTransform(QTransform().scale(self.zoom_factor, self.zoom_factor))

                # Restore center point
                new_center = self.mapToScene(viewport.rect().center())
                delta = new_center - center_point
                self.translate(delta.x(), delta.y())

                # Update the view
                viewport.update()

            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        """Handle keyboard shortcuts for zooming"""
        if event is None:
            super().keyPressEvent(event)
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus:
                self.zoom(1.15)
                event.accept()
            elif event.key() == Qt.Key.Key_Minus:
                self.zoom(1/1.15)
                event.accept()
            elif event.key() == Qt.Key.Key_0:
                self.reset_zoom()
                event.accept()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def zoom(self, factor: float):
        """Apply zoom by factor"""
        new_zoom = self.zoom_factor * factor
        if self.min_zoom <= new_zoom <= self.max_zoom:
            self.zoom_factor = new_zoom
            
            viewport = self.viewport()
            if viewport is None:
                return

            # Store center point
            center_point = self.mapToScene(viewport.rect().center())

            # Apply new transform
            self.setTransform(QTransform().scale(self.zoom_factor, self.zoom_factor))

            # Restore center point
            new_center = self.mapToScene(viewport.rect().center())
            delta = new_center - center_point
            self.translate(delta.x(), delta.y())

            viewport.update()

    def reset_zoom(self):
        """Reset zoom to original size"""
        viewport = self.viewport()
        if viewport is None:
            return

        # Store center point
        center_point = self.mapToScene(viewport.rect().center())

        # Reset transform and zoom factor
        self.zoom_factor = 1.0
        self.setTransform(QTransform().scale(1.0, 1.0))

        # Restore center point
        new_center = self.mapToScene(viewport.rect().center())
        delta = new_center - center_point
        self.translate(delta.x(), delta.y())

        # Ensure view is enabled and interactive
        self.setInteractive(True)
        self.setEnabled(True)

        viewport.update()

    def fit_in_view(self):
        """Fit scene in view"""
        scene = self.scene()
        if scene is None or scene.sceneRect().isEmpty():
            return

        # Store current anchor
        old_anchor = self.transformationAnchor()
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Reset transform first
        self.resetTransform()

        # Fit in view
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

        # Update zoom factor based on current transform
        self.zoom_factor = self.transform().m11()
        
        # Restore anchor
        self.setTransformationAnchor(old_anchor)
        
        # Ensure view is enabled and interactive
        self.setInteractive(True)
        self.setEnabled(True)
        
        self.viewport().update()

class GraphResultView(QWidget):
    """Graph view for displaying DOT format results"""
    
    def __init__(self, data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.results_data = data
        self.dot_content = None
        self.initUI()

    def initUI(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create traditional graph view
        self.traditional_view = QWidget()
        traditional_layout = QVBoxLayout(self.traditional_view)
        traditional_layout.setContentsMargins(5, 5, 5, 5)
        traditional_layout.setSpacing(5)
        
        # Add zoom controls
        zoom_controls = QFrame()
        zoom_controls.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        zoom_layout = QHBoxLayout(zoom_controls)
        zoom_layout.setContentsMargins(5, 5, 5, 5)
        zoom_layout.setSpacing(5)
        
        # Create zoom buttons with tooltips
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom In (Ctrl++)")
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setToolTip("Zoom Out (Ctrl+-)")
        reset_zoom_btn = QPushButton("Reset")
        reset_zoom_btn.setToolTip("Reset Zoom (Ctrl+0)")
        fit_view_btn = QPushButton("Fit")
        fit_view_btn.setToolTip("Fit to View")
        
        for btn in [zoom_in_btn, zoom_out_btn, reset_zoom_btn, fit_view_btn]:
            btn.setMaximumWidth(60)
            zoom_layout.addWidget(btn)
        
        zoom_layout.addStretch()
        traditional_layout.addWidget(zoom_controls)
        
        # Create scene and view
        self.scene = QGraphicsScene(self)
        self.view = ZoomableGraphicsView(self.scene)
        
        traditional_layout.addWidget(self.view)
        
        # Connect zoom buttons
        zoom_in_btn.clicked.connect(lambda: self.view.zoom(1.15))
        zoom_out_btn.clicked.connect(lambda: self.view.zoom(1/1.15))
        reset_zoom_btn.clicked.connect(self.view.reset_zoom)
        fit_view_btn.clicked.connect(self.view.fit_in_view)
        
        # Add traditional view to layout
        layout.addWidget(self.traditional_view)
        
        # Initialize view
        self.view.initialize_view()
        
        # Render visualization
        self.render_graph()

    def render_graph(self):
        """Render the DOT graph"""
        try:
            import graphviz
            
            # Check Graphviz installation first
            if not check_graphviz_installation():
                show_error(self.scene, self.view, 
                           "Graphviz ist nicht korrekt installiert oder nicht im PATH.\n"
                           "Bitte installiere Graphviz und füge es deinem System-PATH hinzu.")
                return
            
            # Generate DOT content
            try:
                self.dot_content = prepare_dot_content(self.results_data)
                logger.debug("DOT content successfully generated")
            except Exception as e:
                logger.error(f"Error generating DOT content: {e}", exc_info=True)
                show_error(self.scene, self.view, f"Error creating graph structure: {str(e)}")
                return
            
            try:
                # Create Source with explicit engine and get SVG directly
                graph = graphviz.Source(self.dot_content, engine='dot')
                svg_data = graph.pipe(format='svg').decode('utf-8')
                
                # Load SVG data directly
                load_svg_data(self.scene, self.view, svg_data)
                
            except graphviz.ExecutableNotFound as e:
                logger.error(f"Graphviz executable not found: {e}")
                show_error(self.scene, self.view, 
                           "Graphviz executable (dot) not found.\n"
                           "Please ensure Graphviz is installed and in your system PATH.")
            except Exception as e:
                logger.error(f"Error rendering graph: {e}", exc_info=True)
                show_error(self.scene, self.view, f"Error rendering graph: {str(e)}")
                    
        except ImportError as e:
            logger.error(f"Import error: {e}", exc_info=True)
            show_error(self.scene, self.view, "Required libraries not installed. Please install the graphviz package.")
        except Exception as e:
            logger.error(f"General error rendering graph: {e}", exc_info=True)
            show_error(self.scene, self.view, f"Error rendering graph: {str(e)}")

    def copy_selected(self):
        """Copy graph as text representation"""
        try:
            if isinstance(self.results_data, dict):
                text = json.dumps(self.results_data, indent=2)
            else:
                text = str(self.results_data)
            QApplication.clipboard().setText(text)
        except Exception as e:
            logger.error(f"Error copying graph: {e}", exc_info=True)

    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        # Only fit in view if zoom factor is close to 1 (not zoomed)
        if 0.9 <= self.view.zoom_factor <= 1.1:
            self.view.fit_in_view()
