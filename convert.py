#encoding: utf-8
#!/usr/bin/env python3
"""
source: https://gist.github.com/quark-zju/e488eb206ba66925dc23692170ba49f9

Script to generate BMP images used by waveshare's ESP32-S3-PhotoPainter

ESP32-S3-PhotoPainter: https://www.waveshare.com/wiki/ESP32-S3-PhotoPainter

Forked from waveshare's color tool: https://files.waveshare.com/wiki/common/ConverTo6c_bmp-7.3.zip
with changes:
- Rotate automatically.
- Adopted epdoptimize's real-world colors: https://github.com/Utzel-Butzel/epdoptimize

There are 3 output formats:
- output/dithered: Preview of the dithering result on computer.
- output/device: BMP images intended to be used on device that takes BMP.
  They look bad on computer, but should look regular on e-ink screens.
  For example, with the waveshare stock PhotoPainter firmware, you can copy
  the BMP files to the SD card.
- output/raw: Raw data (1 pixel = 4 bits, 2 pixels = 1 byte) to be used by
  low-level device functions. Requires need some coding skills to use they
  properly. They are 6x smaller than BMPs so they can reduce ESP32 processing
  time and memory usage, and are more reliable to transmit over Wi-Fi.

For the waveshare 13.3 inch SPECTRA6 e-paper display, try these flags:
    --size=1200x1600 --rotate-180
"""

import sys
import os.path
from PIL import Image, ImagePalette, ImageOps
import argparse

# CONFIG
CONVERT_FOLDER = "pic" # folder where to store converted images
DEVICE_FOLDER = "device" # folder where to store real-world RGB to device RGB images

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='Process some images.')

# Add orientation parameter
parser.add_argument('image_file', type=str, help='Input image file')
parser.add_argument('--dir', choices=['landscape', 'portrait'], help='Image direction (landscape or portrait)')
parser.add_argument('--mode', choices=['scale', 'cut'], default='scale', help='Image conversion mode (scale or cut)')
parser.add_argument('--dither', type=int, choices=[Image.NONE, Image.FLOYDSTEINBERG], default=Image.FLOYDSTEINBERG, help='Image dithering algorithm (NONE(0) or FLOYDSTEINBERG(3))')

# Parse command line arguments
args = parser.parse_args()

# Get input parameter
input_filename = args.image_file
display_direction = args.dir
display_mode = args.mode
display_dither = Image.Dither(args.dither)

resized_image = Image

print(f"input_filename: {input_filename}")

ACEP_REAL_WORLD_RGB = [
    (25, 30, 33), # BLACK
    (241, 241, 241), # WHITE
	(243, 207, 17), # YELLOW
	(210, 14, 19),# RED
    (49, 49, 143),# BLUE
	(83, 164, 40), # GREEN
	(184, 94, 28), # ORANGE
]

ACEP_DEVICE_RGB = [
    (0, 0, 0), # BLACK
    (255, 255, 255), # WHITE
    (255, 255, 0), # YELLOW
    (255, 0, 0), # RED
    (0, 0, 255), # BLUE
    (0, 255, 0), # GREEN
    (255, 128, 0) # ORANGE
]

# ⚠️ Raw values are hardware-defined, not arbitrary. If your panel uses different codes, adjust accordingly.
ACEP_DEVICE_INDEX_TO_RAW = [
    0,  # BLACK
    1,  # WHITE
    2,  # YELLOW
    3,  # RED
    4,  # BLUE
    5,  # GREEN
    6,  # ORANGE
]

# Check whether the input file exists
if not os.path.exists(f"{input_filename}"):
    print(f'Error: file {input_filename} does not exist')
    sys.exit(1)

# Read input image
input_image = Image.open(input_filename)

# Get the original image size
width, height = input_image.size

# Specified target size
if display_direction:
    if display_direction == 'landscape':
        target_width, target_height = 800, 480
    else:
        target_width, target_height = 480, 800
else:
    if  width > height:
        target_width, target_height = 800, 480
    else:
        target_width, target_height = 480, 800

