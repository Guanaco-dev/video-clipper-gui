import sys
import os
import subprocess
import json
import threading
import re
import shutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTimeEdit,
    QFileDialog, QTextEdit, QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt, QTime, QThread, Signal
from PySide6.QtGui import QFont, QIcon

# --- Helper functions (unchanged) ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def check_dependencies():
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    return missing

def show_dependency_error_dialog(missing_deps):
    # This function is unchanged...
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("Dependencies Missing")
    missing_str = " and ".join(f"`{dep}`" for dep in missing_deps)
    msg_box.setText(f"This application requires {missing_str} to function.")
    instructions = "Please install the missing components by running the following commands in your terminal, then restart the application:\n\n"
    if "yt-dlp" in missing_deps:
        instructions += ("# To install yt-dlp (recommended):\n"
                         "sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp\n"
                         "sudo chmod a+rx /usr/local/bin/yt-dlp\n\n"
                         "# Or to update an existing installation:\n"
                         "sudo yt-dlp -U\n\n")
    if "ffmpeg" in missing_deps:
        instructions += ("# To install ffmpeg (for Debian/Ubuntu/Mint):\n"
                         "sudo apt update && sudo apt install ffmpeg\n")
    msg_box.setDetailedText(instructions)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec()

# --- Worker Thread (unchanged from previous fix) ---
class Worker(QThread):
    # ... (This class is exactly the same as the previous version) ...
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.process = None

    def run(self):
        try:
            self.process = subprocess.Popen(
                self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace'
            )
            full_output = ""
            for line in iter(self.process.stdout.readline, ''):
                self.progress.emit(line.strip())
                full_output += line
            
            return_code = self.process.wait()
            is_json_dump = '-j' in self.command or '--dump-json' in self.command

            if is_json_dump:
                try:
                    json_start_index = full_output.find('{')
                    if json_start_index != -1:
                        json_data_string = full_output[json_start_index:]
                        json_output = json.loads(json_data_string)
                        self.finished.emit(json_output)
                    else:
                        self.error.emit("Could not find video information in the output.")
                except json.JSONDecodeError:
                    self.error.emit("Failed to parse video information from yt-dlp's output.")
            elif return_code == 0:
                self.finished.emit(None)
            else:
                self.error.emit(f"Process finished with error code {return_code}")
        except FileNotFoundError:
            self.error.emit(f"Error: Command '{self.command[0]}' not found. Is it in your PATH?")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred: {e}")


