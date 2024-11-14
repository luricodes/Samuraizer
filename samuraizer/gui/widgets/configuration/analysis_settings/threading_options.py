# samuraizer/gui/widgets/options/analysis/threading_options.py

import logging
import multiprocessing
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QSpinBox, QGroupBox, QLabel
)

logger = logging.getLogger(__name__)

class ThreadingOptionsWidget(QWidget):
    """Widget for configuring threading options."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface."""
        layout = QFormLayout()
        
        # Calculate optimal thread settings
        cpu_count = multiprocessing.cpu_count()
        default_threads = min(cpu_count * 2, 16)  # 2x CPU cores, capped at 16
        max_threads = min(cpu_count * 4, 32)      # 4x CPU cores, capped at 32
        
        # Thread Count
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, max_threads)
        self.thread_count.setValue(default_threads)
        layout.addRow("Processing Threads:", self.thread_count)
        
        # Simple explanation label
        info = QLabel(f"While higher values may enhance the speed for large repositories, they may also negatively impact stability.")
        info.setWordWrap(True)
        layout.addRow(info)
        
        group = QGroupBox("Performance Options")
        group.setLayout(layout)
        
        main_layout = QFormLayout(self)
        main_layout.addWidget(group)
        self.setLayout(main_layout)
