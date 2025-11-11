"""
Cinematic Slideshow - 映画的なエフェクトを備えたスライドショーアプリケーション

Copyright (C) 2025 sitarj

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import os
import glob
import json
import random
import math
from typing import List, Tuple, Dict, Any
from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime

try:
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("Warning: pywin32 not installed. Windows shortcut creation disabled.") 
    
try:
    from PIL import Image
    import pillow_avif
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Warning: pillow-avif-plugin not installed. AVIF support disabled.")

PROFILES_FILE = "profiles.json"
ANIM_FPS = 24

# ネイティブでサポートされる形式
NATIVE_IMAGE_FORMATS = (
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", 
    ".webp", ".tiff", ".tif", ".ico", ".svg",
    ".cur", ".icns", ".pbm", ".pgm", ".ppm",
    ".tga", ".wbmp", ".xbm", ".xpm"
)

# Pillow経由でのみサポートされる形式
PILLOW_ONLY_FORMATS = (
    ".avif", ".heic", ".heif", ".jp2", ".j2k"
)

# 実際にサポートされる形式を決定
if PILLOW_AVAILABLE:
    SUPPORTED_IMAGE_FORMATS = NATIVE_IMAGE_FORMATS + PILLOW_ONLY_FORMATS
else:
    SUPPORTED_IMAGE_FORMATS = NATIVE_IMAGE_FORMATS

def create_pixmap_from_file(file_path: str) -> QtGui.QPixmap:
    """ファイルパスからQPixmapを作成（AVIF等の拡張形式対応）"""
    ext = os.path.splitext(file_path)[1].lower()
    
    # まずネイティブ形式として試す
    if ext in NATIVE_IMAGE_FORMATS:
        pixmap = QtGui.QPixmap(file_path)
        if not pixmap.isNull():
            return pixmap
    
    # Pillowで読み込みを試みる
    if PILLOW_AVAILABLE:
        try:
            with Image.open(file_path) as img:
                # 画像を完全にメモリに読み込む
                img.load()
                
                # RGBA形式に変換
                if img.mode == 'RGBA':
                    rgba_img = img.copy()
                elif img.mode == 'LA' or (img.mode == 'P' and 'transparency' in img.info):
                    rgba_img = img.convert('RGBA')
                else:
                    rgba_img = img.convert('RGB')
                
                # QImageに変換
                if rgba_img.mode == 'RGBA':
                    # バイトデータをコピーして保持
                    data = rgba_img.tobytes('raw', 'RGBA')
                    qimage = QtGui.QImage(
                        data, 
                        rgba_img.width, 
                        rgba_img.height, 
                        rgba_img.width * 4,
                        QtGui.QImage.Format_RGBA8888
                    )
                    # データのコピーを作成
                    qimage = qimage.copy()
                else:
                    data = rgba_img.tobytes('raw', 'RGB')
                    qimage = QtGui.QImage(
                        data, 
                        rgba_img.width, 
                        rgba_img.height, 
                        rgba_img.width * 3,
                        QtGui.QImage.Format_RGB888
                    )
                    qimage = qimage.copy()
                
                # メモリ解放
                del rgba_img
                del data
                
                # QPixmapに変換
                pixmap = QtGui.QPixmap.fromImage(qimage)
                return pixmap
                
        except Exception as e:
            print(f"Error loading {file_path} with Pillow: {e}")
    
    # 読み込み失敗
    return QtGui.QPixmap()

class SlideShowWindow(QtWidgets.QWidget):
    def reload_profile(self):
        """プロファイル設定を再読み込み"""
        if not self.main_window:
            return
            
        # 最新の設定を取得
        config = self.main_window.profiles.get(self.current_profile_name)
        if not config:
            return
            
        # 設定を更新
        self.interval_ms = max(1, int(config.get("interval_sec", 5) * 1000))
        self.ken_burns = config.get("ken_burns", True)
        self.ken_intensity = config.get("ken_intensity", 5)
        self.fit_mode = config.get("fit_mode", "cover")
        self.fade_duration_ms = config.get("fade_duration_ms", 1000)
        self.show_filename = config.get("show_filename", False)
        self.filename_v_pos = config.get("filename_v_pos", "bottom")
        self.filename_h_pos = config.get("filename_h_pos", "center")
        self.font_family = config.get("font_family", "游ゴシック")
        self.font_size = config.get("font_size", 18)
        self.font_bold = config.get("font_bold", True)
        self.filename_v_offset = config.get("filename_v_offset", 0)
        self.filename_h_offset = config.get("filename_h_offset", 0)
        self.effects = effects or {"crossfade": True}
        self.effects = config.get("effects", {"crossfade": True})
        self.effect_order = config.get("effect_order", "random")
        self.enabled_effects = [k for k, v in self.effects.items() if v]

        # タイマーを停止
        self.slide_timer.stop()
        self.animation_timer.stop()
        self.animating = False
        self.is_paused = False
        
        # 画像リストを更新
        new_image_files = []
        for item in config.get("folders", []):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                folder_path, recursive = item
            elif isinstance(item, str):
                folder_path, recursive = item, False
            else:
                continue
                
            if os.path.isdir(folder_path):
                try:
                    new_image_files.extend(list_images(folder_path, recursive))
                except Exception:
                    continue
        
        if new_image_files:
            # ランダム順序の設定に応じてシャッフル
            if config.get("random_order", True):
                random.shuffle(new_image_files)
            self.image_files = new_image_files
            # 現在のインデックスをリセット
            self.index = 0

            # 画像があれば最初の画像を表示
            if self.image_files:
                self._show_first_image()
        else:
            # 画像がない場合はメッセージを表示
            self._show_no_images_message()

    # MainWindow に設定画面を開くよう通知するシグナル
    showSettingsRequested = QtCore.pyqtSignal(str)
    switchProfileRequested = QtCore.pyqtSignal(str)

    def _select_next_effect(self):
        """次のエフェクトを選択"""
        if not self.enabled_effects:
            return "none"
            
        if self.effect_order == "random":
            return random.choice(self.enabled_effects)
        else:
            effect = self.enabled_effects[self.current_effect_index]
            
            self.current_effect_index = (self.current_effect_index + 1) % len(self.enabled_effects)
            return effect

    def showEvent(self, event):
        """ウィンドウが表示された後、一度だけ最初の画像を表示する。"""
        super().showEvent(event)

        if self.is_loading:
            return
        
        # 初回でない場合はスキップ
        if not self.image_files:
            # 画像ファイルが1枚もない場合はメッセージを表示
            self._show_no_images_message()
        elif not self.current_item:
            # 画像があるが初回表示の場合
            self._show_first_image()

    def _show_no_images_message(self):
        """画像がない場合のメッセージを表示"""
        # 既存のアイテムをクリア
        self.scene.clear()
        
        # ビューポートサイズを取得
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        
        # シーンの矩形を設定
        self.scene.setSceneRect(-vw/2, -vh/2, vw, vh)
        
        # 半透明の背景矩形
        bg_rect = QtWidgets.QGraphicsRectItem(-vw/2, -vh/2, vw, vh)
        bg_rect.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 150)))
        bg_rect.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.scene.addItem(bg_rect)
        
        # メッセージテキストを作成
        message_html = """
        <div style='
            width: 500px; 
            text-align: center; 
            color: white; 
            background-color: rgba(0,0,0,180); 
            padding: 40px; 
            border-radius: 10px; 
            border: 2px solid #555;
            font-family: "游ゴシック", "Yu Gothic", "YuGothic", sans-serif;
        '>
            <h1 style='color: #FFF; margin-bottom: 28px;'>🎬 Cinematic Slideshow</h1>
            <p style='font-size: 20px; line-height: 1.6; margin-bottom: 20px;'>
                映画的なスライドショーを開始するには<br>
                画像が保存されているフォルダを追加してください。
            </p>
            <p style='font-size: 16px; line-height: 1.6; margin-bottom: 20px; color: #CCC;'>
                <strong>右クリック → 設定</strong> から設定できます
            </p>
        </div>
        """
        
        text_item = QtWidgets.QGraphicsTextItem()
        text_item.setHtml(message_html)
        text_item.setTextWidth(500)
        
        # テキストアイテムのサイズを取得
        text_rect = text_item.boundingRect()
        
        # 完全に中央に配置
        text_x = -text_rect.width() / 2
        text_y = -text_rect.height() / 2
        text_item.setPos(text_x, text_y)
        text_item.setZValue(2.0)
        
        self.scene.addItem(text_item)
        
        # メッセージ用のアイテムとして保存
        self.current_item = text_item
            
    def __init__(
        self,
        image_files: List[str],
        current_profile_name: str,
        monitor_index: int = 0,
        stay_on_top: bool = True,
        interval_sec: int = 5,
        ken_burns: bool = True,
        ken_intensity: int = 5,
        random_order: bool = True,
        fit_mode: str = "cover",
        fade_duration_ms: int = 1000, 
        show_filename: bool = False,
        filename_v_pos: str = "bottom",
        filename_h_pos: str = "center",
        font_family: str = "游ゴシック",
        font_size: int = 18,
        font_bold: bool = True,
        filename_v_offset: int = 0,
        filename_h_offset: int = 0,
        effects: Dict[str, bool] = None,
        effect_order: str = "random",
        main_window: QtWidgets.QWidget = None,
    ):
        super().__init__()
        self.image_files = image_files[:]
        if random_order:
            random.shuffle(self.image_files)
        self.index = 0
        self.current_profile_name = current_profile_name
        self.main_window = main_window
        self.interval_ms = max(1, int(interval_sec * 1000))
        self.ken_burns = ken_burns
        self.ken_intensity = ken_intensity
        self.fit_mode = fit_mode
        self.fade_duration_ms = fade_duration_ms        
        self.show_filename = show_filename
        self.filename_v_pos = filename_v_pos
        self.filename_h_pos = filename_h_pos
        self.font_family = font_family
        self.font_size = font_size
        self.font_bold = font_bold
        self.filename_v_offset = filename_v_offset
        self.filename_h_offset = filename_h_offset
        self.effects = effects or {"crossfade": True}
        self.effect_order = effect_order
        self.enabled_effects = [k for k, v in self.effects.items() if v]
        self.current_effect_index = 0
        self.current_effect = None
        self.next_effect = None
        self.is_transitioning = False
        self.text_item = None
        self.is_paused = False

        # モニター指定
        screens = QtWidgets.QApplication.screens()
        if monitor_index >= len(screens):
            monitor_index = 0
        screen = screens[monitor_index]
        geom = screen.geometry()
        self.setGeometry(geom)

        # ウィンドウ
        if stay_on_top:
            flags = QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        else:
            flags = QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnBottomHint
            
        self.setWindowFlags(flags)

        self.view = QtWidgets.QGraphicsView(self)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.view.setAlignment(QtCore.Qt.AlignCenter)
        self.view.setStyleSheet("background-color: black;")
        self.scene = QtWidgets.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QBrush(QtCore.Qt.black))
        self.view.setScene(self.scene)

        # サイズ合わせ
        self.view.setGeometry(self.rect())

        # 次の pixmap item
        self.current_item = None
        self.next_item = None

        # 移動パターンの定義
        self.MOVEMENT_PATTERNS = ["linear", "arc", "wave", "spiral_in", "zigzag"]  

        # 移動パターン共通の変数
        self.current_movement_pattern = None

        # タイマー：一定間隔で次の画像へ
        self.slide_timer = QtCore.QTimer(self)
        self.slide_timer.setSingleShot(True)
        self.slide_timer.timeout.connect(self._on_slide_timeout)

        # アニメーションタイマー
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self._on_anim_frame)
        self.animating = False

        # アニメーション内部状態
        self.anim_start_time = 0
        self.anim_duration = self.interval_ms
        self.anim_fps_interval = int(1000 / ANIM_FPS)

        # キャッシュサイズの設定
        self._pixmap_cache = {}
        self._cache_max_size = 3

        # 画像読み込みエラーカウンター
        self._load_error_count = {}

        # ローディング画面
        self.loading_items = []
        self.is_loading = True

        if stay_on_top:
            self.showFullScreen()
        else:
            self.showNormal()
            self.setWindowState(QtCore.Qt.WindowMaximized)

        # ローディング画面表示
        self._show_loading_screen()

    def resizeEvent(self, event):
        """ウィンドウサイズ変更時の処理"""
        super().resizeEvent(event)
        self.view.setGeometry(self.rect())
        
        # シーンのサイズも更新
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        self.scene.setSceneRect(-vw/2, -vh/2, vw, vh)
        
        # テキスト位置を再計算
        if self.text_item and self.text_item.scene() == self.scene:
            self._update_text_position(self.text_item)
            
    def contextMenuEvent(self, event):
        """右クリック時にコンテキストメニューを表示する"""

        if hasattr(self, 'is_loading') and self.is_loading:
            return
        
        menu = QtWidgets.QMenu(self)

        # 次の画像
        action_next = menu.addAction("次の画像")
        action_next.triggered.connect(self._go_next)
        
        # 前の画像
        action_prev = menu.addAction("前の画像")
        action_prev.triggered.connect(self._go_prev)

        menu.addSeparator()

        # 一時停止
        action_pause = menu.addAction("一時停止/再開 (Space)")
        action_pause.setCheckable(True)
        action_pause.setChecked(self.is_paused)
        action_pause.triggered.connect(self._toggle_pause)

        menu.addSeparator()
        
        # 設定
        action_settings = menu.addAction("設定")
        action_settings.triggered.connect(lambda: self.showSettingsRequested.emit(self.current_profile_name))

        # エクスプローラーで開く
        action_explorer = menu.addAction("エクスプローラーで開く")
        action_explorer.setEnabled(bool(self.image_files))
        action_explorer.triggered.connect(self._open_in_explorer)
        
        # この画像を削除
        action_delete = menu.addAction("この画像を削除")
        action_delete.setEnabled(bool(self.image_files))
        action_delete.triggered.connect(self._delete_current_image)

        menu.addSeparator()

        # バージョン情報
        action_about = menu.addAction("バージョン情報")
        action_about.triggered.connect(self._show_about_dialog)

        # 終了
        action_exit = menu.addAction("終了 (Esc)")
        action_exit.triggered.connect(self.close)

        menu.exec_(event.globalPos())
        
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif event.key() == QtCore.Qt.Key_Space:
            self._toggle_pause()
        elif event.key() == QtCore.Qt.Key_Right:
            self._go_next()
        elif event.key() == QtCore.Qt.Key_Left:
            self._go_prev()

    def close(self):
        self.slide_timer.stop()
        if self.animation_timer.isActive():
            self.animation_timer.stop()

        if hasattr(self, 'main_window') and self.main_window:
            if hasattr(self.main_window, 'pause_action'):
                self.main_window.pause_action.setEnabled(False)

        super().close()
        
    # -------------------------
    # 操作メソッド
    # -------------------------
    def _toggle_pause(self):
        """一時停止/再開を切り替える"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            # 一時停止時
            self.slide_timer.stop()
            self.animation_timer.stop()
            
            # 一時停止開始時刻を記録
            self._pause_start_time = QtCore.QElapsedTimer()
            self._pause_start_time.start()
            
        else:
            # 再開時
            if hasattr(self, '_pause_start_time'):
                # 一時停止していた時間を累積
                pause_duration = self._pause_start_time.elapsed()
                if hasattr(self, '_pause_duration'):
                    self._pause_duration += pause_duration
                else:
                    self._pause_duration = pause_duration
                delattr(self, '_pause_start_time')
            
            if self.animating:
                self.animation_timer.start(self.anim_fps_interval)
                
                # 残り時間を計算
                if hasattr(self, '_anim_elapsed_timer'):
                    actual_elapsed = self._anim_elapsed_timer.elapsed()
                    if hasattr(self, '_pause_duration'):
                        actual_elapsed -= self._pause_duration
                    remaining_time = max(100, self.anim_duration - actual_elapsed)
                    self.slide_timer.start(remaining_time)
                else:
                    self.slide_timer.start(self.interval_ms)
            else:
                self.slide_timer.start(self.interval_ms)

    def _go_next(self):
        """次の画像に強制的に切り替える"""
        
        # タイマーを停止し、即座に次の画像をセット
        self.slide_timer.stop()
        self.animation_timer.stop()
        self.animating = False
        self.is_paused = False

        if not self.image_files:
            return

        # テキストアイテムの参照をリセット
        if self.text_item and self.text_item.scene() == self.scene:
            self.scene.removeItem(self.text_item)
            self.text_item = None 
            
        self.scene.clear()

        # 次のインデックスを計算
        self.index = (self.index + 1) % len(self.image_files)
        
        # 非アニメーションで次の画像を表示し、新しいサイクルを開始
        self._show_first_image(is_next_prev_op=True)

    def _go_prev(self):
        """前の画像に強制的に切り替える"""
        if not self.image_files:
            return
            
        self.slide_timer.stop()
        self.animation_timer.stop()
        self.animating = False
        self.is_paused = False
        
        # 前のインデックスを計算
        self.index = (self.index - 1 + len(self.image_files)) % len(self.image_files)
        
        # 新しいインデックスで表示を開始
        self._show_first_image(is_next_prev_op=True)

    def _open_in_explorer(self):
        """現在の画像をエクスプローラーで開く（ファイルを選択状態で）"""
        if not self.image_files or self.index >= len(self.image_files):
            return
        
        current_path = self.image_files[self.index]
        
        # ファイルが存在するか確認
        if not os.path.exists(current_path):
            QtWidgets.QMessageBox.warning(
                self, 
                "警告", 
                "ファイルが見つかりません。\n既に削除または移動された可能性があります。"
            )
            return
        
        # Windowsのエクスプローラーでファイルを選択状態で開く
        try:
            import subprocess
            # ファイルを選択状態にする
            subprocess.run(['explorer', '/select,', os.path.normpath(current_path)])
        except Exception as e:
            # エラーの場合はフォルダだけを開く
            try:
                folder_path = os.path.dirname(current_path)
                os.startfile(folder_path)
            except Exception as e2:
                QtWidgets.QMessageBox.critical(
                    self, 
                    "エラー", 
                    f"エクスプローラーを開けませんでした:\n{e2}"
                )

    def _delete_current_image(self):
        """現在表示中の画像を削除し、次の画像へ進む"""
        if not self.image_files:
            return
            
        current_path = self.image_files[self.index]
        base_name = os.path.basename(current_path)

        reply = QtWidgets.QMessageBox.question(
            self, 
            "確認", 
            f"以下のファイルを完全に削除しますか？\n\n"
            f"ファイル名: {base_name}\n"
            f"フルパス: {current_path}\n\n"
            f"この操作は元に戻せません。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                os.remove(current_path)
                
                # リストから削除
                del self.image_files[self.index]
                
                # インデックス調整
                if self.index >= len(self.image_files) and self.image_files:
                    self.index = 0
                elif not self.image_files:
                    self.close()
                    return

                # 次の画像に切り替え
                self._show_first_image(is_next_prev_op=True)
                
                self.is_paused = False
                self.slide_timer.start(self.interval_ms)
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "削除エラー", f"ファイルの削除に失敗しました:\n{e}")

    def _show_loading_screen(self):
        """ローディング画面を表示"""
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        
        # 最初にシーンの矩形を設定
        self.scene.setSceneRect(-vw/2, -vh/2, vw, vh)
        
        logo_item = QtWidgets.QGraphicsTextItem()
        logo_html = """
        <div style='text-align: center; color: white; font-family: "游ゴシック", "Yu Gothic", sans-serif;'>
            <h1 style='font-size: 36px; margin: 0; color: #FFF; font-weight: normal;'>
                Cinematic Slideshow
            </h1>
        </div>
        """
        logo_item.setHtml(logo_html)
        
        # ロゴを中央に配置
        logo_rect = logo_item.boundingRect()
        logo_x = -logo_rect.width() / 2
        logo_y = -50
        logo_item.setPos(logo_x, logo_y)
        logo_item.setZValue(10.0)
        
        self.scene.addItem(logo_item)
        self.loading_items.append(logo_item)

        # プログレスバー
        progress_width = min(300, vw * 0.4)
        progress_height = 4
        progress_x = -progress_width / 2
        progress_y = 20
        
        # プログレスバー背景
        progress_bg = QtWidgets.QGraphicsRectItem(progress_x, progress_y, progress_width, progress_height)
        progress_bg.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60)))
        progress_bg.setPen(QtGui.QPen(QtGui.QColor(100, 100, 100)))
        progress_bg.setZValue(10.0)
        self.scene.addItem(progress_bg)
        self.loading_items.append(progress_bg)
        
        # プログレスバー本体
        self.progress_bar = QtWidgets.QGraphicsRectItem(progress_x, progress_y, 0, progress_height)
        self.progress_bar.setBrush(QtGui.QBrush(QtGui.QColor(70, 130, 200)))
        self.progress_bar.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.progress_bar.setZValue(11.0)
        self.scene.addItem(self.progress_bar)
        self.loading_items.append(self.progress_bar)
        
        # 状況テキスト
        self.status_item = QtWidgets.QGraphicsTextItem()
        status_html = """
        <div style='text-align: center; color: #CCC; font-family: "游ゴシック", sans-serif;'>
            <p style='font-size: 16px; margin: 0;'>準備中...</p>
        </div>
        """
        self.status_item.setHtml(status_html)
        
        # 状況テキストを中央下部に配置
        status_rect = self.status_item.boundingRect()
        status_x = -status_rect.width() / 2
        status_y = progress_y + 30
        self.status_item.setPos(status_x, status_y)
        self.status_item.setZValue(10.0)
        
        self.scene.addItem(self.status_item)
        self.loading_items.append(self.status_item)
        
        # プログレス関連の変数
        self.progress_max_width = progress_width
        self.progress_start_x = progress_x
        
        # 画像読み込み開始
        QtCore.QTimer.singleShot(500, self._start_image_loading)

    def _start_image_loading(self):
        """画像読み込みを開始"""
        if not self.image_files:
            self._update_loading_progress(100, "画像が見つかりませんでした")
            QtCore.QTimer.singleShot(2000, self._finish_loading)
            return
        
        # 画像読み込み用タイマー
        self.loading_timer = QtCore.QTimer()
        self.loading_timer.timeout.connect(self._load_next_image)
        self.loading_index = 0
        self.loading_max = min(5, len(self.image_files))
        
        self._update_loading_progress(0, f"画像を読み込み中... (0/{self.loading_max})")
        self.loading_timer.start(100)

    def _load_next_image(self):
        """次の画像を読み込み"""
        if self.loading_index >= self.loading_max:
            self.loading_timer.stop()
            self._update_loading_progress(100, "読み込み完了")
            QtCore.QTimer.singleShot(800, self._finish_loading)
            return
        
        # 画像を読み込み（キャッシュに保存）
        if self.loading_index < len(self.image_files):
            path = self.image_files[self.loading_index]
            pixmap = create_pixmap_from_file(path)
            if not pixmap.isNull():
                self._get_scaled_pixmap(pixmap, for_anim=True)
        
        self.loading_index += 1
        progress = int((self.loading_index / self.loading_max) * 100)
        self._update_loading_progress(progress, f"画像を読み込み中... ({self.loading_index}/{self.loading_max})")

    def _update_loading_progress(self, percent: int, status_text: str):
        """ローディング画面のプログレスを更新"""
        if hasattr(self, 'progress_bar'):
            new_width = (percent / 100.0) * self.progress_max_width
            self.progress_bar.setRect(self.progress_start_x, self.progress_bar.rect().y(), 
                                    new_width, self.progress_bar.rect().height())
        
        if hasattr(self, 'status_item'):
            status_html = f"""
            <div style='text-align: center; color: #CCC; font-family: "游ゴシック", sans-serif;'>
                <p style='font-size: 16px; margin: 0;'>{status_text}</p>
            </div>
            """
            self.status_item.setHtml(status_html)
            
            # テキストの位置を再調整
            status_rect = self.status_item.boundingRect()
            status_x = -status_rect.width() / 2
            self.status_item.setPos(status_x, self.status_item.pos().y())

    def _finish_loading(self):
        """ローディング完了、スライドショー開始"""
        # ローディング画面をフェードアウト
        self.fade_out_timer = QtCore.QTimer()
        self.fade_out_timer.timeout.connect(self._fade_out_loading)
        self.fade_opacity = 1.0
        self.fade_out_timer.start(50)

    def _fade_out_loading(self):
        """ローディング画面をフェードアウト"""
        self.fade_opacity -= 0.05
        
        for item in self.loading_items:
            if item.scene() == self.scene:
                item.setOpacity(self.fade_opacity)
        
        if self.fade_opacity <= 0:
            self.fade_out_timer.stop()
            
            # ローディングアイテムを削除
            for item in self.loading_items:
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
            self.loading_items.clear()
            
            self.is_loading = False
            
            # スライドショー開始
            if self.image_files:
                self._show_first_image()
            else:
                self._show_no_images_message()

    def _show_about_dialog(self):
        """バージョン情報ダイアログを表示（スライドショーから）"""
        show_about_dialog(self)

    # -------------------------
    # 画像の表示・アニメーション
    # -------------------------
    def _show_first_image(self, is_next_prev_op=False):
        """初回表示時、または前後移動時に使用"""
        if not self.image_files:
            self._show_no_images_message()
            return
        
        # 既存のアイテムをクリーンアップ
        if self.text_item and self.text_item.scene() == self.scene:
            self.scene.removeItem(self.text_item)
            self.text_item = None
        
        self.scene.clear()
        
        path = self.image_files[self.index]
        pixmap = create_pixmap_from_file(path)
        if pixmap.isNull():
            return
        
        pixmap_item = QtWidgets.QGraphicsPixmapItem()

        if self.ken_burns:
            # Ken Burns有効時
            start_scale, end_scale = self._calculate_ken_burns_scales()
            scaled_pixmap, _, _ = self._get_scaled_pixmap(pixmap, for_anim=True)
            pixmap_item.setPixmap(scaled_pixmap)
            pixmap_item.setOpacity(1.0)
            
            # 変換の中心を画像の中心に設定
            pixmap_item.setTransformOriginPoint(
                scaled_pixmap.width() / 2,
                scaled_pixmap.height() / 2
            )
            pixmap_item.setScale(start_scale)
            
            # Ken Burnsのオフセットを計算
            start_off_x, start_off_y, end_off_x, end_off_y = self._calculate_ken_burns_offsets(
                pixmap, start_scale, end_scale
            )

            # スケール適用前の画像で中央配置
            pos_x = -scaled_pixmap.width() / 2 + start_off_x
            pos_y = -scaled_pixmap.height() / 2 + start_off_y            
            pixmap_item.setPos(pos_x, pos_y)

            # 終了時の計算を追加
            end_pos_x = -scaled_pixmap.width() / 2 + end_off_x
            end_pos_y = -scaled_pixmap.height() / 2 + end_off_y
            
            # 実際の表示範囲を計算（スケール適用後）
            start_left = pos_x - (scaled_pixmap.width() * (start_scale - 1) / 2)
            start_right = start_left + scaled_pixmap.width() * start_scale
            end_left = end_pos_x - (scaled_pixmap.width() * (end_scale - 1) / 2)
            end_right = end_left + scaled_pixmap.width() * end_scale
            
            # アニメーション状態
            self.anim_state = {
                "start_offset": (start_off_x, start_off_y),
                "end_offset": (end_off_x, end_off_y),
                "start_scale": start_scale,
                "end_scale": end_scale,
            }
        else:
            # Ken Burns無効時
            vw = self.view.viewport().width()
            vh = self.view.viewport().height()
            
            # スケーリングされた画像を取得
            scaled_pixmap, _, _ = self._get_scaled_pixmap(pixmap, for_anim=False)
            pixmap_item.setPixmap(scaled_pixmap)
            pixmap_item.setOpacity(1.0)
            pixmap_item.setScale(1.0)
            
            # スケール後の画像サイズ
            sw = scaled_pixmap.width()
            sh = scaled_pixmap.height()
            item_x = -sw / 2.0
            item_y = -sh / 2.0
            pixmap_item.setPos(item_x, item_y)

            # アニメーション状態
            self.anim_state = {
                "start_offset": (0, 0),
                "end_offset": (0, 0),
                "start_scale": 1.0,
                "end_scale": 1.0,
            }
        
        self.scene.addItem(pixmap_item)
        self.current_item = pixmap_item
        self.next_item = None
        
        # ファイル名表示
        if self.show_filename:
            self._init_text_item(os.path.basename(path), pixmap)
            self.text_item.setOpacity(1.0)
        
        # 状態フラグの初期化
        self.is_transitioning = False
        self.current_effect = None
        self.next_effect = None
        if hasattr(self, '_paused_offset'):
            delattr(self, '_paused_offset')
        if hasattr(self, '_paused_transition_offset'):
            delattr(self, '_paused_transition_offset')
        
        # アニメーション開始
        self.anim_duration = self.interval_ms
        self.anim_start_time = QtCore.QTime.currentTime()
        self.animating = True
        self.animation_timer.start(self.anim_fps_interval)

        if self.current_item:
            self.frozen_current_pos = self.current_item.pos()
            self.frozen_current_scale = self.current_item.scale()

    def _show_error_overlay(self, message: str, duration: int = 3000):
        """エラーメッセージをオーバーレイ表示"""
        # 半透明の背景
        error_bg = QtWidgets.QGraphicsRectItem(0, 0, 400, 100)
        error_bg.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0, 180)))  # 赤い半透明
        error_bg.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        
        # エラーテキスト
        error_text = QtWidgets.QGraphicsTextItem()
        error_text.setHtml(f"""
            <div style='color: white; padding: 10px; font-size: 16px;'>
                ⚠️ {message}
            </div>
        """)
        
        # 中央に配置
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        error_bg.setPos((vw - 400) / 2, vh - 150)
        error_text.setPos((vw - 380) / 2, vh - 140)
        
        # シーンに追加
        self.scene.addItem(error_bg)
        self.scene.addItem(error_text)
        error_bg.setZValue(100)
        error_text.setZValue(101)
        
        # 一定時間後に削除
        QtCore.QTimer.singleShot(duration, lambda: self._remove_error_overlay(error_bg, error_text))

    def _remove_error_overlay(self, bg, text):
        """エラーオーバーレイを削除"""
        if bg.scene() == self.scene:
            self.scene.removeItem(bg)
        if text.scene() == self.scene:
            self.scene.removeItem(text)
        
    def _on_slide_timeout(self, force_next_item=False):
        if hasattr(self, '_paused_offset'):
            delattr(self, '_paused_offset')
        if hasattr(self, '_paused_transition_offset'):
            delattr(self, '_paused_transition_offset')

        # アニメーション中の二重起動防止
        if self.animating and not force_next_item:
            return
            
        # 一時停止中の場合はスキップ
        if self.is_paused:
            self.slide_timer.start(self.interval_ms)
            return

        # 画像リストの整合性チェック
        if not self.image_files:
            print("[Error] No images in list")
            self._show_error_overlay("画像がありません")
            return
            
        if self.index >= len(self.image_files):
            print(f"[Warning] Index out of range: {self.index}/{len(self.image_files)}")
            self._show_error_overlay("画像インデックスエラー")
            
            self.index = 0

        # 次のインデックスを計算
        next_index = (self.index + 1) % len(self.image_files)
        
        # ターゲットとするファイルのパスを取得
        try:
            path = self.image_files[next_index]
        except IndexError:
            self.index = 0
            path = self.image_files[self.index]
            next_index = self.index + 1
        
        path = os.path.normpath(path).replace('\\', '/')
        
        # QPixmap にロード
        max_retries = 3
        retry_count = 0
        pixmap = None
        
        while retry_count < max_retries:
            try:
                pixmap = create_pixmap_from_file(path)
                
                if pixmap.isNull():
                    retry_count += 1
                    print(f"画像読み込み失敗 (試行 {retry_count}/{max_retries}): {path}")
                    
                    # 少し待機してリトライ
                    QtCore.QThread.msleep(100)
                else:
                    # 成功したらエラーカウントをリセット
                    if hasattr(self, '_load_error_count') and path in self._load_error_count:
                        del self._load_error_count[path]
                    break
                    
            except Exception as e:
                print(f"画像読み込み例外: {path} - {e}")
                retry_count += 1
                QtCore.QThread.msleep(100)

        # エラーカウント管理
        if pixmap is None or pixmap.isNull():
            if not hasattr(self, '_load_error_count'):
                self._load_error_count = {}
                
            if path not in self._load_error_count:
                self._load_error_count[path] = 0
            self._load_error_count[path] += 1
            
            print(f"画像読み込み最終失敗: {path} (累積失敗回数: {self._load_error_count[path]})")
            
            # 3回以上失敗した画像はスキップ
            if self._load_error_count[path] >= 3:
                print(f"画像を永続的にスキップ: {path}")
                self._show_error_overlay(f"画像をスキップ: {os.path.basename(path)}", 2000)
                
                # 元のパスで削除
                original_path = self.image_files[next_index] if next_index < len(self.image_files) else None
                if original_path and original_path in self.image_files:
                    self.image_files.remove(original_path)
                elif path in self.image_files:
                    self.image_files.remove(path)
                else:
                    if next_index < len(self.image_files):
                        removed_path = self.image_files.pop(next_index)

                if self.image_files:
                    self.index = self.index % len(self.image_files)
                else:
                    self._show_error_overlay("表示可能な画像がありません", 5000)
                    return
            
            self.slide_timer.start(100)
            return
            
        # 次のエフェクトを選択
        self.next_effect = self._select_next_effect()

        # スライドエフェクトの場合
        if self.next_effect == "slide":
            self.slide_direction = random.choice(["left", "right", "up", "down"])

        # ワイプエフェクトの場合
        elif self.next_effect == "wipe":
            wipe_directions = [
                "left_to_right", "right_to_left", "top_to_bottom", "bottom_to_top",
                "diagonal_tl_br", "diagonal_tr_bl", "diagonal_bl_tr", "diagonal_br_tl"
            ]
            self.wipe_direction = random.choice(wipe_directions)

        # Ken Burns有効時のみスケール計算
        if self.ken_burns:
            start_scale, end_scale = self._calculate_ken_burns_scales()
        else:
            start_scale = end_scale = 1.0

        # 現在の画像のKen Burnsを凍結
        if self.current_item:
            self.frozen_current_pos = self.current_item.pos()
            self.frozen_current_scale = self.current_item.scale()
                
        # アニメーション開始時間を記録
        self.anim_start_time = QtCore.QTime.currentTime()
        self.animating = True
        self.is_transitioning = True
                
        # 次アイテムを作成
        next_item = QtWidgets.QGraphicsPixmapItem()
        
        if self.ken_burns:
            # Ken Burns有効時
            scaled_pixmap, _, _ = self._get_scaled_pixmap(pixmap, for_anim=True)
            next_item.setPixmap(scaled_pixmap)
            next_item.setOpacity(0.0)
            
            # 変換の中心を画像の中心に設定
            next_item.setTransformOriginPoint(
                scaled_pixmap.width() / 2,
                scaled_pixmap.height() / 2
            )
            next_item.setScale(start_scale)
            
            # Ken Burnsのオフセットを計算
            start_off_x, start_off_y, end_off_x, end_off_y = self._calculate_ken_burns_offsets(
                pixmap, start_scale, end_scale
            )

            # 位置計算
            pos_x = -scaled_pixmap.width() / 2 + start_off_x
            pos_y = -scaled_pixmap.height() / 2 + start_off_y
            
            # 次の画像用のアニメーション状態
            self.anim_state = {
                "start_offset": (start_off_x, start_off_y),
                "end_offset": (end_off_x, end_off_y),
                "start_scale": start_scale,
                "end_scale": end_scale,
            }
        else:
            # Ken Burns無効時
            scaled_pixmap, _, _ = self._get_scaled_pixmap(pixmap, for_anim=False)
            next_item.setPixmap(scaled_pixmap)
            next_item.setOpacity(0.0)
            next_item.setScale(1.0)
            
            # 画像を中央に配置
            sw = scaled_pixmap.width()
            sh = scaled_pixmap.height()
            item_x = -sw / 2.0
            item_y = -sh / 2.0
            next_item.setPos(item_x, item_y)
            
            # アニメーション状態
            self.anim_state = {
                "start_offset": (0, 0),
                "end_offset": (0, 0),
                "start_scale": 1.0,
                "end_scale": 1.0,
            }
        
        self.next_item = next_item
        self.scene.addItem(self.next_item)
        self.next_item.setZValue(1.0)
        
        if self.current_item:
            self.current_item.setZValue(0.0)
            
        # ファイル名表示の更新
        if self.show_filename:
            self._init_text_item(os.path.basename(path), pixmap)
            if self.text_item:
                self.text_item.setOpacity(0.0)
        
        # 切替開始時刻を記録
        self.transition_start_time = QtCore.QTime.currentTime()
        
        self.animation_timer.start(self.anim_fps_interval)
        self.index = next_index

    def _on_anim_frame(self):
        """アニメーションの1フレーム更新"""
        if not self.animating:
            return
        
        if self.is_paused:
            return
        
        if not hasattr(self, '_anim_elapsed_timer'):
            self._anim_elapsed_timer = QtCore.QElapsedTimer()
            self._anim_elapsed_timer.start()
            self._last_pause_time = 0
        
        # 実際の経過時間を計算
        actual_elapsed = self._anim_elapsed_timer.elapsed()
        
        # 一時停止していた時間を考慮
        if hasattr(self, '_pause_duration'):
            actual_elapsed -= self._pause_duration
        
        elapsed_ms = actual_elapsed       
        t_linear = min(1.0, elapsed_ms / self.anim_duration) 
        self._last_t_linear = t_linear
        t = 0.5 - 0.5 * math.cos(t_linear * math.pi)
        
        # 切替エフェクト中かどうかで処理を分ける
        if self.is_transitioning and self.next_effect:
            # エフェクトの進行度
            if not hasattr(self, '_transition_elapsed_timer'):
                self._transition_elapsed_timer = QtCore.QElapsedTimer()
                self._transition_elapsed_timer.start()
            
            # 一時停止からの再開時のオフセットを考慮
            if hasattr(self, '_paused_transition_offset'):
                transition_elapsed = self._transition_elapsed_timer.elapsed() + self._paused_transition_offset
            else:
                transition_elapsed = self._transition_elapsed_timer.elapsed()
                
            effect_t = min(1.0, transition_elapsed / self.fade_duration_ms)
            effect_t_eased = 0.5 - 0.5 * math.cos(effect_t * math.pi)
            
            # Ken Burnsと位置を統合処理
            self._apply_ken_burns_during_transition(t, effect_t_eased)
            
            # エフェクト固有の視覚効果
            if self.next_effect == "crossfade":
                self._apply_crossfade_opacity(effect_t_eased)
            elif self.next_effect == "zoom":
                self._apply_zoom_scale_opacity(effect_t_eased)
            elif self.next_effect == "wipe":
                self._apply_wipe_mask(effect_t_eased)
            elif self.next_effect == "fade_to_black":
                self._apply_fade_to_black_effect(effect_t_eased)
            
            # ファイル名の表示制御
            if self.text_item:
                if self.next_effect == "fade_to_black":
                    if effect_t < 0.6:
                        self.text_item.setOpacity(0.0)
                    else:
                        self.text_item.setOpacity((effect_t - 0.6) / 0.4)
                else:
                    self.text_item.setOpacity(effect_t_eased)
        else:
            # 通常のKen Burns効果のみ
            if self.ken_burns and self.current_item:
                self._apply_ken_burns_normal(t)
        
        # アニメーション終了判定
        if t_linear >= 1.0:
            self._finish_animation()

    def _calculate_ken_burns_scales(self) -> Tuple[float, float]:
        """Ken Burns効果の開始時と終了時のスケール倍率を計算（正式版）"""
        # 基本計算：100% + (強度 × 10%)
        base_zoom = self.ken_intensity * 0.1  # 強度1→10%、強度5→50%、強度10→100%
        
        # ランダム要素：±10%
        random_offset = (random.random() - 0.5) * 0.2  # -0.1 ~ +0.1
        
        # 合計
        total_zoom = base_zoom + random_offset
        start_scale = 1.0 + total_zoom
        
        # 閾値適用
        start_scale = max(1.05, min(2.0, start_scale))  # 105%～200%
        
        # 終了時：100% + (0-5%)のランダム
        end_scale = 1.0 + random.random() * 0.05
        return start_scale, end_scale

    def _calculate_ken_burns_offsets(self, pixmap: QtGui.QPixmap, start_scale: float, end_scale: float) -> Tuple[int, int, int, int]:
        """Ken Burnsエフェクト用のオフセットを計算"""
        if not self.ken_burns:
            return 0, 0, 0, 0
        
        vw, vh = self.view.viewport().width(), self.view.viewport().height()
        
        # 基準サイズ
        if self.fit_mode == "cover":
            base_scale = max(vw / pixmap.width(), vh / pixmap.height())
        else:
            base_scale = min(vw / pixmap.width(), vh / pixmap.height())
        
        # 画像の短辺と長辺を判定
        is_landscape = pixmap.width() > pixmap.height()
        
        # 移動パターンの選択
        movement_pattern = random.choice(self.MOVEMENT_PATTERNS)
        # movement_pattern = "spiral_in"  # linear,arc,spiral_in,wave,zigzag （デバッグ用）固定する場合
        self.current_movement_pattern = movement_pattern
        
        # 強度による調整
        intensity_factor = self.ken_intensity / 10.0  # 0.1 ~ 1.0
        
        # 終了時のスケールに基づいて、許容される最大オフセットを計算
        if self.fit_mode == "cover":
            # パン＆スキャンモード
            end_img_w = pixmap.width() * base_scale * end_scale
            end_img_h = pixmap.height() * base_scale * end_scale
            
            # 終了時の最大許容オフセット（黒帯が出ない範囲）
            end_max_off_x = max(0, (end_img_w - vw) / 2)
            end_max_off_y = max(0, (end_img_h - vh) / 2)
            
            # 開始時の最大オフセット
            start_img_w = pixmap.width() * base_scale * start_scale
            start_img_h = pixmap.height() * base_scale * start_scale
            start_max_off_x = max(0, (start_img_w - vw) / 2)
            start_max_off_y = max(0, (start_img_h - vh) / 2)
        else:
            # containモード（レターボックス）では、終了時は必ず中央（0, 0）
            start_img_w = pixmap.width() * base_scale * start_scale
            start_img_h = pixmap.height() * base_scale * start_scale
            start_max_off_x = max(0, (start_img_w - vw) / 2)
            start_max_off_y = max(0, (start_img_h - vh) / 2)
            end_max_off_x = 0
            end_max_off_y = 0
        
        # 開始位置の計算（パターンに応じて）
        if movement_pattern == "spiral_in":
            # 螺旋は中間距離から開始
            start_distance_factor = 0.5 + random.random() * 0.2  # 0.5 ~ 0.7
            self.spiral_start_angle = random.random() * 2 * math.pi
            start_off_x = math.cos(self.spiral_start_angle) * start_max_off_x * start_distance_factor * intensity_factor
            start_off_y = math.sin(self.spiral_start_angle) * start_max_off_y * start_distance_factor * intensity_factor
        elif movement_pattern == "arc":
            # 円弧は片方の軸は端寄り、もう片方は中央寄り
            if random.choice([True, False]):
                start_x_factor = 0.7 + random.random() * 0.2  # 0.7 ~ 0.9（端寄り）
                start_y_factor = 0.3 + random.random() * 0.3  # 0.3 ~ 0.6（中央寄り）
            else:
                start_x_factor = 0.3 + random.random() * 0.3  # 0.3 ~ 0.6（中央寄り）
                start_y_factor = 0.7 + random.random() * 0.2  # 0.7 ~ 0.9（端寄り）
            start_off_x = random.choice([-1, 1]) * start_max_off_x * start_x_factor * intensity_factor
            start_off_y = random.choice([-1, 1]) * start_max_off_y * start_y_factor * intensity_factor
        else:
            # その他（linear, wave, zigzag）は端寄りから開始
            start_distance_factor = 0.7 + random.random() * 0.2  # 0.7 ~ 0.9
            start_off_x = random.choice([-1, 1]) * start_max_off_x * start_distance_factor * intensity_factor
            start_off_y = random.choice([-1, 1]) * start_max_off_y * start_distance_factor * intensity_factor
        
        # 終了位置の計算
        if self.fit_mode == "contain":
            # レターボックスモードでは必ず中央（0, 0）で終了
            end_off_x = 0
            end_off_y = 0
        else:
            # パン＆スキャンモードでの終了位置
            if movement_pattern in ["wave", "zigzag"]:
                # wave, zigzagは中央付近で終了（許容範囲内でのランダム）
                safe_factor = 0.3  # 安全マージン（最大オフセットの30%以内）
                end_off_x = random.uniform(-end_max_off_x * safe_factor, end_max_off_x * safe_factor)
                end_off_y = random.uniform(-end_max_off_y * safe_factor, end_max_off_y * safe_factor)
            elif movement_pattern == "spiral_in":
                # 螺旋は完全に中央で終了
                end_off_x = 0
                end_off_y = 0
            else:
                # その他のパターンは許容範囲内でランダム
                end_distance_factor = random.random() * 0.4  # 0.0 ~ 0.4
                end_off_x = random.uniform(-end_max_off_x, end_max_off_x) * end_distance_factor
                end_off_y = random.uniform(-end_max_off_y, end_max_off_y) * end_distance_factor
        
        # 整数に変換
        start_off_x = int(start_off_x)
        start_off_y = int(start_off_y)
        end_off_x = int(end_off_x)
        end_off_y = int(end_off_y)
        
        # 移動パターンのパラメータを保存
        if movement_pattern == "arc":
            self.arc_bulge_direction = random.choice([-1, 1])
        elif movement_pattern == "wave":
            self.wave_cycles = 1.5 + random.random() * 1.5  # 1.5～3周期
        elif movement_pattern == "spiral_in":
            self.spiral_rotations = 2.0 + random.random() * 1.5  # 2.0～3.5回転
        elif movement_pattern == "zigzag":
            self.zigzag_segments = random.randint(3, 5)
            
        return start_off_x, start_off_y, end_off_x, end_off_y

    def _get_scaled_pixmap(self, pixmap: QtGui.QPixmap, for_anim: bool = False) -> Tuple[QtGui.QPixmap, int, int]:
        """表示モードに基づいて画像をスケーリング"""
        if pixmap.isNull():
            print("警告: 無効なpixmapが渡されました")
            return QtGui.QPixmap(), 0, 0
        
        # キャッシュキーの生成
        viewport_size = self.view.viewport().size()
        cache_key = (
            pixmap.cacheKey(), 
            (viewport_size.width(), viewport_size.height()),
            for_anim, 
            self.ken_burns, 
            self.fit_mode,
        )
        
        # キャッシュをチェック
        if hasattr(self, '_pixmap_cache') and cache_key in self._pixmap_cache:
            cached_pixmap, x_offset, y_offset = self._pixmap_cache[cache_key]
            if not cached_pixmap.isNull():
                return cached_pixmap, x_offset, y_offset
            else:
                del self._pixmap_cache[cache_key]
        
        vw = max(1, self.view.viewport().width())
        vh = max(1, self.view.viewport().height())
        iw, ih = pixmap.width(), pixmap.height()

        x_offset, y_offset = 0, 0
        
        # 基準スケール倍率の計算
        if self.fit_mode == "cover":
            base_scale_factor = max(vw / iw, vh / ih) 
        else:
            base_scale_factor = min(vw / iw, vh / ih) 

        final_scale_factor = base_scale_factor
        new_w = int(iw * final_scale_factor)
        new_h = int(ih * final_scale_factor)
        
        # 最小サイズチェック
        if new_w < 1 or new_h < 1:
            print(f"警告: スケール後のサイズが無効です - {new_w}x{new_h}")
            return pixmap, 0, 0
        
        # スケーリング実行
        scaled = pixmap.scaled(
            QtCore.QSize(new_w, new_h), 
            QtCore.Qt.IgnoreAspectRatio, 
            QtCore.Qt.SmoothTransformation
        )
        
        if scaled.isNull():
            print(f"警告: スケーリングに失敗しました - 元サイズ: {iw}x{ih}, 目標サイズ: {new_w}x{new_h}")
            return pixmap, 0, 0
        
        # 中央寄せオフセットの計算
        if not self.ken_burns or not for_anim:
            x_offset = (vw - scaled.width()) // 2
            y_offset = (vh - scaled.height()) // 2
        else:
            x_offset = 0
            y_offset = 0
        
        # 結果をキャッシュ
        if not hasattr(self, '_pixmap_cache'):
            self._pixmap_cache = {}

        self._manage_cache()
        self._pixmap_cache[cache_key] = (scaled, x_offset, y_offset)
        
        return scaled, x_offset, y_offset

    def _apply_ken_burns_normal(self, t):
        """通常時のKen Burns効果を適用"""
        if not self.anim_state or not self.current_item:
            return
                        
        # Ken Burns用の補間計算
        t_ken = self._calculate_ken_burns_t(t)
        start_scale = self.anim_state["start_scale"]
        end_scale = self.anim_state["end_scale"]
        current_scale = start_scale + (end_scale - start_scale) * t_ken
        start_x, start_y = self.anim_state["start_offset"]
        end_x, end_y = self.anim_state["end_offset"]
        
        # 移動パターンに応じた座標計算
        if hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "arc":
            # 円弧移動
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2
            bulge = 0.3 * self.ken_intensity / 10.0
            if abs(end_x - start_x) > abs(end_y - start_y):
                control_x = mid_x
                control_y = mid_y + (end_x - start_x) * bulge * getattr(self, 'arc_bulge_direction', 1)
            else:
                control_x = mid_x + (end_y - start_y) * bulge * getattr(self, 'arc_bulge_direction', 1)
                control_y = mid_y
            current_x = (1 - t_ken) * (1 - t_ken) * start_x + 2 * (1 - t_ken) * t_ken * control_x + t_ken * t_ken * end_x
            current_y = (1 - t_ken) * (1 - t_ken) * start_y + 2 * (1 - t_ken) * t_ken * control_y + t_ken * t_ken * end_y

        elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "wave":
            # 波状移動
            base_x = start_x + (end_x - start_x) * t_ken
            base_y = start_y + (end_y - start_y) * t_ken
            
            # 波の振幅を時間とともに減衰させる
            amplitude_decay = 1.0 - t_ken  # 1.0 → 0.0
            amplitude = 50 * self.ken_intensity / 10.0 * amplitude_decay
            cycles = getattr(self, 'wave_cycles', 2.0)
            
            if abs(end_x - start_x) > abs(end_y - start_y):
                wave_offset = amplitude * math.sin(t_ken * math.pi * 2 * cycles)
                current_x = base_x
                current_y = base_y + wave_offset
            else:
                wave_offset = amplitude * math.sin(t_ken * math.pi * 2 * cycles)
                current_x = base_x + wave_offset
                current_y = base_y

        elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "spiral_in":
            # 螺旋移動
            rotations = getattr(self, 'spiral_rotations', 2.5)
            start_angle = getattr(self, 'spiral_start_angle', 0)
            angle = start_angle + t_ken * rotations * 2 * math.pi
            if t_ken < 0.2:
                radius = 1.0 + (t_ken / 0.2) * 0.3  # 1.0 → 1.3
            else:
                radius = 1.3 * (1.0 - (t_ken - 0.2) / 0.8)  # 1.3 → 0.0
            spiral_amplitude = 120 * self.ken_intensity / 10.0 * radius
            base_x = start_x + (end_x - start_x) * t_ken
            base_y = start_y + (end_y - start_y) * t_ken
            current_x = base_x + spiral_amplitude * math.cos(angle)
            current_y = base_y + spiral_amplitude * math.sin(angle)

        elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "zigzag":
            # ジグザグ移動
            base_x = start_x + (end_x - start_x) * t_ken
            base_y = start_y + (end_y - start_y) * t_ken
            
            # ジグザグの振幅を時間とともに減衰させる
            amplitude_decay = 1.0 - t_ken  # 1.0 → 0.0
            amplitude = 60 * self.ken_intensity / 10.0 * amplitude_decay
            segments = getattr(self, 'zigzag_segments', 4)
            
            wave_position = t_ken * segments * 2
            wave_int = int(wave_position)
            wave_frac = wave_position - wave_int
            if wave_int % 2 == 0:
                zigzag_offset = wave_frac * 2 - 1
            else:
                zigzag_offset = 1 - wave_frac * 2
                
            if abs(end_x - start_x) > abs(end_y - start_y):
                current_x = base_x
                current_y = base_y + amplitude * zigzag_offset
            else:
                current_x = base_x + amplitude * zigzag_offset
                current_y = base_y

        else:
            # 直線移動
            current_x = start_x + (end_x - start_x) * t_ken
            current_y = start_y + (end_y - start_y) * t_ken
        
        # 画像のサイズを取得して位置を設定
        pixmap = self.current_item.pixmap()
        if pixmap:
            self.current_item.setTransformOriginPoint(
                pixmap.width() / 2,
                pixmap.height() / 2
            )
            
            # 位置計算
            pos_x = -pixmap.width() / 2 + current_x
            pos_y = -pixmap.height() / 2 + current_y
            self.current_item.setScale(current_scale)
            self.current_item.setPos(pos_x, pos_y)

    def _apply_ken_burns_during_transition(self, t: float, effect_t: float):
        """切替エフェクト中のKen Burns効果を適用"""
        try:
            # Ken Burns有効時のみt_kenを計算
            if self.ken_burns:
                t_ken = self._calculate_ken_burns_t(t)
            else:
                t_ken = 0
            
            vw = self.view.viewport().width()
            vh = self.view.viewport().height()
            
            # 現在の画像の処理
            if self.current_item and hasattr(self, 'frozen_current_pos'):
                self.current_item.setPos(self.frozen_current_pos)
                self.current_item.setScale(self.frozen_current_scale)
                
                # エフェクトごとの位置調整
                if self.next_effect == "zoom":
                    # ズームアウト効果
                    zoom_extra = 1.0 + 1.0 * effect_t
                    self.current_item.setScale(self.frozen_current_scale * zoom_extra)
                    if not hasattr(self, '_zoom_center_ratio_x'):
                        self._zoom_center_ratio_x = random.random()
                        self._zoom_center_ratio_y = random.random()
                    pixmap = self.current_item.pixmap()
                    if pixmap:
                        # 元のサイズ（スケール適用前）
                        orig_w = pixmap.width() * self.frozen_current_scale
                        orig_h = pixmap.height() * self.frozen_current_scale
                        
                        # ズーム中心点（画像内の座標）
                        zoom_center_x = self.frozen_current_pos.x() + orig_w * self._zoom_center_ratio_x
                        zoom_center_y = self.frozen_current_pos.y() + orig_h * self._zoom_center_ratio_y
                        
                        # ズーム後のサイズ
                        new_w = pixmap.width() * self.frozen_current_scale * zoom_extra
                        new_h = pixmap.height() * self.frozen_current_scale * zoom_extra
                        
                        # ズーム中心を維持する新しい位置
                        new_x = zoom_center_x - new_w * self._zoom_center_ratio_x
                        new_y = zoom_center_y - new_h * self._zoom_center_ratio_y
                        
                        self.current_item.setPos(new_x, new_y)
                        
                elif self.next_effect == "slide":
                    # スライド方向に応じて現在の画像も移動
                    if self.slide_direction == "left":
                        self.current_item.setPos(self.frozen_current_pos.x() - vw * effect_t, self.frozen_current_pos.y())
                    elif self.slide_direction == "right":
                        self.current_item.setPos(self.frozen_current_pos.x() + vw * effect_t, self.frozen_current_pos.y())
                    elif self.slide_direction == "up":
                        self.current_item.setPos(self.frozen_current_pos.x(), self.frozen_current_pos.y() - vh * effect_t)
                    elif self.slide_direction == "down":
                        self.current_item.setPos(self.frozen_current_pos.x(), self.frozen_current_pos.y() + vh * effect_t)
                    self.current_item.setOpacity(1.0)
            
            # 次の画像の処理
            if self.next_item:
                if self.ken_burns and hasattr(self, 'anim_state') and self.anim_state:
                    # Ken Burns有効時
                    start_scale = self.anim_state["start_scale"]
                    end_scale = self.anim_state["end_scale"]
                    current_scale = start_scale + (end_scale - start_scale) * t_ken

                    # オフセットの補間
                    start_x, start_y = self.anim_state["start_offset"]
                    end_x, end_y = self.anim_state["end_offset"]
                    
                    # 移動パターンに応じた座標計算
                    if hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "arc":
                        # 円弧移動
                        mid_x = (start_x + end_x) / 2
                        mid_y = (start_y + end_y) / 2
                        bulge = 0.3 * self.ken_intensity / 10.0
                        
                        if abs(end_x - start_x) > abs(end_y - start_y):
                            control_x = mid_x
                            control_y = mid_y + (end_x - start_x) * bulge * getattr(self, 'arc_bulge_direction', 1)
                        else:
                            control_x = mid_x + (end_y - start_y) * bulge * getattr(self, 'arc_bulge_direction', 1)
                            control_y = mid_y
                        
                        ken_x = (1 - t_ken) * (1 - t_ken) * start_x + 2 * (1 - t_ken) * t_ken * control_x + t_ken * t_ken * end_x
                        ken_y = (1 - t_ken) * (1 - t_ken) * start_y + 2 * (1 - t_ken) * t_ken * control_y + t_ken * t_ken * end_y
                        
                    elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "wave":
                        # 波状移動
                        base_x = start_x + (end_x - start_x) * t_ken
                        base_y = start_y + (end_y - start_y) * t_ken
                        
                        # 振幅を時間とともに減衰
                        amplitude_decay = 1.0 - t_ken  # 1.0 → 0.0
                        amplitude = 50 * self.ken_intensity / 10.0 * amplitude_decay
                        cycles = getattr(self, 'wave_cycles', 2.0)
                        
                        if abs(end_x - start_x) > abs(end_y - start_y):
                            wave_offset = amplitude * math.sin(t_ken * math.pi * 2 * cycles)
                            ken_x = base_x
                            ken_y = base_y + wave_offset
                        else:
                            wave_offset = amplitude * math.sin(t_ken * math.pi * 2 * cycles)
                            ken_x = base_x + wave_offset
                            ken_y = base_y

                    elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "spiral_in":
                        # 螺旋移動
                        rotations = getattr(self, 'spiral_rotations', 2.0)
                        start_angle = getattr(self, 'spiral_start_angle', 0)
                        angle = start_angle + t_ken * rotations * 2 * math.pi
                        
                        if t_ken < 0.2:
                            radius = 1.0 + (t_ken / 0.2) * 0.3  # 1.0 → 1.3
                        else:
                            radius = 1.3 * (1.0 - (t_ken - 0.2) / 0.8)  # 1.3 → 0.0
                            
                        spiral_amplitude = 100 * self.ken_intensity / 10.0 * radius
                        base_x = start_x + (end_x - start_x) * t_ken
                        base_y = start_y + (end_y - start_y) * t_ken
                        ken_x = base_x + spiral_amplitude * math.cos(angle)
                        ken_y = base_y + spiral_amplitude * math.sin(angle)

                    elif hasattr(self, 'current_movement_pattern') and self.current_movement_pattern == "zigzag":
                        # ジグザグ移動
                        base_x = start_x + (end_x - start_x) * t_ken
                        base_y = start_y + (end_y - start_y) * t_ken
                        
                        # 振幅を時間とともに減衰
                        amplitude_decay = 1.0 - t_ken  # 1.0 → 0.0
                        amplitude = 60 * self.ken_intensity / 10.0 * amplitude_decay
                        segments = getattr(self, 'zigzag_segments', 4)
                        
                        wave_position = t_ken * segments * 2
                        wave_int = int(wave_position)
                        wave_frac = wave_position - wave_int
                        
                        if wave_int % 2 == 0:
                            zigzag_offset = wave_frac * 2 - 1
                        else:
                            zigzag_offset = 1 - wave_frac * 2
                        
                        if abs(end_x - start_x) > abs(end_y - start_y):
                            ken_x = base_x
                            ken_y = base_y + amplitude * zigzag_offset
                        else:
                            ken_x = base_x + amplitude * zigzag_offset
                            ken_y = base_y

                    else:
                        # 直線移動
                        ken_x = start_x + (end_x - start_x) * t_ken
                        ken_y = start_y + (end_y - start_y) * t_ken

                    # 画像サイズとセンタリング計算
                    pixmap = self.next_item.pixmap()
                    if pixmap:
                        base_pos_x = -pixmap.width() / 2 + ken_x
                        base_pos_y = -pixmap.height() / 2 + ken_y

                        # 最終的なスケールを設定
                        if self.next_effect == "zoom":
                            # ズームエフェクト中は追加のスケールを適用
                            zoom_in_scale = 0.5 + 0.5 * effect_t  # 0.5 → 1.0
                            final_scale = current_scale * zoom_in_scale
                            self.next_item.setScale(final_scale)
                        else:
                            # その他のエフェクトではKen Burnsのスケールのみ
                            self.next_item.setScale(current_scale)

                        # エフェクトごとの位置調整
                        if self.next_effect == "slide":
                            if self.slide_direction == "left":
                                self.next_item.setPos(vw - vw * effect_t + base_pos_x, base_pos_y)
                            elif self.slide_direction == "right":
                                self.next_item.setPos(-vw + vw * effect_t + base_pos_x, base_pos_y)
                            elif self.slide_direction == "up":
                                self.next_item.setPos(base_pos_x, vh - vh * effect_t + base_pos_y)
                            elif self.slide_direction == "down":
                                self.next_item.setPos(base_pos_x, -vh + vh * effect_t + base_pos_y)
                            self.next_item.setOpacity(1.0)

                        elif self.next_effect == "wipe":

                            if self.text_item:
                                self.text_item.setZValue(10.0)
                            self.next_item.setZValue(2.0)

                            if self.wipe_direction == "left_to_right":
                                wipe_x = -vw + vw * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, base_pos_y)
                            elif self.wipe_direction == "right_to_left":
                                wipe_x = vw - vw * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, base_pos_y)
                            elif self.wipe_direction == "top_to_bottom":
                                wipe_y = -vh + vh * effect_t
                                self.next_item.setPos(base_pos_x, wipe_y + base_pos_y)
                            elif self.wipe_direction == "bottom_to_top":
                                wipe_y = vh - vh * effect_t
                                self.next_item.setPos(base_pos_x, wipe_y + base_pos_y)
                            elif self.wipe_direction == "diagonal_tl_br":
                                wipe_x = -vw + vw * effect_t
                                wipe_y = -vh + vh * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, wipe_y + base_pos_y)
                            elif self.wipe_direction == "diagonal_tr_bl":
                                wipe_x = vw - vw * effect_t
                                wipe_y = -vh + vh * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, wipe_y + base_pos_y)
                            elif self.wipe_direction == "diagonal_bl_tr":
                                wipe_x = -vw + vw * effect_t
                                wipe_y = vh - vh * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, wipe_y + base_pos_y)
                            elif self.wipe_direction == "diagonal_br_tl":
                                wipe_x = vw - vw * effect_t
                                wipe_y = vh - vh * effect_t
                                self.next_item.setPos(wipe_x + base_pos_x, wipe_y + base_pos_y)

                        else:
                            # その他のエフェクト
                            self.next_item.setPos(base_pos_x, base_pos_y)
                else:
                    # Ken Burns無効時
                    pixmap = self.next_item.pixmap() 
                    if pixmap:
                        sw = pixmap.width()
                        sh = pixmap.height()
                        
                        # 基本の中央位置
                        center_x = -sw / 2
                        center_y = -sh / 2
                        
                        if self.next_effect == "zoom":
                            # ズームイン効果（0.5倍から1.0倍へ）
                            zoom_in_scale = 0.5 + 0.5 * effect_t
                            self.next_item.setScale(zoom_in_scale)
                            
                            # スケールに応じた中央配置
                            current_w = sw * zoom_in_scale
                            current_h = sh * zoom_in_scale
                            zoom_x = -current_w / 2
                            zoom_y = -current_h / 2
                            self.next_item.setPos(zoom_x, zoom_y)
                            
                        elif self.next_effect == "slide":
                            # スライドイン
                            self.next_item.setScale(1.0)
                            self.next_item.setOpacity(1.0)
                            
                            if self.slide_direction == "left":
                                # 右から左へスライドイン
                                start_x = vw / 2
                                current_x = start_x - vw * effect_t
                                final_x = center_x
                                slide_x = start_x + (final_x - start_x) * effect_t
                                self.next_item.setPos(slide_x, center_y)
                                
                            elif self.slide_direction == "right":
                                # 左から右へスライドイン
                                start_x = -vw / 2 - sw
                                current_x = start_x + vw * effect_t
                                final_x = center_x
                                slide_x = start_x + (final_x - start_x) * effect_t
                                self.next_item.setPos(slide_x, center_y)
                                
                            elif self.slide_direction == "up":
                                # 下から上へスライドイン
                                start_y = vh / 2
                                current_y = start_y - vh * effect_t
                                final_y = center_y 
                                slide_y = start_y + (final_y - start_y) * effect_t
                                self.next_item.setPos(center_x, slide_y)
                                
                            elif self.slide_direction == "down":
                                # 上から下へスライドイン
                                start_y = -vh / 2 - sh
                                current_y = start_y + vh * effect_t
                                final_y = center_y
                                slide_y = start_y + (final_y - start_y) * effect_t
                                self.next_item.setPos(center_x, slide_y)
                            
                            self.next_item.setOpacity(1.0)
                            
                        elif self.next_effect == "wipe":
                            # ワイプエフェクト
                            self.next_item.setScale(1.0)
                            self.next_item.setOpacity(1.0)

                            if self.text_item:
                                self.text_item.setZValue(10.0)
                            self.next_item.setZValue(2.0)
                            
                            if self.wipe_direction == "left_to_right":
                                wipe_x = -vw + vw * effect_t + center_x
                                self.next_item.setPos(wipe_x, center_y)
                            elif self.wipe_direction == "right_to_left":
                                wipe_x = vw - vw * effect_t + center_x
                                self.next_item.setPos(wipe_x, center_y)
                            elif self.wipe_direction == "top_to_bottom":
                                wipe_y = -vh + vh * effect_t + center_y
                                self.next_item.setPos(center_x, wipe_y)
                            elif self.wipe_direction == "bottom_to_top":
                                wipe_y = vh - vh * effect_t + center_y
                                self.next_item.setPos(center_x, wipe_y)
                            elif self.wipe_direction == "diagonal_tl_br":
                                wipe_x = -vw + vw * effect_t + center_x
                                wipe_y = -vh + vh * effect_t + center_y
                                self.next_item.setPos(wipe_x, wipe_y)
                            elif self.wipe_direction == "diagonal_tr_bl":
                                wipe_x = vw - vw * effect_t + center_x
                                wipe_y = -vh + vh * effect_t + center_y
                                self.next_item.setPos(wipe_x, wipe_y)
                            elif self.wipe_direction == "diagonal_bl_tr":
                                wipe_x = -vw + vw * effect_t + center_x
                                wipe_y = vh - vh * effect_t + center_y
                                self.next_item.setPos(wipe_x, wipe_y)
                            elif self.wipe_direction == "diagonal_br_tl":
                                wipe_x = vw - vw * effect_t + center_x
                                wipe_y = vh - vh * effect_t + center_y
                                self.next_item.setPos(wipe_x, wipe_y)
                            
                        else:
                            # その他のエフェクト
                            self.next_item.setScale(1.0)
                            self.next_item.setPos(center_x, center_y)
                        
        except Exception as e:
            print(f"Error in transition: {e}")
            import traceback
            traceback.print_exc()

    def _apply_crossfade_opacity(self, t: float):
        """クロスフェードの不透明度のみを適用"""
        if self.next_item:
            self.next_item.setOpacity(t)
        if self.current_item:
            self.current_item.setOpacity(1.0 - t)

    def _apply_zoom_scale_opacity(self, t: float):
        """ズーム効果の不透明度を適用"""
        if self.current_item:
            self.current_item.setOpacity(1.0 - t)

        if self.next_item:
            self.next_item.setOpacity(t)
            
            # Ken Burns無効時のみズームインを適用
            if not self.ken_burns:
                zoom_in_scale = 0.5 + 0.5 * t  # 0.5 → 1.0
                self.next_item.setScale(zoom_in_scale)

    def _apply_wipe_mask(self, t: float):
        """ワイプ効果（位置ベースの実装）"""
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        
        # エフェクトが完了したら、Ken Burnsの位置を維持
        if t >= 1.0:
            if self.current_item:
                self.current_item.setOpacity(0.0)
            if self.next_item:
                self.next_item.setOpacity(1.0)
                self.next_item.setZValue(2.0)
            return
        
        # エフェクト中の処理
        if self.current_item:
            self.current_item.setOpacity(1.0)
            self.current_item.setZValue(0.0)
        
        if self.next_item:
            self.next_item.setOpacity(1.0)
            self.next_item.setZValue(2.0)

    def _calculate_ken_burns_t(self, t_linear):
        """Ken Burns用の補間値を計算"""
        return t_linear

    def _finish_animation(self):
        """アニメーション終了時の処理"""
        # タイマーをクリーンアップ
        if hasattr(self, '_anim_elapsed_timer'):
            delattr(self, '_anim_elapsed_timer')
        
        if hasattr(self, '_transition_elapsed_timer'):
            delattr(self, '_transition_elapsed_timer')
        
        # 一時停止関連の変数をクリーンアップ
        if hasattr(self, '_pause_duration'):
            delattr(self, '_pause_duration')
        if hasattr(self, '_pause_start_time'):
            delattr(self, '_pause_start_time')
        
        # 切替エフェクト終了
        self.is_transitioning = False
        
        # 現在のエフェクトを更新
        if self.next_effect:
            self.current_effect = self.next_effect
            self.next_effect = None
        
        # transition_start_timeをクリーンアップ
        if hasattr(self, 'transition_start_time'):
            delattr(self, 'transition_start_time')
        
        # ズーム用の基準スケールをクリーンアップ
        if hasattr(self, '_zoom_base_scales'):
            delattr(self, '_zoom_base_scales')

        # 凍結した位置情報をクリーンアップ
        if hasattr(self, 'frozen_current_pos'):
            delattr(self, 'frozen_current_pos')
        if hasattr(self, 'frozen_current_scale'):
            delattr(self, 'frozen_current_scale')
        
        # ズーム中心点情報をクリーンアップ
        if hasattr(self, '_zoom_center_ratio_x'):
            delattr(self, '_zoom_center_ratio_x')
        if hasattr(self, '_zoom_center_ratio_y'):
            delattr(self, '_zoom_center_ratio_y')
        
        # ワイプ用のマスクがあれば削除
        if hasattr(self, '_wipe_mask') and self._wipe_mask:
            if self._wipe_mask.scene() == self.scene:
                self.scene.removeItem(self._wipe_mask)
            self._wipe_mask = None
        
        # 古い current_item を削除
        if self.next_item and self.current_item and self.current_item.scene() == self.scene: 
            self.scene.removeItem(self.current_item)
        
        # next_item があれば current_item に昇格
        if self.next_item:
            self.next_item.setOpacity(1.0)
            self.current_item = self.next_item
            self.next_item = None
            
        # アニメーションフラグとタイマーを停止
        self.animating = False 
        self.animation_timer.stop()
        
        # テキストの不透明度を確定
        if self.text_item and self.show_filename:
            self.text_item.setOpacity(1.0)
        
        # 次の画像への切り替え
        if not self.is_paused:
            QtCore.QTimer.singleShot(50, self._on_slide_timeout)

    def _apply_slide_position_to_current(self, ken_x: float, ken_y: float, effect_t: float):
        """現在の画像にスライド位置を適用"""
        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        
        if self.slide_direction == "left":
            self.current_item.setPos(-ken_x - vw * effect_t, -ken_y)
        elif self.slide_direction == "right":
            self.current_item.setPos(-ken_x + vw * effect_t, -ken_y)
        elif self.slide_direction == "up":
            self.current_item.setPos(-ken_x, -ken_y - vh * effect_t)
        elif self.slide_direction == "down":
            self.current_item.setPos(-ken_x, -ken_y + vh * effect_t)

    def _apply_fade_to_black_effect(self, t: float):
        """フェード・トゥ・ブラック効果"""
        
        if t < 0.4:  # 前半40%
            opacity = 1.0 - (t / 0.4)
            if self.current_item:
                self.current_item.setOpacity(opacity)
            if self.text_item:
                self.text_item.setOpacity(0.0)
        elif t < 0.6:  # 中間20%
            if self.current_item:
                self.current_item.setOpacity(0.0)
            if self.next_item:
                self.next_item.setOpacity(0.0)
        else:  # 後半40%
            if self.next_item:
                opacity = (t - 0.6) / 0.4
                self.next_item.setOpacity(opacity)
            if self.text_item:
                self.text_item.setOpacity((t - 0.6) / 0.4)

    def _manage_cache(self):
        """キャッシュ管理"""
        # 枚数超過時に古いものを削除
        while len(self._pixmap_cache) > self._cache_max_size:
            oldest_key = next(iter(self._pixmap_cache))
            del self._pixmap_cache[oldest_key]
        
        # ガベージコレクション
        import gc
        gc.collect()

    def _init_text_item(self, filename: str, pixmap: QtGui.QPixmap):
        """ファイル名表示用のQGraphicsTextItemを初期化・更新する"""
        if not self.text_item:
            self.text_item = QtWidgets.QGraphicsTextItem()
            self.scene.addItem(self.text_item)
            self.text_item.setZValue(2.0)
            self.text_item.setOpacity(0.0) 
        
        color = QtGui.QColor("white") 
        font = QtGui.QFont(self.font_family, self.font_size)
        if self.font_bold:
            font.setBold(True)
        
        html = f"""
        <table cellpadding='0' cellspacing='0' border='0' style='
            background-color: rgba(0,0,0,100); 
            border-radius: {int(self.font_size * 0.3)}px;
            border: none;
        '>
            <tr>
                <td style='
                    color: {color.name()};
                    padding: {int(self.font_size * 0.6)}px {int(self.font_size * 0.7)}px {int(self.font_size * 0.1)}px {int(self.font_size * 0.7)}px;
                    border: none;
                    vertical-align: middle;
                    height: {int(self.font_size * 1.3)}px;
                    white-space: nowrap;
                '>{filename}</td>
            </tr>
        </table>
        """
        
        self.text_item.setHtml(html)
        self.text_item.setFont(font)
        
        self._update_text_position(self.text_item)
        
    def _update_text_position(self, item: QtWidgets.QGraphicsTextItem):
        """設定された位置に基づいてテキストアイテムの位置を計算し設定する"""
        if not item or not self.view:
            return

        vw = self.view.viewport().width()
        vh = self.view.viewport().height()
        
        text_rect = item.boundingRect()
        tw = text_rect.width()
        th = text_rect.height()
        
        padding = 20
        x, y = 0, 0
        
        # ビューポートの端を計算
        left_edge = -vw / 2
        right_edge = vw / 2
        top_edge = -vh / 2
        bottom_edge = vh / 2
        
        # 垂直位置
        if self.filename_v_pos == "top":
            y = top_edge + padding
        elif self.filename_v_pos == "bottom":
            y = bottom_edge - th - padding
        
        # 水平位置
        if self.filename_h_pos == "left":
            x = left_edge + padding
        elif self.filename_h_pos == "center":
            x = -tw / 2
        elif self.filename_h_pos == "right":
            x = right_edge - tw - padding

        # オフセットを適用
        x += self.filename_h_offset
        y += self.filename_v_offset

        item.setPos(x, y)