# --- Main Application Window ---
class YtdlpGui(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... (init is mostly the same) ...
        self.setWindowTitle("Video Clipper GUI")
        self.setGeometry(100, 100, 700, 600)
        app_icon = QIcon(resource_path("icon.png"))
        self.setWindowIcon(app_icon)
        self.video_info = None
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self._create_url_widgets()
        self._create_info_widgets()
        self._create_quality_widgets()
        self._create_clipping_widgets()
        self._create_output_widgets()
        self._create_action_widgets()
        self._create_log_widgets()
        self.update_ui_state(initial=True)
        
        # --- NEW: Connect the video combo box signal to its handler ---
        self.video_quality_combo.currentIndexChanged.connect(self._on_video_quality_changed)

    # --- NEW: Handler for video quality selection change ---
    def _on_video_quality_changed(self, index):
        """Enable/disable the audio dropdown based on video selection."""
        if index < 0: return
        video_data = self.video_quality_combo.itemData(index)
        if video_data:
            # If the selected video is pre-merged (has audio), disable audio selection.
            is_merged = video_data.get('merged', False)
            self.audio_quality_combo.setEnabled(not is_merged)

    def on_fetch_finished(self, info):
        """Populate UI controls with fetched video data. This is heavily modified."""
        if not info:
            self.on_fetch_error("Received empty video information.")
            return

        self.log_output.append("\nSuccessfully parsed video information!")
        self.video_info = info
        self.title_label.setText(f"Video Title: {self.video_info.get('title', 'N/A')}")
        duration = self.video_info.get('duration', 0)
        duration_time = QTime(0, 0, 0).addSecs(int(duration or 0))
        self.duration_label.setText(f"Duration: {duration_time.toString('HH:mm:ss')}")
        self.end_time_edit.setTime(duration_time)
        self.end_time_edit.setMaximumTime(duration_time)
        self.start_time_edit.setMaximumTime(duration_time)
        self.start_time_edit.setTime(QTime(0, 0, 0))

        # --- MODIFIED LOGIC ---
        self.video_quality_combo.clear()
        self.audio_quality_combo.clear()
        
        # Sort formats by quality to show best ones first
        formats = sorted(self.video_info.get('formats', []), key=lambda x: x.get('height', 0) or 0, reverse=True)

        for f in formats:
            format_id = f.get('format_id')
            ext = f.get('ext')
            height = f.get('height')
            
            # --- Video Streams (including pre-merged) ---
            if f.get('vcodec') != 'none' and height:
                is_merged = f.get('acodec') != 'none'
                note = " (Video+Audio)" if is_merged else " (Video Only)"
                
                label = f"{height}p ({f.get('fps', 'N/A')}fps, {ext}){note}"
                # Store if it's merged so we can check it later
                self.video_quality_combo.addItem(label, {'id': format_id, 'merged': is_merged})

            # --- Audio Only Streams ---
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                label = f"{f.get('abr', 0)}k ({f.get('acodec')}, {ext})"
                self.audio_quality_combo.addItem(label, format_id)

        self.update_ui_state(info_loaded=True)
        # Trigger the check immediately for the default selection
        self._on_video_quality_changed(self.video_quality_combo.currentIndex())


    def download_clip(self):
        """Builds the yt-dlp command based on selection. This is modified."""
        video_data = self.video_quality_combo.currentData()
        if not video_data:
            QMessageBox.warning(self, "Selection Error", "Please select a video quality.")
            return

        video_format_id = video_data['id']
        is_video_merged = video_data['merged']
        
        # --- MODIFIED LOGIC ---
        if is_video_merged:
            # If the video is pre-merged, use only its format ID
            formats_to_dl = video_format_id
        else:
            # If video-only, combine it with an audio format
            audio_format_id = self.audio_quality_combo.currentData()
            if not audio_format_id:
                QMessageBox.warning(self, "Selection Error", "This video format has no audio. Please select an audio format to merge.")
                return
            formats_to_dl = f"{video_format_id}+{audio_format_id}"
        
        # ... (The rest of the function for time, path, and execution is unchanged) ...
        start_time = self.start_time_edit.time().toString("HH:mm:ss")
        end_time = self.end_time_edit.time().toString("HH:mm:ss")
        if self.start_time_edit.time() >= self.end_time_edit.time():
            QMessageBox.warning(self, "Time Error", "Start time must be before end time.")
            return
        output_path = self.output_path_input.text()
        filename = self.filename_input.text().strip()
        if not filename:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", self.video_info.get('title', 'video'))
            output_template = os.path.join(output_path, f"{safe_title}.%(ext)s")
        else:
            output_template = os.path.join(output_path, f"{filename}.%(ext)s")
        command = ['yt-dlp', '-f', formats_to_dl, '--download-sections', f"*{start_time}-{end_time}", '--force-keyframes-at-cuts', '--merge-output-format', 'mkv', '-o', output_template, self.video_info.get('webpage_url')]
        self.log_output.append("\n" + "="*50)
        self.log_output.append("Starting download with command:")
        self.log_output.append(" ".join(f"'{c}'" if " " in c else c for c in command))
        self.log_output.append("="*50 + "\n")
        self.update_ui_state(downloading=True)
        self.worker = Worker(command)
        self.worker.progress.connect(self.update_log)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

    # --- Other methods are unchanged ---
    # ... (All other methods like _create_widgets, update_ui_state, on_fetch_error, etc., are unchanged) ...
    # ...
    # --- Main execution block is unchanged ---
    # ...
    # (Just pasting the full class again for completeness)
    def _create_url_widgets(self):
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL here")
        self.fetch_button = QPushButton("Fetch Info")
        self.fetch_button.clicked.connect(self.fetch_video_info)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_button)
        self.main_layout.addLayout(url_layout)

    def _create_info_widgets(self):
        self.title_label = QLabel("Video Title: (fetch info to see)")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        self.duration_label = QLabel("Duration: 00:00:00")
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.duration_label)

    def _create_quality_widgets(self):
        quality_layout = QFormLayout()
        self.video_quality_combo = QComboBox()
        self.audio_quality_combo = QComboBox()
        quality_layout.addRow("Video Quality:", self.video_quality_combo)
        quality_layout.addRow("Audio Quality:", self.audio_quality_combo)
        self.main_layout.addLayout(quality_layout)

    def _create_clipping_widgets(self):
        clip_layout = QFormLayout()
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        clip_layout.addRow("Clip Start Time:", self.start_time_edit)
        clip_layout.addRow("Clip End Time:", self.end_time_edit)
        self.main_layout.addLayout(clip_layout)

    def _create_output_widgets(self):
        output_path_layout = QHBoxLayout()
        self.output_path_input = QLineEdit(os.path.expanduser("~"))
        self.output_path_input.setReadOnly(True)
        change_loc_button = QPushButton("Change Location")
        change_loc_button.clicked.connect(self.select_output_location)
        output_path_layout.addWidget(self.output_path_input)
        output_path_layout.addWidget(change_loc_button)
        self.main_layout.addLayout(output_path_layout)
        filename_layout = QFormLayout()
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Leave blank for default (video title)")
        filename_layout.addRow("Output Filename:", self.filename_input)
        self.main_layout.addLayout(filename_layout)

    def _create_action_widgets(self):
        self.download_button = QPushButton("✂️ Clip and Download")
        self.download_button.setFixedHeight(40)
        self.download_button.clicked.connect(self.download_clip)
        self.main_layout.addWidget(self.download_button)

    def _create_log_widgets(self):
        log_label = QLabel("Log:")
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Monospace", 9))
        self.main_layout.addWidget(log_label)
        self.main_layout.addWidget(self.log_output)
    
    def update_ui_state(self, initial=False, fetching=False, info_loaded=False, downloading=False):
        if initial:
            self.download_button.setEnabled(False)
            self.video_quality_combo.setEnabled(False)
            self.audio_quality_combo.setEnabled(False)
        self.fetch_button.setEnabled(not (fetching or downloading))
        self.url_input.setEnabled(not (fetching or downloading))
        can_download = info_loaded and not downloading and not fetching
        self.download_button.setEnabled(can_download)
        self.video_quality_combo.setEnabled(can_download)
        self.audio_quality_combo.setEnabled(can_download)

    def fetch_video_info(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a video URL.")
            return
        self.log_output.clear()
        self.log_output.append(f"Fetching info for: {url}...")
        self.update_ui_state(fetching=True)
        command = ['yt-dlp', '--dump-json', url]
        self.worker = Worker(command)
        self.worker.progress.connect(self.update_log)
        self.worker.finished.connect(self.on_fetch_finished)
        self.worker.error.connect(self.on_fetch_error)
        self.worker.start()

    def on_fetch_error(self, error_message):
        self.log_output.append(f"\nERROR: {error_message}")
        QMessageBox.critical(self, "Error", f"Failed to fetch video info.\n\n{error_message}")
        self.update_ui_state(info_loaded=False)

    def select_output_location(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if directory:
            self.output_path_input.setText(directory)
            
    def on_download_finished(self, _):
        self.log_output.append("\nDownload completed successfully!")
        self.update_ui_state(info_loaded=True)
        QMessageBox.information(self, "Success", "Video clip has been downloaded!")

    def on_download_error(self, error_message):
        self.log_output.append(f"\nDOWNLOAD ERROR: {error_message}")
        self.update_ui_state(info_loaded=True)
        QMessageBox.critical(self, "Download Error", f"The download failed.\n\nCheck the log for details.")

    def update_log(self, text):
        self.log_output.append(text)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    missing_dependencies = check_dependencies()
    if missing_dependencies:
        show_dependency_error_dialog(missing_dependencies)
        sys.exit(1)
    window = YtdlpGui()
    window.show()
    sys.exit(app.exec())
