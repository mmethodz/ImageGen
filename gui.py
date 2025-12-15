#
# GUI for Gemini Image Generation using PySide6
#

import os
import json
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
import api
from PIL import Image
import io
import edits


class ImageWorker(QtCore.QObject):
    finished = QtCore.Signal(bytes)
    # emit exception objects so caller can inspect type
    error = QtCore.Signal(object)

    def __init__(self, prompt: str, aspect_ratio: str = "1:1"):
        super().__init__()
        self.prompt = prompt
        self.aspect_ratio = aspect_ratio

    @QtCore.Slot()
    def run(self):
        try:
            data = api.generate_image(self.prompt, self.aspect_ratio)
            if not data:
                raise RuntimeError("No image bytes returned")
            self.finished.emit(data)
        except Exception as e:
            # Emit the actual exception object so GUI can react (e.g. billing)
            self.error.emit(e)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini ImageGen")
        self.resize(1000, 700)

        self.current_pixmap = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Prompt area
        prompt_layout = QtWidgets.QHBoxLayout()
        # Prompt history combo (editable)
        self.prompt_combo = QtWidgets.QComboBox()
        self.prompt_combo.setEditable(True)
        self.prompt_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.prompt_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.prompt_combo.lineEdit().setPlaceholderText("Describe the image to generate...")
        self.prompt_combo.lineEdit().returnPressed.connect(self.on_generate)  # Wire Enter key to Generate
        prompt_layout.addWidget(self.prompt_combo)
        # internal last prompt (used for history on success)
        self._last_prompt = None
        
        # Lens type selector (from Imagen docs)
        self.lens_type = QtWidgets.QComboBox()
        # Include a 'None' option and common lens keywords from Imagen docs
        self.lens_type.addItems(["None", "Macro lens", "Fisheye", "Wide-angle", "Telephoto", "Telephoto zoom"]) 
        self.lens_type.setMaximumWidth(120)
        prompt_layout.addWidget(QtWidgets.QLabel("Lens:"))
        prompt_layout.addWidget(self.lens_type)

        # Focal length selector
        self.focal_length = QtWidgets.QComboBox()
        # Include 'None' and common focal lengths
        self.focal_length.addItems(["None", "10mm", "24mm", "35mm", "50mm", "85mm", "100mm", "200mm", "60-105mm"]) 
        self.focal_length.setMaximumWidth(90)
        prompt_layout.addWidget(QtWidgets.QLabel("Focal:"))
        prompt_layout.addWidget(self.focal_length)

        # Aspect ratio selector
        self.aspect_ratio = QtWidgets.QComboBox()
        self.aspect_ratio.addItems(["1:1", "3:4", "4:3", "9:16", "16:9"])
        self.aspect_ratio.setMaximumWidth(80)
        prompt_layout.addWidget(QtWidgets.QLabel("Aspect:"))
        prompt_layout.addWidget(self.aspect_ratio)
        
        # High-res checkbox
        self.highres_checkbox = QtWidgets.QCheckBox("High-res")
        prompt_layout.addWidget(self.highres_checkbox)
        
        self.generate_btn = QtWidgets.QPushButton("Generate")
        self.generate_btn.clicked.connect(self.on_generate)
        prompt_layout.addWidget(self.generate_btn)

        layout.addLayout(prompt_layout)

        # Image display
        self.image_label = QtWidgets.QLabel(alignment=Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("background: #202020; border: 1px solid #333;")
        layout.addWidget(self.image_label, stretch=1)

        # Edit panel (filters and adjustments)
        edit_layout = QtWidgets.QHBoxLayout()

        # Filter selector
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["None", "Grayscale", "Sepia", "Blur", "Sharpen"])
        self.filter_combo.setMaximumWidth(120)
        edit_layout.addWidget(QtWidgets.QLabel("Filter:"))
        edit_layout.addWidget(self.filter_combo)

        # Preset selector
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(["Custom", "Cinematic", "Filmic", "Vibrant", "Soft", "High Contrast"])
        self.preset_combo.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Preset:"))
        edit_layout.addWidget(self.preset_combo)

        # Brightness slider
        self.brightness_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(50, 200)
        self.brightness_slider.setValue(100)
        self.brightness_slider.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Brightness"))
        edit_layout.addWidget(self.brightness_slider)

        # Contrast slider
        self.contrast_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(50, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Contrast"))
        edit_layout.addWidget(self.contrast_slider)

        # Saturation slider
        self.saturation_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 200)
        self.saturation_slider.setValue(100)
        self.saturation_slider.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Saturation"))
        edit_layout.addWidget(self.saturation_slider)

        # Vignette slider
        self.vignette_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.vignette_slider.setRange(0, 100)
        self.vignette_slider.setValue(0)
        self.vignette_slider.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Vignette"))
        edit_layout.addWidget(self.vignette_slider)
        # Sharpness slider
        self.sharpness_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.sharpness_slider.setRange(0, 200)
        self.sharpness_slider.setValue(100)
        self.sharpness_slider.setMaximumWidth(140)
        edit_layout.addWidget(QtWidgets.QLabel("Sharpness"))
        edit_layout.addWidget(self.sharpness_slider)
        # Apply / Reset buttons
        self.apply_edits_btn = QtWidgets.QPushButton("Apply Edits")
        self.reset_edits_btn = QtWidgets.QPushButton("Reset")
        edit_layout.addWidget(self.apply_edits_btn)
        edit_layout.addWidget(self.reset_edits_btn)

        # Undo / Redo buttons
        self.undo_btn = QtWidgets.QPushButton("Undo")
        self.redo_btn = QtWidgets.QPushButton("Redo")
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        edit_layout.addWidget(self.undo_btn)
        edit_layout.addWidget(self.redo_btn)

        layout.addLayout(edit_layout)

        # Initially disable edit controls until an image is loaded
        self._set_edit_controls_enabled(False)

        # Connect edit controls (once)
        self.apply_edits_btn.clicked.connect(self._apply_edits_to_original)
        self.reset_edits_btn.clicked.connect(self._reset_edits)
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn.clicked.connect(self._redo)
        self.filter_combo.currentIndexChanged.connect(self._schedule_preview)
        self.brightness_slider.valueChanged.connect(self._schedule_preview)
        self.contrast_slider.valueChanged.connect(self._schedule_preview)
        self.saturation_slider.valueChanged.connect(self._schedule_preview)
        self.vignette_slider.valueChanged.connect(self._schedule_preview)
        self.sharpness_slider.valueChanged.connect(self._schedule_preview)
        self.preset_combo.currentIndexChanged.connect(lambda _: (self._apply_preset(self.preset_combo.currentText()), self._schedule_preview()))

        # Bottom actions
        bottom_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save as PNG...")
        self.save_btn.clicked.connect(self.on_save)
        self.save_btn.setEnabled(False)
        bottom_layout.addWidget(self.save_btn)

        self.export_btn = QtWidgets.QPushButton("Export Full Resolution...")
        self.export_btn.clicked.connect(self.on_export_full)
        self.export_btn.setEnabled(False)
        bottom_layout.addWidget(self.export_btn)

        # Progress indicator (indeterminate)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedWidth(160)
        bottom_layout.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("")
        bottom_layout.addWidget(self.status_label)
        layout.addLayout(bottom_layout)

        self._apply_dark_theme()

        # Keep references for preview/export threads so we can avoid leaking
        self._preview_thread = None
        self._preview_worker = None
        self._export_thread = None
        self._export_worker = None
        self._export_path = None  # Store export path for the worker callback
        # Undo / redo stacks hold bytes of the 'original' image (full resolution)
        self._undo_stack = []  # list[bytes]
        self._redo_stack = []  # list[bytes]
        # Debounce timer for preview updates to avoid flooding worker threads
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)  # milliseconds
        self._preview_timer.timeout.connect(self._start_preview_worker)
        
        # Load prompt history from disk
        self._load_prompt_history()

    class ThumbnailWorker(QtCore.QObject):
        finished = QtCore.Signal(bytes)
        error = QtCore.Signal(object)

        def __init__(self, image_bytes: bytes, settings: dict, max_size: int = 512):
            super().__init__()
            self.image_bytes = image_bytes
            self.settings = settings
            self.max_size = max_size

        @QtCore.Slot()
        def run(self):
            try:
                # Apply edits to full-resolution image (preserve quality for preview and save/export)
                edited = edits.apply_edits_bytes(self.image_bytes, self.settings)
                self.finished.emit(edited)
            except Exception as e:
                self.error.emit(e)

    class FullExportWorker(QtCore.QObject):
        finished = QtCore.Signal(bytes)
        error = QtCore.Signal(object)

        def __init__(self, image_bytes: bytes, settings: dict):
            super().__init__()
            self.image_bytes = image_bytes
            self.settings = settings

        @QtCore.Slot()
        def run(self):
            try:
                edited = edits.apply_edits_bytes(self.image_bytes, self.settings)
                self.finished.emit(edited)
            except Exception as e:
                self.error.emit(e)

    def _apply_dark_theme(self):
        # Minimal dark stylesheet
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: #e0e0e0; }
            QLineEdit, QTextEdit { background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; }
            QPushButton { background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px; }
            QPushButton:hover { background: #333333; }
        """)

    def on_generate(self):
        # read prompt from the editable combo
        prompt = self.prompt_combo.currentText().strip()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "No prompt", "Please enter a prompt to generate an image.")
            return

        self.generate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText("Generating...")
        # Show indeterminate progress
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        # Prepare worker and thread
        # Read UI selections
        lens = self.lens_type.currentText()
        focal = self.focal_length.currentText()
        aspect_ratio = self.aspect_ratio.currentText()

        # Build camera modifier string according to examples in the Imagen docs.
        modifier = ""
        if focal != "None" and lens != "None":
            # Use a comma for telephoto styles, otherwise join with a space
            if "telephoto" in lens.lower():
                modifier = f"{focal}, {lens}"
            else:
                modifier = f"{focal} {lens}"
        elif focal != "None":
            modifier = focal
        elif lens != "None":
            modifier = lens

        if modifier:
            augmented_prompt = f"{prompt}, {modifier}"
        else:
            augmented_prompt = prompt

        # Add high-res suffix if checkbox is checked
        if self.highres_checkbox.isChecked():
            augmented_prompt = f"{augmented_prompt}, in high resolution"

        # remember last base prompt for history (add on successful generation)
        self._last_prompt = prompt

        self.thread = QtCore.QThread()
        self.worker = ImageWorker(augmented_prompt, aspect_ratio)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_image_ready)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
        # disable edit controls until image arrives
        self._set_edit_controls_enabled(False)

    def _on_image_ready(self, image_bytes: bytes):
        pix = QtGui.QPixmap()
        ok = pix.loadFromData(image_bytes)
        if not ok:
            self._on_error("Failed to load image data")
            return
        self.current_pixmap = pix
        # store original bytes for edits
        self.original_image_bytes = image_bytes
        self.edited_image_bytes = image_bytes
        # add prompt to history (if available)
        try:
            if getattr(self, '_last_prompt', None):
                self._add_prompt_history(self._last_prompt)
        except Exception:
            pass
        # clear undo/redo when a brand new image arrives
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_redo_buttons()
        # enable edit controls
        self._set_edit_controls_enabled(True)
        self._update_image_label()
        # Hide progress and update status
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.status_label.setText("Done")
        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

    def _on_error(self, exc: object):
        # Hide progress on error
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)

        # If this is a BillingRequired exception from the API, offer to open AI Studio billing
        try:
            from api import BillingRequired
        except Exception:
            BillingRequired = None

        if BillingRequired is not None and isinstance(exc, BillingRequired):
            msg = str(exc)
            self.status_label.setText("Error: billing required")
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Warning)
            box.setWindowTitle("Billing required")
            box.setText("Imagen image generation requires a billed Google account.")
            box.setInformativeText("Would you like to open AI Studio billing instructions?")
            open_btn = box.addButton("Open AI Studio", QtWidgets.QMessageBox.AcceptRole)
            box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is open_btn:
                url = QtCore.QUrl("https://aistudio.google.com/?model=imagen-3")
                QtGui.QDesktopServices.openUrl(url)
        else:
            message = str(exc)
            self.status_label.setText(f"Error: {message}")
            QtWidgets.QMessageBox.critical(self, "Generation error", message)

        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(self.current_pixmap is not None)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self._update_image_label()

    def _update_image_label(self):
        if self.current_pixmap:
            scaled = self.current_pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setPixmap(QtGui.QPixmap())

    def _set_edit_controls_enabled(self, enabled: bool):
        self.filter_combo.setEnabled(enabled)
        self.brightness_slider.setEnabled(enabled)
        self.contrast_slider.setEnabled(enabled)
        self.saturation_slider.setEnabled(enabled)
        self.vignette_slider.setEnabled(enabled)
        self.sharpness_slider.setEnabled(enabled)
        self.apply_edits_btn.setEnabled(enabled)
        self.reset_edits_btn.setEnabled(enabled)

    def _preview_edits(self):
        # Apply edits to original image and show preview (non-destructive)
        if not getattr(self, 'original_image_bytes', None):
            return
        # Build settings from controls
        settings = {
            'filter': self.filter_combo.currentText(),
            'brightness': self.brightness_slider.value() / 100.0,
            'contrast': self.contrast_slider.value() / 100.0,
            'saturation': self.saturation_slider.value() / 100.0,
            'vignette': self.vignette_slider.value() / 100.0,
            'sharpness': self.sharpness_slider.value() / 100.0,
        }

        # If a previous preview thread is running, let it finish (it works on a copy).
        # Start a new thumbnail worker to keep UI responsive.
        try:
            # clean up old thread objects
            if self._preview_thread is not None:
                try:
                    self._preview_thread.quit()
                    self._preview_thread.wait(50)
                except Exception:
                    pass

            self._preview_thread = QtCore.QThread()
            self._preview_worker = MainWindow.ThumbnailWorker(self.original_image_bytes, settings, max_size=512)
            self._preview_worker.moveToThread(self._preview_thread)
            self._preview_thread.started.connect(self._preview_worker.run)
            self._preview_worker.finished.connect(self._on_preview_ready)
            self._preview_worker.error.connect(self._on_preview_error)
            self._preview_worker.finished.connect(self._preview_thread.quit)
            self._preview_worker.error.connect(self._preview_thread.quit)
            self._preview_thread.finished.connect(self._preview_thread.deleteLater)
            self._preview_thread.start()
        except Exception as e:
            print('Edit preview failed (thread):', e)

    def _schedule_preview(self):
        # restart debounce timer; actual preview work runs when timer fires
        try:
            self._preview_timer.start()
        except Exception:
            # fallback: run immediately
            self._preview_edits()

    def _start_preview_worker(self):
        # Timer callback: start the heavy preview worker
        self._preview_edits()

    def _on_preview_ready(self, edited_bytes: bytes):
        try:
            pix = QtGui.QPixmap()
            if pix.loadFromData(edited_bytes):
                self.current_pixmap = pix
                self._update_image_label()
                self.edited_image_bytes = edited_bytes
        except Exception as e:
            print('Preview apply failed:', e)

    def _on_preview_error(self, exc: object):
        print('Preview worker error:', exc)

    def _apply_edits_to_original(self):
        # Finalize edits (already applied to preview), keep edited bytes as original for subsequent edits
        if getattr(self, 'edited_image_bytes', None):
            # push current original to undo stack, then replace
            try:
                self._undo_stack.append(self.original_image_bytes)
                # clear redo stack on new change
                self._redo_stack.clear()
            except Exception:
                pass
            self.original_image_bytes = self.edited_image_bytes
            self._update_undo_redo_buttons()
            self.status_label.setText('Edits applied to the image')

    def _apply_preset(self, preset_name: str):
        # Map presets to slider/filter settings
        presets = {
            'Cinematic': {'filter': 'None', 'brightness': 95, 'contrast': 120, 'saturation': 110, 'vignette': 20, 'sharpness': 110},
            'Filmic': {'filter': 'None', 'brightness': 95, 'contrast': 105, 'saturation': 95, 'vignette': 18, 'sharpness': 105},
            'Vibrant': {'filter': 'None', 'brightness': 105, 'contrast': 110, 'saturation': 140, 'vignette': 0, 'sharpness': 115},
            'Soft': {'filter': 'None', 'brightness': 105, 'contrast': 90, 'saturation': 95, 'vignette': 5, 'sharpness': 85},
            'High Contrast': {'filter': 'None', 'brightness': 100, 'contrast': 140, 'saturation': 100, 'vignette': 10, 'sharpness': 120},
        }

        if preset_name == 'Custom' or preset_name not in presets:
            return
        p = presets[preset_name]
        # set control values (these will trigger preview)
        self.filter_combo.setCurrentText(p.get('filter', 'None'))
        self.brightness_slider.setValue(p.get('brightness', 100))
        self.contrast_slider.setValue(p.get('contrast', 100))
        self.saturation_slider.setValue(p.get('saturation', 100))
        self.vignette_slider.setValue(p.get('vignette', 0))
        self.sharpness_slider.setValue(p.get('sharpness', 100))
        

    def on_export_full(self):
        # Ask for path first, then run full-resolution export in background
        if not getattr(self, 'original_image_bytes', None):
            return
        default_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.PicturesLocation) or os.path.expanduser("~/Pictures")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export full resolution", default_dir, "PNG Files (*.png)")
        if not path:
            return
        if not path.lower().endswith('.png'):
            path += '.png'

        # Build settings
        settings = {
            'filter': self.filter_combo.currentText(),
            'brightness': self.brightness_slider.value() / 100.0,
            'contrast': self.contrast_slider.value() / 100.0,
            'saturation': self.saturation_slider.value() / 100.0,
            'vignette': self.vignette_slider.value() / 100.0,
            'sharpness': self.sharpness_slider.value() / 100.0,
        }

        # disable UI controls while exporting
        self.export_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status_label.setText('Exporting full resolution...')
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        # start export thread
        try:
            if self._export_thread is not None:
                try:
                    self._export_thread.quit()
                    self._export_thread.wait(50)
                except Exception:
                    pass

            self._export_thread = QtCore.QThread()
            self._export_worker = MainWindow.FullExportWorker(self.original_image_bytes, settings)
            self._export_path = path  # Store path for the callback
            self._export_worker.moveToThread(self._export_thread)
            self._export_thread.started.connect(self._export_worker.run)
            # Connect signals to methods directly (avoid lambda capture issues with QueuedConnection)
            self._export_worker.finished.connect(self._handle_export_finished, QtCore.Qt.QueuedConnection)
            self._export_worker.error.connect(self._handle_export_error, QtCore.Qt.QueuedConnection)
            # DirectConnection for quit to avoid reparenting issues
            self._export_worker.finished.connect(self._export_thread.quit, QtCore.Qt.DirectConnection)
            self._export_worker.error.connect(self._export_thread.quit, QtCore.Qt.DirectConnection)
            self._export_thread.finished.connect(self._export_thread.deleteLater)
            self._export_thread.start()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Export failed', str(e))
            self.export_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.progress.setVisible(False)

    def _handle_export_finished(self, data: bytes):
        """Wrapper to call _on_export_finished with stored path."""
        #print(f'[GUI] _handle_export_finished called')
        self._on_export_finished(data, self._export_path)

    def _handle_export_error(self, exc: object):
        """Wrapper to call _on_export_error."""
        #print(f'[GUI] _handle_export_error called')
        self._on_export_error(exc)

    def _on_export_finished(self, data: bytes, path: str):
        #print(f'[GUI] _on_export_finished called with {len(data)} bytes, writing to {path}')
        try:
            with open(path, 'wb') as f:
                f.write(data)
            self.status_label.setText(f'Exported to {path}')
            #print(f'[GUI] File written')
        except Exception as e:
            #print(f'[GUI] Export error: {e}')
            self.status_label.setText('Export save failed')
            QtWidgets.QMessageBox.critical(self, 'Export save failed', str(e))
        finally:
            #print(f'[GUI] Finalizing export UI')
            self.progress.setVisible(False)
            self.export_btn.setEnabled(True)
            self.save_btn.setEnabled(True)

    def _on_export_error(self, exc: object):
        #print(f'[GUI] _on_export_error called: {exc}')
        self.progress.setVisible(False)
        self.status_label.setText('Export failed')
        QtWidgets.QMessageBox.critical(self, 'Export failed', str(exc))
        self.export_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def _reset_edits(self):
        if getattr(self, 'original_image_bytes', None):
            # reset sliders and filter
            self.filter_combo.setCurrentIndex(0)
            self.brightness_slider.setValue(100)
            self.contrast_slider.setValue(100)
            self.saturation_slider.setValue(100)
            self.vignette_slider.setValue(0)
            self.sharpness_slider.setValue(100)
            # restore original image
            # Resetting is considered a change: push current to undo and clear redo
            try:
                self._undo_stack.append(self.original_image_bytes)
                self._redo_stack.clear()
            except Exception:
                pass
            pix = QtGui.QPixmap()
            pix.loadFromData(self.original_image_bytes)
            self.current_pixmap = pix
            self.edited_image_bytes = self.original_image_bytes
            self._update_image_label()
            self._update_undo_redo_buttons()

    def _push_state_and_apply(self, new_bytes: bytes):
        # Helper to push current original to undo and set new original
        try:
            self._undo_stack.append(self.original_image_bytes)
            self._redo_stack.clear()
        except Exception:
            pass
        self.original_image_bytes = new_bytes
        self.edited_image_bytes = new_bytes
        pix = QtGui.QPixmap()
        pix.loadFromData(new_bytes)
        self.current_pixmap = pix
        self._update_image_label()
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(len(self._undo_stack) > 0)
        self.redo_btn.setEnabled(len(self._redo_stack) > 0)

    def _add_prompt_history(self, prompt: str, max_items: int = 50):
        """Add a prompt to the editable combo's history, avoiding duplicates."""
        if not prompt:
            return
        try:
            # remove existing occurrence
            for i in range(self.prompt_combo.count() - 1, -1, -1):
                if self.prompt_combo.itemText(i) == prompt:
                    self.prompt_combo.removeItem(i)
            # insert at top
            self.prompt_combo.insertItem(0, prompt)
            self.prompt_combo.setCurrentIndex(0)
            # trim
            while self.prompt_combo.count() > max_items:
                self.prompt_combo.removeItem(self.prompt_combo.count() - 1)
            # persist to disk
            self._save_prompt_history()
        except Exception:
            pass

    def _get_history_file_path(self) -> Path:
        """Get the path to the prompt history JSON file."""
        app_data = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
        if not app_data:
            app_data = os.path.expanduser("~/.gemini_imagegen")
        data_dir = Path(app_data)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "prompt_history.json"

    def _save_prompt_history(self):
        """Save current prompt history to disk."""
        try:
            history = [self.prompt_combo.itemText(i) for i in range(self.prompt_combo.count())]
            history_file = self._get_history_file_path()
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'Failed to save prompt history: {e}')

    def _load_prompt_history(self):
        """Load prompt history from disk on startup."""
        try:
            history_file = self._get_history_file_path()
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                if isinstance(history, list):
                    for prompt in history[:50]:  # limit to 50
                        if isinstance(prompt, str) and prompt.strip():
                            self.prompt_combo.addItem(prompt)
        except Exception as e:
            print(f'Failed to load prompt history: {e}')

    def _undo(self):
        if not self._undo_stack:
            return
        try:
            # push current original to redo, pop last undo
            self._redo_stack.append(self.original_image_bytes)
            prev = self._undo_stack.pop()
            self.original_image_bytes = prev
            self.edited_image_bytes = prev
            pix = QtGui.QPixmap()
            pix.loadFromData(prev)
            self.current_pixmap = pix
            self._update_image_label()
        finally:
            self._update_undo_redo_buttons()

    def _redo(self):
        if not self._redo_stack:
            return
        try:
            self._undo_stack.append(self.original_image_bytes)
            nxt = self._redo_stack.pop()
            self.original_image_bytes = nxt
            self.edited_image_bytes = nxt
            pix = QtGui.QPixmap()
            pix.loadFromData(nxt)
            self.current_pixmap = pix
            self._update_image_label()
        finally:
            self._update_undo_redo_buttons()

    def _apply_edits_bytes(self, image_bytes: bytes, settings: dict) -> bytes:
        # Use Pillow to apply edits and return PNG bytes
        bio = io.BytesIO(image_bytes)
        img = Image.open(bio).convert('RGB')

        # Filters
        filt = settings.get('filter', 'None')
        if filt == 'Grayscale':
            img = ImageOps.grayscale(img).convert('RGB')
        elif filt == 'Sepia':
            sep = ImageOps.colorize(ImageOps.grayscale(img), '#704214', '#C0A080')
            img = sep
        elif filt == 'Blur':
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
        elif filt == 'Sharpen':
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

        # Brightness, Contrast, Saturation
        bri = settings.get('brightness', 1.0)
        con = settings.get('contrast', 1.0)
        sat = settings.get('saturation', 1.0)
        if bri != 1.0:
            img = ImageEnhance.Brightness(img).enhance(bri)
        if con != 1.0:
            img = ImageEnhance.Contrast(img).enhance(con)
        if sat != 1.0:
            img = ImageEnhance.Color(img).enhance(sat)

        # Vignette (darken corners)
        vig = settings.get('vignette', 0.0)
        if vig and vig > 0.0:
            width, height = img.size
            # create radial mask
            vignette = Image.new('L', (width, height), 255)
            for y in range(height):
                for x in range(width):
                    # distance to center
                    dx = (x - width / 2) / (width / 2)
                    dy = (y - height / 2) / (height / 2)
                    d = (dx * dx + dy * dy) ** 0.5
                    # mask value decreases with distance
                    val = 255 - int(255 * min(1.0, (d - 0.0) * vig * 1.5))
                    vignette.putpixel((x, y), max(0, min(255, val)))
            img.putalpha(vignette)
            background = Image.new('RGB', img.size, (0, 0, 0))
            background.paste(img, mask=img.split()[3])
            img = background

        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue()

    def on_save(self):
        if not self.current_pixmap:
            return
        default_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.PicturesLocation) or os.path.expanduser("~/Pictures")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save as PNG", default_dir, "PNG Files (*.png)")
        if path:
            # Ensure PNG extension
            if not path.lower().endswith('.png'):
                path += '.png'
            try:
                if getattr(self, 'edited_image_bytes', None):
                    with open(path, 'wb') as f:
                        f.write(self.edited_image_bytes)
                else:
                    # fallback to pixmap save
                    saved = self.current_pixmap.save(path, "PNG")
                    if not saved:
                        raise RuntimeError('QPixmap failed to save')
                self.status_label.setText(f"Saved to {path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Save failed", str(e))