from typing import Dict, Any

class FolderListWidget(QtWidgets.QListWidget):
    """ドラッグアンドドロップ対応のフォルダリストウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)
    
    def dragEnterEvent(self, event):
        """ドラッグされたアイテムがフォルダかどうかチェック"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dragMoveEvent(self, event):
        """ドラッグ中の処理"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """ドロップ時の処理"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    exists = False
                    for i in range(self.count()):
                        if os.path.normpath(self.item(i).text()) == os.path.normpath(path):
                            exists = True
                            break
                    
                    if not exists:
                        item = QtWidgets.QListWidgetItem(path)
                        item.setData(QtCore.Qt.UserRole, True)
                        item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
                        self.addItem(item)
                        self.setCurrentItem(item)
        
        event.acceptProposedAction()

# ----------------------------------------------------
# MainWindow クラス
# ----------------------------------------------------

import sys
import os
import json
import glob
from typing import Dict, Any, List, Tuple
from PyQt5 import QtWidgets, QtGui, QtCore, uic # uicは念のため

# ==============================================================================
# 0. 前提条件とヘルパー関数の定義
# ==============================================================================

def list_images(folder_path: str, recursive: bool) -> List[str]:
    """指定されたフォルダ内の画像ファイルをリストアップする"""
    if not os.path.isdir(folder_path):
        return []

    images = []
    
    for ext in SUPPORTED_IMAGE_FORMATS:
        if recursive:
            pattern = os.path.join(folder_path, '**', f'*{ext}')
            images.extend(glob.glob(pattern, recursive=True))
            images.extend(glob.glob(pattern.replace(ext, ext.upper()), recursive=True))
        else:
            pattern = os.path.join(folder_path, f'*{ext}')
            images.extend(glob.glob(pattern))
            images.extend(glob.glob(pattern.replace(ext, ext.upper())))

    # 重複を除去してソート
    return sorted(list(set(images)))

