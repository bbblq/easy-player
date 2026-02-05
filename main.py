import sys
import os
import subprocess # 必须导入这个

# ============================================================================
# 【核心修复】强制隐藏所有子进程（FFmpeg）的黑框
# 这段代码必须放在所有其他 import 之前（除了 sys/os/subprocess）
# ============================================================================
if os.name == 'nt': # 仅在 Windows 下生效
    original_popen = subprocess.Popen

    class NoConsolePopen(original_popen):
        def __init__(self, *args, **kwargs):
            startupinfo = kwargs.get('startupinfo')
            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
            
            # 关键：设置窗口显示标志为“隐藏”
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            kwargs['startupinfo'] = startupinfo
            super().__init__(*args, **kwargs)

    # 替换系统的 Popen，从此 Pydub 调用 FFmpeg 就不会有黑框了
    subprocess.Popen = NoConsolePopen
# ============================================================================

import tempfile
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSlider, 
                             QFileDialog, QScrollArea, QComboBox, QCheckBox, QFrame,
                             QMessageBox, QProgressBar, QDoubleSpinBox)
from PyQt6.QtCore import Qt, QUrl, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

# --- 配置文件路径 ---
CONFIG_FILE = "bgm_config.json"

# --- Pydub 配置与 FFmpeg 检测 ---
HAS_PYDUB = False
try:
    from pydub import AudioSegment
    from pydub.utils import which
    
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    local_ffmpeg = os.path.join(base_path, "ffmpeg.exe")
    local_ffprobe = os.path.join(base_path, "ffprobe.exe")

    if os.path.exists(local_ffmpeg):
        os.environ["PATH"] += os.pathsep + base_path
        AudioSegment.converter = local_ffmpeg
        HAS_PYDUB = True
    elif which("ffmpeg") is not None:
        HAS_PYDUB = True
except ImportError:
    pass

class AudioBoosterThread(QThread):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            if not HAS_PYDUB: raise Exception("未找到 ffmpeg 环境")
            if not os.path.exists(self.file_path): raise Exception("源文件不存在")
                
            audio = AudioSegment.from_file(self.file_path)
            boosted_audio = audio + 6 
            temp_dir = tempfile.gettempdir()
            filename = f"boosted_{os.path.basename(self.file_path)}.wav"
            temp_path = os.path.join(temp_dir, filename)
            boosted_audio.export(temp_path, format="wav")
            self.finished.emit(self.file_path, temp_path)
        except Exception as e:
            self.error.emit(str(e))
