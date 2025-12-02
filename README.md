# Cinematic_Slideshow
A slideshow application with cinematic effects

The English version of the application will be available soon.

使い方

基本的な使い方

    アプリケーションを起動
    「画像フォルダ」で画像が保存されているフォルダを追加
    「OK」ボタンでスライドショー開始

プロファイル機能

    複数の設定を「プロファイル」として保存可能
    用途に応じて設定を切り替え

ショートカット作成

    特定のプロファイルで起動するWindowsショートカットを作成可能
    引数を--settingにすれば、設定画面を呼び出し

設定項目

    表示時間: 各画像の表示時間（1-60秒）
    Ken Burns効果: 映画的なパン＆ズーム効果
    切替エフェクト: 画像間の切り替え演出
    表示方法: パン＆スキャン / レターボックス
    ファイル名表示: 画像ファイル名の表示設定

操作方法
キーボード

    Space: 一時停止/再開
    Esc: 終了

マウス

    右クリック: コンテキストメニュー表示

対応フォーマット
ネイティブ対応

    JPEG, PNG, BMP, GIF, WebP, TIFF, ICO, SVG

拡張対応（pillow-avif-plugin必要）

    AVIF, HEIC, HEIF, JPEG2000

既知の問題

    Ken Burns効果中に一時的に黒帯が表示される場合があります
    大量の画像でも安定動作しますが、初回読み込み時に時間がかかる場合があります

ライセンス

    GPL v3 License - 詳細はLICENSEファイルを参照

作者

    sitarj

-----------------------------------------

How to Use

Basic Usage

    Launch the Application
    Add a folder containing images using "Image Folder"
    Start the slideshow with the "OK" button

Profile Function

    Save multiple settings as "profiles"
    Switch between settings depending on your needs

Create Shortcuts

    Create a Windows shortcut that launches with a specific profile
    Use the --setting argument to access the settings screen

Settings

    Display Time: Display time for each image (1-60 seconds)
    Ken Burns Effect: Cinematic pan-and-zoom effect
    Transition Effect: Image transition effect
    Display Method: Pan-and-Scan / Letterbox
    File Name Display: Set the image file name display

Controls
Keyboard

    Space: Pause/Resume
    Esc: Exit

Mouse

    Right-click: Display context menu

Supported Formats
Native Support

    JPEG, PNG, BMP, GIF, WebP, TIFF, ICO, SVG

Extended support (requires pillow-avif-plugin)

    AVIF, HEIC, HEIF, JPEG2000

Known Issues

    Black bars may temporarily appear when using the Ken Burns effect.
    
    It works reliably even with large numbers of images, but the initial load may take a long time.

License

    GPL v3 License - See the LICENSE file for details.

Author

    sitarj
