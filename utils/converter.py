#encoding: utf-8
#!/usr/bin/env python3

# =======================
#  IMAGE CONVERTER
# =======================

import os
from PIL import Image
from tkinter import messagebox

# Target device map based on TARGET_DEVICE
TARGET_DEVICE_MAP = {
    "acep": {
        "calibrated_to_display": [ # epdoptimize
            (25, 30, 33),    # BLACK #191E21
            (241, 241, 241), # WHITE #F1F1F1
            (243, 207, 17),  # YELLOW #F3CF11
            (210, 14, 19),   # RED #D20E13
            (49, 49, 143),   # BLUE #31318F
            (83, 164, 40),   # GREEN #53A428
            (184, 94, 28),   # ORANGE #B85E1C
        ],

        "device_rgb": [
            (0, 0, 0),       # BLACK
            (255, 255, 255), # WHITE
            (255, 255, 0),   # YELLOW
            (255, 0, 0),     # RED
            (0, 0, 255),     # BLUE
            (0, 255, 0),     # GREEN
            (255, 128, 0),   # ORANGE
        ],

        # ⚠️ Raw values are hardware-defined, not arbitrary.
        # If your panel uses different codes, adjust accordingly.
        # can be found via "Color Index" EPD_7IN3E_[BLACK|WHITE|...]:
        # https://github.com/waveshareteam/PhotoPainter/blob/master/lib/e-Paper/EPD_7in3f.h#L43-L50
        "device_index_to_raw": [
            0, # BLACK
            1, # WHITE
            2, # YELLOW
            3, # RED
            4, # BLUE
            5, # GREEN
            6, # ORANGE
        ],
    },

    "spectra6": {
        "calibrated_to_display": [ # epdoptimize
            (25, 30, 33),    # BLACK #191E21
            (232, 232, 232), # WHITE #E8E8E8
            (239, 222, 68),  # YELLOW #EFDE44
            (178, 19, 24),   # RED #B21318
            (33, 87, 186),   # BLUE #2157BA
            (18, 95, 32),    # GREEN #125F20
        ],

        "calibrated_to_display_": [ # IanusInferus
            (54, 67, 97),    # BLACK #191E21
            (145, 178, 193), # WHITE #E8E8E8
            (159, 150, 80),  # YELLOW #EFDE44
            (122, 61, 78),   # RED #B21318
            (39, 93, 172),   # BLUE #2157BA
            (49, 114, 111),   # GREEN #125F20
        ],

        "device_rgb": [
            (0, 0, 0),        # BLACK
            (255, 255, 255),  # WHITE
            (255, 255, 0),    # YELLOW
            (255, 0, 0),      # RED
            (0, 0, 255),      # BLUE
            (0, 255, 0),      # GREEN
        ],

        # ⚠️ Raw values are hardware-defined, not arbitrary.
        # If your panel uses different codes, adjust accordingly.
        # can be found via "Color Index" EPD_7IN3F_[BLACK|WHITE|...]:
        # https://github.com/waveshareteam/PhotoPainter_B/blob/master/lib/e-Paper/EPD_7in3e.h#L43-L49
        "device_index_to_raw": [
            0, # BLACK
            1, # WHITE
            2, # YELLOW
            3, # RED
            5, # BLUE
            6, # GREEN
        ],
    },

    "4color": {
        "calibrated_to_display": [
            (0, 0, 0),       # BLACK
            (255, 255, 255), # WHITE
            (255, 255, 0),   # YELLOW
            (255, 0, 0),     # RED
            # (25, 30, 33),    # BLACK #191E21
            # (241, 241, 241), # WHITE #F1F1F1
            # (243, 207, 17),  # YELLOW #F3CF11
            # (210, 14, 19),   # RED #D20E13
        ],

        "device_rgb": [
            (0, 0, 0),       # BLACK
            (255, 255, 255), # WHITE
            (255, 255, 0),   # YELLOW
            (255, 0, 0),     # RED
        ],

        # ⚠️ Raw values are hardware-defined, not arbitrary.
        # If your panel uses different codes, adjust accordingly.
        # can be found via "Color Index" EPD_7IN3F_[BLACK|WHITE|...]:
        # https://github.com/waveshareteam/e-Paper/blob/master/E-paper_Separate_Program/1in54_e-Paper_G/ESP8266/EPD_1in54g.h#L22-L25
        "device_index_to_raw": [
            0, # BLACK
            1, # WHITE
            2, # YELLOW
            3, # RED
        ],
    },
}