class AudioTrackWidget(QFrame):
    def __init__(self, file_path, device_info, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        self.setStyleSheet("""
            QFrame { 
                background-color: #FFFFFF; 
                border: 2px solid #555555; 
                border-radius: 8px; 
                margin-bottom: 10px;
            }
            QLabel { 
                color: #000000; 
                font-weight: bold;
                border: none;
                background-color: transparent;
            }
            QPushButton { 
                background-color: #EEEEEE; 
                color: #000000; 
                border: 2px solid #444444; 
                border-radius: 6px; 
                padding: 6px 15px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #DDDDDD; 
                border-color: #000000;
            }
            QCheckBox {
                color: #000000;
                font-weight: bold;
            }
        """)
        
        self.original_path = file_path
        self.current_source = file_path 
        self.is_boosted = False
        self.is_dragging = False
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setDevice(device_info)
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.audio_output.setVolume(1.0)
        
        self.fade_timer = QTimer()
        self.fade_timer.setInterval(50) 
        self.fade_timer.timeout.connect(self._process_fade_step)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Row 1
        row1 = QHBoxLayout()
        
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.setMinimumWidth(100)
        self.btn_play.setMinimumHeight(40)
        self.btn_play.clicked.connect(self.toggle_play)
        
        self.btn_fade_stop = QPushButton("📉 渐隐")
        self.btn_fade_stop.setMinimumWidth(100)
        self.btn_fade_stop.setMinimumHeight(40)
        self.btn_fade_stop.clicked.connect(self.fade_out_stop)
        
        name = os.path.basename(file_path)
        self.lbl_name = QLabel(name)
        font = QFont()
        font.setPointSize(16) 
        font.setBold(True)
        self.lbl_name.setFont(font)
        self.lbl_name.setStyleSheet("color: #000000;")
        
        self.btn_boost = QPushButton("🚀 200%")
        self.btn_boost.setCheckable(True)
        self.btn_boost.setMinimumWidth(100)
        self.btn_boost.setMinimumHeight(40)
        self.btn_boost.clicked.connect(self.toggle_boost)
        if not HAS_PYDUB:
            self.btn_boost.setEnabled(False)
            self.btn_boost.setText("无组件")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setVisible(False)
        
        row1.addWidget(self.btn_play)
        row1.addSpacing(15)
        row1.addWidget(self.btn_fade_stop)
        row1.addSpacing(20)
        row1.addWidget(self.lbl_name, 1)
        row1.addWidget(self.progress_bar)
        row1.addSpacing(15)
        row1.addWidget(self.btn_boost)
        
        # Row 2
        row2 = QHBoxLayout()
        
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setFont(QFont("Consolas", 14))
        self.lbl_time.setFixedWidth(150)
        self.lbl_time.setStyleSheet("color: #333333;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimumHeight(35)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #999; height: 12px; background: #E0E0E0; border-radius: 6px; }
            QSlider::handle:horizontal { background: #0078D7; border: 2px solid #000; width: 24px; height: 24px; margin: -8px 0; border-radius: 12px; }
        """)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.sliderMoved.connect(self.on_slider_moved)

        self.chk_loop = QCheckBox("循环")
        self.chk_loop.setFont(QFont("微软雅黑", 14))
        self.chk_loop.setChecked(True)
        self.chk_loop.toggled.connect(self.set_loop_mode)
        self.set_loop_mode(True)
        
        lbl_vol = QLabel("音量")
        lbl_vol.setFont(QFont("微软雅黑", 12))
        
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(120)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 8px; background: #CCC; }
            QSlider::handle:horizontal { background: #555; width: 18px; margin: -5px 0; border-radius: 9px; }
        """)
        self.vol_slider.valueChanged.connect(self.set_volume)

        self.lbl_vol_val = QLabel("100%")
        self.lbl_vol_val.setFont(QFont("Consolas", 12))
        self.lbl_vol_val.setFixedWidth(50)
        self.lbl_vol_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vol_val.setStyleSheet("color: #333; font-weight: bold;")

        row2.addWidget(self.lbl_time)
        row2.addWidget(self.slider)
        row2.addSpacing(20)
        row2.addWidget(self.chk_loop)
        row2.addSpacing(20)
        row2.addWidget(lbl_vol)
        row2.addWidget(self.vol_slider)
        row2.addWidget(self.lbl_vol_val)

        self.layout.addLayout(row1)
        self.layout.addLayout(row2)
        
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.mediaStatusChanged.connect(self.check_media_status)

    def toggle_boost(self):
        if self.btn_boost.isChecked(): self.start_boost_process()
        else: self.switch_source(self.original_path, is_boosted=False)
    
    def start_boost_process(self):
        self.btn_boost.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_name.setText("正在处理增益...")
        self.boost_thread = AudioBoosterThread(self.original_path)
        self.boost_thread.finished.connect(self.on_boost_finished)
        self.boost_thread.error.connect(self.on_boost_error)
        self.boost_thread.start()

    def on_boost_finished(self, orig_path, temp_path):
        self.progress_bar.setVisible(False)
        self.btn_boost.setEnabled(True)
        self.lbl_name.setText(os.path.basename(orig_path) + " (MAX)")
        self.lbl_name.setStyleSheet("color: #D93025;")
        self.switch_source(temp_path, is_boosted=True)

    def on_boost_error(self, err_msg):
        self.progress_bar.setVisible(False)
        self.btn_boost.setEnabled(True)
        self.btn_boost.setChecked(False)
        self.lbl_name.setText(os.path.basename(self.original_path))
        self.lbl_name.setStyleSheet("color: #000000;")
        # 错误日志静默打印到控制台，避免弹窗打扰
        print(f"增益错误: {err_msg}")

    def switch_source(self, path, is_boosted):
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        position = self.player.position()
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.current_source = path
        self.is_boosted = is_boosted
        if was_playing:
            self.player.setPosition(max(0, position - 500))
            self.player.play()
        if not is_boosted:
            self.lbl_name.setText(os.path.basename(self.original_path))
            self.lbl_name.setStyleSheet("color: #000000;")

    def fade_out_stop(self):
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState: return
        self.btn_fade_stop.setEnabled(False)
        self.btn_play.setEnabled(False)
        
        duration_sec = self.window().fade_spin.value()
        duration_ms = duration_sec * 1000
        
        self.fade_steps_left = int(duration_ms / 50)
        if self.fade_steps_left < 1: self.fade_steps_left = 1
            
        current_vol = self.audio_output.volume()
        self.fade_vol_step = current_vol / self.fade_steps_left
        self.fade_timer.start()

    def _process_fade_step(self):
        if self.fade_steps_left > 0:
            new_vol = self.audio_output.volume() - self.fade_vol_step
            self.audio_output.setVolume(max(0, new_vol))
            self.fade_steps_left -= 1
        else:
            self.fade_timer.stop()
            self.player.stop()
            target_vol = self.vol_slider.value() / 100.0
            self.audio_output.setVolume(target_vol)
            self.btn_fade_stop.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_play.setText("▶ 播放")

    def toggle_play(self):
        if self.fade_timer.isActive():
            self.fade_timer.stop()
            target_vol = self.vol_slider.value() / 100.0
            self.audio_output.setVolume(target_vol)
            self.btn_fade_stop.setEnabled(True)
            self.btn_play.setEnabled(True)
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶ 继续")
        else:
            self.player.play()
            self.btn_play.setText("⏸ 暂停")
    def stop_instant(self):
        self.fade_timer.stop()
        self.player.stop()
        self.btn_play.setText("▶ 播放")
        target_vol = self.vol_slider.value() / 100.0
        self.audio_output.setVolume(target_vol)
    def set_output_device(self, device_info):
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        pos = self.player.position()
        self.audio_output.setDevice(device_info)
        if was_playing: self.player.play()
        else: self.player.setPosition(pos)
    def update_position(self, position):
        if not self.is_dragging:
            self.slider.setValue(position)
            self.lbl_time.setText(f"{self.format_time(position)} / {self.duration_str}")
    def update_duration(self, duration):
        self.slider.setRange(0, duration)
        self.duration_str = self.format_time(duration)
        self.lbl_time.setText(f"00:00 / {self.duration_str}")
    def on_slider_pressed(self): self.is_dragging = True
    def on_slider_moved(self, pos): self.lbl_time.setText(f"{self.format_time(pos)} / {self.duration_str}")
    def on_slider_released(self):
        self.player.setPosition(self.slider.value())
        self.is_dragging = False
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()
            self.btn_play.setText("⏸ 暂停")
    def set_loop_mode(self, checked):
        self.player.setLoops(QMediaPlayer.Loops.Infinite if checked else 1)
    def set_volume(self, value):
        self.lbl_vol_val.setText(f"{value}%")
        if not self.fade_timer.isActive(): self.audio_output.setVolume(value / 100.0)
    def check_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and not self.chk_loop.isChecked():
            self.btn_play.setText("▶ 播放")
    def format_time(self, ms):
        s = (ms // 1000) % 60
        m = (ms // 60000)
        return f"{m:02d}:{s:02d}"
    def cleanup(self):
        self.player.stop()
        if self.is_boosted and os.path.exists(self.current_source):
            try: os.remove(self.current_source)
            except: pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("接力年会 BGM 控制台 v11.0 by liqi")
        self.resize(1200, 900)
        self.tracks = []
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # --- Top Bar ---
        top_frame = QFrame()
        top_frame.setFixedHeight(80)
        top_frame.setStyleSheet("""
            QFrame { background-color: #222222; border-bottom: 2px solid #000; }
            QLabel { color: #FFFFFF; font-weight: bold; }
        """)
        top_layout = QHBoxLayout(top_frame)
        
        lbl_dev = QLabel("🔊 输出:")
        lbl_dev.setFont(QFont("微软雅黑", 14))
        
        self.combo_devices = QComboBox()
        self.combo_devices.setMinimumWidth(300)
        self.combo_devices.setMinimumHeight(45)
        self.combo_devices.setFont(QFont("微软雅黑", 12))
        self.combo_devices.setStyleSheet("""
            QComboBox { background-color: #FFFFFF; color: #000000; border-radius: 5px; padding: 5px; }
            QComboBox QAbstractItemView { background-color: #FFFFFF; color: #000000; selection-background-color: #0078D7; }
        """)
        self.refresh_devices()
        self.combo_devices.currentIndexChanged.connect(self.change_device_global)
        
        lbl_fade = QLabel("渐隐(秒):")
        lbl_fade.setFont(QFont("微软雅黑", 14))
        lbl_fade.setStyleSheet("color: #FFFFFF; margin-left: 10px;")
        
        self.fade_spin = QDoubleSpinBox()
        self.fade_spin.setRange(0.1, 10.0)
        self.fade_spin.setValue(1.0)
        self.fade_spin.setSingleStep(0.5)
        self.fade_spin.setMinimumHeight(45)
        self.fade_spin.setMinimumWidth(80)
        self.fade_spin.setFont(QFont("Consolas", 14))
        self.fade_spin.setStyleSheet("background-color: #FFFFFF; color: #000000;")
        
        top_layout.addWidget(lbl_dev)
        top_layout.addWidget(self.combo_devices)
        top_layout.addWidget(lbl_fade)
        top_layout.addWidget(self.fade_spin)
        
        btn_qss = "QPushButton { font-size: 16px; font-weight: bold; color: white; border-radius: 6px; padding: 0 20px; }"
        
        btn_add = QPushButton("➕ 加歌")
        btn_add.setMinimumHeight(45)
        btn_add.setStyleSheet(btn_qss + "background-color: #0078D7;")
        btn_add.clicked.connect(self.add_files)
        
        btn_fade_all = QPushButton("📉 全部渐隐")
        btn_fade_all.setMinimumHeight(45)
        btn_fade_all.setStyleSheet(btn_qss + "background-color: #D6A000;")
        btn_fade_all.clicked.connect(self.fade_stop_all)

        btn_kill_all = QPushButton("🛑 急停")
        btn_kill_all.setMinimumHeight(45)
        btn_kill_all.setStyleSheet(btn_qss + "background-color: #D93025;")
        btn_kill_all.clicked.connect(self.kill_all)
        
        top_layout.addStretch()
        top_layout.addWidget(btn_add)
        top_layout.addSpacing(10)
        top_layout.addWidget(btn_fade_all)
        top_layout.addSpacing(10)
        top_layout.addWidget(btn_kill_all)
        
        main_layout.addWidget(top_frame)
        
        if not HAS_PYDUB:
            msg = QLabel("⚠️ 未检测到 FFmpeg 工具包！自动记忆的200%状态将无法恢复。")
            msg.setStyleSheet("color: red; font-size: 16px; font-weight: bold; padding: 5px;")
            main_layout.addWidget(msg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: #F0F0F0;")
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #F0F0F0;") 
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(15)
        scroll.setWidget(self.scroll_content)
        main_layout.addWidget(scroll)

        self.load_settings()

    def refresh_devices(self):
        self.output_devices = QMediaDevices.audioOutputs()
        self.combo_devices.clear()
        default = QMediaDevices.defaultAudioOutput()
        cur = 0
        for i, d in enumerate(self.output_devices):
            self.combo_devices.addItem(d.description())
            if d.id() == default.id(): cur = i
        if self.output_devices: self.combo_devices.setCurrentIndex(cur)
        
    def change_device_global(self):
        idx = self.combo_devices.currentIndex()
        if idx >= 0:
            dev = self.output_devices[idx]
            for t in self.tracks: t.set_output_device(dev)
            
    def add_files(self):
        fps, _ = QFileDialog.getOpenFileNames(self, "选歌", "", "Audio (*.mp3 *.wav *.ogg *.flac *.m4a)")
        self._add_files_internal(fps)

    def _add_files_internal(self, file_paths):
        dev = self.output_devices[self.combo_devices.currentIndex()] if self.output_devices else QMediaDevices.defaultAudioOutput()
        new_widgets = []
        for fp in file_paths:
            if any(t.original_path == fp for t in self.tracks): continue
            if not os.path.exists(fp): continue
            
            w = AudioTrackWidget(fp, dev)
            self.scroll_layout.addWidget(w)
            self.tracks.append(w)
            new_widgets.append(w)
        return new_widgets

    def fade_stop_all(self):
        for t in self.tracks:
            if t.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: t.fade_out_stop()
    def kill_all(self):
        for t in self.tracks: t.stop_instant()

    def load_settings(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            dev_name = settings.get("device_name", "")
            if dev_name:
                idx = self.combo_devices.findText(dev_name)
                if idx >= 0: self.combo_devices.setCurrentIndex(idx)
            
            self.fade_spin.setValue(settings.get("fade_duration", 1.0))
            
            saved_tracks = settings.get("tracks", [])
            paths = [t["path"] for t in saved_tracks]
            created_widgets = self._add_files_internal(paths)
            
            widget_map = {w.original_path: w for w in created_widgets}
            
            for t_data in saved_tracks:
                path = t_data["path"]
                if path in widget_map:
                    w = widget_map[path]
                    w.vol_slider.setValue(t_data.get("volume", 100))
                    w.chk_loop.setChecked(t_data.get("loop", True))
                    if t_data.get("boost", False) and HAS_PYDUB:
                        w.btn_boost.setChecked(True)
                        w.start_boost_process()
                        
        except Exception as e:
            print(f"加载配置失败: {e}")

    def save_settings(self):
        settings = {
            "device_name": self.combo_devices.currentText(),
            "fade_duration": self.fade_spin.value(),
            "tracks": []
        }
        for t in self.tracks:
            settings["tracks"].append({
                "path": t.original_path,
                "volume": t.vol_slider.value(),
                "loop": t.chk_loop.isChecked(),
                "boost": t.btn_boost.isChecked()
            })
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def closeEvent(self, e):
        self.save_settings()
        for t in self.tracks: t.cleanup()
        e.accept()

if __name__ == "__main__":
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    font = app.font()
    font.setPointSize(12) 
    font.setFamily("Microsoft YaHei")
    app.setFont(font)
    
    os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.info=false"
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
