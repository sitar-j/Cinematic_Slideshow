"""
Cinematic Slideshow - Slideshow application with cinematic effects

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
import locale
import os
import glob
import json
import random
import math
from typing import List ,Tuple ,Dict ,Any
from PyQt5 import QtWidgets ,QtCore ,QtGui
from datetime import datetime

def detect_system_language():
    try:
        lang = locale.getdefaultlocale()[0] or ""
        return "ja" if lang.lower().startswith("ja") else "en"
    except Exception:
        return "en"
    
def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        relative_path
    )

current_lang = detect_system_language()
locale_path = resource_path("locales.json")

try:
    with open(locale_path, "r", encoding="utf-8") as f:
        translations = json.load(f)

except Exception as e:
    print(f"Failed to load locales.json: {e}")
    translations = {}


def tr(key):
    value = translations.get(key, {}).get(current_lang)

    if value is None:
        return key

    return value

try :
    import win32com .client 
    PYWIN32_AVAILABLE =True 
except ImportError :
    PYWIN32_AVAILABLE =False 
    print ("Warning: pywin32 not installed. Windows shortcut creation disabled.")

try :
    from PIL import Image 
    import pillow_avif 
    PILLOW_AVAILABLE =True 
except ImportError :
    PILLOW_AVAILABLE =False 
    print ("Warning: pillow-avif-plugin not installed. AVIF support disabled.")

PROFILES_FILE ="profiles.json"
ANIM_FPS =24 

NATIVE_IMAGE_FORMATS =(
".jpg",".jpeg",".png",".bmp",".gif",
".webp",".tiff",".tif",".ico",".svg",
".cur",".icns",".pbm",".pgm",".ppm",
".tga",".wbmp",".xbm",".xpm"
)

PILLOW_ONLY_FORMATS =(
".avif",".heic",".heif",".jp2",".j2k"
)

if PILLOW_AVAILABLE :
    SUPPORTED_IMAGE_FORMATS =NATIVE_IMAGE_FORMATS +PILLOW_ONLY_FORMATS 
else :
    SUPPORTED_IMAGE_FORMATS =NATIVE_IMAGE_FORMATS 

def create_pixmap_from_file (file_path :str )->QtGui .QPixmap :
    ext =os .path .splitext (file_path )[1 ].lower ()

    if ext in NATIVE_IMAGE_FORMATS :
        pixmap =QtGui .QPixmap (file_path )
        if not pixmap .isNull ():
            return pixmap 

    if PILLOW_AVAILABLE :
        try :
            with Image .open (file_path )as img :

                img .load ()

                if img .mode =='RGBA':
                    rgba_img =img .copy ()
                elif img .mode =='LA'or (img .mode =='P'and 'transparency'in img .info ):
                    rgba_img =img .convert ('RGBA')
                else :
                    rgba_img =img .convert ('RGB')

                if rgba_img .mode =='RGBA':

                    data =rgba_img .tobytes ('raw','RGBA')
                    qimage =QtGui .QImage (
                    data ,
                    rgba_img .width ,
                    rgba_img .height ,
                    rgba_img .width *4 ,
                    QtGui .QImage .Format_RGBA8888 
                    )

                    qimage =qimage .copy ()
                else :
                    data =rgba_img .tobytes ('raw','RGB')
                    qimage =QtGui .QImage (
                    data ,
                    rgba_img .width ,
                    rgba_img .height ,
                    rgba_img .width *3 ,
                    QtGui .QImage .Format_RGB888 
                    )
                    qimage =qimage .copy ()

                del rgba_img 
                del data 

                pixmap =QtGui .QPixmap .fromImage (qimage )
                return pixmap 

        except Exception as e :
            print (f"Error loading {file_path } with Pillow: {e }")

    return QtGui .QPixmap ()

class SlideShowWindow (QtWidgets .QWidget ):
    def reload_profile (self ):
        if not self .main_window :
            return 

        config =self .main_window .profiles .get (self .current_profile_name )
        if not config :
            return 

        self .interval_ms =max (1 ,int (config .get ("interval_sec",5 )*1000 ))
        self .ken_burns =config .get ("ken_burns",True )
        self .ken_intensity =config .get ("ken_intensity",5 )
        self .fit_mode =config .get ("fit_mode","cover")
        self .fade_duration_ms =config .get ("fade_duration_ms",1000 )
        self .show_filename =config .get ("show_filename",False )
        self .filename_v_pos =config .get ("filename_v_pos","bottom")
        self .filename_h_pos =config .get ("filename_h_pos","center")
        self .font_family = config.get("font_family", "Yu Gothic UI")
        self .font_size =config .get ("font_size",18 )
        self .font_bold =config .get ("font_bold",True )
        self .filename_v_offset =config .get ("filename_v_offset",0 )
        self .filename_h_offset =config .get ("filename_h_offset",0 )
        self .effects =config .get ("effects",{"crossfade":True })
        self .effect_order =config .get ("effect_order","random")
        self .enabled_effects =[k for k ,v in self .effects .items ()if v ]
        self .slide_timer .stop ()
        self .animation_timer .stop ()
        self .animating =False 
        self .is_paused =False 

        new_image_files =[]
        for item in config .get ("folders",[]):
            if isinstance (item ,(list ,tuple ))and len (item )==2 :
                folder_path ,recursive =item 
            elif isinstance (item ,str ):
                folder_path ,recursive =item ,False 
            else :
                continue 

            if os .path .isdir (folder_path ):
                try :
                    new_image_files .extend (list_images (folder_path ,recursive ))
                except Exception :
                    continue 

        if new_image_files :

            if config .get ("random_order",True ):
                random .shuffle (new_image_files )
            self .image_files =new_image_files 

            self .index =0 

            if self .image_files :
                self ._show_first_image ()
        else :

            self ._show_no_images_message ()

    showSettingsRequested =QtCore .pyqtSignal (str )
    switchProfileRequested =QtCore .pyqtSignal (str )

    def _select_next_effect (self ):
        if not self .enabled_effects :
            return "none"

        if self .effect_order =="random":
            return random .choice (self .enabled_effects )
        else :
            effect =self .enabled_effects [self .current_effect_index ]

            self .current_effect_index =(self .current_effect_index +1 )%len (self .enabled_effects )
            return effect
    
    def _select_next_ken_burns_pattern (self ):
        patterns =self .enabled_ken_burns_patterns [:]

        if self .fit_mode !="cover":
            patterns =[p for p in patterns if p !="edge_scan"]
        if not patterns :
            return "none"
        if self .ken_burns_order =="random":
            return random .choice (patterns )

        pattern =patterns [self .current_ken_burns_index %len (patterns )]
        self .current_ken_burns_index =(
        self .current_ken_burns_index +1 
        )%len (patterns )

        return pattern 

    def showEvent (self ,event ):
        super ().showEvent (event )

        if self .is_loading :
            return 

        if not self .image_files :

            self ._show_no_images_message ()
        elif not self .current_item :

            self ._show_first_image ()

    def _show_no_images_message (self ):

        self .scene .clear ()

        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()

        self .scene .setSceneRect (-vw /2 ,-vh /2 ,vw ,vh )

        bg_rect =QtWidgets .QGraphicsRectItem (-vw /2 ,-vh /2 ,vw ,vh )
        bg_rect .setBrush (QtGui .QBrush (QtGui .QColor (0 ,0 ,0 ,150 )))
        bg_rect .setPen (QtGui .QPen (QtCore .Qt .NoPen ))
        self .scene .addItem (bg_rect )

        message_html =f"""
        <div style='
            width: 500px; 
            text-align: center; 
            color: white; 
            background-color: rgba(0,0,0,180); 
            padding: 40px; 
            border-radius: 10px; 
            border: 2px solid #555;
            font-family: "Yu Gothic UI", "Yu Gothic", "Meiryo", "Segoe UI", "Noto Sans CJK JP", sans-serif;
        '>
            <h1 style='color: #FFF; margin-bottom: 28px;'>🎬 Cinematic Slideshow</h1>
            <p style='font-size: 20px; line-height: 1.6; margin-bottom: 20px;'>
                {tr("msg_intro")}<br>
                {tr("msg_add_folder")}
            </p>
            <p style='font-size: 16px; line-height: 1.6; margin-bottom: 20px; color: #CCC;'>
                <strong>{tr("msg_how_to_open_settings")}</strong>
            </p>
        </div>
        """

        text_item =QtWidgets .QGraphicsTextItem ()
        text_item .setHtml (message_html )
        text_item .setTextWidth (500 )

        text_rect =text_item .boundingRect ()

        text_x =-text_rect .width ()/2 
        text_y =-text_rect .height ()/2 
        text_item .setPos (text_x ,text_y )
        text_item .setZValue (2.0 )

        self .scene .addItem (text_item )

        self .current_item =text_item 

    def __init__ (
    self ,
    image_files :List [str ],
    current_profile_name :str ,
    monitor_index :int =0 ,
    window_mode :str ="fullscreen",
    window_width :int =1280 ,
    window_height :int =768 ,
    window_resizable :bool =True ,
    stay_on_top :bool =True ,
    interval_sec :int =5 ,
    ken_burns_patterns :Dict [str ,bool ]=None ,
    ken_burns_order :str ="random",
    ken_burns :bool =True ,
    ken_intensity :int =5 ,
    random_order :bool =True ,
    fit_mode :str ="cover",
    fade_duration_ms :int =1000 ,
    show_filename :bool =False ,
    filename_v_pos :str ="bottom",
    filename_h_pos :str ="center",
    font_family: str = "Yu Gothic UI",
    font_size :int =18 ,
    font_bold :bool =True ,
    filename_v_offset :int =0 ,
    filename_h_offset :int =0 ,
    effects :Dict [str ,bool ]=None ,
    effect_order :str ="random",
    main_window :QtWidgets .QWidget =None ,
    ):
        super ().__init__ ()
        self .image_files =image_files [:]
        if random_order :
            random .shuffle (self .image_files )
        self .index =0 
        self .current_profile_name =current_profile_name 
        self .main_window =main_window 
        self .interval_ms =max (1 ,int (interval_sec *1000 ))
        self .ken_burns =ken_burns 
        self .ken_intensity =ken_intensity
        self .ken_burns_patterns =ken_burns_patterns or {
        "linear":True ,
        "arc":True ,
        "wave":True ,
        "spiral_in":True ,
        "zigzag":True ,
        "edge_scan":False ,
        }

        self .ken_burns_order =ken_burns_order 
        self .enabled_ken_burns_patterns =[
        k for k ,v in self .ken_burns_patterns .items ()if v 
        ]

        if not self .enabled_ken_burns_patterns :
            self .enabled_ken_burns_patterns =["linear"]

        self .current_ken_burns_index =0 
        self .fit_mode =fit_mode 
        self .fade_duration_ms =fade_duration_ms 
        self .show_filename =show_filename 
        self .filename_v_pos =filename_v_pos 
        self .filename_h_pos =filename_h_pos 
        self .font_family =font_family 
        self .font_size =font_size 
        self .font_bold =font_bold 
        self .filename_v_offset =filename_v_offset 
        self .filename_h_offset =filename_h_offset 
        self .effects =effects or {"crossfade":True }
        self .effect_order =effect_order 
        self .enabled_effects =[k for k ,v in self .effects .items ()if v ]
        self .current_effect_index =0 
        self .current_effect =None 
        self .next_effect =None 
        self .is_transitioning =False 
        self .text_item =None 
        self .is_paused =False 
        self .window_mode =window_mode 
        self .window_width =window_width 
        self .window_height =window_height 
        self .window_resizable =window_resizable 

        screens =QtWidgets .QApplication .screens ()
        if monitor_index >=len (screens ):
            monitor_index =0 
        screen =screens [monitor_index ]
        geom =screen .geometry ()
        self .setGeometry (geom )

        if window_mode =="window":

            if stay_on_top :
                flags =QtCore .Qt .Window |QtCore .Qt .WindowStaysOnTopHint 
            else :
                flags =QtCore .Qt .Window 

            self .setWindowFlags (flags )
            self .setWindowTitle (f"Cinematic Slideshow - {current_profile_name }")

            if not window_resizable :
                self .setFixedSize (window_width ,window_height )
            else :
                self .resize (window_width ,window_height )

            primary_screen =QtWidgets .QApplication .primaryScreen ()
            screen_center =primary_screen .geometry ().center ()
            window_rect =QtCore .QRect (0 ,0 ,window_width ,window_height )
            window_rect .moveCenter (screen_center )
            self .move (window_rect .topLeft ())
        else :

            self .setGeometry (geom )
            if stay_on_top :
                flags =QtCore .Qt .FramelessWindowHint |QtCore .Qt .WindowStaysOnTopHint 
            else :
                flags =QtCore .Qt .FramelessWindowHint |QtCore .Qt .WindowStaysOnBottomHint 
            self .setWindowFlags (flags )

        self .view =QtWidgets .QGraphicsView (self )
        self .view .setHorizontalScrollBarPolicy (QtCore .Qt .ScrollBarAlwaysOff )
        self .view .setVerticalScrollBarPolicy (QtCore .Qt .ScrollBarAlwaysOff )
        self .view .setFrameShape (QtWidgets .QFrame .NoFrame )
        self .view .setAlignment (QtCore .Qt .AlignCenter )
        self .view .setStyleSheet ("background-color: black;")
        self .scene =QtWidgets .QGraphicsScene (self )
        self .scene .setBackgroundBrush (QtGui .QBrush (QtCore .Qt .black ))
        self .view .setScene (self .scene )

        self .view .setGeometry (self .rect ())

        self .current_item =None 
        self .next_item =None 

        self .MOVEMENT_PATTERNS =["linear","arc","wave","spiral_in","zigzag"]

        self .current_movement_pattern =None 

        self .slide_timer =QtCore .QTimer (self )
        self .slide_timer .setSingleShot (True )
        self .slide_timer .timeout .connect (self ._on_slide_timeout )

        self .animation_timer =QtCore .QTimer (self )
        self .animation_timer .timeout .connect (self ._on_anim_frame )
        self .animating =False 

        self .anim_start_time =0 
        self .anim_duration =self .interval_ms 
        self .anim_fps_interval =int (1000 /ANIM_FPS )

        self ._pixmap_cache ={}
        self ._cache_max_size =3 

        self ._load_error_count ={}

        self .loading_items =[]
        self .is_loading =True 

        if window_mode =="window":
            self .show ()
        else :
            if stay_on_top :
                self .showFullScreen ()
            else :
                self .showNormal ()
                self .setWindowState (QtCore .Qt .WindowMaximized )

        self ._show_loading_screen ()

    def resizeEvent (self ,event ):
        super ().resizeEvent (event )
        self .view .setGeometry (self .rect ())

        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()
        self .scene .setSceneRect (-vw /2 ,-vh /2 ,vw ,vh )

        if self .text_item and self .text_item .scene ()==self .scene :
            self ._update_text_position (self .text_item )

    def contextMenuEvent (self ,event ):

        if hasattr (self ,'is_loading')and self .is_loading :
            return 

        menu =QtWidgets .QMenu (self )

        action_next =menu .addAction (tr("menu_next_image"))
        action_next .triggered .connect (self ._go_next )

        action_prev =menu .addAction (tr("menu_prev_image"))
        action_prev .triggered .connect (self ._go_prev )

        menu .addSeparator ()

        action_pause =menu .addAction (tr("menu_toggle_pause"))
        action_pause .setCheckable (True )
        action_pause .setChecked (self .is_paused )
        action_pause .triggered .connect (self ._toggle_pause )

        menu .addSeparator ()

        action_settings =menu .addAction (tr("menu_settings"))
        action_settings .triggered .connect (lambda :self .showSettingsRequested .emit (self .current_profile_name ))

        action_explorer =menu .addAction (tr("menu_open_in_explorer"))
        action_explorer .setEnabled (bool (self .image_files ))
        action_explorer .triggered .connect (self ._open_in_explorer )

        action_delete =menu .addAction (tr("menu_delete_image"))
        action_delete .setEnabled (bool (self .image_files ))
        action_delete .triggered .connect (self ._delete_current_image )

        menu .addSeparator ()

        action_about =menu .addAction (tr("menu_about"))
        action_about .triggered .connect (self ._show_about_dialog )

        action_exit =menu .addAction (tr("menu_exit"))
        action_exit .triggered .connect (self .close )

        menu .exec_ (event .globalPos ())

    def keyPressEvent (self ,event ):
        if event .key ()==QtCore .Qt .Key_Escape :
            self .close ()
        elif event .key ()==QtCore .Qt .Key_Space :
            self ._toggle_pause ()
        elif event .key ()==QtCore .Qt .Key_Right :
            self ._go_next ()
        elif event .key ()==QtCore .Qt .Key_Left :
            self ._go_prev ()

    def close (self ):
        self .slide_timer .stop ()
        if self .animation_timer .isActive ():
            self .animation_timer .stop ()

        if hasattr (self ,'main_window')and self .main_window :
            if hasattr (self .main_window ,'pause_action'):
                self .main_window .pause_action .setEnabled (False )

        super ().close ()

    def _toggle_pause (self ):
        self .is_paused =not self .is_paused 

        if self .is_paused :

            self .slide_timer .stop ()
            self .animation_timer .stop ()

            self ._pause_start_time =QtCore .QElapsedTimer ()
            self ._pause_start_time .start ()

        else :

            if hasattr (self ,'_pause_start_time'):

                pause_duration =self ._pause_start_time .elapsed ()
                if hasattr (self ,'_pause_duration'):
                    self ._pause_duration +=pause_duration 
                else :
                    self ._pause_duration =pause_duration 
                delattr (self ,'_pause_start_time')

            if self .animating :
                self .animation_timer .start (self .anim_fps_interval )

                if hasattr (self ,'_anim_elapsed_timer'):
                    actual_elapsed =self ._anim_elapsed_timer .elapsed ()
                    if hasattr (self ,'_pause_duration'):
                        actual_elapsed -=self ._pause_duration 
                    remaining_time =max (100 ,self .anim_duration -actual_elapsed )
                    self .slide_timer .start (remaining_time )
                else :
                    self .slide_timer .start (self .interval_ms )
            else :
                self .slide_timer .start (self .interval_ms )

    def _go_next (self ):

        self .slide_timer .stop ()
        self .animation_timer .stop ()
        self .animating =False 
        self .is_paused =False 

        if not self .image_files :
            return 

        if self .text_item and self .text_item .scene ()==self .scene :
            self .scene .removeItem (self .text_item )
            self .text_item =None 

        self .scene .clear ()

        self .index =(self .index +1 )%len (self .image_files )

        self ._show_first_image (is_next_prev_op =True )

    def _go_prev (self ):
        if not self .image_files :
            return 

        self .slide_timer .stop ()
        self .animation_timer .stop ()
        self .animating =False 
        self .is_paused =False 

        self .index =(self .index -1 +len (self .image_files ))%len (self .image_files )

        self ._show_first_image (is_next_prev_op =True )

    def _open_in_explorer (self ):
        if not self .image_files or self .index >=len (self .image_files ):
            return 

        current_path =self .image_files [self .index ]

        if not os.path.exists(current_path):
            QtWidgets.QMessageBox.warning(
                self,
                tr("title_warning"),
                tr("msg_file_not_found")
            )
            return

        try :
            import subprocess 

            subprocess .run (['explorer','/select,',os .path .normpath (current_path )])
        except Exception as e :

            try :
                folder_path =os .path .dirname (current_path )
                os .startfile (folder_path )
            except Exception as e2 :
                QtWidgets .QMessageBox .critical (
                self ,
                tr("title_error"),
                tr("msg_explorer_open_failed").format(e=e2)
                )

    def _delete_current_image (self ):
        if not self .image_files :
            return 

        current_path =self .image_files [self .index ]
        base_name =os .path .basename (current_path )

        reply = QtWidgets.QMessageBox.question(
            self,
            tr("title_confirm"),
            tr("msg_confirm_delete_file").format(
                name=base_name,
                path=current_path
            ),
        QtWidgets .QMessageBox .Yes |QtWidgets .QMessageBox .No ,
        QtWidgets .QMessageBox .No 
        )

        if reply ==QtWidgets .QMessageBox .Yes :
            try :
                os .remove (current_path )

                del self .image_files [self .index ]

                if self .index >=len (self .image_files )and self .image_files :
                    self .index =0 
                elif not self .image_files :
                    self .close ()
                    return 

                self ._show_first_image (is_next_prev_op =True )

                self .is_paused =False 
                self .slide_timer .start (self .interval_ms )

            except Exception as e :
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("title_delete_error"),
                    tr("msg_delete_failed").format(
                        e=e
                    )
                )

    def _show_loading_screen (self ):
        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()

        self .scene .setSceneRect (-vw /2 ,-vh /2 ,vw ,vh )

        logo_item =QtWidgets .QGraphicsTextItem ()
        logo_html ="""
        <div style='text-align: center; color: white; font-family: "Yu Gothic UI", "Yu Gothic", "Meiryo", "Segoe UI", "Noto Sans CJK JP", sans-serif;'>
            <h1 style='font-size: 36px; margin: 0; color: #FFF; font-weight: normal;'>
                Cinematic Slideshow
            </h1>
        </div>
        """
        logo_item .setHtml (logo_html )

        logo_rect =logo_item .boundingRect ()
        logo_x =-logo_rect .width ()/2 
        logo_y =-50 
        logo_item .setPos (logo_x ,logo_y )
        logo_item .setZValue (10.0 )

        self .scene .addItem (logo_item )
        self .loading_items .append (logo_item )

        progress_width =min (300 ,vw *0.4 )
        progress_height =4 
        progress_x =-progress_width /2 
        progress_y =20 

        progress_bg =QtWidgets .QGraphicsRectItem (progress_x ,progress_y ,progress_width ,progress_height )
        progress_bg .setBrush (QtGui .QBrush (QtGui .QColor (60 ,60 ,60 )))
        progress_bg .setPen (QtGui .QPen (QtGui .QColor (100 ,100 ,100 )))
        progress_bg .setZValue (10.0 )
        self .scene .addItem (progress_bg )
        self .loading_items .append (progress_bg )

        self .progress_bar =QtWidgets .QGraphicsRectItem (progress_x ,progress_y ,0 ,progress_height )
        self .progress_bar .setBrush (QtGui .QBrush (QtGui .QColor (70 ,130 ,200 )))
        self .progress_bar .setPen (QtGui .QPen (QtCore .Qt .NoPen ))
        self .progress_bar .setZValue (11.0 )
        self .scene .addItem (self .progress_bar )
        self .loading_items .append (self .progress_bar )

        self .status_item =QtWidgets .QGraphicsTextItem ()
        status_html ="""
        <div style='text-align: center; color: #CCC; font-family: "Yu Gothic UI", "Yu Gothic", "Meiryo", "Segoe UI", "Noto Sans CJK JP", sans-serif;'>
            <p style='font-size: 16px; margin: 0;'>準備中...</p>
        </div>
        """
        self .status_item .setHtml (status_html )

        status_rect =self .status_item .boundingRect ()
        status_x =-status_rect .width ()/2 
        status_y =progress_y +30 
        self .status_item .setPos (status_x ,status_y )
        self .status_item .setZValue (10.0 )

        self .scene .addItem (self .status_item )
        self .loading_items .append (self .status_item )

        self .progress_max_width =progress_width 
        self .progress_start_x =progress_x 

        QtCore .QTimer .singleShot (500 ,self ._start_image_loading )

    def _start_image_loading (self ):
        if not self .image_files :
            self ._update_loading_progress (100 ,tr("msg_no_images_found"))
            QtCore .QTimer .singleShot (2000 ,self ._finish_loading )
            return 

        self .loading_timer =QtCore .QTimer ()
        self .loading_timer .timeout .connect (self ._load_next_image )
        self .loading_index =0 
        self .loading_max =min (5 ,len (self .image_files ))
        self._update_loading_progress(
            0,
            tr("status_loading_images").format(
                current=0,
                total=self.loading_max
            )
        )
        self .loading_timer .start (100 )

    def _load_next_image (self ):
        if self .loading_index >=self .loading_max :
            self .loading_timer .stop ()
            self ._update_loading_progress (100 ,tr("msg_loading_complete"))
            QtCore .QTimer .singleShot (800 ,self ._finish_loading )
            return 

        if self .loading_index <len (self .image_files ):
            path =self .image_files [self .loading_index ]
            pixmap =create_pixmap_from_file (path )
            if not pixmap .isNull ():
                self ._get_scaled_pixmap (pixmap ,for_anim =True )

        self .loading_index +=1 
        progress =int ((self .loading_index /self .loading_max )*100 )
        self._update_loading_progress(
            progress,
            tr("status_loading_images").format(
                current=self.loading_index,
                total=self.loading_max
            )
        )

    def _update_loading_progress (self ,percent :int ,status_text :str ):
        if hasattr (self ,'progress_bar'):
            new_width =(percent /100.0 )*self .progress_max_width 
            self .progress_bar .setRect (self .progress_start_x ,self .progress_bar .rect ().y (),
            new_width ,self .progress_bar .rect ().height ())

        if hasattr (self ,'status_item'):
            status_html =f"""
            <div style='text-align: center; color: #CCC; font-family: "Yu Gothic UI", "Yu Gothic", "Meiryo", "Segoe UI", "Noto Sans CJK JP", sans-serif;'>
                <p style='font-size: 16px; margin: 0;'>{status_text }</p>
            </div>
            """
            self .status_item .setHtml (status_html )

            status_rect =self .status_item .boundingRect ()
            status_x =-status_rect .width ()/2 
            self .status_item .setPos (status_x ,self .status_item .pos ().y ())

    def _finish_loading (self ):

        self .fade_out_timer =QtCore .QTimer ()
        self .fade_out_timer .timeout .connect (self ._fade_out_loading )
        self .fade_opacity =1.0 
        self .fade_out_timer .start (50 )

    def _fade_out_loading (self ):
        self .fade_opacity -=0.05 

        for item in self .loading_items :
            if item .scene ()==self .scene :
                item .setOpacity (self .fade_opacity )

        if self .fade_opacity <=0 :
            self .fade_out_timer .stop ()

            for item in self .loading_items :
                if item .scene ()==self .scene :
                    self .scene .removeItem (item )
            self .loading_items .clear ()

            self .is_loading =False 

            if self .image_files :
                self ._show_first_image ()
            else :
                self ._show_no_images_message ()

    def _show_about_dialog (self ):
        show_about_dialog (self )

    def _show_first_image (self ,is_next_prev_op =False ):
        if not self .image_files :
            self ._show_no_images_message ()
            return 

        if self .text_item and self .text_item .scene ()==self .scene :
            self .scene .removeItem (self .text_item )
            self .text_item =None 

        self .scene .clear ()

        path =self .image_files [self .index ]
        pixmap =create_pixmap_from_file (path )
        if pixmap .isNull ():
            return 

        pixmap_item =QtWidgets .QGraphicsPixmapItem ()

        if self .ken_burns :
            self .current_movement_pattern =self ._select_next_ken_burns_pattern ()
            start_scale ,end_scale =self ._calculate_ken_burns_scales ()
            scaled_pixmap ,_ ,_ =self ._get_scaled_pixmap (pixmap ,for_anim =True )
            pixmap_item .setPixmap (scaled_pixmap )
            pixmap_item .setOpacity (1.0 )

            pixmap_item .setTransformOriginPoint (
            scaled_pixmap .width ()/2 ,
            scaled_pixmap .height ()/2 
            )
            pixmap_item .setScale (start_scale )

            start_off_x ,start_off_y ,end_off_x ,end_off_y =self ._calculate_ken_burns_offsets (
            pixmap ,start_scale ,end_scale 
            )

            pos_x =-scaled_pixmap .width ()/2 +start_off_x 
            pos_y =-scaled_pixmap .height ()/2 +start_off_y 
            pixmap_item .setPos (pos_x ,pos_y )

            end_pos_x =-scaled_pixmap .width ()/2 +end_off_x 
            end_pos_y =-scaled_pixmap .height ()/2 +end_off_y 

            start_left =pos_x -(scaled_pixmap .width ()*(start_scale -1 )/2 )
            start_right =start_left +scaled_pixmap .width ()*start_scale 
            end_left =end_pos_x -(scaled_pixmap .width ()*(end_scale -1 )/2 )
            end_right =end_left +scaled_pixmap .width ()*end_scale 

            self .anim_state ={
            "start_offset":(start_off_x ,start_off_y ),
            "end_offset":(end_off_x ,end_off_y ),
            "start_scale":start_scale ,
            "end_scale":end_scale ,
            }
        else :

            vw =self .view .viewport ().width ()
            vh =self .view .viewport ().height ()

            scaled_pixmap ,_ ,_ =self ._get_scaled_pixmap (pixmap ,for_anim =False )
            pixmap_item .setPixmap (scaled_pixmap )
            pixmap_item .setOpacity (1.0 )
            pixmap_item .setScale (1.0 )

            sw =scaled_pixmap .width ()
            sh =scaled_pixmap .height ()
            item_x =-sw /2.0 
            item_y =-sh /2.0 
            pixmap_item .setPos (item_x ,item_y )

            self .anim_state ={
            "start_offset":(0 ,0 ),
            "end_offset":(0 ,0 ),
            "start_scale":1.0 ,
            "end_scale":1.0 ,
            }

        self .scene .addItem (pixmap_item )
        self .current_item =pixmap_item 
        self .next_item =None 

        if self .show_filename :
            self ._init_text_item (os .path .basename (path ),pixmap )
            self .text_item .setOpacity (1.0 )

        self .is_transitioning =False 
        self .current_effect =None 
        self .next_effect =None 
        if hasattr (self ,'_paused_offset'):
            delattr (self ,'_paused_offset')
        if hasattr (self ,'_paused_transition_offset'):
            delattr (self ,'_paused_transition_offset')

        self .anim_duration =self .interval_ms 
        self .anim_start_time =QtCore .QTime .currentTime ()
        self .animating =True 
        self .animation_timer .start (self .anim_fps_interval )

        if self .current_item :
            self .frozen_current_pos =self .current_item .pos ()
            self .frozen_current_scale =self .current_item .scale ()

    def _show_error_overlay (self ,message :str ,duration :int =3000 ):

        error_bg =QtWidgets .QGraphicsRectItem (0 ,0 ,400 ,100 )
        error_bg .setBrush (QtGui .QBrush (QtGui .QColor (255 ,0 ,0 ,180 )))
        error_bg .setPen (QtGui .QPen (QtCore .Qt .NoPen ))

        error_text =QtWidgets .QGraphicsTextItem ()
        error_text .setHtml (f"""
            <div style='color: white; padding: 10px; font-size: 16px;'>
                ⚠️ {message }
            </div>
        """)

        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()
        error_bg .setPos ((vw -400 )/2 ,vh -150 )
        error_text .setPos ((vw -380 )/2 ,vh -140 )

        self .scene .addItem (error_bg )
        self .scene .addItem (error_text )
        error_bg .setZValue (100 )
        error_text .setZValue (101 )

        QtCore .QTimer .singleShot (duration ,lambda :self ._remove_error_overlay (error_bg ,error_text ))

    def _remove_error_overlay (self ,bg ,text ):
        if bg .scene ()==self .scene :
            self .scene .removeItem (bg )
        if text .scene ()==self .scene :
            self .scene .removeItem (text )

    def _on_slide_timeout (self ,force_next_item =False ):
        if hasattr (self ,'_paused_offset'):
            delattr (self ,'_paused_offset')
        if hasattr (self ,'_paused_transition_offset'):
            delattr (self ,'_paused_transition_offset')

        if self .animating and not force_next_item :
            return 

        if self .is_paused :
            self .slide_timer .start (self .interval_ms )
            return 

        if not self .image_files :
            print ("[Error] No images in list")
            self ._show_error_overlay (tr("msg_no_images"))
            return 

        if self .index >=len (self .image_files ):
            print (f"[Warning] Index out of range: {self .index }/{len (self .image_files )}")
            self ._show_error_overlay (tr("msg_index_error"))

            self .index =0 

        next_index =(self .index +1 )%len (self .image_files )

        try :
            path =self .image_files [next_index ]
        except IndexError :
            self .index =0 
            path =self .image_files [self .index ]
            next_index =self .index +1 

        path =os .path .normpath (path ).replace ('\\','/')

        max_retries =3 
        retry_count =0 
        pixmap =None 

        while retry_count <max_retries :
            try :
                pixmap =create_pixmap_from_file (path )

                if pixmap .isNull ():
                    retry_count +=1 
                    print(f"Image load failed (attempt {retry_count}/{max_retries}): {path}")

                    QtCore .QThread .msleep (100 )
                else :

                    if hasattr (self ,'_load_error_count')and path in self ._load_error_count :
                        del self ._load_error_count [path ]
                    break 

            except Exception as e :
                print(f"Image load exception: {path} - {e}")
                retry_count +=1 
                QtCore .QThread .msleep (100 )

        if pixmap is None or pixmap .isNull ():
            if not hasattr (self ,'_load_error_count'):
                self ._load_error_count ={}

            if path not in self ._load_error_count :
                self ._load_error_count [path ]=0 
            self ._load_error_count [path ]+=1 

            print(f"Final image load failure: {path} (total failures: {self._load_error_count[path]})")

            if self ._load_error_count [path ]>=3 :
                print(f"Permanently skipping image: {path}")
                self._show_error_overlay(f"Skipping image: {os.path.basename(path)}", 2000)

                original_path =self .image_files [next_index ]if next_index <len (self .image_files )else None 
                if original_path and original_path in self .image_files :
                    self .image_files .remove (original_path )
                elif path in self .image_files :
                    self .image_files .remove (path )
                else :
                    if next_index <len (self .image_files ):
                        removed_path =self .image_files .pop (next_index )

                if self .image_files :
                    self .index =self .index %len (self .image_files )
                else :
                    self ._show_error_overlay (tr("msg_no_display_images"),5000 )
                    return 

            self .slide_timer .start (100 )
            return 

        self .next_effect =self ._select_next_effect ()

        if self .next_effect =="slide":
            self .slide_direction =random .choice (["left","right","up","down"])

        elif self .next_effect =="wipe":
            wipe_directions =[
            "left_to_right","right_to_left","top_to_bottom","bottom_to_top",
            "diagonal_tl_br","diagonal_tr_bl","diagonal_bl_tr","diagonal_br_tl"
            ]
            self .wipe_direction =random .choice (wipe_directions )

        if self .ken_burns :
            self .current_movement_pattern =self ._select_next_ken_burns_pattern ()
            start_scale ,end_scale =self ._calculate_ken_burns_scales ()
        else :
            start_scale =end_scale =1.0 

        if self .current_item :
            self .frozen_current_pos =self .current_item .pos ()
            self .frozen_current_scale =self .current_item .scale ()

        self .anim_start_time =QtCore .QTime .currentTime ()
        self .animating =True 
        self .is_transitioning =True 

        next_item =QtWidgets .QGraphicsPixmapItem ()

        if self .ken_burns :

            scaled_pixmap ,_ ,_ =self ._get_scaled_pixmap (pixmap ,for_anim =True )
            next_item .setPixmap (scaled_pixmap )
            next_item .setOpacity (0.0 )

            next_item .setTransformOriginPoint (
            scaled_pixmap .width ()/2 ,
            scaled_pixmap .height ()/2 
            )
            next_item .setScale (start_scale )

            start_off_x ,start_off_y ,end_off_x ,end_off_y =self ._calculate_ken_burns_offsets (
            pixmap ,start_scale ,end_scale 
            )

            pos_x =-scaled_pixmap .width ()/2 +start_off_x 
            pos_y =-scaled_pixmap .height ()/2 +start_off_y 

            self .anim_state ={
            "start_offset":(start_off_x ,start_off_y ),
            "end_offset":(end_off_x ,end_off_y ),
            "start_scale":start_scale ,
            "end_scale":end_scale ,
            }
        else :

            scaled_pixmap ,_ ,_ =self ._get_scaled_pixmap (pixmap ,for_anim =False )
            next_item .setPixmap (scaled_pixmap )
            next_item .setOpacity (0.0 )
            next_item .setScale (1.0 )

            sw =scaled_pixmap .width ()
            sh =scaled_pixmap .height ()
            item_x =-sw /2.0 
            item_y =-sh /2.0 
            next_item .setPos (item_x ,item_y )

            self .anim_state ={
            "start_offset":(0 ,0 ),
            "end_offset":(0 ,0 ),
            "start_scale":1.0 ,
            "end_scale":1.0 ,
            }

        self .next_item =next_item 
        self .scene .addItem (self .next_item )
        self .next_item .setZValue (1.0 )

        if self .current_item :
            self .current_item .setZValue (0.0 )

        if self .show_filename :
            self ._init_text_item (os .path .basename (path ),pixmap )
            if self .text_item :
                self .text_item .setOpacity (0.0 )

        self .transition_start_time =QtCore .QTime .currentTime ()

        self .animation_timer .start (self .anim_fps_interval )
        self .index =next_index 

    def _on_anim_frame (self ):
        if not self .animating :
            return 

        if self .is_paused :
            return 

        if not hasattr (self ,'_anim_elapsed_timer'):
            self ._anim_elapsed_timer =QtCore .QElapsedTimer ()
            self ._anim_elapsed_timer .start ()
            self ._last_pause_time =0 

        actual_elapsed =self ._anim_elapsed_timer .elapsed ()

        if hasattr (self ,'_pause_duration'):
            actual_elapsed -=self ._pause_duration 

        elapsed_ms =actual_elapsed 
        t_linear =min (1.0 ,elapsed_ms /self .anim_duration )
        self ._last_t_linear =t_linear 
        t =0.5 -0.5 *math .cos (t_linear *math .pi )

        if self .is_transitioning and self .next_effect :

            if not hasattr (self ,'_transition_elapsed_timer'):
                self ._transition_elapsed_timer =QtCore .QElapsedTimer ()
                self ._transition_elapsed_timer .start ()

            if hasattr (self ,'_paused_transition_offset'):
                transition_elapsed =self ._transition_elapsed_timer .elapsed ()+self ._paused_transition_offset 
            else :
                transition_elapsed =self ._transition_elapsed_timer .elapsed ()

            effect_t =min (1.0 ,transition_elapsed /self .fade_duration_ms )
            effect_t_eased =0.5 -0.5 *math .cos (effect_t *math .pi )

            self ._apply_ken_burns_during_transition (t ,effect_t_eased )

            if self .next_effect =="none":
                if self .current_item :
                    self .current_item .setOpacity (0.0 )
                if self .next_item :
                    self .next_item .setOpacity (1.0 )
            # addp1
            elif self .next_effect =="crossfade":
                self ._apply_crossfade_opacity (effect_t_eased )
            if self .next_effect =="crossfade":
                self ._apply_crossfade_opacity (effect_t_eased )
            elif self .next_effect =="zoom":
                self ._apply_zoom_scale_opacity (effect_t_eased )
            elif self .next_effect =="wipe":
                self ._apply_wipe_mask (effect_t_eased )
            elif self.next_effect == "grid":
                self._apply_grid_effect(effect_t_eased)
            elif self.next_effect == "shutter":
                self._apply_shutter_effect(effect_t_eased)
            elif self .next_effect =="fade_to_black":
                self ._apply_fade_to_black_effect (effect_t_eased )

            if self .text_item :
                if self .next_effect =="fade_to_black":
                    if effect_t <0.6 :
                        self .text_item .setOpacity (0.0 )
                    else :
                        self .text_item .setOpacity ((effect_t -0.6 )/0.4 )
                else :
                    self .text_item .setOpacity (effect_t_eased )
        else :

            if self .ken_burns and self .current_item :
                self ._apply_ken_burns_normal (t )

        if t_linear >=1.0 :
            self ._finish_animation ()

    def _calculate_ken_burns_scales (self )->Tuple [float ,float ]:
        if getattr (self ,"current_movement_pattern",None )=="none":
            return 1.0 ,1.0 
        if getattr (self ,"current_movement_pattern",None )=="edge_scan":
            return 1.12 ,1.12
        base_zoom =self .ken_intensity *0.1 

        random_offset =(random .random ()-0.5 )*0.2 

        total_zoom =base_zoom +random_offset 
        start_scale =1.0 +total_zoom 

        start_scale =max (1.05 ,min (2.0 ,start_scale ))

        end_scale =1.0 +random .random ()*0.05 
        return start_scale ,end_scale 

    def _calculate_ken_burns_offsets (self ,pixmap :QtGui .QPixmap ,start_scale :float ,end_scale :float )->Tuple [int ,int ,int ,int ]:
        if not self .ken_burns :
            return 0 ,0 ,0 ,0 

        vw ,vh =self .view .viewport ().width (),self .view .viewport ().height ()

        if self .fit_mode =="cover":
            base_scale =max (vw /pixmap .width (),vh /pixmap .height ())
        else :
            base_scale =min (vw /pixmap .width (),vh /pixmap .height ())

        movement_pattern =getattr (self ,"current_movement_pattern",None )
        if movement_pattern is None:
            movement_pattern ="linear"
        if movement_pattern =="none":
            return 0 ,0 ,0 ,0
        self .current_movement_pattern =movement_pattern 
        intensity_factor =self .ken_intensity /10.0
        
        if movement_pattern =="edge_scan"and self .fit_mode =="cover":
            img_w =pixmap .width ()*base_scale *start_scale 
            img_h =pixmap .height ()*base_scale *start_scale 
            max_off_x =max (0 ,(img_w -vw )/2 )
            max_off_y =max (0 ,(img_h -vh )/2 )
            direction =random .choice ([-1 ,1 ])

            if max_off_x >=max_off_y and max_off_x >0 :
                return (
                int (-max_off_x *direction ),
                0 ,
                int (max_off_x *direction ),
                0 
                )
            if max_off_y >0 :
                return (
                0 ,
                int (-max_off_y *direction ),
                0 ,
                int (max_off_y *direction )
                )

            small_pan =min (vw ,vh )*0.06 
            if vw >=vh :
                return (
                int (-small_pan *direction ),
                0 ,
                int (small_pan *direction ),
                0 
                )
            else :
                return (
                0 ,
                int (-small_pan *direction ),
                0 ,
                int (small_pan *direction )
                )

        if self .fit_mode =="cover":
            end_img_w =pixmap .width ()*base_scale *end_scale 
            end_img_h =pixmap .height ()*base_scale *end_scale 
            end_max_off_x =max (0 ,(end_img_w -vw )/2 )
            end_max_off_y =max (0 ,(end_img_h -vh )/2 )
            start_img_w =pixmap .width ()*base_scale *start_scale 
            start_img_h =pixmap .height ()*base_scale *start_scale 
            start_max_off_x =max (0 ,(start_img_w -vw )/2 )
            start_max_off_y =max (0 ,(start_img_h -vh )/2 )
        else :
            start_img_w =pixmap .width ()*base_scale *start_scale 
            start_img_h =pixmap .height ()*base_scale *start_scale 
            start_max_off_x =max (0 ,(start_img_w -vw )/2 )
            start_max_off_y =max (0 ,(start_img_h -vh )/2 )
            end_max_off_x =0 
            end_max_off_y =0 

        if movement_pattern =="spiral_in":
            start_distance_factor =0.5 +random .random ()*0.2 
            self .spiral_start_angle =random .random ()*2 *math .pi 
            start_off_x =math .cos (self .spiral_start_angle )*start_max_off_x *start_distance_factor *intensity_factor 
            start_off_y =math .sin (self .spiral_start_angle )*start_max_off_y *start_distance_factor *intensity_factor 
        elif movement_pattern =="arc":
            if random .choice ([True ,False ]):
                start_x_factor =0.7 +random .random ()*0.2 
                start_y_factor =0.3 +random .random ()*0.3 
            else :
                start_x_factor =0.3 +random .random ()*0.3 
                start_y_factor =0.7 +random .random ()*0.2 
            start_off_x =random .choice ([-1 ,1 ])*start_max_off_x *start_x_factor *intensity_factor 
            start_off_y =random .choice ([-1 ,1 ])*start_max_off_y *start_y_factor *intensity_factor 
        else :
            start_distance_factor =0.7 +random .random ()*0.2 
            start_off_x =random .choice ([-1 ,1 ])*start_max_off_x *start_distance_factor *intensity_factor 
            start_off_y =random .choice ([-1 ,1 ])*start_max_off_y *start_distance_factor *intensity_factor 

        if self .fit_mode =="contain":
            end_off_x =0 
            end_off_y =0 
        else :
            if movement_pattern in ["wave","zigzag"]:
                safe_factor =0.3 
                end_off_x =random .uniform (-end_max_off_x *safe_factor ,end_max_off_x *safe_factor )
                end_off_y =random .uniform (-end_max_off_y *safe_factor ,end_max_off_y *safe_factor )
            elif movement_pattern =="spiral_in":
                end_off_x =0 
                end_off_y =0 
            else :
                end_distance_factor =random .random ()*0.4 
                end_off_x =random .uniform (-end_max_off_x ,end_max_off_x )*end_distance_factor 
                end_off_y =random .uniform (-end_max_off_y ,end_max_off_y )*end_distance_factor 

        start_off_x =int (start_off_x )
        start_off_y =int (start_off_y )
        end_off_x =int (end_off_x )
        end_off_y =int (end_off_y )

        if movement_pattern =="arc":
            self .arc_bulge_direction =random .choice ([-1 ,1 ])
        elif movement_pattern =="wave":
            self .wave_cycles =1.5 +random .random ()*1.5 
        elif movement_pattern =="spiral_in":
            self .spiral_rotations =2.0 +random .random ()*1.5 
        elif movement_pattern =="zigzag":
            self .zigzag_segments =random .randint (3 ,5 )

        return start_off_x ,start_off_y ,end_off_x ,end_off_y 

    def _get_scaled_pixmap (self ,pixmap :QtGui .QPixmap ,for_anim :bool =False )->Tuple [QtGui .QPixmap ,int ,int ]:
        if pixmap .isNull ():
            print (tr("msg_invalid_pixmap_warning"))
            return QtGui .QPixmap (),0 ,0 

        viewport_size =self .view .viewport ().size ()
        cache_key =(
        pixmap .cacheKey (),
        (viewport_size .width (),viewport_size .height ()),
        for_anim ,
        self .ken_burns ,
        self .fit_mode ,
        )

        if hasattr (self ,'_pixmap_cache')and cache_key in self ._pixmap_cache :
            cached_pixmap ,x_offset ,y_offset =self ._pixmap_cache [cache_key ]
            if not cached_pixmap .isNull ():
                return cached_pixmap ,x_offset ,y_offset 
            else :
                del self ._pixmap_cache [cache_key ]

        vw =max (1 ,self .view .viewport ().width ())
        vh =max (1 ,self .view .viewport ().height ())
        iw ,ih =pixmap .width (),pixmap .height ()

        x_offset ,y_offset =0 ,0 

        if self .fit_mode =="cover":
            base_scale_factor =max (vw /iw ,vh /ih )
        else :
            base_scale_factor =min (vw /iw ,vh /ih )

        final_scale_factor =base_scale_factor 
        new_w =int (iw *final_scale_factor )
        new_h =int (ih *final_scale_factor )

        if new_w <1 or new_h <1 :
            print(f"Warning: invalid size after scaling - {new_w}x{new_h}")
            return pixmap ,0 ,0 

        scaled =pixmap .scaled (
        QtCore .QSize (new_w ,new_h ),
        QtCore .Qt .IgnoreAspectRatio ,
        QtCore .Qt .SmoothTransformation 
        )

        if scaled .isNull ():
            print(f"Warning: scaling failed - original size: {iw}x{ih}, target size: {new_w}x{new_h}")
            return pixmap ,0 ,0 

        if not self .ken_burns or not for_anim :
            x_offset =(vw -scaled .width ())//2 
            y_offset =(vh -scaled .height ())//2 
        else :
            x_offset =0 
            y_offset =0 

        if not hasattr (self ,'_pixmap_cache'):
            self ._pixmap_cache ={}

        self ._manage_cache ()
        self ._pixmap_cache [cache_key ]=(scaled ,x_offset ,y_offset )

        return scaled ,x_offset ,y_offset 

    def _apply_ken_burns_normal (self ,t ):
        if not self .anim_state or not self .current_item :
            return 

        t_ken =self ._calculate_ken_burns_t (t )
        start_scale =self .anim_state ["start_scale"]
        end_scale =self .anim_state ["end_scale"]
        current_scale =start_scale +(end_scale -start_scale )*t_ken 
        start_x ,start_y =self .anim_state ["start_offset"]
        end_x ,end_y =self .anim_state ["end_offset"]

        if hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="arc":

            mid_x =(start_x +end_x )/2 
            mid_y =(start_y +end_y )/2 
            bulge =0.3 *self .ken_intensity /10.0 
            if abs (end_x -start_x )>abs (end_y -start_y ):
                control_x =mid_x 
                control_y =mid_y +(end_x -start_x )*bulge *getattr (self ,'arc_bulge_direction',1 )
            else :
                control_x =mid_x +(end_y -start_y )*bulge *getattr (self ,'arc_bulge_direction',1 )
                control_y =mid_y 
            current_x =(1 -t_ken )*(1 -t_ken )*start_x +2 *(1 -t_ken )*t_ken *control_x +t_ken *t_ken *end_x 
            current_y =(1 -t_ken )*(1 -t_ken )*start_y +2 *(1 -t_ken )*t_ken *control_y +t_ken *t_ken *end_y 

        elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="wave":

            base_x =start_x +(end_x -start_x )*t_ken 
            base_y =start_y +(end_y -start_y )*t_ken 

            amplitude_decay =1.0 -t_ken 
            amplitude =50 *self .ken_intensity /10.0 *amplitude_decay 
            cycles =getattr (self ,'wave_cycles',2.0 )

            if abs (end_x -start_x )>abs (end_y -start_y ):
                wave_offset =amplitude *math .sin (t_ken *math .pi *2 *cycles )
                current_x =base_x 
                current_y =base_y +wave_offset 
            else :
                wave_offset =amplitude *math .sin (t_ken *math .pi *2 *cycles )
                current_x =base_x +wave_offset 
                current_y =base_y 

        elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="spiral_in":

            rotations =getattr (self ,'spiral_rotations',2.5 )
            start_angle =getattr (self ,'spiral_start_angle',0 )
            angle =start_angle +t_ken *rotations *2 *math .pi 
            if t_ken <0.2 :
                radius =1.0 +(t_ken /0.2 )*0.3 
            else :
                radius =1.3 *(1.0 -(t_ken -0.2 )/0.8 )
            spiral_amplitude =120 *self .ken_intensity /10.0 *radius 
            base_x =start_x +(end_x -start_x )*t_ken 
            base_y =start_y +(end_y -start_y )*t_ken 
            current_x =base_x +spiral_amplitude *math .cos (angle )
            current_y =base_y +spiral_amplitude *math .sin (angle )

        elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="zigzag":

            base_x =start_x +(end_x -start_x )*t_ken 
            base_y =start_y +(end_y -start_y )*t_ken 

            amplitude_decay =1.0 -t_ken 
            amplitude =60 *self .ken_intensity /10.0 *amplitude_decay 
            segments =getattr (self ,'zigzag_segments',4 )

            wave_position =t_ken *segments *2 
            wave_int =int (wave_position )
            wave_frac =wave_position -wave_int 
            if wave_int %2 ==0 :
                zigzag_offset =wave_frac *2 -1 
            else :
                zigzag_offset =1 -wave_frac *2 

            if abs (end_x -start_x )>abs (end_y -start_y ):
                current_x =base_x 
                current_y =base_y +amplitude *zigzag_offset 
            else :
                current_x =base_x +amplitude *zigzag_offset 
                current_y =base_y 

        else :

            current_x =start_x +(end_x -start_x )*t_ken 
            current_y =start_y +(end_y -start_y )*t_ken 

        pixmap =self .current_item .pixmap ()
        if pixmap :
            self .current_item .setTransformOriginPoint (
            pixmap .width ()/2 ,
            pixmap .height ()/2 
            )

            pos_x =-pixmap .width ()/2 +current_x 
            pos_y =-pixmap .height ()/2 +current_y 
            self .current_item .setScale (current_scale )
            self .current_item .setPos (pos_x ,pos_y )

    def _apply_ken_burns_during_transition (self ,t :float ,effect_t :float ):
        try :

            if self .ken_burns :
                t_ken =self ._calculate_ken_burns_t (t )
            else :
                t_ken =0 

            vw =self .view .viewport ().width ()
            vh =self .view .viewport ().height ()

            if self .current_item and hasattr (self ,'frozen_current_pos'):
                self .current_item .setPos (self .frozen_current_pos )
                self .current_item .setScale (self .frozen_current_scale )

                if self .next_effect =="zoom":

                    zoom_extra =1.0 +1.0 *effect_t 
                    self .current_item .setScale (self .frozen_current_scale *zoom_extra )
                    if not hasattr (self ,'_zoom_center_ratio_x'):
                        self ._zoom_center_ratio_x =random .random ()
                        self ._zoom_center_ratio_y =random .random ()
                    pixmap =self .current_item .pixmap ()
                    if pixmap :

                        orig_w =pixmap .width ()*self .frozen_current_scale 
                        orig_h =pixmap .height ()*self .frozen_current_scale 

                        zoom_center_x =self .frozen_current_pos .x ()+orig_w *self ._zoom_center_ratio_x 
                        zoom_center_y =self .frozen_current_pos .y ()+orig_h *self ._zoom_center_ratio_y 

                        new_w =pixmap .width ()*self .frozen_current_scale *zoom_extra 
                        new_h =pixmap .height ()*self .frozen_current_scale *zoom_extra 

                        new_x =zoom_center_x -new_w *self ._zoom_center_ratio_x 
                        new_y =zoom_center_y -new_h *self ._zoom_center_ratio_y 

                        self .current_item .setPos (new_x ,new_y )

                elif self .next_effect =="slide":

                    if self .slide_direction =="left":
                        self .current_item .setPos (self .frozen_current_pos .x ()-vw *effect_t ,self .frozen_current_pos .y ())
                    elif self .slide_direction =="right":
                        self .current_item .setPos (self .frozen_current_pos .x ()+vw *effect_t ,self .frozen_current_pos .y ())
                    elif self .slide_direction =="up":
                        self .current_item .setPos (self .frozen_current_pos .x (),self .frozen_current_pos .y ()-vh *effect_t )
                    elif self .slide_direction =="down":
                        self .current_item .setPos (self .frozen_current_pos .x (),self .frozen_current_pos .y ()+vh *effect_t )
                    self .current_item .setOpacity (1.0 )

            if self .next_item :
                if self .ken_burns and hasattr (self ,'anim_state')and self .anim_state :

                    start_scale =self .anim_state ["start_scale"]
                    end_scale =self .anim_state ["end_scale"]
                    current_scale =start_scale +(end_scale -start_scale )*t_ken 

                    start_x ,start_y =self .anim_state ["start_offset"]
                    end_x ,end_y =self .anim_state ["end_offset"]

                    if hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="arc":

                        mid_x =(start_x +end_x )/2 
                        mid_y =(start_y +end_y )/2 
                        bulge =0.3 *self .ken_intensity /10.0 

                        if abs (end_x -start_x )>abs (end_y -start_y ):
                            control_x =mid_x 
                            control_y =mid_y +(end_x -start_x )*bulge *getattr (self ,'arc_bulge_direction',1 )
                        else :
                            control_x =mid_x +(end_y -start_y )*bulge *getattr (self ,'arc_bulge_direction',1 )
                            control_y =mid_y 

                        ken_x =(1 -t_ken )*(1 -t_ken )*start_x +2 *(1 -t_ken )*t_ken *control_x +t_ken *t_ken *end_x 
                        ken_y =(1 -t_ken )*(1 -t_ken )*start_y +2 *(1 -t_ken )*t_ken *control_y +t_ken *t_ken *end_y 

                    elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="wave":

                        base_x =start_x +(end_x -start_x )*t_ken 
                        base_y =start_y +(end_y -start_y )*t_ken 

                        amplitude_decay =1.0 -t_ken 
                        amplitude =50 *self .ken_intensity /10.0 *amplitude_decay 
                        cycles =getattr (self ,'wave_cycles',2.0 )

                        if abs (end_x -start_x )>abs (end_y -start_y ):
                            wave_offset =amplitude *math .sin (t_ken *math .pi *2 *cycles )
                            ken_x =base_x 
                            ken_y =base_y +wave_offset 
                        else :
                            wave_offset =amplitude *math .sin (t_ken *math .pi *2 *cycles )
                            ken_x =base_x +wave_offset 
                            ken_y =base_y 

                    elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="spiral_in":

                        rotations =getattr (self ,'spiral_rotations',2.0 )
                        start_angle =getattr (self ,'spiral_start_angle',0 )
                        angle =start_angle +t_ken *rotations *2 *math .pi 

                        if t_ken <0.2 :
                            radius =1.0 +(t_ken /0.2 )*0.3 
                        else :
                            radius =1.3 *(1.0 -(t_ken -0.2 )/0.8 )

                        spiral_amplitude =100 *self .ken_intensity /10.0 *radius 
                        base_x =start_x +(end_x -start_x )*t_ken 
                        base_y =start_y +(end_y -start_y )*t_ken 
                        ken_x =base_x +spiral_amplitude *math .cos (angle )
                        ken_y =base_y +spiral_amplitude *math .sin (angle )

                    elif hasattr (self ,'current_movement_pattern')and self .current_movement_pattern =="zigzag":

                        base_x =start_x +(end_x -start_x )*t_ken 
                        base_y =start_y +(end_y -start_y )*t_ken 

                        amplitude_decay =1.0 -t_ken 
                        amplitude =60 *self .ken_intensity /10.0 *amplitude_decay 
                        segments =getattr (self ,'zigzag_segments',4 )

                        wave_position =t_ken *segments *2 
                        wave_int =int (wave_position )
                        wave_frac =wave_position -wave_int 

                        if wave_int %2 ==0 :
                            zigzag_offset =wave_frac *2 -1 
                        else :
                            zigzag_offset =1 -wave_frac *2 

                        if abs (end_x -start_x )>abs (end_y -start_y ):
                            ken_x =base_x 
                            ken_y =base_y +amplitude *zigzag_offset 
                        else :
                            ken_x =base_x +amplitude *zigzag_offset 
                            ken_y =base_y 

                    else :

                        ken_x =start_x +(end_x -start_x )*t_ken 
                        ken_y =start_y +(end_y -start_y )*t_ken 

                    pixmap =self .next_item .pixmap ()
                    if pixmap :
                        base_pos_x =-pixmap .width ()/2 +ken_x 
                        base_pos_y =-pixmap .height ()/2 +ken_y 

                        if self .next_effect =="zoom":

                            zoom_in_scale =0.5 +0.5 *effect_t 
                            final_scale =current_scale *zoom_in_scale 
                            self .next_item .setScale (final_scale )
                        else :

                            self .next_item .setScale (current_scale )

                        if self .next_effect =="slide":
                            if self .slide_direction =="left":
                                self .next_item .setPos (vw -vw *effect_t +base_pos_x ,base_pos_y )
                            elif self .slide_direction =="right":
                                self .next_item .setPos (-vw +vw *effect_t +base_pos_x ,base_pos_y )
                            elif self .slide_direction =="up":
                                self .next_item .setPos (base_pos_x ,vh -vh *effect_t +base_pos_y )
                            elif self .slide_direction =="down":
                                self .next_item .setPos (base_pos_x ,-vh +vh *effect_t +base_pos_y )
                            self .next_item .setOpacity (1.0 )

                        elif self .next_effect =="wipe":

                            if self .text_item :
                                self .text_item .setZValue (10.0 )
                            self .next_item .setZValue (2.0 )

                            if self .wipe_direction =="left_to_right":
                                wipe_x =-vw +vw *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,base_pos_y )
                            elif self .wipe_direction =="right_to_left":
                                wipe_x =vw -vw *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,base_pos_y )
                            elif self .wipe_direction =="top_to_bottom":
                                wipe_y =-vh +vh *effect_t 
                                self .next_item .setPos (base_pos_x ,wipe_y +base_pos_y )
                            elif self .wipe_direction =="bottom_to_top":
                                wipe_y =vh -vh *effect_t 
                                self .next_item .setPos (base_pos_x ,wipe_y +base_pos_y )
                            elif self .wipe_direction =="diagonal_tl_br":
                                wipe_x =-vw +vw *effect_t 
                                wipe_y =-vh +vh *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,wipe_y +base_pos_y )
                            elif self .wipe_direction =="diagonal_tr_bl":
                                wipe_x =vw -vw *effect_t 
                                wipe_y =-vh +vh *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,wipe_y +base_pos_y )
                            elif self .wipe_direction =="diagonal_bl_tr":
                                wipe_x =-vw +vw *effect_t 
                                wipe_y =vh -vh *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,wipe_y +base_pos_y )
                            elif self .wipe_direction =="diagonal_br_tl":
                                wipe_x =vw -vw *effect_t 
                                wipe_y =vh -vh *effect_t 
                                self .next_item .setPos (wipe_x +base_pos_x ,wipe_y +base_pos_y )

                        else :

                            self .next_item .setPos (base_pos_x ,base_pos_y )
                else :

                    pixmap =self .next_item .pixmap ()
                    if pixmap :
                        sw =pixmap .width ()
                        sh =pixmap .height ()

                        center_x =-sw /2 
                        center_y =-sh /2 

                        if self .next_effect =="zoom":

                            zoom_in_scale =0.5 +0.5 *effect_t 
                            self .next_item .setScale (zoom_in_scale )

                            current_w =sw *zoom_in_scale 
                            current_h =sh *zoom_in_scale 
                            zoom_x =-current_w /2 
                            zoom_y =-current_h /2 
                            self .next_item .setPos (zoom_x ,zoom_y )

                        elif self .next_effect =="slide":

                            self .next_item .setScale (1.0 )
                            self .next_item .setOpacity (1.0 )

                            if self .slide_direction =="left":

                                start_x =vw /2 
                                current_x =start_x -vw *effect_t 
                                final_x =center_x 
                                slide_x =start_x +(final_x -start_x )*effect_t 
                                self .next_item .setPos (slide_x ,center_y )

                            elif self .slide_direction =="right":

                                start_x =-vw /2 -sw 
                                current_x =start_x +vw *effect_t 
                                final_x =center_x 
                                slide_x =start_x +(final_x -start_x )*effect_t 
                                self .next_item .setPos (slide_x ,center_y )

                            elif self .slide_direction =="up":

                                start_y =vh /2 
                                current_y =start_y -vh *effect_t 
                                final_y =center_y 
                                slide_y =start_y +(final_y -start_y )*effect_t 
                                self .next_item .setPos (center_x ,slide_y )

                            elif self .slide_direction =="down":

                                start_y =-vh /2 -sh 
                                current_y =start_y +vh *effect_t 
                                final_y =center_y 
                                slide_y =start_y +(final_y -start_y )*effect_t 
                                self .next_item .setPos (center_x ,slide_y )

                            self .next_item .setOpacity (1.0 )

                        elif self .next_effect =="wipe":

                            self .next_item .setScale (1.0 )
                            self .next_item .setOpacity (1.0 )

                            if self .text_item :
                                self .text_item .setZValue (10.0 )
                            self .next_item .setZValue (2.0 )

                            if self .wipe_direction =="left_to_right":
                                wipe_x =-vw +vw *effect_t +center_x 
                                self .next_item .setPos (wipe_x ,center_y )
                            elif self .wipe_direction =="right_to_left":
                                wipe_x =vw -vw *effect_t +center_x 
                                self .next_item .setPos (wipe_x ,center_y )
                            elif self .wipe_direction =="top_to_bottom":
                                wipe_y =-vh +vh *effect_t +center_y 
                                self .next_item .setPos (center_x ,wipe_y )
                            elif self .wipe_direction =="bottom_to_top":
                                wipe_y =vh -vh *effect_t +center_y 
                                self .next_item .setPos (center_x ,wipe_y )
                            elif self .wipe_direction =="diagonal_tl_br":
                                wipe_x =-vw +vw *effect_t +center_x 
                                wipe_y =-vh +vh *effect_t +center_y 
                                self .next_item .setPos (wipe_x ,wipe_y )
                            elif self .wipe_direction =="diagonal_tr_bl":
                                wipe_x =vw -vw *effect_t +center_x 
                                wipe_y =-vh +vh *effect_t +center_y 
                                self .next_item .setPos (wipe_x ,wipe_y )
                            elif self .wipe_direction =="diagonal_bl_tr":
                                wipe_x =-vw +vw *effect_t +center_x 
                                wipe_y =vh -vh *effect_t +center_y 
                                self .next_item .setPos (wipe_x ,wipe_y )
                            elif self .wipe_direction =="diagonal_br_tl":
                                wipe_x =vw -vw *effect_t +center_x 
                                wipe_y =vh -vh *effect_t +center_y 
                                self .next_item .setPos (wipe_x ,wipe_y )

                        else :

                            self .next_item .setScale (1.0 )
                            self .next_item .setPos (center_x ,center_y )

        except Exception as e :
            print (f"Error in transition: {e }")
            import traceback 
            traceback .print_exc ()

    def _apply_crossfade_opacity (self ,t :float ):
        if self .next_item :
            self .next_item .setOpacity (t )
        if self .current_item :
            self .current_item .setOpacity (1.0 -t )

    def _apply_zoom_scale_opacity (self ,t :float ):
        if self .current_item :
            self .current_item .setOpacity (1.0 -t )

        if self .next_item :
            self .next_item .setOpacity (t )

            if not self .ken_burns :
                zoom_in_scale =0.5 +0.5 *t 
                self .next_item .setScale (zoom_in_scale )

    def _apply_wipe_mask (self ,t :float ):
        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()

        if t >=1.0 :
            if self .current_item :
                self .current_item .setOpacity (0.0 )
            if self .next_item :
                self .next_item .setOpacity (1.0 )
                self .next_item .setZValue (2.0 )
            return 

        if self .current_item :
            self .current_item .setOpacity (1.0 )
            self .current_item .setZValue (0.0 )

        if self .next_item :
            self .next_item .setOpacity (1.0 )
            self .next_item .setZValue (2.0 )
            
    def _apply_grid_effect(self, t: float):
        if not self.current_item or not self.next_item:
            return

        rows = 7
        cols = 7
        total = rows * cols
        visible_count = int(total * t)

        self.current_item.setOpacity(1.0)
        self.current_item.setZValue(0.0)

        self.next_item.setOpacity(1.0)
        self.next_item.setZValue(2.0)

        if not hasattr(self, "_grid_original_pixmap"):
            self._grid_original_pixmap = self.next_item.pixmap()

        pixmap = self._grid_original_pixmap
        if pixmap.isNull():
            return

        if not hasattr(self, "_grid_cells"):
            cells = [(r, c) for r in range(rows) for c in range(cols)]
            random.shuffle(cells)
            self._grid_cells = cells

        masked = QtGui.QPixmap(pixmap.size())
        masked.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(masked)

        sw = pixmap.width()
        sh = pixmap.height()
        cell_w = sw / cols
        cell_h = sh / rows

        for r, c in self._grid_cells[:visible_count]:
            rect = QtCore.QRect(
                int(c * cell_w),
                int(r * cell_h),
                int(cell_w + 1),
                int(cell_h + 1)
            )
            painter.drawPixmap(rect, pixmap, rect)

        painter.end()

        self.next_item.setPixmap(masked)

        if t >= 1.0:
            self.next_item.setPixmap(pixmap)
            self.current_item.setOpacity(0.0)
            
    def _apply_shutter_effect(self, t: float):
        if not self.current_item or not self.next_item:
            return

        bands = 16

        self.current_item.setOpacity(1.0)
        self.current_item.setZValue(0.0)

        self.next_item.setOpacity(1.0)
        self.next_item.setZValue(2.0)

        if not hasattr(self, "_shutter_original_pixmap"):
            self._shutter_original_pixmap = self.next_item.pixmap()

        pixmap = self._shutter_original_pixmap
        if pixmap.isNull():
            return

        masked = QtGui.QPixmap(pixmap.size())
        masked.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(masked)

        sw = pixmap.width()
        sh = pixmap.height()

        if sw >= sh:
            band_w = sw / bands

            for i in range(bands):
                x = int(i * band_w)
                w = int((band_w + 1) * t)

                rect = QtCore.QRect(x, 0, w, sh)
                source_rect = QtCore.QRect(x, 0, w, sh)

                painter.drawPixmap(rect, pixmap, source_rect)
        else:
            band_h = sh / bands

            for i in range(bands):
                y = int(i * band_h)
                h = int((band_h + 1) * t)

                rect = QtCore.QRect(0, y, sw, h)
                source_rect = QtCore.QRect(0, y, sw, h)

                painter.drawPixmap(rect, pixmap, source_rect)

        painter.end()

        self.next_item.setPixmap(masked)

        if t >= 1.0:
            self.next_item.setPixmap(pixmap)
            self.current_item.setOpacity(0.0)
        
    def _calculate_ken_burns_t (self ,t_linear ):
        return t_linear 

    def _finish_animation (self ):

        if hasattr (self ,'_anim_elapsed_timer'):
            delattr (self ,'_anim_elapsed_timer')

        if hasattr (self ,'_transition_elapsed_timer'):
            delattr (self ,'_transition_elapsed_timer')

        if hasattr (self ,'_pause_duration'):
            delattr (self ,'_pause_duration')
        if hasattr (self ,'_pause_start_time'):
            delattr (self ,'_pause_start_time')

        self .is_transitioning =False 

        if self .next_effect :
            self .current_effect =self .next_effect 
            self .next_effect =None 

        # addp2
        if hasattr (self ,'transition_start_time'):
            delattr (self ,'transition_start_time')

        if hasattr (self ,'_zoom_base_scales'):
            delattr (self ,'_zoom_base_scales')

        if hasattr (self ,'frozen_current_pos'):
            delattr (self ,'frozen_current_pos')
        if hasattr (self ,'frozen_current_scale'):
            delattr (self ,'frozen_current_scale')

        if hasattr (self ,'_zoom_center_ratio_x'):
            delattr (self ,'_zoom_center_ratio_x')
        if hasattr (self ,'_zoom_center_ratio_y'):
            delattr (self ,'_zoom_center_ratio_y')

        if hasattr (self ,'_wipe_mask')and self ._wipe_mask :
            if self ._wipe_mask .scene ()==self .scene :
                self .scene .removeItem (self ._wipe_mask )
            self ._wipe_mask =None
        
        if hasattr(self, "_grid_cells"):
            delattr(self, "_grid_cells")

        if hasattr(self, "_grid_original_pixmap"):
            delattr(self, "_grid_original_pixmap")
            
        if hasattr(self, "_shutter_original_pixmap"):
            delattr(self, "_shutter_original_pixmap")

        if self .next_item and self .current_item and self .current_item .scene ()==self .scene :
            self .scene .removeItem (self .current_item )

        if self .next_item :
            self .next_item .setOpacity (1.0 )
            self .current_item =self .next_item 
            self .next_item =None 

        self .animating =False 
        self .animation_timer .stop ()

        if self .text_item and self .show_filename :
            self .text_item .setOpacity (1.0 )

        if not self .is_paused :
            QtCore .QTimer .singleShot (50 ,self ._on_slide_timeout )

    def _apply_slide_position_to_current (self ,ken_x :float ,ken_y :float ,effect_t :float ):
        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()

        if self .slide_direction =="left":
            self .current_item .setPos (-ken_x -vw *effect_t ,-ken_y )
        elif self .slide_direction =="right":
            self .current_item .setPos (-ken_x +vw *effect_t ,-ken_y )
        elif self .slide_direction =="up":
            self .current_item .setPos (-ken_x ,-ken_y -vh *effect_t )
        elif self .slide_direction =="down":
            self .current_item .setPos (-ken_x ,-ken_y +vh *effect_t )

    def _apply_fade_to_black_effect (self ,t :float ):

        if t <0.4 :
            opacity =1.0 -(t /0.4 )
            if self .current_item :
                self .current_item .setOpacity (opacity )
            if self .text_item :
                self .text_item .setOpacity (0.0 )
        elif t <0.6 :
            if self .current_item :
                self .current_item .setOpacity (0.0 )
            if self .next_item :
                self .next_item .setOpacity (0.0 )
        else :
            if self .next_item :
                opacity =(t -0.6 )/0.4 
                self .next_item .setOpacity (opacity )
            if self .text_item :
                self .text_item .setOpacity ((t -0.6 )/0.4 )

    def _manage_cache (self ):

        while len (self ._pixmap_cache )>self ._cache_max_size :
            oldest_key =next (iter (self ._pixmap_cache ))
            del self ._pixmap_cache [oldest_key ]

        import gc 
        gc .collect ()

    def _init_text_item (self ,filename :str ,pixmap :QtGui .QPixmap ):
        if not self .text_item :
            self .text_item =QtWidgets .QGraphicsTextItem ()
            self .scene .addItem (self .text_item )
            self .text_item .setZValue (2.0 )
            self .text_item .setOpacity (0.0 )

        color =QtGui .QColor ("white")
        font =QtGui .QFont (self .font_family ,self .font_size )
        if self .font_bold :
            font .setBold (True )

        html =f"""
        <table cellpadding='0' cellspacing='0' border='0' style='
            background-color: rgba(0,0,0,100); 
            border-radius: {int (self .font_size *0.3 )}px;
            border: none;
        '>
            <tr>
                <td style='
                    color: {color .name ()};
                    padding: {int (self .font_size *0.6 )}px {int (self .font_size *0.7 )}px {int (self .font_size *0.1 )}px {int (self .font_size *0.7 )}px;
                    border: none;
                    vertical-align: middle;
                    height: {int (self .font_size *1.3 )}px;
                    white-space: nowrap;
                '>{filename }</td>
            </tr>
        </table>
        """

        self .text_item .setHtml (html )
        self .text_item .setFont (font )

        self ._update_text_position (self .text_item )

    def _update_text_position (self ,item :QtWidgets .QGraphicsTextItem ):
        if not item or not self .view :
            return 

        vw =self .view .viewport ().width ()
        vh =self .view .viewport ().height ()

        text_rect =item .boundingRect ()
        tw =text_rect .width ()
        th =text_rect .height ()

        padding =20 
        x ,y =0 ,0 

        left_edge =-vw /2 
        right_edge =vw /2 
        top_edge =-vh /2 
        bottom_edge =vh /2 

        if self .filename_v_pos =="top":
            y =top_edge +padding 
        elif self .filename_v_pos =="bottom":
            y =bottom_edge -th -padding 

        if self .filename_h_pos =="left":
            x =left_edge +padding 
        elif self .filename_h_pos =="center":
            x =-tw /2 
        elif self .filename_h_pos =="right":
            x =right_edge -tw -padding 

        x +=self .filename_h_offset 
        y +=self .filename_v_offset 

        item .setPos (x ,y )

from typing import Dict ,Any 

class FolderListWidget (QtWidgets .QListWidget ):

    def __init__ (self ,parent =None ):
        super ().__init__ (parent )
        self .setAcceptDrops (True )
        self .setDefaultDropAction (QtCore .Qt .CopyAction )

    def dragEnterEvent (self ,event ):
        if event .mimeData ().hasUrls ():
            for url in event .mimeData ().urls ():
                path =url .toLocalFile ()
                if os .path .isdir (path ):
                    event .acceptProposedAction ()
                    return 
        event .ignore ()

    def dragMoveEvent (self ,event ):
        if event .mimeData ().hasUrls ():
            event .acceptProposedAction ()
        else :
            event .ignore ()

    def dropEvent (self ,event ):
        if event .mimeData ().hasUrls ():
            for url in event .mimeData ().urls ():
                path =url .toLocalFile ()
                if os .path .isdir (path ):
                    exists =False 
                    for i in range (self .count ()):
                        if os .path .normpath (self .item (i ).text ())==os .path .normpath (path ):
                            exists =True 
                            break 

                    if not exists :
                        item =QtWidgets .QListWidgetItem (path )
                        item .setData (QtCore .Qt .UserRole ,True )
                        item .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_DirIcon ))
                        self .addItem (item )
                        self .setCurrentItem (item )

        event .acceptProposedAction ()

import sys 
import os 
import json 
import glob 
from typing import Dict ,Any ,List ,Tuple 
from PyQt5 import QtWidgets ,QtGui ,QtCore ,uic 

def list_images (folder_path :str ,recursive :bool )->List [str ]:
    if not os .path .isdir (folder_path ):
        return []

    images =[]

    for ext in SUPPORTED_IMAGE_FORMATS :
        if recursive :
            pattern =os .path .join (folder_path ,'**',f'*{ext }')
            images .extend (glob .glob (pattern ,recursive =True ))
            images .extend (glob .glob (pattern .replace (ext ,ext .upper ()),recursive =True ))
        else :
            pattern =os .path .join (folder_path ,f'*{ext }')
            images .extend (glob .glob (pattern ))
            images .extend (glob .glob (pattern .replace (ext ,ext .upper ())))

    return sorted (list (set (images )))

def load_profiles ()->Dict [str ,Any ]:
    default_data ={
    "last_used_profile":"Default",
    "global_settings": {
        "language": detect_system_language()
    },
    "profiles":{
    "Default":{
    "folders":[],
    "monitor_index":0 ,
    "interval_sec":5 ,
    "fade_duration_ms":1000 ,
    "random_order":True ,
    "ken_burns":True ,
    "fit_mode":"cover",
    "stay_on_top":False ,
    "show_filename":False ,
    "filename_v_pos":"bottom",
    "filename_h_pos":"center",
    "font_family": "Yu Gothic UI",
    "font_size":18 ,
    "font_bold":True ,
    }
    }
    }

    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

                if isinstance(data, dict) and "profiles" in data:

                    if "global_settings" not in data:
                        data["global_settings"] = {}

                    if "language" not in data["global_settings"]:
                        data["global_settings"]["language"] = detect_system_language()

                    global current_lang
                    current_lang = data["global_settings"].get(
                        "language",
                        detect_system_language()
                    )

                    if "Default" not in data["profiles"]:
                        data["profiles"]["Default"] = default_data["profiles"]["Default"]

                    return data
        except Exception as e :
            print (f"Error loading profiles: {e }")
            print ("Creating new profiles.json...")

    print ("Creating default profiles.json...")
    _save_profiles_data (default_data )
    return default_data 

def _save_profiles_data (data :Dict [str ,Any ]):
    try :
        with open (PROFILES_FILE ,'w',encoding ='utf-8')as f :
            json .dump (data ,f ,ensure_ascii =False ,indent =4 )
        print (f"Profiles saved to {PROFILES_FILE }")
    except Exception as e :
        print (f"Error saving profiles: {e }")

def show_about_dialog (parent_widget ):
    dialog =QtWidgets .QDialog (parent_widget )
    dialog .setWindowTitle (tr("title_about"))
    dialog .setFixedSize (450 ,520 )
    dialog .setWindowFlags (dialog .windowFlags ()&~QtCore .Qt .WindowContextHelpButtonHint )

    app =QtWidgets .QApplication .instance ()
    if app and not app .windowIcon ().isNull ():
        dialog .setWindowIcon (app .windowIcon ())
    elif parent_widget and hasattr (parent_widget ,'windowIcon')and not parent_widget .windowIcon ().isNull ():
        dialog .setWindowIcon (parent_widget .windowIcon ())

    if parent_widget :
        dialog .move (
        parent_widget .x ()+(parent_widget .width ()-dialog .width ())//2 ,
        parent_widget .y ()+(parent_widget .height ()-dialog .height ())//2 
        )
    else :
        screen_center =QtWidgets .QApplication .desktop ().screen ().rect ().center ()
        dialog .move (screen_center -dialog .rect ().center ())

    layout =QtWidgets .QVBoxLayout (dialog )
    layout .setSpacing (5 )
    layout .setContentsMargins (20 ,15 ,20 ,10 )
    header_layout =QtWidgets .QHBoxLayout ()
    icon_label =QtWidgets .QLabel ()

    if app and not app .windowIcon ().isNull ():
        app_icon =app .windowIcon ()
        pixmap =app_icon .pixmap (64 ,64 )
        if not pixmap .isNull ():
            icon_label .setPixmap (pixmap )
            icon_found =True 

    if not icon_found and parent_widget and hasattr (parent_widget ,'windowIcon'):
        app_icon =parent_widget .windowIcon ()
        if not app_icon .isNull ():
            pixmap =app_icon .pixmap (64 ,64 )
            if not pixmap .isNull ():
                icon_label .setPixmap (pixmap )
                icon_found =True 

    if not icon_found :
        icon_label .setText ("🎬")
        icon_label .setStyleSheet ("""
            font-size: 48px;
            border: 1px solid #ddd; 
            border-radius: 8px; 
            background: white;
            padding: 8px;
        """)
    else :
        icon_label .setStyleSheet ("""
            border: 1px solid #ddd; 
            border-radius: 8px; 
            background: white;
            padding: 8px;
        """)

        icon_label .setFixedSize (80 ,80 )
        icon_label .setAlignment (QtCore .Qt .AlignCenter )

    title_layout =QtWidgets .QVBoxLayout ()
    app_name =QtWidgets .QLabel ("<h1 style='margin: 0; color: #2c3e50;'>Cinematic Slideshow</h1>")

    version_info =QtWidgets .QLabel ("""
    <p style='margin: 5px 0; color: #7f8c8d; font-size: 12px;'>
    <b>Version :</b> 2.0<br>
    <b>Release :</b> May, 2026<br>
    <b>Build :</b> Python + PyQt5
    </p>
    """)

    title_layout .addWidget (app_name )
    title_layout .addWidget (version_info )
    title_layout .addStretch ()

    header_layout .addWidget (icon_label )
    header_layout .addLayout (title_layout )

    license_info =QtWidgets .QLabel ()
    license_info .setWordWrap (True )
    license_info .setStyleSheet ("""
        font-size: 12px;
        color: #495057; 
        background-color: #f8f9fa;
        border-left: 4px solid #28a745;
        padding: 10px;
        margin: 10px 0;
        line-height: 1.3;
    """)
    license_info .setText ("""
