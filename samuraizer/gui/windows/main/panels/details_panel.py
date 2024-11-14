# samuraizer/gui/widgets/analysis_viewer/details_panel.py

import logging
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QToolBar, QTabWidget,
    QTextEdit, QMessageBox, QSpinBox, QDialog,
    QProgressBar, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal, QThread, QTimer, QSize
from PyQt6.QtGui import QFont, QAction, QTextCursor, QPalette
import json
import random

from ....workers.analysis.ai_worker import AIWorker

logger = logging.getLogger(__name__)

class AIProgressIndicator(QTextEdit):
    """Simple progress indicator for AI analysis."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        
        # Use system palette colors for theme compatibility
        self.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 8px;
            }
        """)
        
        # Remove fixed height constraints to allow dynamic sizing
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Simple spinner for activity indication
        self.spinner_frames = ["◐", "◓", "◑", "◒"]
        self.current_frame = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        
        # Initialize current status
        self._current_status = "Initializing..."
        
    def start_animation(self):
        """Start the progress animation."""
        self.clear()
        self.animation_timer.start(250)  # Slower animation for better readability
        self.update_display()
        
    def stop_animation(self):
        """Stop the progress animation."""
        self.animation_timer.stop()
        
    def update_animation(self):
        """Update the spinner animation frame."""
        self.current_frame = (self.current_frame + 1) % len(self.spinner_frames)
        self.update_display()
        
    def update_display(self):
        """Update the display with current status."""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        
        # Use system palette colors
        color = self.palette().text().color().name()
        status_text = f'<span style="color: {color};">{self.spinner_frames[self.current_frame]} {self._current_status}</span>'
        self.setHtml(status_text)
        
    def set_status(self, message: str):
        """Update with a specific status message."""
        self._current_status = message
        self.update_display()

class AnalysisTab(QWidget):
    """Custom widget for analysis results tab."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # Remove spacing between widgets
        
        # Create a container for the progress indicator
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        # AI Progress Indicator
        self.progress_indicator = AIProgressIndicator()
        self.progress_indicator.hide()
        progress_layout.addWidget(self.progress_indicator)
        
        # Cancel button - integrate it with the progress indicator
        self.cancel_button = QPushButton("Cancel Analysis")
        self.cancel_button.hide()
        self.cancel_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 5px;
                margin: 0px;
            }
        """)
        progress_layout.addWidget(self.cancel_button)
        
        layout.addWidget(self.progress_container)
        
        # Results text area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.results_text)

