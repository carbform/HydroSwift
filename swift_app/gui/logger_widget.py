"""
HydroSwift GUI - Logger Widget

Provides a text widget for displaying execution logs and status messages
with color-coded severity levels.
"""

from __future__ import annotations

from datetime import datetime
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from PyQt5.QtCore import Qt, pyqtSlot


class LoggerWidget(QTextEdit):
    """Text widget for displaying colored log messages."""

    # Color scheme for log levels
    LOG_COLORS = {
        "info": QColor(100, 150, 200),      # Blue
        "success": QColor(50, 180, 50),     # Green
        "warning": QColor(200, 150, 50),    # Orange
        "error": QColor(200, 50, 50),       # Red
        "debug": QColor(150, 150, 150),     # Gray
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setReadOnly(True)
        self.setMaximumHeight(150)
        
        # Configure font
        font = QFont("Courier")
        font.setPointSize(9)
        self.setFont(font)
        
        # Configure document margins
        self.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
        """)

    def append_log(
        self,
        message: str,
        level: str = "info"
    ) -> None:
        """Append a log message with specified level.
        
        Parameters
        ----------
        message : str
            The log message to append
        level : str, default "info"
            Severity level: "info", "success", "warning", "error", "debug"
        """
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create formatted message
        formatted_message = f"[{timestamp}] {message}"
        
        # Get cursor and move to end
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Create text format for the message
        text_format = QTextCharFormat()
        text_format.setForeground(self.LOG_COLORS.get(level, self.LOG_COLORS["info"]))
        text_format.setFont(self.font())
        
        # Insert text with formatting
        cursor.insertText(formatted_message + "\n", text_format)
        
        # Scroll to show the new message
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_section(self, section_title: str) -> None:
        """Append a section divider."""
        self.append_log("=" * 60, "debug")
        self.append_log(section_title, "info")
        self.append_log("=" * 60, "debug")

    def success(self, message: str) -> None:
        """Append a success message."""
        self.append_log(f"✓ {message}", "success")

    def error(self, message: str) -> None:
        """Append an error message."""
        self.append_log(f"✗ {message}", "error")

    def warning(self, message: str) -> None:
        """Append a warning message."""
        self.append_log(f"⚠ {message}", "warning")

    def info(self, message: str) -> None:
        """Append an info message."""
        self.append_log(f"ℹ {message}", "info")

    @pyqtSlot()
    def clear(self) -> None:
        """Clear all log messages."""
        super().clear()
        self.append_log("Log cleared", "info")