<p><b>📄 Open source license:</b></p>
<ul style="margin: 8px 0 0 18px; padding: 0;">
<li><b>Software :</b> GPL v3 License</li>
<li><b>PyQt5:</b> GPL v3 - Riverbank Computing</li>
<li><b>Python:</b> PSF License</li>
<li><b>Pillow:</b> HPND License</li>
</ul>
<p style="margin-top: 10px; font-size: 11px;">
<b>Source code: </b> https://github.com/sitar-j/Cinematic_Slideshow<br>
<b>Full license :</b> https://www.gnu.org/licenses/gpl-3.0.html
</p>
    """)

    footer =QtWidgets .QLabel ()
    footer .setAlignment (QtCore .Qt .AlignCenter )
    footer .setStyleSheet ("""
        color: #95a5a6; 
        font-size: 13px;
        border-top: 1px solid #ecf0f1; 
        padding-top: 5px;
        margin-top: 3px;
        line-height: 1.4;
    """)
    footer_text = tr("msg_about_footer").replace("\n", "<br>")

    footer.setText(f"""
    <p><b>{tr("label_developer")}</b> sitarj</p>

    <p style="color:#28a745;font-weight:bold;">
    🆓 {tr("label_open_source")}
    </p>

    <p style="font-size:12px;">
    {footer_text}
    </p>
    """)
    
    disclaimer =QtWidgets .QLabel ()
    disclaimer .setWordWrap (True )
    disclaimer .setStyleSheet ("""
        font-size: 11px;
        color: #7f8c8d; 
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 8px;
        margin: 5px 0;
        line-height: 1.0;
    """)
    disclaimer_text = tr("msg_disclaimer").split("\n")
    disclaimer.setText(f"""
    <p><b>{disclaimer_text[0]}</b></p>

    <ul style="margin: 6px 0 0 18px; padding: 0;">
    <li>{disclaimer_text[1]}</li>
    <li>{disclaimer_text[2]}</li>
    <li>{disclaimer_text[3]}</li>
    </ul>

    <p style="margin-top:8px; font-weight:bold;">
    {disclaimer_text[4]}
    </p>
    """)

    button_box =QtWidgets .QDialogButtonBox (
    QtWidgets .QDialogButtonBox .Close ,
    QtCore .Qt .Horizontal ,
    dialog 
    )
    button_box .button (QtWidgets .QDialogButtonBox .Close ).setText ("OK")
    button_box .rejected .connect (dialog .accept )

    layout .addLayout (header_layout )
    layout .addWidget (license_info )
    layout .addWidget (footer )
    layout .addWidget (disclaimer )
    layout .addWidget (button_box )

    dialog .exec_ ()

class MainWindow (QtWidgets .QWidget ):

    DEFAULT_FONT_FAMILY = "Yu Gothic UI"
    DEFAULT_FONT_SIZE =18 
    DEFAULT_FONT_BOLD =True 

    def __init__ (self ):
        super ().__init__ ()
        self .setWindowTitle (tr("title_profile_settings"))
        self .resize (650 ,570 )

        self .profiles ={}
        self .current_profile =None 

        self .current_font_family =self .DEFAULT_FONT_FAMILY 
        self .current_font_size =self .DEFAULT_FONT_SIZE 

        self .slideshow_window =None 
        self ._original_profile =None 

        self .profile_combo =QtWidgets .QComboBox ()
        self .profile_combo .setMinimumWidth (150 )

        button_width =70 
        self .btn_profile_add =QtWidgets .QPushButton (tr("btn_profile_new"))
        self .btn_profile_add .setMaximumWidth (button_width )
        self .btn_profile_save =QtWidgets .QPushButton (tr("btn_profile_save"))
        self .btn_profile_save .setMaximumWidth (button_width )
        self .btn_profile_rename =QtWidgets .QPushButton (tr("btn_profile_rename"))
        self .btn_profile_rename .setMaximumWidth (button_width )
        self .btn_profile_duplicate =QtWidgets .QPushButton (tr("btn_profile_duplicate"))
        self .btn_profile_duplicate .setMaximumWidth (button_width )
        self .btn_profile_remove =QtWidgets .QPushButton (tr("btn_profile_delete"))
        self .btn_profile_remove .setMaximumWidth (button_width )

        self .folder_list =FolderListWidget ()
        self .folder_list .setMinimumHeight (120 )
        self .folder_list .setSelectionMode (QtWidgets .QAbstractItemView .SingleSelection )
        self .folder_list .itemSelectionChanged .connect (self ._on_list_selection_changed )

        self .btn_folder_add =QtWidgets .QPushButton (tr("btn_add"))
        self .btn_folder_remove =QtWidgets .QPushButton (tr("btn_profile_delete"))
        self .chk_recursive =QtWidgets .QCheckBox (tr("chk_include_subfolders"))
        self .chk_recursive .setEnabled (False )

        self .monitor_combo =QtWidgets .QComboBox ()
        for i ,s in enumerate (QtWidgets .QApplication .screens ()):
            geom =s .geometry ()
            w ,h =geom .size ().width (),geom .size ().height ()
            self .monitor_combo .addItem (f"{i }: {s .name ()} ({w }x{h })")

        self .interval_spin =QtWidgets .QSpinBox ()
        self .interval_spin .setRange (1 ,60 )
        self .interval_spin .setValue (5 )

        self .radio_mode_fullscreen =QtWidgets .QRadioButton (tr("mode_fullscreen"))
        self .radio_mode_window =QtWidgets .QRadioButton (tr("mode_window"))
        self .radio_mode_fullscreen .setChecked (True )

        self .window_width_spin =QtWidgets .QSpinBox ()
        self .window_width_spin .setRange (320 ,7680 )
        self .window_width_spin .setValue (1280 )
        self .window_width_spin .setSuffix (" px")

        self .window_height_spin =QtWidgets .QSpinBox ()
        self .window_height_spin .setRange (240 ,4320 )
        self .window_height_spin .setValue (768 )
        self .window_height_spin .setSuffix (" px")

        self .chk_window_resizable =QtWidgets .QCheckBox (tr("chk_window_resizable"))
        self .chk_window_resizable .setChecked (True )

        self .radio_mode_fullscreen .toggled .connect (self ._on_mode_changed )
        self .radio_mode_window .toggled .connect (self ._on_mode_changed )

        self .radio_order_name =QtWidgets .QRadioButton (tr("order_name"))
        self .radio_order_random =QtWidgets .QRadioButton (tr("order_random"))
        self .radio_order_random .setChecked (True )

        self .radio_front =QtWidgets .QRadioButton (tr("layer_front"))
        self .radio_back =QtWidgets .QRadioButton (tr("layer_back"))
        self .radio_back .setChecked (True )

        self .radio_fit_cover =QtWidgets .QRadioButton (tr("fit_cover"))
        self .radio_fit_contain =QtWidgets .QRadioButton (tr("fit_contain"))
        self .radio_fit_cover .setChecked (True )

        self .chk_show_filename =QtWidgets .QCheckBox (tr("chk_show_filename"))
        self .combo_v_pos =QtWidgets .QComboBox ()
        self .combo_v_pos .addItems ([tr("pos_vertical_top"),tr("pos_vertical_bottom")])
        self .combo_v_pos .setCurrentText (tr("pos_vertical_bottom"))
        self .combo_h_pos =QtWidgets .QComboBox ()
        self .combo_h_pos .addItems ([tr("pos_horizontal_left"),tr("pos_horizontal_center"),tr("pos_horizontal_right")])
        self .combo_h_pos .setCurrentText (tr("pos_horizontal_center"))
        self .font_button =QtWidgets .QPushButton (tr("btn_font"))
        self .font_label =QtWidgets .QLabel (f"{self .DEFAULT_FONT_FAMILY }, {self .DEFAULT_FONT_SIZE }pt")

        self .filename_v_offset_spin =QtWidgets .QSpinBox ()
        self .filename_v_offset_spin .setRange (-200 ,200 )
        self .filename_v_offset_spin .setValue (0 )
        self .filename_v_offset_spin .setSuffix (" px")

        self .filename_h_offset_spin =QtWidgets .QSpinBox ()
        self .filename_h_offset_spin .setRange (-200 ,200 )
        self .filename_h_offset_spin .setValue (0 )
        self .filename_h_offset_spin .setSuffix (" px")

        # addp3
        self .chk_crossfade =QtWidgets .QCheckBox (tr("effect_crossfade"))
        self .chk_crossfade .setChecked (True )
        self .chk_slide =QtWidgets .QCheckBox (tr("effect_slide"))
        self .chk_slide .setChecked (False )
        self .chk_zoom =QtWidgets .QCheckBox (tr("effect_zoom"))
        self .chk_zoom .setChecked (False )
        self .chk_wipe =QtWidgets .QCheckBox (tr("effect_wipe"))
        self .chk_wipe .setChecked (False )
        self .chk_grid = QtWidgets.QCheckBox(tr("effect_grid"))
        self .chk_grid.setChecked(False)
        self .chk_shutter = QtWidgets.QCheckBox(tr("effect_shutter"))
        self .chk_shutter.setChecked(False)
        self .chk_fade_to_black =QtWidgets .QCheckBox (tr("effect_fade_to_black"))
        self .chk_fade_to_black .setChecked (False )  

        self .radio_effect_order =QtWidgets .QRadioButton (tr("effect_order_sequential"))
        self .radio_effect_random =QtWidgets .QRadioButton (tr("effect_order_random"))
        self .radio_effect_random .setChecked (True )

        self .fade_spin =QtWidgets .QDoubleSpinBox ()
        self .fade_spin .setRange (0.1 ,10.0 )
        self .fade_spin .setSingleStep (0.1 )
        self .fade_spin .setDecimals (1 )
        self .fade_spin .setValue (1.0 )

        self .chk_ken =QtWidgets .QCheckBox (tr("effect_ken_burns"))
        self .chk_ken .setChecked (True )

        self .chk_ken_linear =QtWidgets .QCheckBox ("linear")
        self .chk_ken_arc =QtWidgets .QCheckBox ("arc")
        self .chk_ken_wave =QtWidgets .QCheckBox ("wave")
        self .chk_ken_spiral =QtWidgets .QCheckBox ("spiral_in")
        self .chk_ken_zigzag =QtWidgets .QCheckBox ("zigzag")
        self .chk_ken_edge_scan =QtWidgets .QCheckBox ("edge_scan")

        self .chk_ken_linear .setChecked (True)
        self .chk_ken_arc .setChecked (True)
        self .chk_ken_wave .setChecked (True)
        self .chk_ken_spiral .setChecked (True)
        self .chk_ken_zigzag .setChecked (True)
        self .chk_ken_edge_scan .setChecked (False)

        self .radio_ken_order =QtWidgets .QRadioButton (tr("effect_order_sequential"))
        self .radio_ken_random =QtWidgets .QRadioButton (tr("effect_order_random"))
        self .radio_ken_random .setChecked (True)

        self .ken_intensity_slider =QtWidgets .QSlider (QtCore .Qt .Horizontal )
        self .ken_intensity_slider .setRange (1 ,10 )
        self .ken_intensity_slider .setValue (5 )
        self .ken_intensity_label =QtWidgets .QLabel ("5")
        self .ken_intensity_slider .valueChanged .connect (
        lambda v :self .ken_intensity_label .setText (str (v ))
        )

        self .shortcut_label =QtWidgets .QLabel (tr("label_shortcut_create"))
        self .btn_create_shortcut =QtWidgets .QPushButton (tr("btn_create_shortcut"))

        self .backup_label =QtWidgets .QLabel (tr("label_backup_restore"))
        self .btn_backup =QtWidgets .QPushButton (tr("btn_backup"))
        self .btn_restore =QtWidgets .QPushButton (tr("btn_restore"))
      
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItem("日本語", "ja")
        self.language_combo.addItem("English", "en")

        lang = self.profiles.get(
            "global_settings", {}
        ).get(
            "language",
            current_lang
        )

        index = self.language_combo.findData(lang)

        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        self.language_combo.currentIndexChanged.connect(
            self._on_language_changed
        )

        self .button_box =QtWidgets .QDialogButtonBox (
        QtWidgets .QDialogButtonBox .Ok |
        QtWidgets .QDialogButtonBox .Cancel |
        QtWidgets .QDialogButtonBox .Apply ,
        QtCore .Qt .Horizontal 
        )

        self .button_box .button (QtWidgets .QDialogButtonBox .Ok ).setText ("OK")
        self .button_box .button (QtWidgets .QDialogButtonBox .Cancel ).setText (tr("btn_cancel"))
        self .button_box .button (QtWidgets .QDialogButtonBox .Apply ).setText (tr("btn_apply"))

        self .setWindowTitle (tr("title_profile_settings"))
        self ._set_application_icon ()

        profile_group =QtWidgets .QGroupBox (tr("group_profile"))
        profile_layout =QtWidgets .QVBoxLayout (profile_group )

        profile_h =QtWidgets .QHBoxLayout ()
        profile_h .addWidget (QtWidgets .QLabel (tr("label_profile")))
        profile_h .addWidget (self .profile_combo )
        profile_h .addWidget (self .btn_profile_add )
        profile_h .addWidget (self .btn_profile_save )
        profile_h .addWidget (self .btn_profile_rename )
        profile_h .addWidget (self .btn_profile_duplicate )
        profile_h .addWidget (self .btn_profile_remove )
        profile_h .addStretch ()
        profile_layout .addLayout (profile_h )

        profile_manage_group = QtWidgets.QGroupBox(
            tr("group_profile_management")
        )

        profile_manage_layout = QtWidgets.QVBoxLayout(profile_manage_group)

        shortcut_h = QtWidgets.QHBoxLayout()
        shortcut_h.addWidget(self.shortcut_label)
        shortcut_h.addWidget(self.btn_create_shortcut)
        shortcut_h.addStretch()

        backup_h = QtWidgets.QHBoxLayout()
        backup_h.addWidget(self.backup_label)
        backup_h.addWidget(self.btn_backup)
        backup_h.addWidget(self.btn_restore)
        backup_h.addStretch()

        profile_manage_layout.addLayout(shortcut_h)
        profile_manage_layout.addLayout(backup_h)

        folder_group =QtWidgets .QGroupBox (tr("group_folder"))
        folder_layout =QtWidgets .QVBoxLayout (folder_group )
        folder_btn_h =QtWidgets .QHBoxLayout ()
        folder_btn_h .addWidget (self .btn_folder_add )
        folder_btn_h .addWidget (self .btn_folder_remove )
        folder_btn_h .addWidget (self .chk_recursive )
        folder_btn_h .addStretch ()
        folder_layout .addLayout (folder_btn_h )
        folder_layout .addWidget (self .folder_list )

        display_group =QtWidgets .QGroupBox (tr("group_display"))
        display_layout =QtWidgets .QGridLayout (display_group )

        display_layout .setColumnStretch (0 ,1 )
        display_layout .setColumnStretch (1 ,2 )
        display_layout .setColumnStretch (2 ,1 )
        display_layout .setColumnStretch (3 ,2 )

        mode_group =QtWidgets .QGroupBox (tr("group_mode"))
        mode_layout =QtWidgets .QHBoxLayout (mode_group )
        mode_layout .addWidget (self .radio_mode_fullscreen )
        mode_layout .addWidget (self .radio_mode_window )
        display_layout .addWidget (mode_group ,0 ,0 ,1 ,2 )

        display_layout.addWidget(QtWidgets.QLabel(tr("label_monitor")), 0, 2)
        display_layout .addWidget (self .monitor_combo ,0 ,3 )

        window_size_label =QtWidgets .QLabel (tr("label_window_size"))
        display_layout .addWidget (window_size_label ,1 ,0 )

        window_size_widget =QtWidgets .QWidget ()
        window_size_h =QtWidgets .QHBoxLayout (window_size_widget )
        window_size_h .setContentsMargins (0 ,0 ,0 ,0 )
        window_size_h.addWidget(QtWidgets.QLabel(tr("label_width")))
        window_size_h .addWidget (self .window_width_spin )
        window_size_h.addWidget(QtWidgets.QLabel(tr("label_height")))
        window_size_h .addWidget (self .window_height_spin )
        window_size_h .addStretch ()
        display_layout .addWidget (window_size_widget ,1 ,1 ,1 ,2 )

        display_layout .addWidget (self .chk_window_resizable ,1 ,3 ,1 ,2 )

        order_group =QtWidgets .QGroupBox (tr("group_order"))
        order_layout =QtWidgets .QHBoxLayout (order_group )
        order_layout .addWidget (self .radio_order_name )
        order_layout .addWidget (self .radio_order_random )
        display_layout .addWidget (order_group ,2 ,0 ,1 ,2 )

        depth_group =QtWidgets .QGroupBox (tr("group_depth"))
        depth_layout =QtWidgets .QHBoxLayout (depth_group )
        depth_layout .addWidget (self .radio_front )
        depth_layout .addWidget (self .radio_back )
        display_layout .addWidget (depth_group ,2 ,2 ,1 ,3 )

        fit_group =QtWidgets .QGroupBox (tr("group_fit"))
        fit_layout =QtWidgets .QVBoxLayout (fit_group )

        fit_radio_layout =QtWidgets .QHBoxLayout ()
        fit_radio_layout .addWidget (self .radio_fit_cover )
        fit_radio_layout .addWidget (self .radio_fit_contain )
        fit_layout .addLayout (fit_radio_layout )

        fit_time_layout =QtWidgets .QHBoxLayout ()
        fit_time_layout.addWidget(QtWidgets.QLabel(tr("label_display_time")))
        fit_time_layout .addWidget (self .interval_spin )
        fit_time_layout .addWidget (QtWidgets .QLabel (tr("unit_seconds")))
        fit_time_layout .addStretch ()
        fit_layout .addLayout (fit_time_layout )

        display_layout .addWidget (fit_group ,3 ,0 ,1 ,2 )

        filename_group =QtWidgets .QGroupBox (tr("label_file_name"))
        filename_layout =QtWidgets .QGridLayout (filename_group )
        filename_layout .addWidget (self .chk_show_filename ,0 ,0 )
        filename_layout.addWidget(QtWidgets.QLabel(tr("label_vertical")), 0, 1)
        filename_layout .addWidget (self .combo_v_pos ,0 ,2 )
        filename_layout.addWidget(QtWidgets.QLabel(tr("label_horizontal")), 0, 3)
        filename_layout .addWidget (self .combo_h_pos ,0 ,4 )
        filename_layout .addWidget (self .font_button ,1 ,0 )
        filename_layout .addWidget (self .font_label ,1 ,1 ,1 ,4 )
        filename_layout.addWidget(QtWidgets.QLabel(tr("label_adjustment")), 2, 0)
        filename_layout.addWidget(QtWidgets.QLabel(tr("label_vertical")), 2, 1)
        filename_layout .addWidget (self .filename_v_offset_spin ,2 ,2 )
        filename_layout.addWidget(QtWidgets.QLabel(tr("label_horizontal")), 2, 3)
        filename_layout .addWidget (self .filename_h_offset_spin ,2 ,4 )
        display_layout .addWidget (filename_group ,3 ,2 ,1 ,3 )

        effect_group =QtWidgets .QGroupBox (tr("group_effect"))
        effect_layout =QtWidgets .QVBoxLayout (effect_group )

        # addp4
        transition_group =QtWidgets .QGroupBox (tr("group_transition"))
        transition_layout =QtWidgets .QGridLayout (transition_group )
        transition_layout .addWidget (self .chk_crossfade ,0 ,0 )
        transition_layout .addWidget (self .chk_slide ,0 ,1 )
        transition_layout .addWidget (self .chk_zoom ,0 ,2 )
        transition_layout .addWidget (self .chk_wipe ,0 ,3 )
        transition_layout.addWidget(self.chk_grid, 1, 0)
        transition_layout.addWidget(self.chk_shutter, 1, 1)
        transition_layout .addWidget (self .chk_fade_to_black ,1 ,2 )

        effect_order_layout =QtWidgets .QHBoxLayout ()
        effect_order_layout.addWidget(QtWidgets.QLabel(tr("label_effect_order")))
        effect_order_layout .addWidget (self .radio_effect_order )
        effect_order_layout .addWidget (self .radio_effect_random )
        effect_order_layout .addStretch ()
        transition_layout .addLayout (effect_order_layout ,2 ,0 ,1 ,3 )

        effect_layout .addWidget (transition_group )

        time_h =QtWidgets .QHBoxLayout ()
        time_h.addWidget(QtWidgets.QLabel(tr("label_effect_time"))) 
        time_h .addWidget (self .fade_spin )
        time_h .addStretch ()
        effect_layout .addLayout (time_h )

        image_effect_group =QtWidgets .QGroupBox (tr("group_image_effect"))
        image_effect_layout =QtWidgets .QVBoxLayout (image_effect_group )
        ken_top_h =QtWidgets .QHBoxLayout ()
        ken_top_h .addWidget (self .chk_ken )
        ken_top_h .addSpacing (20 )
        ken_top_h .addWidget (QtWidgets .QLabel (tr("label_strength")))
        ken_top_h .addWidget (self .ken_intensity_slider )
        ken_top_h .addWidget (self .ken_intensity_label )
        ken_top_h .addStretch ()
        
        ken_type_label =QtWidgets .QLabel (tr("label_ken_burns_type"))
        ken_patterns_h =QtWidgets .QHBoxLayout ()
        ken_patterns_h .addWidget (self .chk_ken_linear )
        ken_patterns_h .addWidget (self .chk_ken_arc )
        ken_patterns_h .addWidget (self .chk_ken_wave )
        ken_patterns_h .addWidget (self .chk_ken_spiral )
        ken_patterns_h .addWidget (self .chk_ken_zigzag )
        ken_patterns_h .addWidget (self .chk_ken_edge_scan )
        ken_patterns_h .addStretch ()

        ken_order_h =QtWidgets .QHBoxLayout ()
        ken_order_h .addWidget (QtWidgets .QLabel (tr("label_effect_order")))
        ken_order_h .addWidget (self .radio_ken_order )
        ken_order_h .addWidget (self .radio_ken_random )
        ken_order_h .addStretch ()

        ken_note =QtWidgets .QLabel (tr("note_ken_edge_scan_disabled"))
        ken_note .setWordWrap (True)
        ken_note .setStyleSheet ("color: #666; font-size: 11px;")

        image_effect_layout .addLayout (ken_top_h )
        image_effect_layout .addWidget (ken_type_label )
        image_effect_layout .addLayout (ken_patterns_h )
        image_effect_layout .addLayout (ken_order_h )
        image_effect_layout .addWidget (ken_note )

        effect_layout .addWidget (image_effect_group )

        self ._setup_tooltips ()

        tabs = QtWidgets.QTabWidget()

        general_tab = QtWidgets.QWidget()
        general_layout = QtWidgets.QVBoxLayout(general_tab)

        general_layout.addWidget(profile_group)
        general_layout.addWidget(profile_manage_group)
        general_layout.addWidget(folder_group)

        language_group = QtWidgets.QGroupBox(tr("label_language"))
        language_layout = QtWidgets.QHBoxLayout(language_group)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()

        general_layout.addWidget(language_group)
        general_layout.addStretch(1)

        display_tab = QtWidgets.QWidget()
        display_tab_layout = QtWidgets.QVBoxLayout(display_tab)
        display_tab_layout.addWidget(display_group)
        display_tab_layout.addStretch(1)

        effect_tab = QtWidgets.QWidget()
        effect_tab_layout = QtWidgets.QVBoxLayout(effect_tab)
        effect_tab_layout.addWidget(effect_group)
        effect_tab_layout.addStretch(1)

        info_tab = QtWidgets.QWidget()
        info_tab_layout = QtWidgets.QVBoxLayout(info_tab)
        info_tab_layout.setSpacing(8)
        info_tab_layout.setContentsMargins(20, 15, 20, 10)

        header_layout = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel()

        icon_found = False

        try:
            app = QtWidgets.QApplication.instance()
            if app and not app.windowIcon().isNull():
                pixmap = app.windowIcon().pixmap(64, 64)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap)
                    icon_found = True

            if not icon_found and not self.windowIcon().isNull():
                pixmap = self.windowIcon().pixmap(64, 64)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap)
                    icon_found = True
        except Exception:
            icon_found = False

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

        title_layout = QtWidgets.QVBoxLayout()

        app_name = QtWidgets.QLabel(
            "<h1 style='margin: 0; color: #2c3e50;'>Cinematic Slideshow</h1>"
        )

        version_info = QtWidgets.QLabel("""
        <p style='margin: 5px 0; color: #7f8c8d; font-size: 12px;'>
        <b>Version :</b> 2.2<br>
        <b>Release :</b> June, 2026<br>
        <b>Build :</b> Python + PyQt5
        </p>
        """)

        title_layout.addWidget(app_name)
        title_layout.addWidget(version_info)
        title_layout.addStretch()

        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_layout)

        license_info = QtWidgets.QLabel()
        license_info.setWordWrap(True)
        license_info.setOpenExternalLinks(True)
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
        <p><b>📄 Open source license:</b></p>
        <ul style="margin: 8px 0 0 18px; padding: 0;">
        <li><b>Software :</b> GPL v3 License</li>
        <li><b>PyQt5:</b> GPL v3 - Riverbank Computing</li>
        <li><b>Python:</b> PSF License</li>
        <li><b>Pillow:</b> HPND License</li>
        </ul>
        <p style="margin-top: 10px; font-size: 11px;">
        <b>Source code: </b>
        <a href="https://github.com/sitar-j/Cinematic_Slideshow">
        https://github.com/sitar-j/Cinematic_Slideshow
        </a><br>
        <b>Full license :</b>
        <a href="https://www.gnu.org/licenses/gpl-3.0.html">
        https://www.gnu.org/licenses/gpl-3.0.html
        </a>
        </p>
        """)

        footer = QtWidgets.QLabel()
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setWordWrap(True)
        footer.setStyleSheet("""
            color: #95a5a6;
            font-size: 13px;
            border-top: 1px solid #ecf0f1;
            padding-top: 5px;
            margin-top: 3px;
            line-height: 1.4;
        """)

        footer_text = tr("msg_about_footer").replace("\n", "<br>")

        footer.setText(f"""
        <p><b>{tr("label_developer")}</b> sitarj</p>

        <p style="color:#28a745;font-weight:bold;">
        🆓 {tr("label_open_source")}
        </p>

        <p style="font-size:12px;">
        {footer_text}
        </p>
        """)

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

        disclaimer_text = tr("msg_disclaimer").split("\n")

        if len(disclaimer_text) >= 5:
            disclaimer.setText(f"""
            <p><b>{disclaimer_text[0]}</b></p>

            <ul style="margin: 6px 0 0 18px; padding: 0;">
            <li>{disclaimer_text[1]}</li>
            <li>{disclaimer_text[2]}</li>
            <li>{disclaimer_text[3]}</li>
            </ul>

            <p style="margin-top:8px; font-weight:bold;">
            {disclaimer_text[4]}
            </p>
            """)
        else:
            disclaimer.setText(tr("msg_disclaimer"))

        info_tab_layout.addLayout(header_layout)
        info_tab_layout.addWidget(license_info)
        info_tab_layout.addWidget(footer)
        info_tab_layout.addWidget(disclaimer)
        info_tab_layout.addStretch(1)

        tabs.addTab(general_tab, tr("tab_general"))
        tabs.addTab(display_tab, tr("tab_display"))
        tabs.addTab(effect_tab, tr("tab_effect"))
        tabs.addTab(info_tab, tr("tab_info"))

        main_v = QtWidgets.QVBoxLayout(self)
        main_v.addWidget(tabs)
        main_v.addWidget(self.button_box)

        self .profile_combo .currentIndexChanged .connect (self ._on_profile_changed )
        self .btn_profile_add .clicked .connect (self .on_add_profile )
        self .btn_profile_duplicate .clicked .connect (self .on_duplicate_profile )
        self .btn_profile_rename .clicked .connect (self .on_rename_profile )
        self .btn_profile_save .clicked .connect (self ._on_apply_clicked )
        self .btn_profile_remove .clicked .connect (self .on_remove_profile )
        self .btn_create_shortcut .clicked .connect (self ._on_create_shortcut )
        self .btn_backup .clicked .connect (self ._on_backup_profiles )
        self .btn_restore .clicked .connect (self ._on_restore_profiles )

        self .btn_folder_add .clicked .connect (self ._on_add_folder )
        self .btn_folder_remove .clicked .connect (self ._on_remove_folder )
        self .chk_recursive .stateChanged .connect (self ._on_recursive_changed )

        self .font_button .clicked .connect (self ._on_select_font )

        self .button_box .accepted .connect (self ._on_ok_clicked )
        self .button_box .rejected .connect (self ._on_cancel_clicked )
        self .button_box .button (QtWidgets .QDialogButtonBox .Apply ).clicked .connect (self ._on_apply_clicked )

        self ._load_profiles ()
        self ._setup_system_tray ()
        
    def _on_language_changed(self):
        global current_lang
        lang = self.language_combo.currentData()
        if not lang:
            return

        current_lang = lang
        self.profiles.setdefault(
            "global_settings",
            {}
        )
        self.profiles["global_settings"]["language"] = lang
        self._save_profiles()
        QtWidgets.QMessageBox.information(
            self,
            tr("title_info"),
            tr("msg_language_changed_restart")
        )

    def _setup_tooltips (self ):

        self .profile_combo .setToolTip (tr("tooltip_profile_select"))
        self .btn_profile_add .setToolTip (tr("tooltip_profile_new"))
        self .btn_profile_save .setToolTip (tr("tooltip_profile_save"))
        self .btn_profile_rename .setToolTip (tr("tooltip_profile_rename"))
        self .btn_profile_duplicate .setToolTip (tr("tooltip_profile_duplicate"))
        self .btn_profile_remove.setToolTip(tr("tooltip_profile_remove"))
        self .btn_create_shortcut.setToolTip(tr("tooltip_create_shortcut"))
        self .btn_backup.setToolTip(tr("tooltip_backup"))
        self .btn_restore.setToolTip(tr("tooltip_restore"))
        self .folder_list.setToolTip(tr("tooltip_folder_list"))
        self .btn_folder_add .setToolTip (tr("tooltip_folder_add"))
        self .btn_folder_remove .setToolTip (tr("tooltip_folder_remove"))
        self .chk_recursive .setToolTip (tr("tooltip_recursive"))

        self .radio_mode_fullscreen .setToolTip (tr("tooltip_mode_fullscreen"))
        self .radio_mode_window .setToolTip (tr("tooltip_mode_window"))
        self .window_width_spin .setToolTip (tr("tooltip_window_width"))
        self .window_height_spin .setToolTip (tr("tooltip_window_height"))
        self .chk_window_resizable .setToolTip (tr("tooltip_window_resizable"))

        self .monitor_combo .setToolTip (tr("tooltip_monitor_select"))
        self .interval_spin .setToolTip (tr("tooltip_interval"))

        self .radio_order_name .setToolTip (tr("tooltip_order_name"))
        self .radio_order_random .setToolTip (tr("tooltip_order_random"))

        self .radio_front .setToolTip (tr("tooltip_front"))
        self .radio_back .setToolTip (tr("tooltip_back"))

        self .radio_fit_cover .setToolTip (tr("tooltip_fit_cover"))
        self .radio_fit_contain .setToolTip (tr("tooltip_fit_contain"))

        self .chk_show_filename .setToolTip (tr("tooltip_show_filename"))
        self .combo_v_pos .setToolTip (tr("tooltip_v_pos"))
        self .combo_h_pos .setToolTip (tr("tooltip_h_pos"))
        self .font_button .setToolTip (tr("tooltip_font_select"))
        self .filename_v_offset_spin.setToolTip(tr("tooltip_filename_v_offset"))
        self .filename_h_offset_spin.setToolTip(tr("tooltip_filename_h_offset"))

        # addp5
        self .chk_crossfade .setToolTip (tr("tooltip_crossfade"))
        self .chk_slide .setToolTip (tr("tooltip_slide"))
        self .chk_zoom .setToolTip (tr("tooltip_zoom"))
        self .chk_wipe .setToolTip (tr("tooltip_wipe"))
        self .chk_fade_to_black .setToolTip (tr("tooltip_fade_to_black"))
        self .chk_grid.setToolTip(tr("tooltip_grid"))
        self.chk_shutter.setToolTip(tr("tooltip_shutter"))

        self .radio_effect_order .setToolTip (tr("tooltip_effect_order"))
        self .radio_effect_random .setToolTip (tr("tooltip_effect_random"))

        self .fade_spin .setToolTip (tr("tooltip_fade_duration"))

        self .chk_ken.setToolTip(tr("tooltip_ken_burns"))
        self .ken_intensity_slider.setToolTip(tr("tooltip_ken_intensity"))

    def _set_application_icon (self ):
        icon_set =False 

        try :

            if getattr (sys ,'frozen',False ):

                exe_dir =os .path .dirname (sys .executable )
                icon_path =os .path .join (exe_dir ,"icon.ico")
            else :

                script_dir =os .path .dirname (os .path .abspath (__file__ ))
                icon_path =os .path .join (script_dir ,"icon.ico")

            if os .path .exists (icon_path ):
                icon =QtGui .QIcon (icon_path )
                if not icon .isNull ():

                    app =QtWidgets .QApplication .instance ()
                    if app :
                        app .setWindowIcon (icon )

                    self .setWindowIcon (icon )

                    self .app_icon =icon 
                    icon_set =True 

            if not icon_set :
                print (tr("log_icon_missing"))
                icon =self .style ().standardIcon (QtWidgets .QStyle .SP_ComputerIcon )

                app =QtWidgets .QApplication .instance ()
                if app :
                    app .setWindowIcon (icon )

                self .setWindowIcon (icon )
                self .app_icon =icon 

        except Exception as e :
            print(f"Icon setup error: {e}")

            icon =self .style ().standardIcon (QtWidgets .QStyle .SP_ComputerIcon )

            app =QtWidgets .QApplication .instance ()
            if app :
                app .setWindowIcon (icon )

            self .setWindowIcon (icon )
            self .app_icon =icon 

    def _show_about_dialog (self ):
        show_about_dialog (self )

    def _on_ok_clicked (self ):

        current_config =self ._get_current_ui_config ()

        has_changes =False 
        if hasattr (self ,'_initial_config'):
            has_changes =(self ._initial_config !=current_config )

        self ._write_current_profile ()

        if hasattr (self ,'_original_profile')and self ._original_profile :
            self .hide ()

            if has_changes :
                if hasattr (self ,'tray_icon')and self .tray_icon .isVisible ():
                    self .tray_icon .showMessage (
                    "Cinematic Slideshow",
                    tr("msg_restart_required"),
                    QtWidgets .QSystemTrayIcon .Information ,
                    2000 
                    )

                    QtCore .QTimer .singleShot (500 ,self ._restart_slideshow )

            else :

                if hasattr (self ,'slideshow_window')and self .slideshow_window :
                    self .slideshow_window .show ()
                    self .slideshow_window .raise_ ()
                    self .slideshow_window .activateWindow ()

            self ._original_profile =None 
        else :

            self .close ()

    def _on_cancel_clicked (self ):

        if hasattr (self ,'_original_profile')and self ._original_profile :
            self .hide ()
            if hasattr (self ,'slideshow_window')and self .slideshow_window :
                self .slideshow_window .show ()
                self .slideshow_window .raise_ ()
                self .slideshow_window .activateWindow ()
            self ._original_profile =None 
        else :

            self .close ()

    def _on_apply_clicked (self ):
        self ._write_current_profile ()

    def _on_mode_changed (self ):
        is_window_mode =self .radio_mode_window .isChecked ()

        self .window_width_spin .setEnabled (is_window_mode )
        self .window_height_spin .setEnabled (is_window_mode )
        self .chk_window_resizable .setEnabled (is_window_mode )
        self .monitor_combo .setEnabled (not is_window_mode )

    def _restart_slideshow (self ):

        self ._write_current_profile ()

        self ._load_profiles ()

        if hasattr (self ,'slideshow_window')and self .slideshow_window :
            self .slideshow_window .close ()
            self .slideshow_window =None 

        self .start_slideshow ()

    def _create_default_config (self )->Dict [str ,Any ]:
        return {
        "folders":[],
        "monitor_index":0 ,
        "interval_sec":5 ,
        "window_mode":"fullscreen",
        "window_width":1280 ,
        "window_height":768 ,
        "window_resizable":True ,
        "fade_duration_ms":1000 ,
        "random_order":True ,
        "ken_burns":True ,
        "fit_mode":"cover",
        "stay_on_top":False ,
        "show_filename":False ,
        "filename_v_pos":"bottom",
        "filename_h_pos":"center",
        "font_family":self .DEFAULT_FONT_FAMILY ,
        "font_size":self .DEFAULT_FONT_SIZE ,
        "font_bold":self .DEFAULT_FONT_BOLD ,
        "filename_v_offset":0 ,
        "filename_h_offset":0 ,
        # addp6
        "effects":{
        "crossfade":True ,
        "slide":False ,
        "zoom":False ,
        "wipe":False ,
        "fade_to_black":False ,
        "grid": False,
        "shutter": False,
        },
        "effect_order":"random",
        }

    def _validate_config (self ,config :Dict [str ,Any ])->Tuple [bool ,str ]:

        required_keys =["folders","monitor_index","interval_sec"]
        for key in required_keys :
            if key not in config:
                return False, tr("error_missing_setting_key").format(key=key)

        if not 1 <=config .get ("interval_sec",5 )<=3600 :
            return False ,tr("error_invalid_interval_range")

        if not 100 <=config .get ("fade_duration_ms",1000 )<=10000 :
            return False ,tr("error_invalid_effect_duration_range")

        monitor_count =len (QtWidgets .QApplication .screens ())
        if config.get("monitor_index", 0) >= monitor_count:
            return False, tr("error_monitor_out_of_range").format(max_monitor=monitor_count - 1)
        return True ,""

    def _load_profiles (self ):
        data =load_profiles ()
        self .profiles =data .get ("profiles",{})

        if not self .profiles or "Default"not in self .profiles :
            self .profiles ["Default"]=self ._create_default_config ()
            self .current_profile ="Default"
            self ._save_profiles ()

        last_used =data .get ("last_used_profile","Default")
        if last_used in self .profiles :
            self .current_profile =last_used 
        else :
            self .current_profile ="Default"

        self ._load_profile_list ()
        self ._load_current_profile ()

    def _save_profiles(self):
        try:
            data = {
                "last_used_profile": self.current_profile,
                "global_settings": {
                    "language": current_lang
                },
                "profiles": self.profiles
            }
            with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    data,
                    f,
                    ensure_ascii=False,
                    indent=4
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                tr("title_error"),
                tr("error_profile_write_failed").format(e=e)
            )

    def _load_profile_list (self ):
        self .profile_combo .blockSignals (True )
        self .profile_combo .clear ()

        sorted_keys =sorted (self .profiles .keys ())

        profile_names =list (self .profiles .keys ())
        if "Default"in profile_names :
            profile_names .remove ("Default")
            profile_names .insert (0 ,"Default")

        self .profile_combo .addItems (profile_names )

        if self .current_profile in self .profiles :
            self .profile_combo .setCurrentText (self .current_profile )

        self .profile_combo .blockSignals (False )

    def _load_current_profile (self ):
        if not self .current_profile or self .current_profile not in self .profiles :
            return 

        config =self .profiles [self .current_profile ]

        is_valid ,error_msg =self ._validate_config (config )
        if not is_valid :
            QtWidgets .QMessageBox .warning (self ,tr("error_settings_validation"),error_msg )
            config .update (self ._create_default_config ())

        self ._loaded_config ={
        "folders":config .get ("folders",[]),
        "monitor_index":config .get ("monitor_index",0 ),
        "interval_sec":config .get ("interval_sec",5 ),
        "fade_duration_ms":config .get ("fade_duration_ms",1000 ),
        "random_order":config .get ("random_order",True ),
        "ken_burns":config .get ("ken_burns",True ),
        "ken_intensity":config .get ("ken_intensity",5 ),
        "fit_mode":config .get ("fit_mode","cover"),
        "stay_on_top":config .get ("stay_on_top",True ),
        "show_filename":config .get ("show_filename",False ),
        "filename_v_pos":config .get ("filename_v_pos","bottom"),
        "filename_h_pos":config .get ("filename_h_pos","center"),
        "font_family":config .get ("font_family",self .DEFAULT_FONT_FAMILY ),
        "font_size":config .get ("font_size",self .DEFAULT_FONT_SIZE ),
        "font_bold":config .get ("font_bold",self .DEFAULT_FONT_BOLD ),
        "effects":config .get ("effects",{"crossfade":True }),
        "effect_order":config .get ("effect_order","random"),
        "window_mode":config .get ("window_mode","fullscreen"),
        "window_width":config .get ("window_width",1280 ),
        "window_height":config .get ("window_height",768 ),
        "window_resizable":config .get ("window_resizable",True ),
        }

        self .blockSignals (True )

        self .folder_list .clear ()
        for item in config .get ("folders",[]):
            if isinstance (item ,(list ,tuple ))and len (item )==2 :
                folder_path ,recursive =item 
            elif isinstance (item ,str ):
                folder_path ,recursive =item ,False 
            else :
                continue 

            list_item =QtWidgets .QListWidgetItem (folder_path )
            list_item .setData (QtCore .Qt .UserRole ,recursive )
            list_item .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_DirIcon ))
            self .folder_list .addItem (list_item )

        if self .folder_list .count ()>0 :
            self .folder_list .setCurrentRow (0 )
        self ._on_list_selection_changed ()

        self .monitor_combo .setCurrentIndex (config .get ("monitor_index",0 ))
        self .interval_spin .setValue (config .get ("interval_sec",5 ))

        window_mode =config .get ("window_mode","fullscreen")
        self .radio_mode_fullscreen .setChecked (window_mode =="fullscreen")
        self .radio_mode_window .setChecked (window_mode =="window")

        self .window_width_spin .setValue (config .get ("window_width",1280 ))
        self .window_height_spin .setValue (config .get ("window_height",768 ))
        self .chk_window_resizable .setChecked (config .get ("window_resizable",True ))

        self ._on_mode_changed ()

        random_order =config .get ("random_order",True )
        self .radio_order_random .setChecked (random_order )
        self .radio_order_name .setChecked (not random_order )

        stay_on_top =config .get ("stay_on_top",True )
        self .radio_front .setChecked (stay_on_top )
        self .radio_back .setChecked (not stay_on_top )

        fit_mode =config .get ("fit_mode","cover")
        self .radio_fit_cover .setChecked (fit_mode =="cover")
        self .radio_fit_contain .setChecked (fit_mode =="contain")

        self .chk_show_filename .setChecked (config .get ("show_filename",False ))

        v_pos =config .get ("filename_v_pos","bottom")
        if v_pos =="top":
            self .combo_v_pos .setCurrentText (tr("pos_vertical_top"))
        else :
            self .combo_v_pos .setCurrentText (tr("pos_vertical_bottom"))

        h_pos =config .get ("filename_h_pos","center")
        if h_pos =="left":
            self .combo_h_pos .setCurrentText (tr("pos_horizontal_left"))
        elif h_pos =="right":
            self .combo_h_pos .setCurrentText (tr("pos_horizontal_right"))
        else :
            self .combo_h_pos .setCurrentText (tr("pos_horizontal_center"))

        self .current_font_family =config .get ("font_family",self .DEFAULT_FONT_FAMILY )
        self .current_font_size =config .get ("font_size",self .DEFAULT_FONT_SIZE )
        self .current_font_bold =config .get ("font_bold",self .DEFAULT_FONT_BOLD )
        bold_text =tr("font_bold_label")if self .current_font_bold else tr("font_regular_label")
        self .font_label .setText (f"{self .current_font_family }, {self .current_font_size }pt, {bold_text }")

        self .filename_v_offset_spin .setValue (config .get ("filename_v_offset",0 ))
        self .filename_h_offset_spin .setValue (config .get ("filename_h_offset",0 ))

        fade_ms =config .get ("fade_duration_ms",1000 )
        self .fade_spin .setValue (fade_ms /1000.0 )

        self .chk_ken .setChecked (config .get ("ken_burns",True ))
        self .chk_ken_linear.setChecked(config.get("ken_burns_patterns", {}).get("linear", True))
        self .chk_ken_arc.setChecked(config.get("ken_burns_patterns", {}).get("arc", True))
        self .chk_ken_wave.setChecked(config.get("ken_burns_patterns", {}).get("wave", True))
        self .chk_ken_spiral.setChecked(config.get("ken_burns_patterns", {}).get("spiral_in", True))
        self .chk_ken_zigzag.setChecked(config.get("ken_burns_patterns", {}).get("zigzag", True))
        self .chk_ken_edge_scan.setChecked(config.get("ken_burns_patterns", {}).get("edge_scan", False))
        ken_order = config.get("ken_burns_order","random")
        self .radio_ken_order.setChecked(ken_order == "sequential")
        self .radio_ken_random.setChecked(ken_order == "random")

        ken_intensity =config .get ("ken_intensity",5 )
        self .ken_intensity_slider .setValue (ken_intensity )
        self .ken_intensity_label .setText (str (ken_intensity ))

        self .blockSignals (False )

        is_default =self .current_profile =="Default"
        self .btn_profile_remove .setEnabled (not is_default )
        self .btn_profile_rename .setEnabled (not is_default )
        self .btn_profile_duplicate .setEnabled (True )

        # addp7
        effects =config .get ("effects",{})
        self .chk_crossfade .setChecked (effects .get ("crossfade",True ))
        self .chk_slide .setChecked (effects .get ("slide",False ))
        self .chk_zoom .setChecked (effects .get ("zoom",False ))
        self .chk_wipe .setChecked (effects .get ("wipe",False ))
        self .chk_fade_to_black .setChecked (effects .get ("fade_to_black",False ))
        self .chk_grid .setChecked(effects.get("grid", False))
        self .chk_shutter.setChecked(effects.get("shutter", False))

        effect_order =config .get ("effect_order","random")
        self .radio_effect_random .setChecked (effect_order =="random")
        self .radio_effect_order .setChecked (effect_order =="sequential")

    def _write_current_profile (self ):
        if not self .current_profile :
            return 

        try :

            latest_data =load_profiles ()

            if self .current_profile not in latest_data ["profiles"]:
                QtWidgets .QMessageBox .warning (
                    self ,
                    tr("title_warning"),
                    tr("error_profile_deleted_external").format(
                        profile=self.current_profile
                    )
                )
                self .current_profile ="Default"
                self .profile_combo .setCurrentText ("Default")
                self ._load_current_profile ()
                return 

            config =latest_data ["profiles"][self .current_profile ]

            folders_list =[]
            for i in range (self .folder_list .count ()):
                item =self .folder_list .item (i )
                folder_path =item .text ()
                recursive =item .data (QtCore .Qt .UserRole )
                folders_list .append ((folder_path ,recursive if isinstance (recursive ,bool )else False ))

            config ["folders"]=folders_list 
            config ["monitor_index"]=self .monitor_combo .currentIndex ()
            config ["interval_sec"]=self .interval_spin .value ()
            config ["window_mode"]="window"if self .radio_mode_window .isChecked ()else "fullscreen"
            config ["window_width"]=self .window_width_spin .value ()
            config ["window_height"]=self .window_height_spin .value ()
            config ["window_resizable"]=self .chk_window_resizable .isChecked ()
            config ["fade_duration_ms"]=int (self .fade_spin .value ()*1000 )
            config ["random_order"]=self .radio_order_random .isChecked ()
            config ["ken_burns"]=self .chk_ken .isChecked ()
            config ["ken_burns_patterns"]={
            "linear":self .chk_ken_linear .isChecked (),
            "arc":self .chk_ken_arc .isChecked (),
            "wave":self .chk_ken_wave .isChecked (),
            "spiral_in":self .chk_ken_spiral .isChecked (),
            "zigzag":self .chk_ken_zigzag .isChecked (),
            "edge_scan":self .chk_ken_edge_scan .isChecked (),
            }
            config ["ken_burns_order"]="sequential" if self .radio_ken_order .isChecked () else "random"
            config ["ken_intensity"]=self .ken_intensity_slider .value ()
            config ["fit_mode"]="cover"if self .radio_fit_cover .isChecked ()else "contain"
            config ["stay_on_top"]=self .radio_front .isChecked ()
            config ["show_filename"]=self .chk_show_filename .isChecked ()

            v_text =self .combo_v_pos .currentText ()
            config ["filename_v_pos"]="top"if v_text ==tr("pos_vertical_top")else "bottom"

            h_text =self .combo_h_pos .currentText ()
            if h_text ==tr("pos_horizontal_left"):
                config ["filename_h_pos"]="left"
            elif h_text ==tr("pos_horizontal_right"):
                config ["filename_h_pos"]="right"
            else :
                config ["filename_h_pos"]="center"

            config ["font_family"]=self .current_font_family 
            config ["font_size"]=self .current_font_size 
            config ["font_bold"]=self .current_font_bold 
            config ["filename_v_offset"]=self .filename_v_offset_spin .value ()
            config ["filename_h_offset"]=self .filename_h_offset_spin .value ()

            # addp8
            config ["effects"]={
            "crossfade":self .chk_crossfade .isChecked (),
            "slide":self .chk_slide .isChecked (),
            "zoom":self .chk_zoom .isChecked (),
            "wipe":self .chk_wipe .isChecked (),
            "fade_to_black":self .chk_fade_to_black .isChecked (),
            "grid": self.chk_grid.isChecked(),
            "shutter": self.chk_shutter.isChecked(),
            }
            config ["effect_order"]="random"if self .radio_effect_random .isChecked ()else "sequential"

            latest_data ["last_used_profile"]=self .current_profile 
            _save_profiles_data (latest_data )

            self .profiles =latest_data ["profiles"]

            self ._loaded_config =self ._get_current_ui_config ()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                tr("title_save_error"),
                tr("error_profile_save_failed").format(e=e)
            )

    def _on_profile_changed (self ,index ):
        if index >=0 :
            new_name =self .profile_combo .itemText (index )
            if new_name !=self .current_profile :
                self .current_profile =new_name 
                self ._load_current_profile ()

    def _has_unsaved_changes (self ):
        if not self .current_profile or self .current_profile not in self .profiles :
            return False 

        if not hasattr (self ,'_loaded_config')or not self ._loaded_config :
            return False 

        current_config =self ._get_current_ui_config ()
        return self ._loaded_config !=current_config 

    def _get_current_ui_config (self ):
        folders_list =[]
        for i in range (self .folder_list .count ()):
            item =self .folder_list .item (i )
            folder_path =item .text ()
            recursive =item .data (QtCore .Qt .UserRole )
            folders_list .append ((folder_path ,recursive if isinstance (recursive ,bool )else False ))

        v_text =self .combo_v_pos .currentText ()
        v_pos ="top"if v_text ==tr("pos_vertical_top")else "bottom"

        h_text =self .combo_h_pos .currentText ()
        if h_text ==tr("pos_horizontal_left"):
            h_pos ="left"
        elif h_text ==tr("pos_horizontal_right"):
            h_pos ="right"
        else :
            h_pos ="center"

        return {
        "folders":folders_list ,
        "monitor_index":self .monitor_combo .currentIndex (),
        "interval_sec":self .interval_spin .value (),
        "window_mode":"window"if self .radio_mode_window .isChecked ()else "fullscreen",
        "window_width":self .window_width_spin .value (),
        "window_height":self .window_height_spin .value (),
        "window_resizable":self .chk_window_resizable .isChecked (),
        "fade_duration_ms":int (self .fade_spin .value ()*1000 ),
        "random_order":self .radio_order_random .isChecked (),
        "ken_burns":self .chk_ken .isChecked (),
        "ken_burns_patterns": {
        "linear": self .chk_ken_linear .isChecked (),
        "arc": self .chk_ken_arc .isChecked (),
        "wave": self .chk_ken_wave .isChecked (),
        "spiral_in": self .chk_ken_spiral .isChecked (),
        "zigzag": self .chk_ken_zigzag .isChecked (),
        "edge_scan": self .chk_ken_edge_scan .isChecked ()},"ken_burns_order":"sequential"
        if self .radio_ken_order .isChecked () else "random",
        "ken_intensity":self .ken_intensity_slider .value (),
        "fit_mode":"cover"if self .radio_fit_cover .isChecked () else "contain",
        "stay_on_top":self .radio_front .isChecked (),
        "show_filename":self .chk_show_filename .isChecked (),
        "filename_v_pos":v_pos ,
        "filename_h_pos":h_pos ,
        "font_family":self .current_font_family ,
        "font_size":self .current_font_size ,
        "font_bold":self .current_font_bold ,
        "filename_v_offset":self .filename_v_offset_spin .value (),
        "filename_h_offset":self .filename_h_offset_spin .value (),
        # addp9
        "effects":{
        "crossfade":self .chk_crossfade .isChecked (),
        "slide":self .chk_slide .isChecked (),
        "zoom":self .chk_zoom .isChecked (),
        "wipe":self .chk_wipe .isChecked (),
        "fade_to_black":self .chk_fade_to_black .isChecked (),
        "grid": self.chk_grid.isChecked(),
        "shutter": self.chk_shutter.isChecked(),
        },
        "effect_order":"random"if self .radio_effect_random .isChecked ()else "sequential",
        }

    def _show_save_confirmation (self ,profile_name ):
        msg_box =QtWidgets .QMessageBox (self )
        msg_box.setWindowTitle(tr("title_confirm"))
        msg_box.setText(
            tr("msg_profile_unsaved_changes").format(
                profile=profile_name
            )
        )

        save_btn =msg_box .addButton (tr("btn_profile_save"),QtWidgets .QMessageBox .AcceptRole )
        discard_btn =msg_box .addButton (tr("btn_discard"),QtWidgets .QMessageBox .DestructiveRole )
        cancel_btn =msg_box .addButton (tr("btn_cancel"),QtWidgets .QMessageBox .RejectRole )

        msg_box .setDefaultButton (save_btn )
        msg_box .exec_ ()

        clicked_button =msg_box .clickedButton ()

        if clicked_button ==save_btn :
            return "save"
        elif clicked_button ==discard_btn :
            return "discard"
        else :
            return "cancel"

    def on_add_profile (self ):
        new_name ,ok =QtWidgets .QInputDialog .getText (self ,tr("dialog_new_profile"),tr("msg_enter_new_profile_name"))
        if ok and new_name :
            new_name =new_name .strip ()
            if not new_name :return 
            if new_name in self .profiles :
                QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_profile_exists"))
                return 

            source_config =self ._create_default_config ()

            self .profiles [new_name ]=source_config 
            self .current_profile =new_name 
            self ._save_profiles ()

            self ._load_profile_list ()
            self ._load_current_profile ()
            self .profile_combo .setCurrentText (new_name )

            self ._update_tray_menu ()

    def on_rename_profile (self ):
        if not self .current_profile :return 
        if self .current_profile =="Default":
            QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_default_profile_rename"))
            return 

        new_name ,ok =QtWidgets .QInputDialog .getText (
        self ,
        tr("dialog_profile_rename"),
        tr("msg_enter_new_profile_name_for").format(
            profile=self.current_profile
        ),
        QtWidgets .QLineEdit .Normal ,
        self .current_profile 
        )

        if ok and new_name and new_name .strip ()!=self .current_profile :
            new_name =new_name .strip ()
            if not new_name :
                QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_profile_name_empty"))
                return 

            if new_name in self .profiles :
                QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_profile_exists"))
                return 

            config =self .profiles [self .current_profile ]
            del self .profiles [self .current_profile ]
            self .profiles [new_name ]=config 

            self .current_profile =new_name 
            self ._save_profiles ()

            self ._load_profile_list ()
            self ._load_current_profile ()
            self .profile_combo .setCurrentText (new_name )

            self ._update_tray_menu ()

    def on_duplicate_profile (self ):
        if not self .current_profile or self .current_profile not in self .profiles :
            return 

        base_name =f"{self .current_profile }_copy"
        new_name =base_name 
        counter =1 

        while new_name in self .profiles :
            new_name =f"{base_name }_{counter }"
            counter +=1 

        new_name ,ok =QtWidgets .QInputDialog .getText (
        self ,
        tr("dialog_profile_duplicate"),
        tr("msg_enter_duplicate_profile_name_for").format(
            profile=self.current_profile
        ),
        QtWidgets .QLineEdit .Normal ,
        new_name 
        )

        if ok and new_name :
            new_name =new_name .strip ()
            if not new_name :
                QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_profile_name_empty"))
                return 

            if new_name in self .profiles :
                QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warn_profile_exists"))
                return 

            current_config =self ._get_current_ui_config ()

            import copy 
            self .profiles [new_name ]=copy .deepcopy (current_config )

            self .current_profile =new_name 
            self ._save_profiles ()

            self ._load_profile_list ()
            self .profile_combo .setCurrentText (new_name )

            self ._loaded_config =self ._get_current_ui_config ()

            QtWidgets .QMessageBox .information (
            self ,
            tr("msg_duplicate_done"),
            tr("msg_profile_created").format(
                profile=new_name
            )
            )

            self ._update_tray_menu ()

    def on_remove_profile(self):
        if not self.current_profile:
            return

        if self.current_profile == "Default":
            QtWidgets.QMessageBox.warning(
                self,
                tr("title_warning"),
                tr("warn_default_profile_delete")
            )
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            tr("title_confirm"),
            tr("msg_profile_delete_confirm").format(
                profile=self.current_profile
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            del self.profiles[self.current_profile]
            self.current_profile = "Default"
            self._save_profiles()
            self._load_profile_list()
            self._load_current_profile()
            self._update_tray_menu()

    def _on_create_shortcut (self ):
        if not self .current_profile :
            return 

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("dialog_shortcut_save_title").format(
                profile=self.current_profile
            ),
        f"Cinematic Slideshow - {self .current_profile }.lnk",
        tr("filetype_shortcut")
        )

        if file_path :
            try :
                self ._create_windows_shortcut (file_path )
                QtWidgets .QMessageBox .information (
                self ,
                tr("msg_shortcut_created_title"),
                tr("msg_shortcut_created").format(
                    profile=self.current_profile
                )
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    tr("title_error"),
                    tr("error_shortcut_creation").format(e=e)
                )

    def _create_windows_shortcut (self ,shortcut_path :str ):
        try :

            shell =win32com .client .Dispatch ("WScript.Shell")
            shortcut =shell .CreateShortCut (shortcut_path )

            if getattr (sys ,'frozen',False ):

                target_path =sys .executable 
                work_dir =os .path .dirname (sys .executable )
            else :

                target_path =sys .executable 
                work_dir =os .path .dirname (os .path .abspath (__file__ ))

            shortcut .TargetPath =target_path 
            shortcut .WorkingDirectory =work_dir 
            shortcut .Arguments =f'--profile "{self .current_profile }"'
            shortcut .Description =f"Cinematic Slideshow - {self .current_profile }"

            if getattr (sys ,'frozen',False ):
                shortcut .IconLocation =f"{sys .executable },0"

            shortcut .save ()

        except ImportError :

            self ._create_batch_shortcut_fallback (shortcut_path )
        except Exception as e:
            raise Exception(
                tr("error_shortcut_failed").format(e=e)
            )

    def _create_batch_shortcut_fallback (self ,shortcut_path :str ):

        batch_path =shortcut_path .replace ('.lnk','.bat')

        if getattr (sys ,'frozen',False ):
            exe_path =sys .executable 
            work_dir =os .path .dirname (exe_path )
        else :
            script_path =os .path .abspath (__file__ )
            exe_path =f'python "{script_path }"'
            work_dir =os .path .dirname (script_path )

        batch_content =f'''@echo off
    cd /d "{work_dir }"
    {exe_path } --profile "{self .current_profile }"
    '''

        with open (batch_path ,'w',encoding ='shift_jis')as f :
            f .write (batch_content )

        QtWidgets .QMessageBox .information (
        None ,
        tr("title_warning"),
        tr("msg_pywin32_missing").format(
            path=batch_path
        )
        )

    def _on_backup_profiles (self ):
        try :

            documents_path =os .path .expanduser ("~/Documents")

            from datetime import datetime 
            timestamp =datetime .now ().strftime ("%Y%m%d_%H%M%S")
            default_filename =f"CinematicSlideshow_Backup_{timestamp }.json"
            default_path =os .path .join (documents_path ,default_filename )

            file_path ,_ =QtWidgets .QFileDialog .getSaveFileName (
            self ,
            tr("dialog_backup_title"),
            default_path ,
            tr("filetype_json")
            )

            if file_path :

                self ._write_current_profile ()

                if os .path .exists (PROFILES_FILE ):
                    import shutil 
                    shutil .copy2 (PROFILES_FILE ,file_path )

                    QtWidgets .QMessageBox .information (
                    self ,
                    tr("msg_backup_done"),
                    tr("msg_backup_saved").format(
                        path=file_path
                    )
                    )
                else :
                    QtWidgets .QMessageBox .warning (
                    self ,
                    tr("title_error"),
                    tr("error_profile_file_not_found")
                    )

        except Exception as e :
            QtWidgets .QMessageBox .critical (
            self ,
            tr("dialog_backup_error_title"),
            tr("error_backup_failed").format(
                e=e
            )
            )

    def _on_restore_profiles (self ):
        try :

            documents_path =os .path .expanduser ("~/Documents")

            file_path ,_ =QtWidgets .QFileDialog .getOpenFileName (
            self ,
            tr("dialog_restore_title"),
            documents_path ,
            tr("filetype_json")
            )

            if file_path :

                reply =QtWidgets .QMessageBox .question (
                self ,
                tr("dialog_restore_confirm_title"),
                tr("msg_restore_confirm"),
                QtWidgets .QMessageBox .Yes |QtWidgets .QMessageBox .No ,
                QtWidgets .QMessageBox .No 
                )

                if reply ==QtWidgets .QMessageBox .Yes :

                    if self ._validate_backup_file (file_path ):

                        import shutil 
                        shutil .copy2 (file_path ,PROFILES_FILE )

                        self ._load_profiles ()

                        QtWidgets .QMessageBox .information (
                        self ,
                        tr("msg_restore_done_title"),
                        tr("msg_restore_done")
                        )
                    else :
                        QtWidgets .QMessageBox .warning (
                        self ,
                        tr("title_error"),
                        tr("error_invalid_backup_file")
                        )

        except Exception as e :
            QtWidgets .QMessageBox .critical (
            self ,
            tr("dialog_restore_error_title"),
            tr("error_restore_failed").format(
                e=e
            )
            )

    def _validate_backup_file (self ,file_path :str )->bool :
        try :
            with open (file_path ,'r',encoding ='utf-8')as f :
                data =json .load (f )

            if not isinstance (data ,dict ):
                return False 
            if "profiles"not in data :
                return False 
            if not isinstance (data ["profiles"],dict ):
                return False 

            if len (data ["profiles"])==0 :
                return False 

            for profile_name ,profile_data in data ["profiles"].items ():
                if not isinstance (profile_data ,dict ):
                    return False 

                required_keys =["folders","monitor_index","interval_sec"]
                for key in required_keys :
                    if key not in profile_data :
                        return False 

            return True 

        except Exception as e :
            print (f"Backup validation error: {e }")
            return False 

    def _on_add_folder (self ):
        folder_path =QtWidgets .QFileDialog .getExistingDirectory (self ,tr("dialog_folder_select"))
        if folder_path :

            for i in range (self .folder_list .count ()):
                if os .path .normpath (self .folder_list .item (i ).text ())==os .path .normpath (folder_path ):
                    QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warning_folder_duplicate"))
                    return 

            item =QtWidgets .QListWidgetItem (folder_path )

            item .setData (QtCore .Qt .UserRole ,True )
            item .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_DirIcon ))
            self .folder_list .addItem (item )

            self .folder_list .setCurrentItem (item )

    def _on_remove_folder (self ):
        current_row =self .folder_list .currentRow ()
        if current_row >=0 :
            self .folder_list .takeItem (current_row )

            if self .folder_list .count ()==0 :
                self .chk_recursive .setEnabled (False )

    def _on_list_selection_changed (self ):
        item =self .folder_list .currentItem ()
        if item :
            recursive =item .data (QtCore .Qt .UserRole )
            self .chk_recursive .blockSignals (True )

            self .chk_recursive .setChecked (recursive if isinstance (recursive ,bool )else True )
            self .chk_recursive .blockSignals (False )
            self .chk_recursive .setEnabled (True )
        else :
            self .chk_recursive .setEnabled (False )

    def _on_recursive_changed (self ):
        item =self .folder_list .currentItem ()
        if item :
            new_recursive =self .chk_recursive .isChecked ()
            item .setData (QtCore .Qt .UserRole ,new_recursive )

    def _on_select_font (self ):
        current_font =QtGui .QFont (self .current_font_family ,self .current_font_size )
        if self .current_font_bold :
            current_font .setBold (True )

        font ,ok =QtWidgets .QFontDialog .getFont (current_font ,self ,tr("dialog_font_select"))

        if ok :
            self .current_font_family =font .family ()
            self .current_font_size =font .pointSize ()
            self .current_font_bold =font .bold ()

            bold_text =tr("font_bold_label")if self .current_font_bold else tr("font_regular_label")
            self .font_label .setText (f"{self .current_font_family }, {self .current_font_size }pt, {bold_text }")

    def _on_slideshow_settings_requested (self ,profile_name :str ):
        print(f"Opening settings: slideshow profile='{profile_name}', settings profile='{self.current_profile}'")

        self ._original_profile =profile_name 

        if profile_name !=self .current_profile :
            self .current_profile =profile_name 
            self .profile_combo .blockSignals (True )
            self .profile_combo .setCurrentText (profile_name )
            self .profile_combo .blockSignals (False )
            self ._load_current_profile ()

        self ._loaded_config =self ._get_current_ui_config ()

        self ._initial_config =self ._get_current_ui_config ()
        self ._initial_profile =profile_name 

        self .setWindowFlags (self .windowFlags ()|QtCore .Qt .WindowStaysOnTopHint )
        self .show ()
        self .raise_ ()
        self .activateWindow ()

    def start_slideshow (self ):
        self ._write_current_profile ()
        config =self .profiles .get (self .current_profile )
        if not config :
            QtWidgets .QMessageBox .critical (self ,tr("title_error"),tr("error_profile_not_loaded"))
            return 

        image_files =[]
        folders =config .get ("folders",[])

        for idx ,item in enumerate (folders ):
            if isinstance (item ,(list ,tuple ))and len (item )==2 :
                folder_path ,recursive =item 
            elif isinstance (item ,str ):
                folder_path ,recursive =item ,False 
            else :
                continue 

            if os .path .isdir (folder_path ):
                try :
                    image_files .extend (list_images (folder_path ,recursive ))
                except Exception as e :
                    QtWidgets.QMessageBox.critical(
                    self,
                    tr("title_error"),
                    tr("error_image_list_failed").format(
                        folder=folder_path,
                        e=e
                    )
                )
                    return 

        if not image_files :
            QtWidgets .QMessageBox .warning (self ,tr("title_warning"),tr("warning_no_images_found"))
            return 

        if self .slideshow_window and self .slideshow_window .isVisible ():
            self .slideshow_window .close ()

        try :
            self .hide ()
            # addp10
            effects ={
            "crossfade":self .chk_crossfade .isChecked (),
            "slide":self .chk_slide .isChecked (),
            "zoom":self .chk_zoom .isChecked (),
            "wipe":self .chk_wipe .isChecked (),
            "fade_to_black":self .chk_fade_to_black .isChecked (),
            "grid": self.chk_grid.isChecked(),
            "shutter": self.chk_shutter.isChecked(),
            }
            effect_order ="random"if self .radio_effect_random .isChecked ()else "sequential"
            self .slideshow_window =SlideShowWindow (
            image_files =image_files ,
            current_profile_name =self .current_profile ,
            monitor_index =config .get ("monitor_index",0 ),
            stay_on_top =config .get ("stay_on_top",True ),
            interval_sec =config .get ("interval_sec",5 ),
            ken_burns =config .get ("ken_burns",True ),
            ken_intensity =config .get ("ken_intensity",5 ),
            ken_burns_patterns =config .get ("ken_burns_patterns",
            {
            "linear":True ,
            "arc":True ,
            "wave":True ,
            "spiral_in":True ,
            "zigzag":True ,
            "edge_scan":False ,
            }),
            ken_burns_order =config .get ("ken_burns_order","random"),
            random_order =config .get ("random_order",True ),
            fit_mode =config .get ("fit_mode","cover"),
            fade_duration_ms =config .get ("fade_duration_ms",1000 ),
            show_filename =config .get ("show_filename",False ),
            filename_v_pos =config .get ("filename_v_pos","bottom"),
            filename_h_pos =config .get ("filename_h_pos","center"),
            font_family =config .get ("font_family",self .DEFAULT_FONT_FAMILY ),
            font_size =config .get ("font_size",self .DEFAULT_FONT_SIZE ),
            font_bold =config .get ("font_bold",self .DEFAULT_FONT_BOLD ),
            filename_v_offset =config .get ("filename_v_offset",0 ),
            filename_h_offset =config .get ("filename_h_offset",0 ),
            effects =effects ,
            effect_order =effect_order ,
            main_window =self ,
            window_mode =config .get ("window_mode","fullscreen"),
            window_width =config .get ("window_width",1280 ),
            window_height =config .get ("window_height",768 ),
            window_resizable =config .get ("window_resizable",True ),
            )

            self .slideshow_window .showSettingsRequested .connect (self ._on_slideshow_settings_requested )

            self .slideshow_window .show ()
            if hasattr (self ,'pause_action'):
                self .pause_action .setEnabled (True )

        except NameError :
            QtWidgets .QMessageBox .critical (self ,tr("title_error"),tr("error_slideshow_window_missing"))
            self .slideshow_window =None 
        except Exception as e :
            QtWidgets.QMessageBox.critical(
                self,
                tr("title_error"),
                tr("error_slideshow_start_failed").format(
                    e=e
                )
            )
            self .slideshow_window =None 

    def _setup_system_tray (self ):

        if not QtWidgets .QSystemTrayIcon .isSystemTrayAvailable ():
            QtWidgets .QMessageBox .critical (
            None ,
            tr("tray_system"),
            tr("tray_not_available")
            )
            return 

        self .tray_icon =QtWidgets .QSystemTrayIcon (self )

        if not self .windowIcon ().isNull ():
            self .tray_icon .setIcon (self .windowIcon ())
        else :

            icon =self .style ().standardIcon (QtWidgets .QStyle .SP_ComputerIcon )
            self .tray_icon .setIcon (icon )

        self .tray_icon .setToolTip (f"Cinematic Slideshow - {self .current_profile }")

        self ._create_tray_menu ()

        self .tray_icon .activated .connect (self ._on_tray_activated )

        self .tray_icon .show ()

    def _create_tray_menu (self ):
        tray_menu =QtWidgets .QMenu ()

        profile_menu =tray_menu .addMenu (tr("tray_profile_switch"))
        profile_menu .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_FileDialogDetailedView ))

        self .profile_actions =[]
        for profile_name in sorted (self .profiles .keys ()):
            action =profile_menu .addAction (profile_name )
            action .setCheckable (True )
            action .setChecked (profile_name ==self .current_profile )
            action .triggered .connect (lambda checked ,name =profile_name :self ._switch_profile_and_restart (name ))
            self .profile_actions .append (action )

        tray_menu .addSeparator ()

        self .pause_action =tray_menu .addAction (tr("tray_pause_resume"))
        self .pause_action .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_MediaPause ))
        self .pause_action .triggered .connect (self ._toggle_pause_from_tray )
        self .pause_action .setEnabled (False )

        tray_menu .addSeparator ()

        settings_action =tray_menu .addAction (tr("menu_settings"))
        settings_action .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_FileDialogDetailedView ))
        settings_action .triggered .connect (self ._show_settings_from_tray )

        about_action =tray_menu .addAction (tr("menu_about"))
        about_action .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_MessageBoxInformation ))
        about_action .triggered .connect (self ._show_about_dialog )

        tray_menu .addSeparator ()

        quit_action =tray_menu .addAction (tr("tray_exit"))
        quit_action .setIcon (self .style ().standardIcon (QtWidgets .QStyle .SP_DialogCloseButton ))
        quit_action .triggered .connect (self ._quit_application )

        self .tray_icon .setContextMenu (tray_menu )

    def _on_tray_activated (self ,reason ):
        if reason ==QtWidgets .QSystemTrayIcon .DoubleClick :
            self ._show_settings_from_tray ()

    def _switch_profile_and_restart (self ,profile_name :str ):
        if profile_name ==self .current_profile :
            return 
        self .current_profile =profile_name 
        self .profile_combo .setCurrentText (profile_name )
        self ._load_current_profile ()
        try :
            if os .path .exists (PROFILES_FILE ):
                with open (PROFILES_FILE ,'r',encoding ='utf-8')as f :
                    data =json .load (f )

                data ["last_used_profile"]=profile_name 

                with open (PROFILES_FILE ,'w',encoding ='utf-8')as f :
                    json .dump (data ,f ,ensure_ascii =False ,indent =4 )
        except Exception as e :
            print (f"Profile save error: {e }")

        if hasattr (self ,'slideshow_window')and self .slideshow_window :
            self ._restart_slideshow ()

        for action in self .profile_actions :
            action .setChecked (action .text ()==profile_name )

    def _update_tray_menu (self ):
        if hasattr (self ,'tray_icon')and self .tray_icon :

            self .tray_icon .setContextMenu (None )

            self ._create_tray_menu ()

    def _toggle_pause_from_tray (self ):
        if hasattr (self ,'slideshow_window')and self .slideshow_window :
            self .slideshow_window ._toggle_pause ()

    def _show_settings_from_tray (self ):
        if hasattr (self ,'slideshow_window')and self .slideshow_window :

            self ._on_slideshow_settings_requested (self .current_profile )
        else :
            self .show ()
            self .raise_ ()
            self .activateWindow ()

    def _quit_application (self ):
        if hasattr (self ,'slideshow_window')and self .slideshow_window :
            self .slideshow_window .close ()
        if hasattr (self ,'tray_icon'):
            self .tray_icon .hide ()
        QtWidgets .QApplication .quit ()