def load_profiles() -> Dict[str, Any]:
    """プロファイルファイルからデータをロードする"""
    default_data = {
        "last_used_profile": "Default",
        "profiles": {
            "Default": {
                "folders": [],
                "monitor_index": 0,
                "interval_sec": 5,
                "fade_duration_ms": 1000,
                "random_order": True,
                "ken_burns": True,
                "fit_mode": "cover",
                "stay_on_top": False,
                "show_filename": False,
                "filename_v_pos": "bottom",
                "filename_h_pos": "center",
                "font_family": "游ゴシック",
                "font_size": 18,
                "font_bold": True,
            }
        }
    }
    
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "profiles" in data:
                    # Defaultプロファイルが存在しない場合は追加
                    if "Default" not in data["profiles"]:
                        data["profiles"]["Default"] = default_data["profiles"]["Default"]
                    return data
        except Exception as e:
            print(f"Error loading profiles: {e}")
            print("Creating new profiles.json...")
    
    # ファイルが存在しないか、読み込みエラーの場合は新規作成
    print("Creating default profiles.json...")
    _save_profiles_data(default_data)
    return default_data

def _save_profiles_data(data: Dict[str, Any]):
    """プロファイルデータをファイルに保存するヘルパー関数"""
    try:
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Profiles saved to {PROFILES_FILE}")
    except Exception as e:
        print(f"Error saving profiles: {e}")

