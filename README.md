# PhotoPainter Cropper & Converter

Interactive image cropper and converter for the **Waveshare PhotoPainter**7.3" ACeP (A) and Spectra6 (B) version.

The **PhotoPainter Cropper & Converter** helps you to frame the primary subject of each photo within a specified folder, applying a given target size mainly for the mentioned device above with 800×480 or any other user-defined target size. The crop rectangle can extend beyond the original image boundaries, and any resulting empty areas are automatically filled with either *white space* or a *blurred background* derived from the image itself.

This project is an enhanced (much improved for my own needs) version of an image crop & convert application based on the idea from [@geegeek](https://github.com/geegeek)/[photopainter-cropper](https://github.com/geegeek/photopainter-cropper). It eases the workflow to convert photos into a format that the Waveshare PhotoPainter can handle. It works on MacOS, Windows and Linux which has Python3 installed.

## Key Features

- Supported image types: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`, `.heic`*
- Load image by **EXIF** orientation
- Fixed **800x480** (landscape) or **480x800** (portrait) crop ratio
  — You can set the output dimensions via `image_target_size` in `settings.ini`
- **ACeP** or **Spectra6** optimized output
- **Image enhancements** — Brightness, Contrast, Saturation, Edge, Smooth, Sharpen
- Crop rectangle can **exceed image bounds** and empty areas will be filled with **White** or **Blur** background
- **Per-image state**
  — A `*_ppcrop.txt` sidecar file (configurable via the `state_suffix` parameter in `settings.ini`) is saved alongside each original image to persist all per-image settings allowing the application to automatically restore the exact crop rectangle and settings on subsequent runs
- App and some image **properties configuration** via `settings.ini` file (see **Settings** section)
- Crisp **crop area grid lines** aligned to device pixels
- (optional) **Generate fileList.txt** on app exit
  — useful for original Mode 2 or custom firmware which uses this file to retrieve image list

\* HEIC support needs `pillow-heif` installed alongside `Pillow`. If you're following the **Install & Run** section below you should be all set.

## How it works

A sample image:

![sample/sample.jpg](sample/sample.jpg)

...cropped beyond the border:

![screenshot/001_chooseFrameVerticalPicture.jpg](screenshot/001_chooseFrameVerticalPicture.jpg)

...becomes this image as JPG:

![sample/cropped_landscape/sample.jpg](sample/cropped_landscape/sample.jpg)

...converts to a dithered BMP:

![sample/cropped_landscape/dithered/sample.bmp](sample/cropped_landscape/dithered/sample.bmp)

...and finally maps to a device specific color palette (Waveshare PhotoPainter Pico ACeP 7-color) which looks much punchier on your computer screen:

![sample/cropped_landscape/dithered/pic_acep/sample.bmp](sample/cropped_landscape/dithered/pic_acep/sample.bmp)

...but much right when displayed on the PhotoPainter e-Paper device itself:

![screenshot/002_PhotoPainterRealWorld.jpg](screenshot/002_PhotoPainterRealWorld.jpg)

## How to use

1. **Start the app** and select the folder with the images you want to convert.

2. Use **mouse/keyboard** to position and size the crop rectangle.

   - **Mouse**:
     - Drag to move
     - Scroll to resize (hold **Shift** = faster)
   - **Keyboard**:
     - Arrows = move (hold **Shift** = faster)
     - `+` / `-` = resize (hold **Shift** = faster)
     - **O** = toggle orientation (Landscape ↔ Portrait)
     - **F** = toggle fill (White ↔ Blur)
     - **D** = toggle device (ACeP ↔ Spectra6)
     - **ESC** = skip current image
     - **PAGE_UP** = previous image without processing current image
     - **PAGE_DOWN** = next image without processing current image
     - **Enter** or **S** = process & save current image and go to next

   Optionally apply some **image optimizations** if you you want.

3. Use **Enter** or **S** to crop and convert the image.

   - **Cropped JPGs** are saved to `cropped_[landscape|portrait]` next to your originals
   - **Converted BMP** images are saved to `cropped_[landscape|portrait]/dithered` next to your originals
   - **Converted Real-color BMP** images are saved to `cropped_[landscape|portrait]/dithered/pic_[acep|spectra6]` next to your originals

   The folders can be set via the `settings.ini`. See **Settings** section.

4. **Copy** the converted images from `cropped_[landscape|portrait]/dithered/pic_[acep|spectra6]` to your SD card's `pic` folder.

## Why all these convert steps?

This app does the following:

1. **Scale and Crop**
   — The app exports the marked area to **JPG 800×480** (landscape) or **480x800** (portrait). The output dimensions can be set in `settings.ini`. Orientation will be set per image in the app.
2. **Convert JPG → 24-bit BMP**
   — The image will be dithered with the Floyd-Steinberg dithering algorithm.
3. **Map 24-bit BMP → Real world ePaper Screen colors**
   — For the final 24-bit BMP device format, it uses part of a Gist by **@quark-zju** with color maps from [epdoptimize](https://github.com/Utzel-Butzel/epdoptimize). It provides way better color/tonal results on the 6- and 7-color panels than a plain BMP export by the original Waveshare converter.

Using the direct BMP export of the original Waveshare converter that follows the device format by using the suggested 6-/7-color palette is rendering the images to look a bit **flat** on the device, somehow like a "vintage" filter. This app applies **dithering** and (kind of) **device calibrated color mapping**. The result **looks way better** on the PhotoPainter device than the export of the original Waveshare converter.

## Samples and Outputs included

- Example **input** photo and **outputs** from this tool (JPG 800×480) are available in `sample` folder.
- For convenience, this repository also includes a **BMP file** in `sample/cropped_landscape/dithered/pic_acep` folder created with this converter, so you can copy it directly to the device.

## Settings (`settings.ini`)

*"With great power comes great responsibility."*

If it's not existing, the `settings.ini` file will be automatically created the first time after closing the app properly. The next time closing the app, this file will be updated.

Available settings and their defaults:

```ini
# PhotoPainter app state
window_min=1024x768        # minimum size of window
last_window_size=1024x768  # last window dimensions
image_target_size=800x480  # exact JPG output image dimensions
image_quality=90           # quality of the JPG output
orientation=landscape      # landscape, portrait
fill_mode=blur             # blur, white
target_device=acep         # acep, spectra6
enhancer_edge=False        # default for Edge enhancer
enhancer_smooth=False      # default for Smooth enhancer
enhancer_sharpen=False     # default for Sharpen enhancer
grid_color=#00ff00         # rectangle border color
export_folder=cropped      # folder where to store cropped images
convert_folder=dithered    # folder where to store converted/dithered images
raw_folder=raw             # folder where to store raw images
pic_folder_on_device=pic   # first part of the folder for final image
state_suffix=_ppcrop.txt   # file extension for sidecar file
export_raw=False           # should export raw image suitable for direct use?
save_filelist=True         # save fileList.txt at app exit for both orientations
exit_after_last_image=True # exit app after last image was processed
```

## Device SD Card layout

- Create a folder named `pic` at the **root** of the SD card.
- Copy all **24-bit BMP** files from your desired target device folder (e.g. `pic_acep`) into the `pic` folder.
- Stock firmware expects fewer than ~100 images in `pic` folder.
- I personally use a **custom firmware** for my 7-color ACeP version, a mix of the official Waveshare firmware with improvements from @myevit made for the Spectra6 firmware which supports nearly **unlimited photos** in theory. Practically it has *"a reasonable limit to prevent memory issues"* of **100.000** photos on the SD Card.

## Install & Run

Clone repo:

```bash
git clone https://github.com/one-step-behind/photopainter-cropper-converter.git
```

### MacOS

Use the **official** Python for macOS (includes Tkinter).

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv ~/ppainter-venv
source ~/ppainter-venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

```bash
source ~/ppainter-venv/bin/activate
python photo_painter_cropper.py
```

### Windows

Virtual environment & installing requirements:

```bash
cd photopainter-cropper-converter
# create virtual environment for project (also creates folder by name)
python -m venv .venv
# install and update PIP
python -m pip install --upgrade pip
# activate venv and install requirements
.\.venv\Scripts\activate
# it now says:
# (.venv) PS path\to\photopainter-cropper-converter>
# install requirements
python -m pip install -r requirements.txt
```

Run script:

```bash
# run script
python photo_painter_cropper.py

# VSCode
1. `Ctrl+Shift+P`
2. enter "Python: Select Interpreter"
3. select ".\.venv\Scripts\python.exe"
4. click Run button to run the script
```

You can create a standalone executable with pyinstaller:

```bash
# build executable first time and auto-generate `.spec` file
pyinstaller --onefile --windowed -i='.\_source\icon.ico' --add-data "_source/icon.ico;_source" --name "PhotoPainterCropper" ".\photo_painter_cropper.py"
# later you can run compilation with just:
pyinstaller PhotoPainterCropper.spec
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
# if module tkinter not found, install python tk
(optional) sudo apt-get install python3-tk
# run script
python photo_painter_cropper.py
```

Quit virtual env:

```bash
# quit venv
deactivate
```

## Project Type (GitHub Topics)

Desktop GUI **application** (Tkinter) for macOS, Windows and Linux. Suggested topics:
`app`, `desktop`, `gui`, `tkinter`, `pillow`, `macos`, `windows`, `image-processing`, `waveshare`, `photopainter`, `e-paper`, `acep`, `spectra6`, `cropper`, `converter`.

## References

- Waveshare [PhotoPainter wiki](https://www.waveshare.com/wiki/PhotoPainter) (specs, formats, conversion tools)
- **Official JPEG→BMP converter** [@waveshareteam](https://github.com/waveshareteam)/[PhotoPainter_B](https://github.com/waveshareteam/PhotoPainter_B)
- **UI/App** forked from [@geegeek](https://github.com/geegeek)/[photopainter-cropper](https://github.com/geegeek/photopainter-cropper)
- inspired by the image processor Gist from [@quark-zju](https://gist.github.com/quark-zju)/[epd-dither-resize-spectra6.py](https://gist.github.com/quark-zju/e488eb206ba66925dc23692170ba49f9) which is a fork of Waveshare's original ConverTo6c_bmp-7.3 converter
- Usage of [device color palettes](https://github.com/Utzel-Butzel/epdoptimize/blob/main/src/dither/data/default-palettes.json) from [@Utzel-Butzel](https://github.com/Utzel-Butzel)/[epdoptimize](https://github.com/Utzel-Butzel/epdoptimize/)
- Custom **firmware** by [@myevit](https://github.com/myevit)/[PhotoPainter_B](https://github.com/myevit/PhotoPainter_B) (adapted to the Photopainter RP2040 **ACeP** version by myself) — real random photos from up to **100.000** files on your SD Card

## License & Credits

- License: **MIT**
- Not affiliated with Waveshare. All trademarks belong to their owners.
- Firmware credit: **@myevit** (see link above).