def start_slideshow_direct (profile_name :str ,profile_data :Dict [str ,Any ]):
    app =QtWidgets .QApplication .instance ()
    if app is None :
        app =QtWidgets .QApplication (sys .argv )

    main_window =MainWindow ()
    main_window .hide ()

    main_window .current_profile =profile_name 
    if profile_name not in main_window .profiles :
        main_window .profiles [profile_name ]=profile_data 
    main_window .profile_combo .setCurrentText (profile_name )

    main_window ._load_profile_list ()
    main_window .profile_combo .setCurrentText (profile_name )
    main_window ._load_current_profile ()

    folders_with_recursive =profile_data .get ("folders",[])
    all_images =[]

    for item in folders_with_recursive :
        if isinstance (item ,(list ,tuple ))and len (item )==2 :
            folder_path ,recursive_flag =item 
            if os .path .isdir (folder_path ):
                all_images .extend (list_images (folder_path ,recursive =recursive_flag ))
        elif isinstance (item ,str )and os .path .isdir (item ):
            all_images .extend (list_images (item ,recursive =False ))

    if not all_images :
        print (tr("log_no_images_show_window"))
    else :
        print(f"{len(all_images)} images found.")

    monitor_index =profile_data .get ("monitor_index",0 )
    interval_sec =profile_data .get ("interval_sec",5 )
    ken_burns =profile_data .get ("ken_burns",True )
    ken_intensity =profile_data .get ("ken_intensity",5 )
    random_order =profile_data .get ("random_order",True )
    fit_mode =profile_data .get ("fit_mode","cover")
    fade_duration_ms =profile_data .get ("fade_duration_ms",1000 )
    stay_on_top =profile_data .get ("stay_on_top",True )
    show_filename =profile_data .get ("show_filename",False )
    filename_v_pos =profile_data .get ("filename_v_pos","bottom")
    filename_h_pos =profile_data .get ("filename_h_pos","center")
    font_family =profile_data .get ("font_family",MainWindow .DEFAULT_FONT_FAMILY )
    font_size =profile_data .get ("font_size",MainWindow .DEFAULT_FONT_SIZE )
    font_bold =profile_data .get ("font_bold",MainWindow .DEFAULT_FONT_BOLD )
    filename_v_offset =profile_data .get ("filename_v_offset",0 )
    filename_h_offset =profile_data .get ("filename_h_offset",0 )
    effects =profile_data .get ("effects",{"crossfade":True })
    effect_order =profile_data .get ("effect_order","random")
    window_mode =profile_data .get ("window_mode","fullscreen")
    window_width =profile_data .get ("window_width",1280 )
    window_height =profile_data .get ("window_height",768 )
    window_resizable =profile_data .get ("window_resizable",True )
    ken_burns_patterns =profile_data .get ("ken_burns_patterns",
    {
    "linear":True ,
    "arc":True ,
    "wave":True ,
    "spiral_in":True ,
    "zigzag":True ,
    "edge_scan":False ,
    }
    )
    ken_burns_order =profile_data .get ("ken_burns_order","random")

    try :
        slideshow_win =SlideShowWindow (
        image_files = all_images,
        current_profile_name = profile_name,
        monitor_index = monitor_index,
        stay_on_top = stay_on_top,
        interval_sec = interval_sec,
        ken_burns = ken_burns,
        ken_intensity = ken_intensity,
        ken_burns_patterns = ken_burns_patterns,
        ken_burns_order = ken_burns_order,
        random_order = random_order,
        fit_mode =fit_mode,
        fade_duration_ms = fade_duration_ms,
        show_filename = show_filename,
        filename_v_pos = filename_v_pos,
        filename_h_pos = filename_h_pos,
        font_family = font_family,
        font_size = font_size,
        filename_v_offset = filename_v_offset,
        filename_h_offset = filename_h_offset,
        effects = effects,
        effect_order = effect_order,
        window_mode = window_mode,
        window_width = window_width,
        window_height = window_height,
        window_resizable = window_resizable,
        main_window = main_window 
        )

        main_window .slideshow_window =slideshow_win 

        slideshow_win .showSettingsRequested .connect (main_window ._on_slideshow_settings_requested )

        if hasattr (main_window ,'pause_action'):
            main_window .pause_action .setEnabled (True )

        def on_slideshow_closed ():
            if hasattr (main_window ,'pause_action'):
                main_window .pause_action .setEnabled (False )

            try :
                if main_window and hasattr (main_window ,'isVisible'):
                    if main_window .isVisible ():
                        pass 
                    else :
                        app .quit ()
                else :
                    app .quit ()
            except RuntimeError :
                app .quit ()

        slideshow_win .destroyed .connect (on_slideshow_closed )

        slideshow_win .show ()
        sys .exit (app .exec_ ())

    except Exception as e :
        QtWidgets.QMessageBox.critical(
            None,
            tr("title_error"),
            tr("error_slideshow_start_failed").format(
                e=e
            )
        )
        main_window .show ()
        sys .exit (app .exec_ ())

