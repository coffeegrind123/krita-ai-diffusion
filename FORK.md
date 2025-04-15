# Random Artists and Tags Fork

![Screenshot of the plugin](Screenshot.png)
![Screenshot of the plugin](Screenshot2.png)

## Features

- **Random Artists Button** pulls from two databases:
  - e621_artist_webui.csv
  - danbooru_artist_webui.csv
- **Random Tags Button** fetches tags from random posts
- **Settings Menu** with categories filter and tag exclusion
- **Favorite Artists** dropdown
- **Solo-Only** checkbox for filtering

## Installation

### Arch Linux

1. **Install dependencies**
   - python-pyqt5 needed for Tools -> Scripts menu to show up
   ```bash
   sudo pacman -S python-pyqt5 krita
   ```

3. **Install main plugin**
   - Run Krita
   - Go to: Tools → Scripts → Import plugin from web
   - Enter: `https://github.com/Acly/krita-ai-diffusion/download/v1.33.0/krita_ai_diffusion-1.33.0.zip`
   - Click Yes and close Krita

4. **Install this fork**
   - Extract krita_ai_diffusion-random-tags-and-artists.zip to `~/.local/share/krita`
   - Open and close Krita once

5. **Setup canvas**
   - Create new image (Ctrl+N)
   - Select dimensions: 1216×832 or 832×1216

6. **Switch workspace**
   - Go to: Window → Workspace → diffusion

### Windows

1. **Install main plugin**
   - Open Krita
   - Go to: Tools → Scripts → Import Plugin from Web
   - Enter: `https://github.com/Acly/krita-ai-diffusion/download/v1.33.0/krita_ai_diffusion-1.33.0.zip`
   - Click Yes and close Krita

2. **Install this fork**
   - Extract release zip to `%appdata%\krita`

3. **Setup as above**
   - Follow steps 4-5 from Arch Linux section

## Usage

The plugin adds these features to the interface:

- **Random Artist**: Select from database
- **Random Tags**: Fetch from posts
- **Settings**: Configure filters
- **Favorites**: Quick artist access
- **Solo Only**: Filter for solo posts