def show_about_dialog(parent_widget):
    """バージョン情報ダイアログを表示"""
    dialog = QtWidgets.QDialog(parent_widget)
    dialog.setWindowTitle("Cinematic Slideshowについて")
    dialog.setFixedSize(450, 520)
    dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
    
    # アプリケーションアイコンを優先的に使用
    app = QtWidgets.QApplication.instance()
    if app and not app.windowIcon().isNull():
        dialog.setWindowIcon(app.windowIcon())
    elif parent_widget and hasattr(parent_widget, 'windowIcon') and not parent_widget.windowIcon().isNull():
        dialog.setWindowIcon(parent_widget.windowIcon())
    
    # 中央配置
    if parent_widget:
        dialog.move(
            parent_widget.x() + (parent_widget.width() - dialog.width()) // 2,
            parent_widget.y() + (parent_widget.height() - dialog.height()) // 2
        )
    else:
        screen_center = QtWidgets.QApplication.desktop().screen().rect().center()
        dialog.move(screen_center - dialog.rect().center())
    
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setSpacing(5)
    layout.setContentsMargins(20, 15, 20, 10)
    header_layout = QtWidgets.QHBoxLayout()
    icon_label = QtWidgets.QLabel()
    
    # アプリケーション全体のアイコン
    if app and not app.windowIcon().isNull():
        app_icon = app.windowIcon()
        pixmap = app_icon.pixmap(64, 64)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap)
            icon_found = True
    
    # 親ウィンドウのアイコン
    if not icon_found and parent_widget and hasattr(parent_widget, 'windowIcon'):
        app_icon = parent_widget.windowIcon()
        if not app_icon.isNull():
            pixmap = app_icon.pixmap(64, 64)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
                icon_found = True
    
    # フォールバック：絵文字
    if not icon_found:
        icon_label.setText("🎬")
        icon_label.setStyleSheet("""
            font-size: 48px;
            border: 1px solid #ddd; 
            border-radius: 8px; 
            background: white;
            padding: 8px;
        """)
    else:
        icon_label.setStyleSheet("""
            border: 1px solid #ddd; 
            border-radius: 8px; 
            background: white;
            padding: 8px;
        """)

        icon_label.setFixedSize(80, 80)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
    
    # タイトル情報
    title_layout = QtWidgets.QVBoxLayout()
    app_name = QtWidgets.QLabel("<h1 style='margin: 0; color: #2c3e50;'>Cinematic Slideshow</h1>")
    
    version_info = QtWidgets.QLabel("""
    <p style='margin: 5px 0; color: #7f8c8d; font-size: 12px;'>
    <b>バージョン:</b> 1.0<br>
    <b>リリース:</b> 2025年11月<br>
    <b>ビルド:</b> Python + PyQt5
    </p>
    """)
    
    title_layout.addWidget(app_name)
    title_layout.addWidget(version_info)
    title_layout.addStretch()
    
    header_layout.addWidget(icon_label)
    header_layout.addLayout(title_layout)
    
    # ライセンス情報
    license_info = QtWidgets.QLabel()
    license_info.setWordWrap(True)
    license_info.setStyleSheet("""
        font-size: 12px;
        color: #495057; 
        background-color: #f8f9fa;
        border-left: 4px solid #28a745;
        padding: 10px;
        margin: 10px 0;
        line-height: 1.3;
    """)
    license_info.setText("""
<p><b>📄 オープンソースライセンス:</b></p>
<ul style="margin: 8px 0 0 18px; padding: 0;">
<li><b>本ソフトウェア:</b> GPL v3 License</li>
<li><b>PyQt5:</b> GPL v3 - Riverbank Computing</li>
<li><b>Python:</b> PSF License</li>
<li><b>Pillow:</b> HPND License</li>
</ul>
<p style="margin-top: 10px; font-size: 11px;">
<b>ソースコード:</b> https://github.com/sitar-j/Cinematic_Slideshow<br>
<b>ライセンス全文:</b> https://www.gnu.org/licenses/gpl-3.0.html
</p>
    """)
    
    # フッター情報
    footer = QtWidgets.QLabel()
    footer.setAlignment(QtCore.Qt.AlignCenter)
    footer.setStyleSheet("""
        color: #95a5a6; 
        font-size: 13px;
        border-top: 1px solid #ecf0f1; 
        padding-top: 5px;
        margin-top: 3px;
        line-height: 1.4;
    """)
    footer.setText("""
<p><b>開発者:</b> sitarj</p>
<p style="color: #28a745; font-weight: bold; margin: 8px 0;">
🆓 オープンソース・フリーウェア
</p>
<p style="font-size: 12px; margin: 5px 0;">
個人・商用利用可能（GPL v3準拠）<br>
改変・再配布も自由です
</p>
<p style="font-size: 11px; color: #7f8c8d; margin-top: 8px;">© 2025 All rights reserved.</p>
    """)
    
    # 免責事項
    disclaimer = QtWidgets.QLabel()
    disclaimer.setWordWrap(True)
    disclaimer.setStyleSheet("""
        font-size: 11px;
        color: #7f8c8d; 
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 8px;
        margin: 5px 0;
        line-height: 1.0;
    """)
    disclaimer.setText("""
<p><b>⚠️ 免責事項:</b></p>
<ul style="margin: 6px 0 0 18px; padding: 0;">
<li>本ソフトウェアは「現状のまま」提供され、動作保証はありません</li>
<li>使用によって生じたいかなる損害も作者は責任を負いません</li>
<li>画像ファイルの取り扱いには十分ご注意ください</li>
</ul>
<p style="margin-top: 8px; font-weight: bold;">ご利用は自己責任でお願いします</p>
    """)
    
    button_box = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Close,
        QtCore.Qt.Horizontal,
        dialog
    )
    button_box.button(QtWidgets.QDialogButtonBox.Close).setText("OK")
    button_box.rejected.connect(dialog.accept)


    # レイアウト組み立て
    layout.addLayout(header_layout)
    layout.addWidget(license_info)
    layout.addWidget(footer)
    layout.addWidget(disclaimer)
    layout.addWidget(button_box)
    
    # ダイアログを表示
    dialog.exec_()