if __name__ =='__main__':

    QtCore .QCoreApplication .setAttribute (QtCore .Qt .AA_EnableHighDpiScaling ,True )
    QtCore .QCoreApplication .setAttribute (QtCore .Qt .AA_UseHighDpiPixmaps ,True )

    app =QtWidgets .QApplication .instance ()
    if app is None :
        app =QtWidgets .QApplication (sys .argv )
        app .setApplicationName ("Cinematic Slideshow")
        app .setOrganizationName ("sitarj")

    def handle_exception (exc_type ,exc_value ,exc_traceback ):
        if issubclass (exc_type ,KeyboardInterrupt ):
            sys .__excepthook__ (exc_type ,exc_value ,exc_traceback )
            return 
        print (f"Uncaught exception: {exc_type .__name__ }: {exc_value }")

    sys .excepthook =handle_exception 

    try :
        profiles_data =load_profiles ()

        if len (sys .argv )>1 :
            if sys .argv [1 ]=="--settings"or sys .argv [1 ]=="-s":

                main_window =MainWindow ()
                main_window .show ()
                sys .exit (app .exec_ ())
            elif sys .argv [1 ]=="--profile"or sys .argv [1 ]=="-p":

                if len (sys .argv )>2 :
                    target_profile_name =sys .argv [2 ]
                    if target_profile_name in profiles_data .get ("profiles",{}):
                        profile_name =target_profile_name 
                    else :
                        print(f"Error: profile '{target_profile_name}' not found")
                        profile_name =profiles_data .get ("last_used_profile","Default")
                else :
                    print (tr("error_profile_name_missing"))
                    profile_name =profiles_data .get ("last_used_profile","Default")
            else :

                target_profile_name =sys .argv [1 ]
                if target_profile_name in profiles_data .get ("profiles",{}):
                    profile_name =target_profile_name 
                else :
                    print(f"Error: profile '{target_profile_name}' not found")
                    profile_name =profiles_data .get ("last_used_profile","Default")
        else :
            profile_name =profiles_data .get ("last_used_profile","Default")
            if profile_name not in profiles_data .get ("profiles",{}):
                profile_name ="Default"

        print(f"Starting slideshow with profile '{profile_name}'")

        start_slideshow_direct (profile_name ,profiles_data ["profiles"][profile_name ])

    except Exception as e :
        print(f"Startup error: {e}")
        sys .exit (1 )