class Converter:
    """
    Image converter for Waveshare PhotoPainter.
    No CLI, no sys.exit(), completely embeddable.
    Call Converter.convert() directly from your Tkinter app.
    Supports progress callbacks.
    """

    def __init__(self):
        self.flag=False

    # -----------------------
    # main API
    # -----------------------
    def convert(
        self,
        source_image: Image.Image,
        source_path: str,
        target_device: str,
        export_folder: str,
        pic_folder_on_device: str,
        dither_method: int | Image.Dither = Image.Dither.FLOYDSTEINBERG,
        progress_callback=None,
    ):
        """
        Converts one RGB image into:
        - quantized device BMP

        Returns device_out path.

        progress_callback(step:int, message:str) is optional.
        
        :param self: instance
        :param source_image: source image object to convert
        :type source_image: PIL.Image.Image
        :param source_path: original source path, used for output folder and filename
        :type source_path: str
        :param target_device: acep | spectra6
        :type target_device: str
        :param export_folder: orientation-aware output folder name
        :type export_folder: str
        :param pic_folder_on_device: folder where the pictures will reside on SD Card (default: "pic")
        :type pic_folder_on_device: str
        :param dither_method: dither method
        :param progress_callback: callback for progress
        """

        if self.flag:
            return

        try:
            self.target_device_map = TARGET_DEVICE_MAP[target_device]
            # constant-time lookup table: Faster mapping: real_world_color → index
            self._rgb_to_index = {
                rgb: i for i, rgb in enumerate(self.target_device_map["calibrated_to_display"])
            }

            # prebuild palette
            palette = (
                tuple(
                    v for rgb in self.target_device_map["calibrated_to_display"] for v in rgb
                ) + self.target_device_map["calibrated_to_display"][0] * (256 - len(self.target_device_map["calibrated_to_display"]))
            )

            self._palette_image = Image.new("P", (1, 1))
            self._palette_image.putpalette(palette)
        except Exception as e:
            messagebox.showwarning("Target device palette error", f"The given device ({target_device}) does not exist in config.\nSkipping device target conversion.")
            self.flag=True

        def report(step, msg):
            if progress_callback:
                progress_callback(step, msg)

        # -----------------------------------------
        # 1. Loading
        # -----------------------------------------
        report(1, "Loading image…")
        img = source_image.convert("RGB")

        # -------------------
        # Palette quantization
        # -------------------
        report(2, "Quantizing to palette…")
        dither = dither_method if isinstance(dither_method, Image.Dither) else Image.Dither(dither_method)
        quant = img.quantize(dither=dither, palette=self._palette_image)
        quant_rgb = quant.convert("RGB")

        # -------------------
        # Build output paths and save quantized image
        # -------------------
        report(3, "Prepare output path…")
        basedir = os.path.dirname(source_path)
        output_basename_without_ext = os.path.splitext(os.path.basename(source_path))[0]
 
        # Prepare folder structure: <source>/<orientation>/<device>/pic/<image>.bmp
        device_dir = os.path.join(basedir, export_folder, target_device)
        pic_dir = os.path.join(device_dir, pic_folder_on_device)
        device_out_dir = os.path.join(pic_dir, f"{output_basename_without_ext}.bmp")
        os.makedirs(pic_dir, exist_ok=True)

        # -------------------
        # Device BMP mapping
        # -------------------
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
        report(4, "Packing device BMP…")
        px = quant_rgb.load()
        assert px is not None
        width, height = quant_rgb.size

        for y in reversed(range(height)):
            for x in reversed(range(width)):
                rgb = px[x, y]
                idx = self._rgb_to_index[rgb]
                px[x, y] = self.target_device_map["device_rgb"][idx]

        # save device BMP
        # BMP images intended to be used on devices that takes BMP.
        # They look bad on computer, but should look regular on e-ink screens.
        # For example, with the waveshare stock PhotoPainter firmware, you can copy
        # the BMP files to the SD card.
        quant_rgb.save(device_out_dir)

        print(f"✔ Converted: {source_path}")
        print(f"   → Device BMP : {device_out_dir}")
        print(f"   → Folder    : {device_dir}")

        report(4, f"Done: {device_out_dir}")

        return device_out_dir
