# Cinematic_Slideshow
- A slideshow application with cinematic effects

### New Features
- English language support
- Windowed mode

### Installation
- It operates as a standalone application（スタンドアローンで動作します）

### Usage（使い方）
#### Basic Usage（基本的な使い方）
- Launch the Application（アプリケーションを起動）
- Add a folder containing images using "Image Folder"（「画像フォルダ」で画像が保存されているフォルダを追加）
- Start the slideshow with the "OK" button（「OK」ボタンでスライドショー開始）

#### Profile Function（プロファイル機能）
- Save multiple settings as "profiles"（複数の設定を「プロファイル」として保存可能）
- Switch between settings depending on your needs（用途に応じて設定を切り替え）

#### Create Shortcuts（ショートカット作成）
- Create a Windows shortcut that launches with a specific profile（特定のプロファイルで起動するWindowsショートカットを作成可能）
- Use the --setting argument to access the settings screen（引数を--settingにすれば、設定画面を呼び出し）

#### Settings（設定項目）
- Display settings: Full screen / Window（表示設定: 全画面 / ウインドウ）
- Ken Burns Effect: Cinematic pan-and-zoom effect（Ken Burns効果: 映画的なパン＆ズーム効果）
- Transition Effect: Image transition effect（切替エフェクト: 画像間の切り替え演出）
- Display Method: Pan-and-Scan / Letterbox（表示方法: パン＆スキャン / レターボックス）
- Display Time: Display time for each image (1-60 seconds)（表示時間: 各画像の表示時間（1-60秒））
- File Name Display: Set the image file name display（ファイル名表示: 画像ファイル名の表示設定）
- Language: English / Japanese（日本語）

### Controls（操作方法）
#### Keyboard（キーボード）
- Space: Pause（一時停止）/Resume（再開）
- Esc: Exit（終了）

#### Mouse（マウス）
- Right-click（右クリック）: Display context menu（コンテキストメニュー表示）

### Supported Formats（対応フォーマット）
#### Native Support（ネイティブ対応）
- JPEG, PNG, BMP, GIF, WebP, TIFF, ICO, SVG

#### Extended support (requires pillow-avif-plugin)（拡張対応（pillow-avif-plugin必要））
-  AVIF, HEIC, HEIF, JPEG2000

### Known Issues（既知の問題）
- Black bars may temporarily appear when using the Ken Burns effect.（Ken Burns効果中に一時的に黒帯が表示される場合があります）
- It works reliably even with large numbers of images, but the initial load may take a long time.（大量の画像でも安定動作しますが、初回読み込み時に時間がかかる場合があります）
- In multi-monitor environments with different scaling settings, proper scaling may not be achieved.（スケーリングの異なるマルチモニター環境で、適切なスケーリングが得られない場合があります）

### License（ライセンス）
- GPL v3 License - See the LICENSE file for details.（詳細はLICENSEファイルを参照）

### Author（作者）
- sitarj