if display_mode == 'scale':
    # Computed scaling
    scale_ratio = max(target_width / width, target_height / height)

    # Calculate the size after scaling
    resized_width = int(width * scale_ratio)
    resized_height = int(height * scale_ratio)

    # Resize image
    output_image = input_image.resize((resized_width, resized_height))

    # Create the target image and center the resized image
    resized_image = Image.new('RGB', (target_width, target_height), (255, 255, 255))
    left = (target_width - resized_width) // 2
    top = (target_height - resized_height) // 2
    resized_image.paste(output_image, (left, top))
elif display_mode == 'cut':
    # Calculate the fill size to add or the area to crop
    if width / height >= target_width / target_height:
        # The image aspect ratio is larger than the target aspect ratio, and padding needs to be added on the left and right
        delta_width = int(height * target_width / target_height - width)
        padding = (delta_width // 2, 0, delta_width - delta_width // 2, 0)
        box = (0, 0, width, height)
    else:
        # The image aspect ratio is smaller than the target aspect ratio and needs to be filled up and down
        delta_height = int(width * target_height / target_width - height)
        padding = (0, delta_height // 2, 0, delta_height - delta_height // 2)
        box = (0, 0, width, height)

    resized_image = ImageOps.pad(input_image.crop(box), size=(target_width, target_height), color=(255, 255, 255), centering=(0.5, 0.5))


# Create a palette object
pal_image = Image.new("P", (1,1))
palette = (
    tuple(v for rgb in ACEP_REAL_WORLD_RGB for v in rgb)
    + ACEP_REAL_WORLD_RGB[0] * 249
)
pal_image.putpalette(palette)
# pal_image.putpalette( (0,0,0,  255,255,255,  0,255,0,   0,0,255,  255,0,0,  255,255,0, 255,128,0) + (0,0,0)*249)

# The color quantization and dithering algorithms are performed, and the results are converted to RGB mode
quantized_image = resized_image.quantize(
    dither=display_dither, 
    palette=pal_image
).convert('RGB')

# Save output image
# output_filename = os.path.splitext(input_filename)[0] + '_' + display_mode + '_' + display_direction + '_output.bmp'
basedir = os.path.dirname(input_filename)
output_path = os.path.join(basedir, f"{CONVERT_FOLDER}")
output_basename = os.path.basename(input_filename)
output_basename_without_ext = os.path.splitext(output_basename)[0]
output_filename = os.path.join(output_path, output_basename_without_ext + "_" + display_mode + "_" + display_direction + '.bmp')

os.makedirs(output_path, exist_ok=True)

print(f"output_path: {output_path}")
print(f"output_basename_without_ext: {output_basename_without_ext}")
print(f"output_filename: {output_filename}")

quantized_image.save(output_filename)

def convertToDeviceRgb():
    """
    This code:
        1. Iterates over an image pixel by pixel, starting from the bottom-right corner and moving leftwards and upwards.
        2. Converts each pixel’s RGB value from a “real world” color palette to a device-specific color palette.
        3. Encodes each pixel as a 3-bit value (0–7).
        4. Packs two pixels into one byte (each pixel stored in 4 bits / a nibble).
        5. Appends those bytes to a list called raw_bytes.
    In short:
        👉 It recolors an image using a device palette and serializes the pixels into packed raw bytes suitable for a low-color device (likely embedded hardware or a display).
    """
    # For each pixel, convert ACEP real-world RGB to device RGB
    raw_bytes = bytearray()
    raw_pending = 0
    pixels = quantized_image.load()
    for y in reversed(range(quantized_image.height)):
        for x in reversed(range(quantized_image.width)):
            r, g, b = pixels[x, y]
            index = ACEP_REAL_WORLD_RGB.index((r, g, b))
            pixels[x, y] = ACEP_DEVICE_RGB[index]
            raw_value = ACEP_DEVICE_INDEX_TO_RAW[index]
            assert raw_value < 8
            if (x & 1) == 0:
                raw_pending = raw_value
            else:
                raw_bytes.append((raw_pending << 4) | raw_value)
    os.makedirs(os.path.join(output_path, f"{DEVICE_FOLDER}"), exist_ok=True)
    output_filename = os.path.join(output_path, f"{DEVICE_FOLDER}", output_basename_without_ext + "_" + display_mode + "_" + display_direction + '.bmp')
    quantized_image.save(output_filename)

convertToDeviceRgb()

print(f'Successfully converted {input_filename} to {output_filename}')