class LLMConfigDialog(QDialog):
    """Dialog for configuring LLM settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Configuration")
        self.settings = QSettings()
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # LLM Provider selection
        provider_layout = QHBoxLayout()
        provider_label = QLabel("LLM Provider:")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenAI", "Anthropic", "Custom"])
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.provider_combo)
        layout.addLayout(provider_layout)
        
        # API Key input
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        self.api_key_input = QTextEdit()
        self.api_key_input.setMaximumHeight(60)
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.api_key_input)
        layout.addLayout(key_layout)
        
        # Endpoint URL (for custom provider)
        endpoint_layout = QHBoxLayout()
        endpoint_label = QLabel("Endpoint URL:")
        self.endpoint_input = QTextEdit()
        self.endpoint_input.setMaximumHeight(60)
        endpoint_layout.addWidget(endpoint_label)
        endpoint_layout.addWidget(self.endpoint_input)
        layout.addLayout(endpoint_layout)
        
        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        self.update_model_choices(self.provider_combo.currentText())
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        layout.addLayout(model_layout)
        
        # Max tokens
        tokens_layout = QHBoxLayout()
        tokens_label = QLabel("Max Tokens:")
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(100, 10000)
        self.max_tokens.setValue(2000)
        tokens_layout.addWidget(tokens_label)
        tokens_layout.addWidget(self.max_tokens)
        layout.addLayout(tokens_layout)
        
        # Save and Cancel buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Connect provider change to model update
        self.provider_combo.currentTextChanged.connect(self.update_model_choices)
        
    def update_model_choices(self, provider: str):
        self.model_combo.clear()
        if provider == "OpenAI":
            self.model_combo.addItems([
                "gpt-4-turbo-preview",
                "gpt-4",
                "gpt-3.5-turbo"
            ])
        elif provider == "Anthropic":
            self.model_combo.addItems([
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ])
        else:
            self.model_combo.setEditable(True)
            self.model_combo.setPlaceholderText("Enter model name...")
            
    def load_settings(self):
        self.provider_combo.setCurrentText(
            self.settings.value("llm/provider", "OpenAI")
        )
        self.api_key_input.setText(
            self.settings.value("llm/api_key", "")
        )
        self.endpoint_input.setText(
            self.settings.value("llm/endpoint", "")
        )
        self.model_combo.setCurrentText(
            self.settings.value("llm/model", "gpt-4-turbo-preview")
        )
        self.max_tokens.setValue(
            self.settings.value("llm/max_tokens", 2000, type=int)
        )
        
    def accept(self):
        """Save settings and close dialog."""
        self.settings.setValue("llm/provider", self.provider_combo.currentText())
        self.settings.setValue("llm/api_key", self.api_key_input.toPlainText())
        self.settings.setValue("llm/endpoint", self.endpoint_input.toPlainText())
        self.settings.setValue("llm/model", self.model_combo.currentText())
        self.settings.setValue("llm/max_tokens", self.max_tokens.value())
        self.settings.sync()
        super().accept()

class DetailsPanel(QWidget):
    """Panel for displaying and analyzing detailed information about selected items."""
    
    analysis_completed = pyqtSignal(dict)  # Signal emitted when analysis completes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.current_selection = None
        self.current_analysis_type = None
        self.ai_thread = None
        self.ai_worker = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # Analysis type selection
        self.analysis_type = QComboBox()
        self.analysis_type.addItems([
            "Security Analysis",
            "Code Structure Analysis",
            "Import Analysis",
            "Performance Analysis",
            "Documentation Analysis"
        ])
        toolbar.addWidget(QLabel("Analysis Type: "))
        toolbar.addWidget(self.analysis_type)
        
        # Add analyze button
        self.analyze_button = QPushButton("Analyze Further")
        self.analyze_button.clicked.connect(self.start_analysis)
        self.analyze_button.setEnabled(False)
        toolbar.addWidget(self.analyze_button)
        
        # Add configure LLM button
        config_button = QPushButton("Configure LLM")
        config_button.clicked.connect(self.show_llm_config)
        toolbar.addWidget(config_button)
        
        layout.addWidget(toolbar)
        
        # Create tab widget for results
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_analysis_tab)
        self.tab_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.customContextMenuRequested.connect(self.show_tab_context_menu)
        layout.addWidget(self.tab_widget)

    def show_tab_context_menu(self, position):
        """Show context menu for tabs."""
        menu = QMenu()
        
        # Add actions
        save_action = QAction("Save Analysis", self)
        save_action.triggered.connect(lambda: self.save_analysis(self.tab_widget.currentIndex()))
        
        export_action = QAction("Export as PDF", self)
        export_action.triggered.connect(lambda: self.export_analysis(self.tab_widget.currentIndex()))
        
        copy_action = QAction("Copy to Clipboard", self)
        copy_action.triggered.connect(lambda: self.copy_analysis(self.tab_widget.currentIndex()))
        
        # Add actions to menu
        menu.addAction(save_action)
        menu.addAction(export_action)
        menu.addAction(copy_action)
        
        # Show menu
        menu.exec(self.tab_widget.mapToGlobal(position))

    def save_analysis(self, tab_index):
        """Save analysis results to file."""
        if tab_index < 0:
            return
            
        try:
            tab = self.tab_widget.widget(tab_index)
            if isinstance(tab, AnalysisTab):
                from PyQt6.QtWidgets import QFileDialog
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Analysis",
                    "",
                    "Text Files (*.txt);;JSON Files (*.json);;All Files (*.*)"
                )
                
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(tab.results_text.toPlainText())
                        
        except Exception as e:
            logger.error(f"Error saving analysis: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save analysis: {str(e)}"
            )

    def export_analysis(self, tab_index):
        """Export analysis results as PDF."""
        if tab_index < 0:
            return
            
        try:
            tab = self.tab_widget.widget(tab_index)
            if isinstance(tab, AnalysisTab):
                from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
                from PyQt6.QtGui import QTextDocument
                
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                
                dialog = QPrintDialog(printer, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    doc = QTextDocument()
                    doc.setPlainText(tab.results_text.toPlainText())
                    doc.print_(printer)
                    
        except Exception as e:
            logger.error(f"Error exporting analysis: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export analysis: {str(e)}"
            )

    def copy_analysis(self, tab_index):
        """Copy analysis results to clipboard."""
        if tab_index < 0:
            return
            
        try:
            tab = self.tab_widget.widget(tab_index)
            if isinstance(tab, AnalysisTab):
                from PyQt6.QtGui import QClipboard
                from PyQt6.QtWidgets import QApplication
                
                QApplication.clipboard().setText(tab.results_text.toPlainText())
                
        except Exception as e:
            logger.error(f"Error copying analysis: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Copy Error",
                f"Failed to copy analysis: {str(e)}"
            )

    def show_llm_config(self):
        """Show LLM configuration dialog."""
        dialog = LLMConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "LLM Configuration saved successfully!")
        
    def set_selection(self, selection_data: Dict[str, Any]):
        """Set the current selection data and enable analysis."""
        self.current_selection = selection_data
        self.analyze_button.setEnabled(True)
        
    def start_analysis(self):
        """Start the analysis process with the selected type."""
        if not self.current_selection:
            return
            
        try:
            # Get LLM settings
            provider = self.settings.value("llm/provider", "OpenAI")
            api_key = self.settings.value("llm/api_key", "")
            model = self.settings.value("llm/model", "gpt-4-turbo-preview")
            endpoint = self.settings.value("llm/endpoint", "")
            max_tokens = self.settings.value("llm/max_tokens", 2000, type=int)
            
            if not api_key:
                QMessageBox.warning(
                    self,
                    "Configuration Error",
                    "Please configure LLM settings first"
                )
                return
                
            # Create analysis prompt based on type
            analysis_type = self.analysis_type.currentText()
            prompt = self._create_analysis_prompt(analysis_type)
            
            # Create new analysis tab
            tab = AnalysisTab()
            tab_index = self.tab_widget.addTab(
                tab,
                f"{analysis_type} Results"
            )
            self.tab_widget.setCurrentIndex(tab_index)
            
            # Show and start progress animation
            tab.progress_indicator.show()
            tab.progress_indicator.start_animation()
            tab.cancel_button.show()
            
            # Hide results area until analysis is complete
            tab.results_text.hide()
            
            # Disable analyze button during processing
            self.analyze_button.setEnabled(False)
            
            # Create worker and thread
            self.ai_thread = QThread()
            self.ai_worker = AIWorker(prompt, {
                'provider': provider,
                'api_key': api_key,
                'model': model,
                'endpoint': endpoint,
                'max_tokens': max_tokens
            })
            
            # Move worker to thread
            self.ai_worker.moveToThread(self.ai_thread)
            
            # Connect signals
            self.ai_thread.started.connect(self.ai_worker.run)
            self.ai_worker.started.connect(lambda: tab.progress_indicator.set_status("Initializing neural networks..."))
            self.ai_worker.progress.connect(lambda msg: tab.progress_indicator.set_status(msg))
            self.ai_worker.finished.connect(lambda result: self._handle_analysis_complete(result, tab))
            self.ai_worker.error.connect(lambda err: self._handle_analysis_error(err, tab))
            self.ai_worker.finished.connect(self.ai_thread.quit)
            self.ai_worker.finished.connect(self.ai_worker.deleteLater)
            self.ai_thread.finished.connect(self.ai_thread.deleteLater)
            self.ai_thread.finished.connect(lambda: self.analyze_button.setEnabled(True))
            
            # Connect cancel button
            tab.cancel_button.clicked.connect(self.ai_worker.stop)
            
            # Store current tab and analysis type
            self.ai_worker.current_tab = tab
            self.ai_worker.analysis_type = analysis_type
            
            # Start processing
            self.ai_thread.start()
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Analysis Error",
                f"Failed to start analysis: {str(e)}"
            )
            self.analyze_button.setEnabled(True)
            
    def _handle_analysis_complete(self, result: str, tab: AnalysisTab):
        """Handle completed analysis."""
        try:
            # Stop progress animation
            tab.progress_indicator.stop_animation()
            tab.progress_indicator.hide()
            
            # Show and update results
            tab.results_text.show()
            tab.results_text.setText(result)
            
            # Hide cancel button
            tab.cancel_button.hide()
            
            # Emit completion signal
            self.analysis_completed.emit({
                "type": self.ai_worker.analysis_type,
                "results": result
            })
            
        except Exception as e:
            logger.error(f"Error handling analysis completion: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to process analysis results: {str(e)}"
            )
            
    def _handle_analysis_error(self, error_msg: str, tab: AnalysisTab):
        """Handle analysis error."""
        logger.error(f"Analysis error: {error_msg}")
        
        # Stop progress animation
        tab.progress_indicator.stop_animation()
        tab.progress_indicator.hide()
        
        # Show and update results with error
        tab.results_text.show()
        tab.results_text.setText(f"Analysis failed: {error_msg}")
        
        # Hide cancel button
        tab.cancel_button.hide()
        
        QMessageBox.critical(
            self,
            "Analysis Error",
            f"Failed to complete analysis: {error_msg}"
        )
        self.analyze_button.setEnabled(True)

    def close_analysis_tab(self, index: int):
        """Close the specified analysis tab."""
        self.tab_widget.removeTab(index)

    def _create_analysis_prompt(self, analysis_type: str) -> str:
        """Create appropriate prompt based on analysis type."""
        base_prompt = f"Analyze the following code/data for {analysis_type.lower()}:\n\n"
        
        if analysis_type == "Security Analysis":
            base_prompt += """
            Please perform a comprehensive security analysis, including:
            1. Potential vulnerabilities
            2. Security best practices adherence
            3. Input validation and sanitization
            4. Authentication and authorization concerns
            5. Data protection measures
            """
        elif analysis_type == "Code Structure Analysis":
            base_prompt += """
            Please analyze the code structure, including:
            1. Architecture patterns
            2. Code organization
            3. Class and function relationships
            4. Dependency management
            5. Potential improvements
            """
        elif analysis_type == "Import Analysis":
            base_prompt += """
            Please analyze the imports and dependencies, including:
            1. External dependencies
            2. Import organization
            3. Unused imports
            4. Circular dependencies
            5. Version compatibility
            """
        elif analysis_type == "Performance Analysis":
            base_prompt += """
            Please analyze performance aspects, including:
            1. Computational complexity
            2. Resource usage
            3. Optimization opportunities
            4. Bottlenecks
            5. Memory management
            """
        elif analysis_type == "Documentation Analysis":
            base_prompt += """
            Please analyze documentation quality, including:
            1. Docstring coverage
            2. Documentation clarity
            3. Code comments
            4. API documentation
            5. Usage examples
            """
            
        # Add the selection data
        base_prompt += f"\n\nCode/Data to analyze:\n{json.dumps(self.current_selection, indent=2)}"
        
        return base_prompt