# ==============================================================================
# 1. MainWindow クラスの定義
# ==============================================================================

class MainWindow(QtWidgets.QWidget):
    
    DEFAULT_FONT_FAMILY = "游ゴシック" 
    DEFAULT_FONT_SIZE = 18
    DEFAULT_FONT_BOLD = True

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cinematic Slideshow - プロファイル設定")
        self.resize(650, 700) 

        self.profiles = {}
        self.current_profile = None
        
        # フォント設定はプロファイルに依存
        self.current_font_family = self.DEFAULT_FONT_FAMILY
        self.current_font_size = self.DEFAULT_FONT_SIZE
        
        self.slideshow_window = None
        self._original_profile = None

        # プロファイル関連UI
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.setMinimumWidth(150)
        
        # ボタンサイズを統一
        button_width = 70
        self.btn_profile_add = QtWidgets.QPushButton("新規作成")
        self.btn_profile_add.setMaximumWidth(button_width)
        self.btn_profile_save = QtWidgets.QPushButton("保存")
        self.btn_profile_save.setMaximumWidth(button_width)
        self.btn_profile_rename = QtWidgets.QPushButton("名前変更")
        self.btn_profile_rename.setMaximumWidth(button_width)
        self.btn_profile_duplicate = QtWidgets.QPushButton("複製")
        self.btn_profile_duplicate.setMaximumWidth(button_width)
        self.btn_profile_remove = QtWidgets.QPushButton("削除")
        self.btn_profile_remove.setMaximumWidth(button_width)
        
        # フォルダ関連UI
        self.folder_list = FolderListWidget()
        self.folder_list.setMinimumHeight(120)
        self.folder_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.folder_list.itemSelectionChanged.connect(self._on_list_selection_changed)

        self.btn_folder_add = QtWidgets.QPushButton("追加")
        self.btn_folder_remove = QtWidgets.QPushButton("削除")
        self.chk_recursive = QtWidgets.QCheckBox("サブフォルダを含める")
        self.chk_recursive.setEnabled(False)

        # 表示設定UI
        self.monitor_combo = QtWidgets.QComboBox()
        for i, s in enumerate(QtWidgets.QApplication.screens()):
            geom = s.geometry()
            w, h = geom.size().width(), geom.size().height()
            self.monitor_combo.addItem(f"{i}: {s.name()} ({w}x{h})")

        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)

        # 画像再生順
        self.radio_order_name = QtWidgets.QRadioButton("名前順")
        self.radio_order_random = QtWidgets.QRadioButton("ランダム再生")
        self.radio_order_random.setChecked(True)

        # 画像表示深度
        self.radio_front = QtWidgets.QRadioButton("最前面")
        self.radio_back = QtWidgets.QRadioButton("最背面")
        self.radio_back.setChecked(True)

        # 画像表示方法
        self.radio_fit_cover = QtWidgets.QRadioButton("パン＆スキャン")
        self.radio_fit_contain = QtWidgets.QRadioButton("レターボックス")
        self.radio_fit_cover.setChecked(True)

        # ファイル名表示
        self.chk_show_filename = QtWidgets.QCheckBox("表示")
        self.combo_v_pos = QtWidgets.QComboBox()
        self.combo_v_pos.addItems(["上", "下"])
        self.combo_v_pos.setCurrentText("下")
        self.combo_h_pos = QtWidgets.QComboBox()
        self.combo_h_pos.addItems(["左", "中央", "右"])
        self.combo_h_pos.setCurrentText("中央")
        self.font_button = QtWidgets.QPushButton("フォント...")
        self.font_label = QtWidgets.QLabel(f"{self.DEFAULT_FONT_FAMILY}, {self.DEFAULT_FONT_SIZE}pt")

        # オフセット設定
        self.filename_v_offset_spin = QtWidgets.QSpinBox()
        self.filename_v_offset_spin.setRange(-200, 200)
        self.filename_v_offset_spin.setValue(0)
        self.filename_v_offset_spin.setSuffix(" px")
        self.filename_v_offset_spin.setToolTip("垂直方向の微調整（マイナス値で上、プラス値で下）")
        
        self.filename_h_offset_spin = QtWidgets.QSpinBox()
        self.filename_h_offset_spin.setRange(-200, 200)
        self.filename_h_offset_spin.setValue(0)
        self.filename_h_offset_spin.setSuffix(" px")
        self.filename_h_offset_spin.setToolTip("水平方向の微調整（マイナス値で左、プラス値で右）")

        # 切替効果UI
        self.chk_crossfade = QtWidgets.QCheckBox("クロスフェード")
        self.chk_crossfade.setChecked(True)
        
        self.chk_slide = QtWidgets.QCheckBox("スライド")
        self.chk_slide.setChecked(False)
        
        self.chk_zoom = QtWidgets.QCheckBox("ズーム")
        self.chk_zoom.setChecked(False)
        
        self.chk_wipe = QtWidgets.QCheckBox("ワイプ")
        self.chk_wipe.setChecked(False)
        
        self.chk_fade_to_black = QtWidgets.QCheckBox("フェード・トゥ・ブラック")
        self.chk_fade_to_black.setChecked(False)

        # エフェクト適用順
        self.radio_effect_order = QtWidgets.QRadioButton("順番")
        self.radio_effect_random = QtWidgets.QRadioButton("ランダム")
        self.radio_effect_random.setChecked(True)
        
        # 切替効果時間
        self.fade_spin = QtWidgets.QDoubleSpinBox()
        self.fade_spin.setRange(0.1, 10.0)
        self.fade_spin.setSingleStep(0.1)
        self.fade_spin.setDecimals(1)
        self.fade_spin.setValue(1.0)

        # Ken Burns効果
        self.chk_ken = QtWidgets.QCheckBox("Ken Burns効果")
        self.chk_ken.setChecked(True)
        
        # Ken Burns強度スライダー
        self.ken_intensity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.ken_intensity_slider.setRange(1, 10)  # 1-10の範囲
        self.ken_intensity_slider.setValue(5)  # デフォルト中間
        self.ken_intensity_label = QtWidgets.QLabel("5")
        self.ken_intensity_slider.valueChanged.connect(
            lambda v: self.ken_intensity_label.setText(str(v))
        )

        # ショートカット関連
        self.shortcut_label = QtWidgets.QLabel("現在のプロファイルで起動するショートカット")
        self.btn_create_shortcut = QtWidgets.QPushButton("作成")

        # バックアップ・リストア関連
        self.backup_label = QtWidgets.QLabel("プロファイルのバックアップ・リストア")
        self.btn_backup = QtWidgets.QPushButton("バックアップ")
        self.btn_restore = QtWidgets.QPushButton("リストア")

        # バージョン情報ボタン
        self.btn_about = QtWidgets.QPushButton("ソフトウェア情報 ℹ️")
        self.btn_about.setToolTip("Cinematic Slideshowについて")
        self.btn_about.clicked.connect(self._show_about_dialog)

        # OS標準ボタンボックスを作成
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | 
            QtWidgets.QDialogButtonBox.Cancel | 
            QtWidgets.QDialogButtonBox.Apply,
            QtCore.Qt.Horizontal
        )

        # ボタンのテキストをカスタマイズ（必要に応じて）
        self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setText("OK")
        self.button_box.button(QtWidgets.QDialogButtonBox.Cancel).setText("キャンセル")
        self.button_box.button(QtWidgets.QDialogButtonBox.Apply).setText("適用")

        # ウィンドウタイトルとアイコン
        self.setWindowTitle("Cinematic Slideshow - プロファイル設定")
        self._set_application_icon()

        # --- レイアウト構築 ---
        
        # プロファイル部分
        profile_group = QtWidgets.QGroupBox("プロファイル")
        profile_layout = QtWidgets.QVBoxLayout(profile_group)
        
        profile_h = QtWidgets.QHBoxLayout()
        profile_h.addWidget(QtWidgets.QLabel("プロファイル:"))
        profile_h.addWidget(self.profile_combo)
        profile_h.addWidget(self.btn_profile_add)
        profile_h.addWidget(self.btn_profile_save)
        profile_h.addWidget(self.btn_profile_rename)
        profile_h.addWidget(self.btn_profile_duplicate)
        profile_h.addWidget(self.btn_profile_remove)
        profile_h.addStretch()
        profile_layout.addLayout(profile_h)
        
        #ショートカット作成とバックアップ・リストア
        shortcut_backup_h = QtWidgets.QHBoxLayout()
        shortcut_backup_h.addWidget(self.shortcut_label)
        shortcut_backup_h.addWidget(self.btn_create_shortcut)
        shortcut_backup_h.addSpacing(20)
        shortcut_backup_h.addWidget(self.backup_label)
        shortcut_backup_h.addWidget(self.btn_backup)
        shortcut_backup_h.addWidget(self.btn_restore)
        shortcut_backup_h.addStretch()
        profile_layout.addLayout(shortcut_backup_h)

        # フォルダ部分
        folder_group = QtWidgets.QGroupBox("画像フォルダ")
        folder_layout = QtWidgets.QVBoxLayout(folder_group)
        folder_btn_h = QtWidgets.QHBoxLayout()
        folder_btn_h.addWidget(self.btn_folder_add)
        folder_btn_h.addWidget(self.btn_folder_remove)
        folder_btn_h.addWidget(self.chk_recursive)
        folder_btn_h.addStretch()
        folder_layout.addLayout(folder_btn_h)
        folder_layout.addWidget(self.folder_list)

        # 表示設定部分
        display_group = QtWidgets.QGroupBox("表示設定")
        display_layout = QtWidgets.QGridLayout(display_group)

        # 列の伸縮比を設定
        display_layout.setColumnStretch(0, 1)
        display_layout.setColumnStretch(1, 2)
        display_layout.setColumnStretch(2, 1)
        display_layout.setColumnStretch(3, 2) 
        
        # 1行目
        display_layout.addWidget(QtWidgets.QLabel("実行モニター:"), 0, 0)
        display_layout.addWidget(self.monitor_combo, 0, 1)
        display_layout.addWidget(QtWidgets.QLabel("表示時間 (秒):"), 0, 2)
        display_layout.addWidget(self.interval_spin, 0, 3)
        
        # 2行目
        order_group = QtWidgets.QGroupBox("再生順")
        order_layout = QtWidgets.QHBoxLayout(order_group)
        order_layout.addWidget(self.radio_order_name)
        order_layout.addWidget(self.radio_order_random)
        display_layout.addWidget(order_group, 1, 0, 1, 2)

        depth_group = QtWidgets.QGroupBox("深度")
        depth_layout = QtWidgets.QHBoxLayout(depth_group)
        depth_layout.addWidget(self.radio_front)
        depth_layout.addWidget(self.radio_back)
        display_layout.addWidget(depth_group, 1, 2, 1, 2)
        
        # 3行目
        fit_group = QtWidgets.QGroupBox("表示方法")
        fit_layout = QtWidgets.QHBoxLayout(fit_group)
        fit_layout.addWidget(self.radio_fit_cover)
        fit_layout.addWidget(self.radio_fit_contain)
        display_layout.addWidget(fit_group, 2, 0, 1, 2)
        
        filename_group = QtWidgets.QGroupBox("ファイル名")
        filename_layout = QtWidgets.QGridLayout(filename_group)
        filename_layout.addWidget(self.chk_show_filename, 0, 0)
        filename_layout.addWidget(QtWidgets.QLabel("垂直:"), 0, 1)
        filename_layout.addWidget(self.combo_v_pos, 0, 2)
        filename_layout.addWidget(QtWidgets.QLabel("水平:"), 0, 3)
        filename_layout.addWidget(self.combo_h_pos, 0, 4)
        filename_layout.addWidget(self.font_button, 1, 0)
        filename_layout.addWidget(self.font_label, 1, 1, 1, 4)
        display_layout.addWidget(filename_group, 2, 2, 1, 2)
        filename_layout.addWidget(QtWidgets.QLabel("微調整:"), 2, 0)
        filename_layout.addWidget(QtWidgets.QLabel("垂直:"), 2, 1)
        filename_layout.addWidget(self.filename_v_offset_spin, 2, 2)
        filename_layout.addWidget(QtWidgets.QLabel("水平:"), 2, 3)
        filename_layout.addWidget(self.filename_h_offset_spin, 2, 4)

        # エフェクト設定部分
        effect_group = QtWidgets.QGroupBox("エフェクト設定")
        effect_layout = QtWidgets.QVBoxLayout(effect_group)
        
        # 切替効果
        transition_group = QtWidgets.QGroupBox("切替時のエフェクト種別")
        transition_layout = QtWidgets.QGridLayout(transition_group)
        transition_layout.addWidget(self.chk_crossfade, 0, 0)
        transition_layout.addWidget(self.chk_slide, 0, 1)
        transition_layout.addWidget(self.chk_zoom, 0, 2)
        transition_layout.addWidget(self.chk_wipe, 1, 0)
        transition_layout.addWidget(self.chk_fade_to_black, 1, 1)
        
        # エフェクト適用順
        effect_order_layout = QtWidgets.QHBoxLayout()
        effect_order_layout.addWidget(QtWidgets.QLabel("適用順:"))
        effect_order_layout.addWidget(self.radio_effect_order)
        effect_order_layout.addWidget(self.radio_effect_random)
        effect_order_layout.addStretch()
        transition_layout.addLayout(effect_order_layout, 2, 0, 1, 3)

        effect_layout.addWidget(transition_group)
        
        # 切替効果時間
        time_h = QtWidgets.QHBoxLayout()
        time_h.addWidget(QtWidgets.QLabel("切替時のエフェクト時間 (秒):"))
        time_h.addWidget(self.fade_spin)
        time_h.addStretch()
        effect_layout.addLayout(time_h)
        
        # 画像表示効果
        image_effect_group = QtWidgets.QGroupBox("表示エフェクト")
        image_effect_layout = QtWidgets.QHBoxLayout(image_effect_group)
        image_effect_layout.addWidget(self.chk_ken)
        image_effect_layout.addWidget(QtWidgets.QLabel("強度:"))
        image_effect_layout.addWidget(self.ken_intensity_slider)
        image_effect_layout.addWidget(self.ken_intensity_label)
        image_effect_layout.addStretch()
        effect_layout.addWidget(image_effect_group)

        # 下部ボタン
        btn_h = QtWidgets.QHBoxLayout()
        btn_h.addWidget(self.btn_about)
        btn_h.addStretch()
        btn_h.addWidget(self.button_box)  

        # --- ツールチップの設定 ---
        self._setup_tooltips()

        # メインレイアウト
        main_v = QtWidgets.QVBoxLayout(self)
        main_v.addWidget(profile_group)
        main_v.addWidget(folder_group)
        main_v.addWidget(display_group)
        main_v.addWidget(effect_group)
        main_v.addLayout(btn_h)
        main_v.addStretch(1)

        # --- イベント接続 ---
        
        # プロファイル操作
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.btn_profile_add.clicked.connect(self.on_add_profile)
        self.btn_profile_duplicate.clicked.connect(self.on_duplicate_profile)
        self.btn_profile_rename.clicked.connect(self.on_rename_profile)
        self.btn_profile_save.clicked.connect(self._on_apply_clicked)
        self.btn_profile_remove.clicked.connect(self.on_remove_profile)
        self.btn_create_shortcut.clicked.connect(self._on_create_shortcut)
        self.btn_backup.clicked.connect(self._on_backup_profiles)
        self.btn_restore.clicked.connect(self._on_restore_profiles)
        
        # フォルダ操作
        self.btn_folder_add.clicked.connect(self._on_add_folder)
        self.btn_folder_remove.clicked.connect(self._on_remove_folder)
        self.chk_recursive.stateChanged.connect(self._on_recursive_changed)

        # フォント選択
        self.font_button.clicked.connect(self._on_select_font)
        
        # 標準ボタンのイベント接続
        self.button_box.accepted.connect(self._on_ok_clicked)
        self.button_box.rejected.connect(self._on_cancel_clicked)
        self.button_box.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self._on_apply_clicked)

        # --- 初期化の完了 ---
        self._load_profiles()
        self._setup_system_tray()

    def _setup_tooltips(self):
        """全UIコンポーネントにツールチップを設定"""
        
        # プロファイル関連
        self.profile_combo.setToolTip("使用するプロファイルを選択します")
        self.btn_profile_add.setToolTip("新しいプロファイルを作成します")
        self.btn_profile_save.setToolTip("現在の設定をプロファイルに保存します")
        self.btn_profile_rename.setToolTip("選択中のプロファイル名を変更します")
        self.btn_profile_duplicate.setToolTip("選択中のプロファイルを複製します")
        self.btn_profile_remove.setToolTip("選択中のプロファイルを削除します\n（Defaultプロファイルは削除できません）")

        # ショートカット
        self.btn_create_shortcut.setToolTip("現在のプロファイル設定でスライドショーを起動する\nWindowsショートカットを作成します")

        # バックアップ・リストア
        self.btn_backup.setToolTip("現在の全プロファイル設定を任意の場所へバックアップします")
        self.btn_restore.setToolTip("バックアップファイルから全プロファイル設定を復元します\n（現在の全設定は上書きされます）")
        
        # フォルダ関連
        self.folder_list.setToolTip("画像が保存されているフォルダの一覧です\nドラッグ&ドロップでも追加できます")
        self.btn_folder_add.setToolTip("画像フォルダを追加します")
        self.btn_folder_remove.setToolTip("選択されたフォルダを一覧から削除します")
        self.chk_recursive.setToolTip("選択されたフォルダのサブフォルダも検索対象に含めます")
        
        # 表示設定
        self.monitor_combo.setToolTip("スライドショーを表示するモニターを選択します")
        self.interval_spin.setToolTip("各画像の表示時間を設定します（1-60秒）")
        
        # 再生順
        self.radio_order_name.setToolTip("ファイル名順に画像を表示します")
        self.radio_order_random.setToolTip("ランダムな順序で画像を表示します")
        
        # 深度
        self.radio_front.setToolTip("スライドショーを他のウィンドウより前面に表示します")
        self.radio_back.setToolTip("スライドショーを他のウィンドウより背面に表示します")
        
        # 表示方法
        self.radio_fit_cover.setToolTip("画像を画面全体に表示します（一部がトリミングされる場合があります）")
        self.radio_fit_contain.setToolTip("画像全体が見えるように表示します（黒い余白が表示される場合があります）")
        
        # ファイル名表示
        self.chk_show_filename.setToolTip("画像の下部にファイル名を表示します")
        self.combo_v_pos.setToolTip("ファイル名の垂直位置を設定します")
        self.combo_h_pos.setToolTip("ファイル名の水平位置を設定します")
        self.font_button.setToolTip("ファイル名表示に使用するフォントを選択します")
        self.filename_v_offset_spin.setToolTip("ファイル名の垂直位置を微調整します\n（マイナス値で上、プラス値で下に移動）")
        self.filename_h_offset_spin.setToolTip("ファイル名の水平位置を微調整します\n（マイナス値で左、プラス値で右に移動）")
        
        # エフェクト設定
        self.chk_crossfade.setToolTip("画像が徐々に切り替わるクロスフェード効果")
        self.chk_slide.setToolTip("画像が上下左右からスライドして切り替わる効果")
        self.chk_zoom.setToolTip("ズームイン・ズームアウトしながら切り替わる効果")
        self.chk_wipe.setToolTip("画像が8方向からワイプして切り替わる効果")
        self.chk_fade_to_black.setToolTip("一度黒画面になってから次の画像に切り替わる効果")
        
        self.radio_effect_order.setToolTip("選択されたエフェクトを順番に適用します")
        self.radio_effect_random.setToolTip("選択されたエフェクトをランダムに適用します")
        
        self.fade_spin.setToolTip("画像切り替え時のエフェクト時間を設定します（0.1-10.0秒）")
        
        # Ken Burns効果
        self.chk_ken.setToolTip("画像にゆっくりとしたズーム・パン効果を適用します\n映画的な動きのある表示になります")
        self.ken_intensity_slider.setToolTip("Ken Burns効果の強度を調整します\n1:控えめな動き ← → 10:ダイナミックな動き\n2※速度は画像表示時間でも変化します（長いほど遅い）")

        # 下部ボタン
        self.btn_about.setToolTip("アプリケーションのバージョン情報と機能説明を表示します")

    def _set_application_icon(self):
        """開発時・EXE化後両対応のアイコン設定"""
        icon_set = False
        
        try:
            # 実行ファイルと同じディレクトリのicon.icoを読み込み
            if getattr(sys, 'frozen', False):
                # EXE化されている場合
                exe_dir = os.path.dirname(sys.executable)
                icon_path = os.path.join(exe_dir, "icon.ico")
            else:
                # 開発時
                script_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path = os.path.join(script_dir, "icon.ico")
            
            if os.path.exists(icon_path):
                icon = QtGui.QIcon(icon_path)
                if not icon.isNull():
                    # アプリケーション全体にアイコンを設定
                    app = QtWidgets.QApplication.instance()
                    if app:
                        app.setWindowIcon(icon)
                    
                    # メインウィンドウにも設定
                    self.setWindowIcon(icon)
                    
                    # アイコンをメンバ変数として保持
                    self.app_icon = icon                    
                    icon_set = True
            
            # フォールバック：システムアイコン
            if not icon_set:
                print("icon.icoが見つかりません。システムアイコンを使用します。")
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
                
                app = QtWidgets.QApplication.instance()
                if app:
                    app.setWindowIcon(icon)
                
                self.setWindowIcon(icon)
                self.app_icon = icon
                    
        except Exception as e:
            print(f"アイコン設定エラー: {e}")
            # 最終フォールバック
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
            
            app = QtWidgets.QApplication.instance()
            if app:
                app.setWindowIcon(icon)
            
            self.setWindowIcon(icon)
            self.app_icon = icon

    def _show_about_dialog(self):
        """バージョン情報ダイアログを表示"""
        show_about_dialog(self)

    def _on_ok_clicked(self):
        """OKボタン: 保存して閉じる（変更があれば再起動）"""
        # 現在の設定を取得
        current_config = self._get_current_ui_config()
        
        # 変更があるかチェック
        has_changes = False
        if hasattr(self, '_initial_config'):
            has_changes = (self._initial_config != current_config)
        
        # 保存
        self._write_current_profile()
        
        # スライドショーから呼ばれた場合
        if hasattr(self, '_original_profile') and self._original_profile:
            self.hide()
            
            # 変更がある場合のみ再起動
            if has_changes:
                if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                    self.tray_icon.showMessage(
                        "Cinematic Slideshow",
                        "設定変更を反映するため、スライドショーを再起動します",
                        QtWidgets.QSystemTrayIcon.Information,
                        2000
                    )            
                    # 少し待ってから再起動
                    QtCore.QTimer.singleShot(500, self._restart_slideshow)

            else:
                # 変更がない場合はスライドショーに戻る
                if hasattr(self, 'slideshow_window') and self.slideshow_window:
                    self.slideshow_window.show()
                    self.slideshow_window.raise_()
                    self.slideshow_window.activateWindow()
            
            self._original_profile = None
        else:
            # 直接起動の場合は通常終了
            self.close()

    def _on_cancel_clicked(self):
        """キャンセルボタン: ただ閉じる"""
        # スライドショーから呼ばれた場合
        if hasattr(self, '_original_profile') and self._original_profile:
            self.hide()
            if hasattr(self, 'slideshow_window') and self.slideshow_window:
                self.slideshow_window.show()
                self.slideshow_window.raise_()
                self.slideshow_window.activateWindow()
            self._original_profile = None
        else:
            # 直接起動の場合
            self.close()

    def _on_apply_clicked(self):
        """適用ボタン: 保存のみ"""
        self._write_current_profile()
        
    def _restart_slideshow(self):
        """現在の設定でスライドショーを再起動"""
        # 現在の設定を保存
        self._write_current_profile()
        
        # 設定を再読み込みして最新状態にする
        self._load_profiles()
        
        # 現在のスライドショーを閉じる
        if hasattr(self, 'slideshow_window') and self.slideshow_window:
            self.slideshow_window.close()
            self.slideshow_window = None
        
        # 新しい設定でスライドショーを開始
        self.start_slideshow()
 
    # ----------------------------------------------------
    # プロファイル操作関連メソッド
    # ----------------------------------------------------
    
    def _create_default_config(self) -> Dict[str, Any]:
        """新しい/デフォルトのプロファイル設定を返す"""
        return {
            "folders": [],
            "monitor_index": 0,
            "interval_sec": 5,
            "fade_duration_ms": 1000,
            "random_order": True,
            "ken_burns": True,
            "fit_mode": "cover",
            "stay_on_top": False,
            "show_filename": False,
            "filename_v_pos": "bottom",
            "filename_h_pos": "center",
            "font_family": self.DEFAULT_FONT_FAMILY,
            "font_size": self.DEFAULT_FONT_SIZE,
            "font_bold": self.DEFAULT_FONT_BOLD,
            "filename_v_offset": 0,
            "filename_h_offset": 0,
            "effects": {
                "crossfade": True,
                "slide": False,
                "zoom": False,
                "wipe": False,
                "fade_to_black": False,
            },
            "effect_order": "random",
            }
        
    def _validate_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """設定の妥当性をチェック"""
        # 必須キーの確認
        required_keys = ["folders", "monitor_index", "interval_sec"]
        for key in required_keys:
            if key not in config:
                return False, f"必須設定 '{key}' が見つかりません"
        
        # 値の範囲チェック
        if not 1 <= config.get("interval_sec", 5) <= 3600:
            return False, "切替時間は1〜3600秒の範囲で設定してください"
        
        if not 100 <= config.get("fade_duration_ms", 1000) <= 10000:
            return False, "切替エフェクト時間は1〜10秒の範囲で設定してください"
        
        # モニターインデックスの確認
        monitor_count = len(QtWidgets.QApplication.screens())
        if config.get("monitor_index", 0) >= monitor_count:
            return False, f"モニター番号が範囲外です（利用可能: 0〜{monitor_count-1}）"
        
        return True, ""
    
    def _load_profiles(self):
        """プロファイルファイルを読み込む"""
        data = load_profiles()
        self.profiles = data.get("profiles", {})
        
        # プロファイルがない場合は Default を作成
        if not self.profiles or "Default" not in self.profiles:
            self.profiles["Default"] = self._create_default_config()
            self.current_profile = "Default"
            self._save_profiles()
        
        # current_profileの設定
        last_used = data.get("last_used_profile", "Default")
        if last_used in self.profiles:
            self.current_profile = last_used
        else:
            self.current_profile = "Default"
            
        self._load_profile_list()
        self._load_current_profile()

    def _save_profiles(self):
        """プロファイル設定を保存"""
        try:
            data = {
                "last_used_profile": self.current_profile,
                "profiles": self.profiles 
            }
            with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "エラー", f"プロファイルファイルの書き込みに失敗しました: {e}")

    def _load_profile_list(self):
        """プロファイルコンボボックスを更新する"""
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        
        sorted_keys = sorted(self.profiles.keys())
        # Defaultを先頭にする
        profile_names = list(self.profiles.keys())
        if "Default" in profile_names:
            profile_names.remove("Default")
            profile_names.insert(0, "Default")
            
        self.profile_combo.addItems(profile_names)
        
        if self.current_profile in self.profiles:
            self.profile_combo.setCurrentText(self.current_profile)
            
        self.profile_combo.blockSignals(False)

    def _load_current_profile(self):
        """現在のプロファイルの設定をUIに反映する"""
        if not self.current_profile or self.current_profile not in self.profiles:
            return

        config = self.profiles[self.current_profile]

        is_valid, error_msg = self._validate_config(config)
        if not is_valid:
            QtWidgets.QMessageBox.warning(self, "設定エラー", error_msg)
            config.update(self._create_default_config())

        self._loaded_config = {
            "folders": config.get("folders", []),
            "monitor_index": config.get("monitor_index", 0),
            "interval_sec": config.get("interval_sec", 5),
            "fade_duration_ms": config.get("fade_duration_ms", 1000),
            "random_order": config.get("random_order", True),
            "ken_burns": config.get("ken_burns", True),
            "ken_intensity": config.get("ken_intensity", 5),
            "fit_mode": config.get("fit_mode", "cover"),
            "stay_on_top": config.get("stay_on_top", True),
            "show_filename": config.get("show_filename", False),
            "filename_v_pos": config.get("filename_v_pos", "bottom"),
            "filename_h_pos": config.get("filename_h_pos", "center"),
            "font_family": config.get("font_family", self.DEFAULT_FONT_FAMILY),
            "font_size": config.get("font_size", self.DEFAULT_FONT_SIZE),
            "font_bold": config.get("font_bold", self.DEFAULT_FONT_BOLD),
            "effects": config.get("effects", {"crossfade": True}),
            "effect_order": config.get("effect_order", "random"),
        }
        
        self.blockSignals(True)
        
        # フォルダリスト
        self.folder_list.clear()
        for item in config.get("folders", []):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                folder_path, recursive = item
            elif isinstance(item, str):
                folder_path, recursive = item, False
            else:
                continue
                
            list_item = QtWidgets.QListWidgetItem(folder_path)
            list_item.setData(QtCore.Qt.UserRole, recursive)
            list_item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
            self.folder_list.addItem(list_item)
            
        if self.folder_list.count() > 0:
            self.folder_list.setCurrentRow(0)
        self._on_list_selection_changed()
        
        # 表示設定
        self.monitor_combo.setCurrentIndex(config.get("monitor_index", 0))
        self.interval_spin.setValue(config.get("interval_sec", 5))
        
        # 画像再生順
        random_order = config.get("random_order", True)
        self.radio_order_random.setChecked(random_order)
        self.radio_order_name.setChecked(not random_order)
        
        # 画像表示深度
        stay_on_top = config.get("stay_on_top", True)
        self.radio_front.setChecked(stay_on_top)
        self.radio_back.setChecked(not stay_on_top)
        
        # 画像表示方法
        fit_mode = config.get("fit_mode", "cover")
        self.radio_fit_cover.setChecked(fit_mode == "cover")
        self.radio_fit_contain.setChecked(fit_mode == "contain")

        # ファイル名表示設定
        self.chk_show_filename.setChecked(config.get("show_filename", False))
        
        # 垂直・水平位置の変換
        v_pos = config.get("filename_v_pos", "bottom")
        if v_pos == "top":
            self.combo_v_pos.setCurrentText("上")
        else:
            self.combo_v_pos.setCurrentText("下")
            
        h_pos = config.get("filename_h_pos", "center")
        if h_pos == "left":
            self.combo_h_pos.setCurrentText("左")
        elif h_pos == "right":
            self.combo_h_pos.setCurrentText("右")
        else:
            self.combo_h_pos.setCurrentText("中央")
        
        # フォント設定
        self.current_font_family = config.get("font_family", self.DEFAULT_FONT_FAMILY)
        self.current_font_size = config.get("font_size", self.DEFAULT_FONT_SIZE)
        self.current_font_bold = config.get("font_bold", self.DEFAULT_FONT_BOLD)
        bold_text = "太字" if self.current_font_bold else "標準"
        self.font_label.setText(f"{self.current_font_family}, {self.current_font_size}pt, {bold_text}")

        # オフセット設定の読み込み
        self.filename_v_offset_spin.setValue(config.get("filename_v_offset", 0))
        self.filename_h_offset_spin.setValue(config.get("filename_h_offset", 0))

        # エフェクト時間設定
        fade_ms = config.get("fade_duration_ms", 1000)
        self.fade_spin.setValue(fade_ms / 1000.0)
        
        # Ken Burns効果
        self.chk_ken.setChecked(config.get("ken_burns", True))
        
        # Ken Burns強度
        ken_intensity = config.get("ken_intensity", 5)
        self.ken_intensity_slider.setValue(ken_intensity)
        self.ken_intensity_label.setText(str(ken_intensity))

        self.blockSignals(False)
        
        # ボタンの有効/無効制御
        is_default = self.current_profile == "Default"
        self.btn_profile_remove.setEnabled(not is_default)
        self.btn_profile_rename.setEnabled(not is_default)
        self.btn_profile_duplicate.setEnabled(True)

        # エフェクト設定
        effects = config.get("effects", {})
        self.chk_crossfade.setChecked(effects.get("crossfade", True))
        self.chk_slide.setChecked(effects.get("slide", False))
        self.chk_zoom.setChecked(effects.get("zoom", False))
        self.chk_wipe.setChecked(effects.get("wipe", False))
        self.chk_fade_to_black.setChecked(effects.get("fade_to_black", False))
        
        # エフェクト適用順
        effect_order = config.get("effect_order", "random")
        self.radio_effect_random.setChecked(effect_order == "random")
        self.radio_effect_order.setChecked(effect_order == "sequential")

    def _write_current_profile(self):
        """現在のUI設定をプロファイルに保存する"""
        if not self.current_profile:
            return
        
        try:
            # 最新のプロファイルデータを読み込み
            latest_data = load_profiles()
            
            # プロファイルの存在確認
            if self.current_profile not in latest_data["profiles"]:
                QtWidgets.QMessageBox.warning(
                    self,
                    "警告",
                    f"プロファイル '{self.current_profile}' は他のプロセスで削除されました。\n"
                    f"Defaultプロファイルに切り替えます。"
                )
                self.current_profile = "Default"
                self.profile_combo.setCurrentText("Default")
                self._load_current_profile()
                return
            
            # 現在のプロファイルを取得
            config = latest_data["profiles"][self.current_profile]
        
            # フォルダ設定
            folders_list = []
            for i in range(self.folder_list.count()):
                item = self.folder_list.item(i)
                folder_path = item.text()
                recursive = item.data(QtCore.Qt.UserRole)
                folders_list.append((folder_path, recursive if isinstance(recursive, bool) else False))
                
            config["folders"] = folders_list
            config["monitor_index"] = self.monitor_combo.currentIndex()
            config["interval_sec"] = self.interval_spin.value()
            config["fade_duration_ms"] = int(self.fade_spin.value() * 1000)
            config["random_order"] = self.radio_order_random.isChecked()
            config["ken_burns"] = self.chk_ken.isChecked()
            config["ken_intensity"] = self.ken_intensity_slider.value()
            config["fit_mode"] = "cover" if self.radio_fit_cover.isChecked() else "contain"
            config["stay_on_top"] = self.radio_front.isChecked()

            # ファイル名表示設定
            config["show_filename"] = self.chk_show_filename.isChecked()
            
            # 垂直・水平位置の変換
            v_text = self.combo_v_pos.currentText()
            config["filename_v_pos"] = "top" if v_text == "上" else "bottom"
            
            h_text = self.combo_h_pos.currentText()
            if h_text == "左":
                config["filename_h_pos"] = "left"
            elif h_text == "右":
                config["filename_h_pos"] = "right"
            else:
                config["filename_h_pos"] = "center"
                
            config["font_family"] = self.current_font_family
            config["font_size"] = self.current_font_size
            config["font_bold"] = self.current_font_bold
            config["filename_v_offset"] = self.filename_v_offset_spin.value()
            config["filename_h_offset"] = self.filename_h_offset_spin.value()

            # エフェクト設定
            config["effects"] = {
                "crossfade": self.chk_crossfade.isChecked(),
                "slide": self.chk_slide.isChecked(),
                "zoom": self.chk_zoom.isChecked(),
                "wipe": self.chk_wipe.isChecked(),
                "fade_to_black": self.chk_fade_to_black.isChecked(),
            }
            config["effect_order"] = "random" if self.radio_effect_random.isChecked() else "sequential"

            # latest_dataを保存
            latest_data["last_used_profile"] = self.current_profile
            _save_profiles_data(latest_data)
            
            # メモリ上のデータを最新に更新
            self.profiles = latest_data["profiles"]
            
            # 保存後に_loaded_configを更新
            self._loaded_config = self._get_current_ui_config()
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "保存エラー",
                f"プロファイルの保存中にエラーが発生しました:\n{e}"
            )
        
    def _on_profile_changed(self, index):
        """プロファイルが切り替わったときの処理"""
        if index >= 0:
            new_name = self.profile_combo.itemText(index)
            if new_name != self.current_profile:
                self.current_profile = new_name
                self._load_current_profile()

    def _has_unsaved_changes(self):
        """現在のUI設定が保存済みの設定と異なるかチェック"""
        if not self.current_profile or self.current_profile not in self.profiles:
            return False

        if not hasattr(self, '_loaded_config') or not self._loaded_config:
            return False
        
        current_config = self._get_current_ui_config()
        return self._loaded_config != current_config

    def _get_current_ui_config(self):
        """現在のUI設定を辞書として取得"""
        folders_list = []
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            folder_path = item.text()
            recursive = item.data(QtCore.Qt.UserRole)
            folders_list.append((folder_path, recursive if isinstance(recursive, bool) else False))
        
        # 垂直・水平位置の変換
        v_text = self.combo_v_pos.currentText()
        v_pos = "top" if v_text == "上" else "bottom"
        
        h_text = self.combo_h_pos.currentText()
        if h_text == "左":
            h_pos = "left"
        elif h_text == "右":
            h_pos = "right"
        else:
            h_pos = "center"
        
        return {
            "folders": folders_list,
            "monitor_index": self.monitor_combo.currentIndex(),
            "interval_sec": self.interval_spin.value(),
            "fade_duration_ms": int(self.fade_spin.value() * 1000),
            "random_order": self.radio_order_random.isChecked(),
            "ken_burns": self.chk_ken.isChecked(),
            "ken_intensity": self.ken_intensity_slider.value(), 
            "fit_mode": "cover" if self.radio_fit_cover.isChecked() else "contain",
            "stay_on_top": self.radio_front.isChecked(),
            "show_filename": self.chk_show_filename.isChecked(),
            "filename_v_pos": v_pos,
            "filename_h_pos": h_pos,
            "font_family": self.current_font_family,
            "font_size": self.current_font_size,
            "font_bold": self.current_font_bold,
            "filename_v_offset": self.filename_v_offset_spin.value(),
            "filename_h_offset": self.filename_h_offset_spin.value(),
            "effects": {
                "crossfade": self.chk_crossfade.isChecked(),
                "slide": self.chk_slide.isChecked(),
                "zoom": self.chk_zoom.isChecked(),
                "wipe": self.chk_wipe.isChecked(),
                "fade_to_black": self.chk_fade_to_black.isChecked(),
            },
            "effect_order": "random" if self.radio_effect_random.isChecked() else "sequential",
        }
    
    def _show_save_confirmation(self, profile_name):
        """保存確認ダイアログを表示"""
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("確認")
        msg_box.setText(f"プロファイル '{profile_name}' に未保存の変更があります。\n保存しますか？")
        
        save_btn = msg_box.addButton("保存", QtWidgets.QMessageBox.AcceptRole)
        discard_btn = msg_box.addButton("破棄", QtWidgets.QMessageBox.DestructiveRole)
        cancel_btn = msg_box.addButton("キャンセル", QtWidgets.QMessageBox.RejectRole)
        
        msg_box.setDefaultButton(save_btn)
        msg_box.exec_()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == save_btn:
            return "save"
        elif clicked_button == discard_btn:
            return "discard"
        else:
            return "cancel"

    def on_add_profile(self):
        """新規プロファイルを作成し、選択する"""
        new_name, ok = QtWidgets.QInputDialog.getText(self, "新規プロファイル", "新しいプロファイル名を入力:")
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name: return
            if new_name in self.profiles:
                QtWidgets.QMessageBox.warning(self, "警告", "そのプロファイル名は既に存在します。")
                return

            # デフォルト設定を使用
            source_config = self._create_default_config()
            
            self.profiles[new_name] = source_config
            self.current_profile = new_name
            self._save_profiles()
            
            self._load_profile_list()
            self._load_current_profile()
            self.profile_combo.setCurrentText(new_name)    

            # トレイメニューを更新
            self._update_tray_menu()     
            
    def on_rename_profile(self):
        """現在のプロファイルの名前を変更する"""
        if not self.current_profile: return
        if self.current_profile == "Default":
            QtWidgets.QMessageBox.warning(self, "警告", "Defaultプロファイルの名前は変更できません。")
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "プロファイルの名前変更", 
            f"プロファイル '{self.current_profile}' の新しい名前を入力:",
            QtWidgets.QLineEdit.Normal,
            self.current_profile
        )

        if ok and new_name and new_name.strip() != self.current_profile:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "警告", "プロファイル名は空にできません。")
                return

            if new_name in self.profiles:
                QtWidgets.QMessageBox.warning(self, "警告", "そのプロファイル名は既に存在します。")
                return

            # 既存の設定を新しいキーに移動
            config = self.profiles[self.current_profile]
            del self.profiles[self.current_profile]
            self.profiles[new_name] = config
            
            self.current_profile = new_name
            self._save_profiles()

            # ComboBoxを更新し、新しいプロファイルを選択
            self._load_profile_list()
            self._load_current_profile()
            self.profile_combo.setCurrentText(new_name)

            # トレイメニューを更新
            self._update_tray_menu()
            
    def on_duplicate_profile(self):
        """現在のプロファイルを複製する"""
        if not self.current_profile or self.current_profile not in self.profiles:
            return
            
        # デフォルトの複製名を生成
        base_name = f"{self.current_profile}_copy"
        new_name = base_name
        counter = 1
        
        # 重複しない名前を生成
        while new_name in self.profiles:
            new_name = f"{base_name}_{counter}"
            counter += 1
        
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            "プロファイルの複製", 
            f"'{self.current_profile}' の複製名を入力:",
            QtWidgets.QLineEdit.Normal,
            new_name
        )
        
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "警告", "プロファイル名は空にできません。")
                return
                
            if new_name in self.profiles:
                QtWidgets.QMessageBox.warning(self, "警告", "そのプロファイル名は既に存在します。")
                return
            
            # 現在のUI設定を取得して複製
            current_config = self._get_current_ui_config()
            
            # 深いコピーを作成（フォルダリストなど）
            import copy
            self.profiles[new_name] = copy.deepcopy(current_config)
            
            # 新しいプロファイルに切り替え
            self.current_profile = new_name
            self._save_profiles()
            
            self._load_profile_list()
            self.profile_combo.setCurrentText(new_name)
            
            # 複製後は「変更なし」状態にする
            self._loaded_config = self._get_current_ui_config()
            
            QtWidgets.QMessageBox.information(
                self, 
                "複製完了", 
                f"プロファイル '{new_name}' を作成しました。"
            )

            # トレイメニューを更新
            self._update_tray_menu()
                        
    def on_remove_profile(self):
        """現在のプロファイルを削除する"""
        if not self.current_profile: return
        if self.current_profile == "Default":
            QtWidgets.QMessageBox.warning(self, "警告", "Defaultプロファイルは削除できません。")
            return

        reply = QtWidgets.QMessageBox.question(self, "確認", 
            f"プロファイル '{self.current_profile}' を削除しますか？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, 
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            del self.profiles[self.current_profile]
            self.current_profile = "Default"
            self._save_profiles()

            self._load_profile_list()
            self._load_current_profile()

            # トレイメニューを更新
            self._update_tray_menu()

    def _on_create_shortcut(self):
        """Windowsショートカット作成（.lnk形式）"""
        if not self.current_profile:
            return
        
        # ショートカットの保存場所を選択
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            f"'{self.current_profile}' プロファイルのショートカットを保存", 
            f"Cinematic Slideshow - {self.current_profile}.lnk", 
            "ショートカット (*.lnk)"
        )
        
        if file_path:
            try:
                self._create_windows_shortcut(file_path)
                QtWidgets.QMessageBox.information(
                    self, 
                    "ショートカット作成完了", 
                    f"プロファイル '{self.current_profile}' のショートカットを作成しました。"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "エラー", f"ショートカット作成エラー: {e}")

    def _create_windows_shortcut(self, shortcut_path: str):
        """Windowsショートカット（.lnk）を作成する"""
        try:
            # COM オブジェクトを使用してショートカットを作成
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            
            # 実行ファイルのパスを取得
            if getattr(sys, 'frozen', False):
                # EXE化されている場合
                target_path = sys.executable
                work_dir = os.path.dirname(sys.executable)
            else:
                # 開発環境の場合
                target_path = sys.executable
                work_dir = os.path.dirname(os.path.abspath(__file__))
                
            # ショートカットの設定
            shortcut.TargetPath = target_path
            shortcut.WorkingDirectory = work_dir
            shortcut.Arguments = f'--profile "{self.current_profile}"'
            shortcut.Description = f"Cinematic Slideshow - {self.current_profile}"
            
            # アイコンの設定（EXEファイル自体のアイコンを使用）
            if getattr(sys, 'frozen', False):
                shortcut.IconLocation = f"{sys.executable},0"
            
            # ショートカットを保存
            shortcut.save()
            
        except ImportError:
            # pywin32がインストールされていない場合のフォールバック
            self._create_batch_shortcut_fallback(shortcut_path)
        except Exception as e:
            raise Exception(f"ショートカット作成に失敗しました: {e}")

    def _create_batch_shortcut_fallback(self, shortcut_path: str):
        """pywin32が利用できない場合のフォールバック（バッチファイル）"""
        # .lnk を .bat に変更
        batch_path = shortcut_path.replace('.lnk', '.bat')
        
        # 実行ファイルのパスを取得
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            work_dir = os.path.dirname(exe_path)
        else:
            script_path = os.path.abspath(__file__)
            exe_path = f'python "{script_path}"'
            work_dir = os.path.dirname(script_path)
        
        batch_content = f'''@echo off
    cd /d "{work_dir}"
    {exe_path} --profile "{self.current_profile}"
    '''
        
        with open(batch_path, 'w', encoding='shift_jis') as f:
            f.write(batch_content)
        
        QtWidgets.QMessageBox.information(
            None,
            "注意", 
            "pywin32がインストールされていないため、バッチファイルを作成しました。\n"
            f"ファイル: {batch_path}"
        )

    def _on_backup_profiles(self):
        """プロファイル設定をバックアップする"""
        try:
            # ドキュメントフォルダを取得
            documents_path = os.path.expanduser("~/Documents")
            
            # デフォルトファイル名（日時付き）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"CinematicSlideshow_Backup_{timestamp}.json"
            default_path = os.path.join(documents_path, default_filename)
            
            # ファイル保存ダイアログ
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "プロファイル設定のバックアップ",
                default_path,
                "JSON ファイル (*.json);;すべてのファイル (*)"
            )
            
            if file_path:
                # 現在の設定を保存してからバックアップ
                self._write_current_profile()
                
                # profiles.jsonの内容をコピー
                if os.path.exists(PROFILES_FILE):
                    import shutil
                    shutil.copy2(PROFILES_FILE, file_path)
                    
                    QtWidgets.QMessageBox.information(
                        self,
                        "バックアップ完了",
                        f"プロファイル設定をバックアップしました。\n\n"
                        f"保存先: {file_path}"
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "エラー",
                        "プロファイルファイルが見つかりません。"
                    )
                    
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "バックアップエラー",
                f"バックアップに失敗しました:\n{e}"
            )

    def _on_restore_profiles(self):
        """プロファイル設定をリストアする"""
        try:
            # ドキュメントフォルダを取得
            documents_path = os.path.expanduser("~/Documents")
            
            # ファイル選択ダイアログ
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "プロファイル設定のリストア",
                documents_path,
                "JSON ファイル (*.json);;すべてのファイル (*)"
            )
            
            if file_path:
                # 確認ダイアログ
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "リストア確認",
                    "現在のプロファイル設定がすべて置き換えられます。\n"
                    "続行しますか？\n\n"
                    "※現在の設定は失われます。事前にバックアップを取ることをお勧めします。",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    # バックアップファイルの妥当性をチェック
                    if self._validate_backup_file(file_path):
                        # profiles.jsonを置き換え
                        import shutil
                        shutil.copy2(file_path, PROFILES_FILE)
                        
                        # プロファイルを再読み込み
                        self._load_profiles()
                        
                        QtWidgets.QMessageBox.information(
                            self,
                            "リストア完了",
                            "プロファイル設定をリストアしました。\n\n"
                            "変更を反映するには、アプリケーションを再起動してください。"
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "エラー",
                            "選択されたファイルは有効なバックアップファイルではありません。"
                        )
                        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "リストアエラー",
                f"リストアに失敗しました:\n{e}"
            )

    def _validate_backup_file(self, file_path: str) -> bool:
        """バックアップファイルの妥当性をチェック"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 必須キーの確認
            if not isinstance(data, dict):
                return False
            if "profiles" not in data:
                return False
            if not isinstance(data["profiles"], dict):
                return False
            
            # 少なくとも1つのプロファイルがあるかチェック
            if len(data["profiles"]) == 0:
                return False
            
            # 各プロファイルの基本構造をチェック
            for profile_name, profile_data in data["profiles"].items():
                if not isinstance(profile_data, dict):
                    return False
                # 必須キーの存在確認
                required_keys = ["folders", "monitor_index", "interval_sec"]
                for key in required_keys:
                    if key not in profile_data:
                        return False
            
            return True
            
        except Exception as e:
            print(f"Backup validation error: {e}")
            return False

    # ----------------------------------------------------
    # フォルダ/フォント操作
    # ----------------------------------------------------

    def _on_add_folder(self):
        """画像フォルダを追加する"""
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "画像フォルダの選択")
        if folder_path:
            # 既にリストにあるかチェック（重複防止）
            for i in range(self.folder_list.count()):
                if os.path.normpath(self.folder_list.item(i).text()) == os.path.normpath(folder_path):
                    QtWidgets.QMessageBox.warning(self, "警告", "そのフォルダは既に追加されています。")
                    return

            item = QtWidgets.QListWidgetItem(folder_path)
            # ユーザーデータとして再帰フラグ(Trueをデフォルト)を保存
            item.setData(QtCore.Qt.UserRole, True) 
            item.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
            self.folder_list.addItem(item)
            
            # 追加後、新しいアイテムを選択状態にする
            self.folder_list.setCurrentItem(item)
            
    def _on_remove_folder(self):
        """選択されている画像フォルダを削除する"""
        current_row = self.folder_list.currentRow()
        if current_row >= 0:
            self.folder_list.takeItem(current_row)
            
            # フォルダリストが空になったら再帰チェックボックスを無効化
            if self.folder_list.count() == 0:
                self.chk_recursive.setEnabled(False)            

    def _on_list_selection_changed(self):
        """フォルダリストの選択が変更されたとき、再帰チェックボックスの状態を更新"""
        item = self.folder_list.currentItem()
        if item:
            recursive = item.data(QtCore.Qt.UserRole) 
            self.chk_recursive.blockSignals(True)
            # データがbooleanでない場合も考慮し、デフォルトをTrueとする
            self.chk_recursive.setChecked(recursive if isinstance(recursive, bool) else True) 
            self.chk_recursive.blockSignals(False)
            self.chk_recursive.setEnabled(True)
        else:
            self.chk_recursive.setEnabled(False)

    def _on_recursive_changed(self):
        """再帰チェックボックスの状態が変更されたときの処理"""
        item = self.folder_list.currentItem()
        if item:
            new_recursive = self.chk_recursive.isChecked()
            item.setData(QtCore.Qt.UserRole, new_recursive)
            
    def _on_select_font(self):
        """フォント選択ダイアログを表示し、選択結果を保存する"""
        current_font = QtGui.QFont(self.current_font_family, self.current_font_size)
        if self.current_font_bold:
            current_font.setBold(True)

        font, ok = QtWidgets.QFontDialog.getFont(current_font, self, "フォントの選択")

        if ok:
            self.current_font_family = font.family()
            self.current_font_size = font.pointSize()
            self.current_font_bold = font.bold()
            
            bold_text = "太字" if self.current_font_bold else "標準"
            self.font_label.setText(f"{self.current_font_family}, {self.current_font_size}pt, {bold_text}")
            
    # ----------------------------------------------------
    # スライドショーの起動とコールバック
    # ----------------------------------------------------
    def _on_slideshow_settings_requested(self, profile_name: str):
        """スライドショーから設定画面に戻るリクエストを受けたときの処理"""
        print(f"設定画面を開く: スライドショーのプロファイル='{profile_name}', 設定画面のプロファイル='{self.current_profile}'")
        
        # 元のプロファイル名を保存（これがスライドショーから呼ばれたことを示すフラグにもなる）
        self._original_profile = profile_name
        
        # スライドショーのプロファイルに合わせる
        if profile_name != self.current_profile:
            self.current_profile = profile_name
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentText(profile_name)
            self.profile_combo.blockSignals(False)
            self._load_current_profile()
        
        # 現在のUI設定を保存して、変更検出の基準とする
        self._loaded_config = self._get_current_ui_config()
        
        # 設定画面を開いた時点の設定を保存（最終的な変更判定用）
        self._initial_config = self._get_current_ui_config()
        self._initial_profile = profile_name

        # 設定画面を最前面で表示
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.show()
        self.raise_()
        self.activateWindow()

    def start_slideshow(self):
        """スライドショーを開始する"""
        self._write_current_profile()
        config = self.profiles.get(self.current_profile)
        if not config:
            QtWidgets.QMessageBox.critical(self, "エラー", "プロファイルがロードされていません。")
            return

        image_files = []
        folders = config.get("folders", [])
        total_folders = len(config.get("folders", []))

        for idx, item in enumerate(folders):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                folder_path, recursive = item
            elif isinstance(item, str):
                folder_path, recursive = item, False
            else:
                continue
                
            if os.path.isdir(folder_path):
                try:
                    image_files.extend(list_images(folder_path, recursive))
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "エラー", f"フォルダ: {folder_path} の画像リストアップ中にエラーが発生しました: {e}")
                    return

        if not image_files:
            QtWidgets.QMessageBox.warning(self, "警告", "表示する画像ファイルが見つかりません。フォルダ設定を確認してください。")
            return

        if self.slideshow_window and self.slideshow_window.isVisible():
            self.slideshow_window.close()

        try:
            self.hide() 
            effects = {
                "crossfade": self.chk_crossfade.isChecked(),
                "slide": self.chk_slide.isChecked(),
                "zoom": self.chk_zoom.isChecked(),
                "wipe": self.chk_wipe.isChecked(),
                "fade_to_black": self.chk_fade_to_black.isChecked(),
            }
            effect_order = "random" if self.radio_effect_random.isChecked() else "sequential"
            self.slideshow_window = SlideShowWindow(
                image_files=image_files,
                current_profile_name=self.current_profile,
                monitor_index=config.get("monitor_index", 0),
                stay_on_top=config.get("stay_on_top", True),
                interval_sec=config.get("interval_sec", 5),
                ken_burns=config.get("ken_burns", True),
                ken_intensity=config.get("ken_intensity", 5),
                random_order=config.get("random_order", True),
                fit_mode=config.get("fit_mode", "cover"),
                fade_duration_ms=config.get("fade_duration_ms", 1000),
                show_filename=config.get("show_filename", False),
                filename_v_pos=config.get("filename_v_pos", "bottom"),
                filename_h_pos=config.get("filename_h_pos", "center"),
                font_family=config.get("font_family", self.DEFAULT_FONT_FAMILY),
                font_size=config.get("font_size", self.DEFAULT_FONT_SIZE),
                font_bold=config.get("font_bold", self.DEFAULT_FONT_BOLD),
                filename_v_offset=config.get("filename_v_offset", 0),
                filename_h_offset=config.get("filename_h_offset", 0),
                effects=effects,
                effect_order=effect_order,
                main_window=self
            )
            
            # スライドショーからの信号接続
            self.slideshow_window.showSettingsRequested.connect(self._on_slideshow_settings_requested)
            
            self.slideshow_window.show() 
            if hasattr(self, 'pause_action'):
                self.pause_action.setEnabled(True)
                    
        except NameError:
            QtWidgets.QMessageBox.critical(self, "エラー", "SlideShowWindowクラスが未定義です。スライドショーを開始できません。")
            self.slideshow_window = None
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "エラー", f"スライドショーの開始に失敗しました:\n{e}")
            self.slideshow_window = None
        
    def _setup_system_tray(self):
        """システムトレイアイコンを設定"""
        # システムトレイがサポートされているかチェック
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            QtWidgets.QMessageBox.critical(
                None, 
                "システムトレイ", 
                "システムトレイが利用できません。"
            )
            return
        
        # トレイアイコンを作成
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        
        # アイコンを設定
        if not self.windowIcon().isNull():
            self.tray_icon.setIcon(self.windowIcon())
        else:
            # フォールバック：システムアイコン
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
            self.tray_icon.setIcon(icon)
        
        # ツールチップを設定
        self.tray_icon.setToolTip(f"Cinematic Slideshow - {self.current_profile}")
        
        # コンテキストメニューを作成
        self._create_tray_menu()
        
        # シグナルを接続
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # トレイアイコンを表示
        self.tray_icon.show()

    def _create_tray_menu(self):
        """トレイアイコンのコンテキストメニューを作成"""
        tray_menu = QtWidgets.QMenu()
        
        # プロファイル切り替えサブメニュー
        profile_menu = tray_menu.addMenu("プロファイル切り替え")
        profile_menu.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        
        # プロファイル一覧を追加
        self.profile_actions = []
        for profile_name in sorted(self.profiles.keys()):
            action = profile_menu.addAction(profile_name)
            action.setCheckable(True)
            action.setChecked(profile_name == self.current_profile)
            action.triggered.connect(lambda checked, name=profile_name: self._switch_profile_and_restart(name))
            self.profile_actions.append(action)
        
        tray_menu.addSeparator()
        
        # 一時停止/再開
        self.pause_action = tray_menu.addAction("一時停止/再開")
        self.pause_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self.pause_action.triggered.connect(self._toggle_pause_from_tray)
        self.pause_action.setEnabled(False) 
        
        tray_menu.addSeparator()
        
        # 設定
        settings_action = tray_menu.addAction("設定")
        settings_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        settings_action.triggered.connect(self._show_settings_from_tray)
        
        # バージョン情報
        about_action = tray_menu.addAction("バージョン情報")
        about_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        about_action.triggered.connect(self._show_about_dialog)
        
        tray_menu.addSeparator()
        
        # 終了
        quit_action = tray_menu.addAction("終了")
        quit_action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        quit_action.triggered.connect(self._quit_application)
        
        # メニューをトレイアイコンに設定
        self.tray_icon.setContextMenu(tray_menu)

    def _on_tray_activated(self, reason):
        """トレイアイコンが右クリックされた時の処理"""
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            # ダブルクリックで設定画面を表示
            self._show_settings_from_tray()

    def _switch_profile_and_restart(self, profile_name: str):
        """プロファイルを切り替えて即座に再起動"""
        if profile_name == self.current_profile:
            return
        
        # プロファイルを切り替え
        self.current_profile = profile_name
        self.profile_combo.setCurrentText(profile_name)
        self._load_current_profile()
        
        # profiles.jsonを更新
        try:
            if os.path.exists(PROFILES_FILE):
                with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data["last_used_profile"] = profile_name
                
                with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"プロファイル保存エラー: {e}")
        
        # スライドショーを再起動
        if hasattr(self, 'slideshow_window') and self.slideshow_window:
            self._restart_slideshow()
        
        # メニューのチェック状態を更新
        for action in self.profile_actions:
            action.setChecked(action.text() == profile_name)

    def _update_tray_menu(self):
        """トレイメニューを更新（プロファイル変更時）"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            # 既存のメニューをクリア
            self.tray_icon.setContextMenu(None)
            # 新しいメニューを作成
            self._create_tray_menu()

    def _toggle_pause_from_tray(self):
        """トレイから一時停止/再開を切り替え"""
        if hasattr(self, 'slideshow_window') and self.slideshow_window:
            self.slideshow_window._toggle_pause()

    def _show_settings_from_tray(self):
        """トレイから設定画面を表示"""
        if hasattr(self, 'slideshow_window') and self.slideshow_window:
            # スライドショー実行中の場合
            self._on_slideshow_settings_requested(self.current_profile)
        else:
            # スライドショー停止中の場合は通常表示
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_application(self):
        """アプリケーションを終了"""
        # スライドショーウィンドウを閉じる
        if hasattr(self, 'slideshow_window') and self.slideshow_window:
            self.slideshow_window.close()
        
        # トレイアイコンを非表示
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        
        # アプリケーション終了
        QtWidgets.QApplication.quit()
          
