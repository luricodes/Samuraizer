import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
    QLabel,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QObject
from PyQt6.QtCore import pyqtProperty  # type: ignore[attr-defined]
from PyQt6.QtGui import QPalette, QColor

logger = logging.getLogger(__name__)

# Define color constants
ORANGE_COLOR = QColor("#FF9800")
GREEN_COLOR = QColor("#4CAF50")
BLUE_COLOR = QColor("#2196F3")

class ColorInterpolator(QObject):
    """Helper class to handle color interpolation for smooth transitions."""
    def __init__(self) -> None:
        super().__init__()
        self._color: QColor = ORANGE_COLOR

    def _get_color(self) -> QColor:
        return self._color

    def _set_color(self, color: QColor) -> None:
        self._color = color

    color = pyqtProperty(QColor, fget=_get_color, fset=_set_color)  # type: ignore[misc]

class ModernProgressBar(QProgressBar):
    """Custom progress bar with smooth color transitions."""
    def __init__(self):
        super().__init__()
        self.setTextVisible(True)
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hide()  # Start hidden
        
        # Initialize color interpolator and animation
        self.color_interpolator = ColorInterpolator()
        self.color_animation = QPropertyAnimation(self.color_interpolator, b"color")
        self.color_animation.setDuration(1000)  # 1 second transition
        self.color_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Connect animation value changed to update style
        self.color_animation.valueChanged.connect(self._updateStyleSheet)
        
        # Initial color (orange)
        self._updateStyleSheet(ORANGE_COLOR)

    def _updateStyleSheet(self, color):
        """Update progress bar style with the current color."""
        if isinstance(color, QColor):
            color_hex = color.name()
        else:
            color_hex = color
            
        gradient_color = self._adjustColor(color_hex)
        
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #cccccc;
                border-radius: 5px;
                background-color: #f0f0f0;
                text-align: center;
                margin: 0px;
                padding: 0px;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color_hex},
                    stop:1 {gradient_color}
                );
            }}
        """)

    def _adjustColor(self, color: str) -> str:
        """Create a slightly darker variant of the color for gradient."""
        if len(color) == 7:  # #RRGGBB format
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            
            r = max(0, int(r * 0.9))
            g = max(0, int(g * 0.9))
            b = max(0, int(b * 0.9))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        return color

    def updateColorByProgress(self, value, maximum):
        """Update progress bar color with smooth transition based on progress percentage."""
        if maximum <= 0:
            return
            
        progress = (value / maximum) * 100
        
        # Define color stops for different progress levels
        if progress < 30:
            target_color = ORANGE_COLOR
        elif progress < 60:
            # Interpolate between orange and green
            factor = (progress - 30) / 30
            target_color = QColor(
                int(ORANGE_COLOR.red() * (1 - factor) + GREEN_COLOR.red() * factor),
                int(ORANGE_COLOR.green() * (1 - factor) + GREEN_COLOR.green() * factor),
                int(ORANGE_COLOR.blue() * (1 - factor) + GREEN_COLOR.blue() * factor)
            )
        elif progress < 80:
            # Interpolate between green and blue
            factor = (progress - 60) / 30
            target_color = QColor(
                int(GREEN_COLOR.red() * (1 - factor) + BLUE_COLOR.red() * factor),
                int(GREEN_COLOR.green() * (1 - factor) + BLUE_COLOR.green() * factor),
                int(GREEN_COLOR.blue() * (1 - factor) + BLUE_COLOR.blue() * factor)
            )
        else:
            target_color = BLUE_COLOR
        
        # Stop any current animation
        self.color_animation.stop()
        
        # Set up new animation
        self.color_animation.setStartValue(self.color_interpolator.color)
        self.color_animation.setEndValue(target_color)
        
        # Start the animation
        self.color_animation.start()

    def reset(self):
        """Reset progress bar to initial state."""
        super().reset()
        # Stop any ongoing animation
        self.color_animation.stop()
        # Reset interpolator color
        self.color_interpolator._color = ORANGE_COLOR
        # Update style immediately
        self._updateStyleSheet(ORANGE_COLOR)

class ModernLabel(QLabel):
    """Enhanced label with modern styling and hover effects."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QLabel {
                color: #333333;
                padding: 2px 5px;
                border-radius: 3px;
            }
            QLabel:hover {
                background-color: #f0f0f0;
            }
        """)

class ProgressMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_label = None
        self.file_count_label = None
        self.progress_bar = None
        self.time_estimate_label = None
        self.start_time = None
        self.processed_count = 0
        self.total_count = 0
        self.initUI()

    def initUI(self):
        # Main layout with minimal margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(4)

        # Status layout
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)
        
        self.status_label = ModernLabel("Ready")
        self.file_count_label = ModernLabel("Processed: 0")
        
        self.status_label.setToolTip("Current analysis status")
        self.file_count_label.setToolTip("Processed files and estimated totals")
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.file_count_label)
        status_layout.addStretch()

        # Create progress bar
        self.progress_bar = ModernProgressBar()
        self.progress_bar.setFormat("%p% (%v/%m files)")
        
        # Time estimate label
        self.time_estimate_label = ModernLabel("")
        self.time_estimate_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.time_estimate_label.hide()  # Start hidden

        # Add widgets to main layout
        main_layout.addLayout(status_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.time_estimate_label)

        # Set overall widget style
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 5px;
            }
        """)

    def _format_time(self, seconds: float) -> str:
        """Format seconds into a human-readable time string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            seconds = int(seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _update_tooltip(self):
        """Update progress bar tooltip with detailed statistics."""
        if self.start_time and self.processed_count > 0:
            elapsed_time = (datetime.now() - self.start_time).total_seconds()
            files_per_second = self.processed_count / elapsed_time

            tooltip = (
                f"Processing Speed: {files_per_second:.1f} files/second\n"
                f"Processed: {self.processed_count} files\n"
                f"Remaining: {max(self.total_count - self.processed_count, 0)} files\n"
                f"Elapsed Time: {self._format_time(elapsed_time)}"
            )

            self.progress_bar.setToolTip(tooltip)

    def updateProgress(self, current: int, total: int):
        try:
            self.processed_count = current
            self.total_count = total

            if total <= 0:
                if not self.start_time and current > 0:
                    self.start_time = datetime.now()
                    self.progress_bar.reset()

                self.progress_bar.setMinimum(0)
                self.progress_bar.setMaximum(0)
                self.progress_bar.setFormat(f"Processing... ({current} files)")
                self.progress_bar.show()
                self.file_count_label.setText(
                    f"Processed: {current} (estimating total)"
                )

                if current > 0 and self.start_time:
                    elapsed_time = (datetime.now() - self.start_time).total_seconds()
                    elapsed_formatted = self._format_time(elapsed_time)
                    self.time_estimate_label.setText(
                        f"Elapsed: {elapsed_formatted} | Estimating total..."
                    )
                    self.time_estimate_label.show()
                    self.progress_bar.setToolTip(
                        f"Processed {current} files. Total count is being estimated."
                    )
                else:
                    self.time_estimate_label.hide()
                    self.progress_bar.setToolTip("Estimating total number of files...")
            else:
                if not self.start_time and current > 0:
                    self.start_time = datetime.now()
                    self.progress_bar.reset()  # Reset to orange at start

                self.progress_bar.setMaximum(total)
                self.progress_bar.setValue(current)
                self.progress_bar.setFormat(f"%p% ({current}/{total} files)")
                self.progress_bar.updateColorByProgress(current, total)
                self.progress_bar.show()

                self.file_count_label.setText(f"Processed: {current}/{total}")

                # Calculate time estimate
                if self.start_time and current > 0:
                    elapsed_time = (datetime.now() - self.start_time).total_seconds()
                    files_per_second = current / elapsed_time if elapsed_time > 0 else 0
                    remaining_files = max(total - current, 0)

                    if files_per_second > 0:
                        estimated_remaining = remaining_files / files_per_second
                        elapsed_formatted = self._format_time(elapsed_time)
                        remaining_formatted = self._format_time(estimated_remaining)
                        self.time_estimate_label.setText(
                            f"Elapsed: {elapsed_formatted} | Remaining: {remaining_formatted}"
                        )
                        self.time_estimate_label.show()

                        # Update tooltip with detailed statistics
                        self._update_tooltip()
                    else:
                        self.time_estimate_label.hide()

        except Exception as e:
            logger.error(f"Error updating progress bar: {e}")

    def updateStatus(self, message: str):
        try:
            self.status_label.setText(message)
            lowered = message.lower()

            if any(keyword in lowered for keyword in ["starting", "running streaming analysis"]):
                if not self.start_time:
                    self.start_time = datetime.now()
                self.progress_bar.reset()  # Reset to orange at start
                self.progress_bar.show()
            elif any(keyword in lowered for keyword in ["analysis completed", "analysis cancelled", "analysis stopped"]):
                self.start_time = None
                self.time_estimate_label.hide()
                self.progress_bar.hide()
                self.progress_bar.reset()  # Ensure reset on completion
            logger.debug(f"Status update: {message}")
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def updateFileCount(self, count: int):
        try:
            if self.total_count > 0:
                self.file_count_label.setText(f"Processed: {count}/{self.total_count}")
            else:
                self.file_count_label.setText(f"Processed: {count} (estimating total)")
        except Exception as e:
            logger.error(f"Error updating file count: {e}")

    def hideProgress(self):
        self.progress_bar.hide()
        self.time_estimate_label.hide()
        self.start_time = None
        self.progress_bar.reset()  # Reset to orange when hidden
        self.file_count_label.setText("Processed: 0")
