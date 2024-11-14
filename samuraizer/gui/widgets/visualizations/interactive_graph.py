# samuraizer/GUI/ui/widgets/interactive_graph.py

import os
import tempfile
from typing import Optional
import logging
from pathlib import Path
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal
from pyvis.network import Network
import networkx as nx
from pydot import graph_from_dot_data
import threading
import shutil
import re

logger = logging.getLogger(__name__)

class InteractiveGraphWidget(QWidget):
    """Widget for displaying interactive graph visualizations using PyVis."""
    
    # Signal to update the UI from the worker thread
    process_complete = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_file: Optional[str] = None
        self.network = None
        self.setup_ui()
        
        # Connect signal to slot
        self.process_complete.connect(self._handle_process_complete)
        
    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Create progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Create web view for PyVis
        self.web_view = QWebEngineView()
        self.web_view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.web_view)
        
        self.setLayout(layout)

    def _on_load_finished(self, success: bool):
        """Handle web view load completion."""
        if success:
            self.status_label.setText("Graph loaded successfully")
            self.progress_bar.hide()
            logger.debug("Graph visualization loaded successfully")
        else:
            self.status_label.setText("Failed to load graph visualization")
            logger.error("Failed to load graph visualization")

    def _handle_process_complete(self, success: bool, message: str):
        """Handle completion of graph processing."""
        if success:
            if self.temp_file and os.path.exists(self.temp_file):
                logger.debug(f"Loading graph from {self.temp_file}")
                self.web_view.setUrl(QUrl.fromLocalFile(self.temp_file))
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(100)
            else:
                self.status_label.setText("Error: Graph file not generated")
                logger.error("Graph file not generated")
        else:
            self.status_label.setText(f"Error: {message}")
            self.progress_bar.hide()
            logger.error(f"Graph processing failed: {message}")

    def display_graph(self, dot_data: str):
        """
        Convert DOT data to interactive PyVis visualization.
        
        Args:
            dot_data (str): Graph data in DOT format
        """
        try:
            logger.debug("Starting graph processing")
            self.status_label.setText("Processing graph data...")
            self.progress_bar.setMaximum(0)  # Indeterminate progress
            self.progress_bar.show()
            
            # Start processing in a separate thread
            processing_thread = threading.Thread(
                target=self._process_graph,
                args=(dot_data,),
                daemon=True
            )
            processing_thread.start()
            
        except Exception as e:
            error_msg = f"Error initializing graph display: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.process_complete.emit(False, error_msg)

    def _create_network_init(self, nodes_data: str, edges_data: str, options_data: str) -> str:
        """Create network initialization script."""
        return f"""
            if (typeof vis === 'undefined') {{
                console.error('vis.js not loaded');
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Required libraries not loaded. Please check your internet connection.';
                return;
            }}
            
            try {{
                console.log('Creating network...');
                
                // Hide loading indicator
                document.getElementById('loading').style.display = 'none';
                
                // Initialize network data
                var nodes = new vis.DataSet({nodes_data});
                var edges = new vis.DataSet({edges_data});
                var container = document.getElementById('mynetwork');
                var data = {{
                    nodes: nodes,
                    edges: edges
                }};
                var options = {options_data};
                
                // Create network in global scope
                window.network = new vis.Network(container, data, options);
                
                // Log network creation
                console.log('Network initialized');
                
                // Handle network events
                network.once('stabilizationIterationsDone', function() {{
                    console.log('Network stabilized');
                    var event = new Event('networkReady');
                    document.dispatchEvent(event);
                }});
                
                network.on('error', function(err) {{
                    console.error('Network error:', err);
                    document.getElementById('error').style.display = 'block';
                    document.getElementById('error').textContent = 'Network error: ' + err.message;
                }});
            }} catch (error) {{
                console.error('Failed to initialize network:', error);
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Failed to initialize network: ' + error.message;
            }}
        """

    def _process_graph(self, dot_data: str):
        """Process graph data in a separate thread."""
        try:
            logger.debug("Converting DOT to NetworkX")
            # Parse DOT data
            dot_graphs = graph_from_dot_data(dot_data)
            if not dot_graphs:
                raise ValueError("No graph found in DOT data")
            
            dot_graph = dot_graphs[0]
            
            # Convert to NetworkX
            nx_graph = nx.nx_pydot.from_pydot(dot_graph)
            
            # Create PyVis network with optimized settings for large graphs
            net = Network(
                height="100%",
                width="100%",
                bgcolor="#ffffff",
                font_color="#000000",
                directed=True,
                neighborhood_highlight=True,
                select_menu=True,
                filter_menu=True
            )
            
            # Add nodes with optimized settings
            logger.debug(f"Processing {len(nx_graph.nodes)} nodes")
            for node in nx_graph.nodes():
                # Get node attributes
                attrs = nx_graph.nodes[node]
                
                # Extract label and other attributes from DOT
                label = attrs.get('label', str(node))
                color = attrs.get('fillcolor', '#97C2FC')
                border_color = attrs.get('color', '#2B7CE9')
                shape = attrs.get('shape', 'dot')
                
                # Add node to network with performance optimizations
                net.add_node(
                    node,
                    label=label,
                    color={
                        'background': color,
                        'border': border_color,
                        'highlight': {
                            'background': '#FFD700',
                            'border': '#FFA500'
                        }
                    },
                    shape=shape,
                    size=20,  # Smaller default size
                    borderWidth=1,  # Thinner borders
                    borderWidthSelected=2,
                    font={'size': 12},  # Smaller font
                    title=attrs.get('tooltip', label)
                )
            
            # Add edges with performance optimizations
            logger.debug(f"Processing {len(nx_graph.edges)} edges")
            for edge in nx_graph.edges():
                net.add_edge(
                    edge[0],
                    edge[1],
                    color={'color': '#848484', 'highlight': '#FB7E81'},
                    width=1,  # Thinner edges
                    arrowStrikethrough=False,
                    smooth={'type': 'continuous', 'roundness': 0.2}  # More efficient edge rendering
                )
            
            # Configure options optimized for large graphs
            net.set_options("""
            {
                "nodes": {
                    "shadow": false,
                    "shape": "dot",
                    "scaling": {
                        "min": 10,
                        "max": 30,
                        "label": {
                            "enabled": true,
                            "min": 8,
                            "max": 20
                        }
                    }
                },
                "edges": {
                    "shadow": false,
                    "smooth": {
                        "type": "continuous",
                        "roundness": 0.2
                    },
                    "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}}
                },
                "physics": {
                    "enabled": true,
                    "forceAtlas2Based": {
                        "gravitationalConstant": -50,
                        "centralGravity": 0.01,
                        "springLength": 100,
                        "springConstant": 0.08,
                        "damping": 0.4,
                        "avoidOverlap": 0
                    },
                    "solver": "forceAtlas2Based",
                    "stabilization": {
                        "enabled": true,
                        "iterations": 1000,
                        "updateInterval": 50,
                        "fit": true
                    },
                    "adaptiveTimestep": true,
                    "minVelocity": 0.75
                },
                "interaction": {
                    "hover": true,
                    "tooltipDelay": 200,
                    "hideEdgesOnDrag": true,
                    "multiselect": true,
                    "keyboard": {
                        "enabled": true,
                        "speed": {"x": 10, "y": 10, "zoom": 0.02},
                        "bindToWindow": false
                    },
                    "navigationButtons": true,
                    "zoomView": true
                },
                "configure": {
                    "enabled": true,
                    "filter": ["physics", "nodes", "edges"],
                    "showButton": true
                }
            }
            """)
            
            # Generate network data
            nodes_data = json.dumps([node for node in net.nodes])
            edges_data = json.dumps([edge for edge in net.edges])
            options_data = net.options
            
            # Create network initialization script
            network_init = self._create_network_init(nodes_data, edges_data, options_data)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w+', encoding='utf-8') as f:
                self.temp_file = f.name
                logger.debug(f"Saving graph to temporary file: {f.name}")
                
                # Get the template path
                template_path = os.path.join(os.path.dirname(__file__), 'templates', 'graph_template.html')
                
                # Read the template
                with open(template_path, 'r', encoding='utf-8') as template_file:
                    template_content = template_file.read()
                
                # Insert the network initialization script in the initialization function
                final_html = template_content.replace(
                    '// Network initialization will be injected here',
                    network_init
                )
                
                # Write the final HTML to the temporary file
                f.write(final_html)
                f.flush()  # Ensure all data is written
                
                logger.debug(f"Final HTML preview: {final_html[:500]}...")  # First 500 chars
            
            # Signal completion
            self.process_complete.emit(True, "Graph processed successfully")
            logger.debug("Graph processing completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing graph: {error_msg}", exc_info=True)
            self.process_complete.emit(False, error_msg)

    def clear(self):
        """Clear the current visualization."""
        self.web_view.setHtml("")
        self.status_label.setText("Ready")
        self.progress_bar.hide()

    def closeEvent(self, event):
        """Handle widget closure."""
        super().closeEvent(event)