# ==============================================================================
# 2. 実行ブロック (エントリポイント)
# ==============================================================================

def start_slideshow_direct(profile_name: str, profile_data: Dict[str, Any]):
    """指定されたプロファイル設定で直接スライドショーウィンドウを起動する"""
    # 既存のインスタンスをチェック
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    # MainWindowのインスタンスを作成
    main_window = MainWindow()
    main_window.hide() 

    # プロファイルを設定
    main_window.current_profile = profile_name
    if profile_name not in main_window.profiles:
        main_window.profiles[profile_name] = profile_data
    main_window.profile_combo.setCurrentText(profile_name)

    # プロファイルを反映
    main_window._load_profile_list()
    main_window.profile_combo.setCurrentText(profile_name)
    main_window._load_current_profile()

    folders_with_recursive = profile_data.get("folders", []) 
    all_images = []
    
    for item in folders_with_recursive:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            folder_path, recursive_flag = item
            if os.path.isdir(folder_path):
                all_images.extend(list_images(folder_path, recursive=recursive_flag))
        elif isinstance(item, str) and os.path.isdir(item):
            all_images.extend(list_images(item, recursive=False))

    if not all_images:
        print("画像ファイルが見つかりませんが、スライドショーウィンドウを表示します。")
    else:
        print(f"{len(all_images)}枚の画像が見つかりました。")
        
    # 設定の抽出
    monitor_index = profile_data.get("monitor_index", 0)
    interval_sec = profile_data.get("interval_sec", 5)
    ken_burns = profile_data.get("ken_burns", True)
    ken_intensity = profile_data.get("ken_intensity", 5) 
    random_order = profile_data.get("random_order", True)
    fit_mode = profile_data.get("fit_mode", "cover")
    fade_duration_ms = profile_data.get("fade_duration_ms", 1000)
    stay_on_top = profile_data.get("stay_on_top", True)    
    show_filename = profile_data.get("show_filename", False)
    filename_v_pos = profile_data.get("filename_v_pos", "bottom")
    filename_h_pos = profile_data.get("filename_h_pos", "center")
    font_family = profile_data.get("font_family", MainWindow.DEFAULT_FONT_FAMILY)
    font_size = profile_data.get("font_size", MainWindow.DEFAULT_FONT_SIZE)
    font_bold = profile_data.get("font_bold", MainWindow.DEFAULT_FONT_BOLD) 
    filename_v_offset = profile_data.get("filename_v_offset", 0)
    filename_h_offset = profile_data.get("filename_h_offset", 0)
    effects = profile_data.get("effects", {"crossfade": True})
    effect_order = profile_data.get("effect_order", "random")

    try:
        slideshow_win = SlideShowWindow(
            image_files=all_images,
            current_profile_name=profile_name,
            monitor_index=monitor_index,
            stay_on_top=stay_on_top,
            interval_sec=interval_sec,
            ken_burns=ken_burns,
            ken_intensity=ken_intensity,
            random_order=random_order,
            fit_mode=fit_mode,
            fade_duration_ms=fade_duration_ms,
            show_filename=show_filename,
            filename_v_pos=filename_v_pos,
            filename_h_pos=filename_h_pos,
            font_family=font_family,
            font_size=font_size,
            filename_v_offset=filename_v_offset,
            filename_h_offset=filename_h_offset,
            effects=effects,
            effect_order=effect_order,
            main_window=main_window
        )

        main_window.slideshow_window = slideshow_win

        # スライドショーからの信号を接続
        slideshow_win.showSettingsRequested.connect(main_window._on_slideshow_settings_requested)

        if hasattr(main_window, 'pause_action'):
            main_window.pause_action.setEnabled(True)
        
        # スライドショーが閉じられたときの処理
        def on_slideshow_closed():
            if hasattr(main_window, 'pause_action'):
                main_window.pause_action.setEnabled(False)

            try:
                if main_window and hasattr(main_window, 'isVisible'):
                    if main_window.isVisible():
                        pass
                    else:
                        app.quit()
                else:
                    app.quit()
            except RuntimeError:
                app.quit()
        
        slideshow_win.destroyed.connect(on_slideshow_closed)
        
        slideshow_win.show() 
        sys.exit(app.exec_())

    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "エラー", f"スライドショーの開始に失敗しました:\n{e}")
        main_window.show()
        sys.exit(app.exec_())

