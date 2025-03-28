import json
import os
import platform
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt5.QtCore import QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QIcon, QMouseEvent, QShowEvent
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.config import ConfigManager
from ..utils.dialogs import DialogManager
from ..utils.qt_types import QtConstants, WindowFlags

logger = getLogger(__name__)


class SettingsWindow(QWidget):
    """Window for managing application settings."""

    windowOpened = pyqtSignal(bool)
    windowClosed = pyqtSignal()
    settings_changed = pyqtSignal(dict)

    def __init__(self, settings: Dict[str, Any], version: str) -> None:
        """Initialize settings window."""
        super().__init__()
        self.config_manager = ConfigManager()
        self.dialog_manager = DialogManager()
        self.settings = settings.copy()
        self._original_settings = settings.copy()
        self.version = version
        self.drag_position: Optional[QPoint] = None
        self.reset_timer: Optional[QTimer] = None

        # Initialize UI elements
        self.destination_folder_label = QLabel()
        self.sound_checkbox = QPushButton("Mute Sound")
        self.sound_checkbox.setCheckable(True)
        self.illegal_chars_checkbox = QPushButton("Remove Illegal Characters")
        self.illegal_chars_checkbox.setCheckable(True)
        self.reset_button = QPushButton("Reset && Save All Settings")

        self._setup_platform_specific()
        try:
            # Initialize attributes
            self.music_folder_path = ""
            self.destination_folder_path = ""

            # Setup and show user interface
            self.setup_ui()

            # Load settings from file if it exists
            self.load_settings()
        except Exception as e:
            logger.error(f"Failed to initialize settings window: {e}")
            raise

    def showEvent(self, event: QShowEvent) -> None:
        """Handle show event."""
        self.windowOpened.emit(False)
        super().showEvent(event)
        self.center_window()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close with settings check."""
        try:
            if self._settings_changed():
                self.settings_changed.emit(self.settings)
            self.windowClosed.emit()
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Close event error: {e}")
            event.accept()

    def _settings_changed(self) -> bool:
        """Check if settings have been modified."""
        return any(
            self.settings.get(key) != self._original_settings.get(key) for key in self.settings
        )

    def setup_titlebar(self) -> None:
        """Set up the custom titlebar."""
        self.setWindowFlag(QtConstants.FramelessWindowHint)

        self.title_bar = QWidget(self)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(32)

        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(0, 0, 0, 0)

        # Icon and title
        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon(":/Octopus.ico").pixmap(24, 24))
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(f"Settings Window v{self.version}")
        self.title_label.setStyleSheet("color: white;")
        layout.addWidget(self.title_label)

        layout.addStretch()
        layout.setAlignment(QtConstants.AlignRight)

        # Close button
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events for window dragging."""
        if event and event.button() == QtConstants.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move events."""
        if event and self.drag_position is not None:
            if event.buttons() & QtConstants.LeftButton:
                self.move(event.globalPos() - self.drag_position)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release events."""
        if event.button() == QtConstants.LeftButton:
            self.drag_position = None

    def setup_ui(self) -> None:
        """Set up the settings window UI with platform-specific adjustments."""
        try:
            # Platform-specific adjustments
            is_mac = platform.system() == "Darwin"

            main_layout = QVBoxLayout()
            main_layout.setContentsMargins(*(20,) * 4 if is_mac else (10,) * 4)

            # Title bar (skip on macOS to use native window decorations)
            if not is_mac:
                self.setup_titlebar()

            # Folder selection section with platform-specific spacing
            folder_section = QVBoxLayout()
            folder_section.setSpacing(10 if is_mac else 5)

            # Music folder selection
            music_folder_layout = QHBoxLayout()
            self.music_folder_label = QLabel()
            self.music_folder_label.setWordWrap(True)
            music_folder_layout.addWidget(self.music_folder_label)

            select_music_btn = QPushButton("Select Music Folder")
            select_music_btn.clicked.connect(self.select_music_folder)
            music_folder_layout.addWidget(select_music_btn)

            folder_section.addLayout(music_folder_layout)
            main_layout.addLayout(folder_section)

            # Apply platform-specific window flags
            if is_mac:
                flags: WindowFlags = QtConstants.Window
            else:
                flags = QtConstants.Window | QtConstants.FramelessWindowHint
            self.setWindowFlags(flags)

            self.setLayout(main_layout)

        except Exception as e:
            logger.error(f"Failed to set up settings UI: {e}")
            raise

    def center_window(self) -> None:
        """Center the window on the screen."""
        desktop = QApplication.desktop()
        if desktop is None:
            logger.warning("Could not get desktop widget")
            return

        screen = desktop.screenGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(x, y)

    def select_music_folder(self) -> None:
        """Handle music folder selection."""
        try:
            folder_path = QFileDialog.getExistingDirectory(
                self,
                "Select Music Folder",
                (
                    str(Path.home() / "Music")
                    if not self.music_folder_path
                    else self.music_folder_path
                ),
                QFileDialog.ShowDirsOnly,
            )

            if not folder_path:
                logger.debug("Music folder selection cancelled")
                return

            if not self._validate_folder_path(folder_path):
                logger.warning(f"Invalid music folder path: {folder_path}")
                return

            self.music_folder_path = folder_path
            self.music_folder_label.setText(self.music_folder_path)
            self._save_settings()

        except Exception as e:
            logger.error(f"Failed to select music folder: {e}")
            self.show_error("Failed to select music folder")

    def _validate_folder_path(self, path: str) -> bool:
        """Validate folder path exists and is accessible.

        Args:
            path: Folder path to validate

        Returns:
            bool: True if valid, False otherwise
        """
        try:
            folder = Path(path)
            return folder.exists() and folder.is_dir() and os.access(folder, os.R_OK)
        except Exception as e:
            logger.error(f"Folder validation error: {e}")
            return False

    def clear_music_folder(self) -> None:
        """Clear music folder path with proper cleanup."""
        try:
            self.music_folder_path = ""
            self.music_folder_label.setText("")
            self._save_settings()
        except Exception as e:
            logger.error(f"Failed to clear music folder: {e}")

    def select_destination_folder(self) -> None:
        """Handle destination folder selection with validation."""
        try:
            destination_folder_path = QFileDialog.getExistingDirectory(
                self, "Select Destination Folder", "", QFileDialog.ShowDirsOnly
            )

            if not destination_folder_path:
                logger.debug("Destination folder selection cancelled")
                return

            if not self._validate_folder_path(destination_folder_path):
                logger.warning(f"Invalid destination folder path: {destination_folder_path}")
                return

            self.destination_folder_path = destination_folder_path
            self.destination_folder_label.setText(self.destination_folder_path)
            self._save_settings()
        except Exception as e:
            logger.error(f"Failed to select destination folder: {e}")

    def clear_destination_folder(self) -> None:
        """Clear destination folder path with proper cleanup."""
        try:
            self.destination_folder_path = ""
            self.destination_folder_label.setText("")
            self._save_settings()
        except Exception as e:
            logger.error(f"Failed to clear destination folder: {e}")

    def load_settings(self) -> None:
        """Load settings from file and update UI."""
        try:
            if not Path("settings_jmo.json").exists():
                logger.debug("No settings file found")
                return

            with open("settings_jmo.json", "r", encoding="utf-8") as f:
                settings = json.load(f)

            # Update UI with loaded settings
            self.music_folder_path = settings.get("music_folder_path", "")
            self.destination_folder_path = settings.get("destination_folder_path", "")
            self.music_folder_label.setText(self.music_folder_path)
            self.destination_folder_label.setText(self.destination_folder_path)
            self.sound_checkbox.setChecked(settings.get("mute_sound", False))
            self.illegal_chars_checkbox.setChecked(settings.get("remove_illegal_chars", True))

        except json.JSONDecodeError as e:
            logger.error(f"Invalid settings file format: {e}")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def save_settings(self) -> None:
        """Save current settings to file."""
        try:
            settings = {
                "music_folder_path": self.music_folder_path,
                "destination_folder_path": self.destination_folder_path,
                "mute_sound": self.sound_checkbox.isChecked(),
                "remove_illegal_chars": self.illegal_chars_checkbox.isChecked(),
                "version": self.version,
            }

            with open("settings_jmo.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)

            logger.debug("Settings saved successfully")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            raise RuntimeError("Failed to save settings") from e

    def reset_settings(self) -> None:
        """Reset all settings to default values."""
        # Default settings
        self.music_folder_path = ""
        self.destination_folder_path = ""
        self.sound_checkbox.setChecked(False)
        self.illegal_chars_checkbox.setChecked(True)  # Default to True

        # Reset settings to default
        self.music_folder_label.setText(self.music_folder_path)
        self.destination_folder_label.setText(self.destination_folder_path)

        # Save settings to file
        self.save_settings()

        # Fix timer handling
        if self.reset_timer is not None:
            self.reset_timer.stop()

        self.reset_timer = QTimer(self)
        self.reset_timer.timeout.connect(self.resetResetButton)
        self.reset_timer.start(1000)

    def resetResetButton(self) -> None:
        """Reset the reset button appearance."""
        self.reset_button.setText("Reset && Save All Settings")
        self.reset_button.setStyleSheet("")

    def _save_settings(self) -> None:
        """Save settings with validation."""
        try:
            if self._validate_settings(self.settings):
                self.config_manager.save(self.settings)
                self.settings_changed.emit(self.settings)
            else:
                logger.error("Invalid settings configuration")
                self.show_error("Invalid settings configuration")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            self.show_error(f"Failed to save settings: {str(e)}")

    def _validate_settings(self, settings: Dict[str, Any]) -> bool:
        """Validate settings before saving."""
        # Implement your validation logic here
        return True  # Placeholder, actual implementation needed

    def _setup_platform_specific(self) -> None:
        """Set up platform-specific configurations."""
        # Implement platform-specific setup logic
        pass

    def show_error(self, message: str) -> None:
        """Show error message to user."""
        # Implement error handling logic
        pass

    def close(self) -> bool:
        """Override close to ensure proper cleanup."""
        result = super().close()
        self.windowClosed.emit()
        return result