if __name__ == '__main__':
    # Qt設定の最適化
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    # 既存のQApplicationインスタンスをチェック
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("Cinematic Slideshow")
        app.setOrganizationName("sitarj")
    
    # 例外ハンドラを設定
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        print(f"Uncaught exception: {exc_type.__name__}: {exc_value}")
    
    sys.excepthook = handle_exception
    
    try:
        profiles_data = load_profiles()
        
        # 引数処理
        if len(sys.argv) > 1:
            if sys.argv[1] == "--settings" or sys.argv[1] == "-s":
                # 設定画面モード
                main_window = MainWindow()
                main_window.show()
                sys.exit(app.exec_())
            elif sys.argv[1] == "--profile" or sys.argv[1] == "-p":
                # プロファイル指定
                if len(sys.argv) > 2:
                    target_profile_name = sys.argv[2]
                    if target_profile_name in profiles_data.get("profiles", {}):
                        profile_name = target_profile_name
                    else:
                        print(f"エラー: プロファイル '{target_profile_name}' が見つかりません")
                        profile_name = profiles_data.get("last_used_profile", "Default")
                else:
                    print("エラー: プロファイル名が指定されていません")
                    profile_name = profiles_data.get("last_used_profile", "Default")
            else:
                # プロファイル名直接指定
                target_profile_name = sys.argv[1]
                if target_profile_name in profiles_data.get("profiles", {}):
                    profile_name = target_profile_name
                else:
                    print(f"エラー: プロファイル '{target_profile_name}' が見つかりません")
                    profile_name = profiles_data.get("last_used_profile", "Default")
        else:
            profile_name = profiles_data.get("last_used_profile", "Default")
            if profile_name not in profiles_data.get("profiles", {}):
                profile_name = "Default"
        
        print(f"プロファイル '{profile_name}' でスライドショーを開始します。")
        
        # スライドショー起動
        start_slideshow_direct(profile_name, profiles_data["profiles"][profile_name])
        
    except Exception as e:
        print(f"起動エラー: {e}")
        sys.exit(1)
