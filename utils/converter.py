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
    }
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
        in_path: str,
        target_device: str,
        convert_folder: str,
        raw_folder: str,
        export_raw: bool,
        pic_folder_on_device: str,
        dither_method=Image.FLOYDSTEINBERG,
        progress_callback=None,
    ):
        """
        Converts one RGB image into:
        - quantized preview BMP
        - quantized device BMP
        - raw image

        Returns (bmp_out, dev_out)

        progress_callback(step:int, message:str) is optional.
        
        :param self: instance
        :param in_path: image path
        :type in_path: str
        :param target_device: acep | spectra6
        :type target_device: str
        :param convert_folder: folder name, where to store the converted images
        :type convert_folder: str
        :param raw_folder: folder name, where to store the raw images
        :type raw_folder: str
        :param export_raw: weather or not to store raw images for direct usage with ESP version
        :type export_raw: bool
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
        img = Image.open(in_path).convert("RGB")

        # -------------------
        # Palette quantization
        # -------------------
        report(2, "Quantizing to palette…")
        quant = img.quantize(dither=dither_method, palette=self._palette_image)
        quant_rgb = quant.convert("RGB")

        # -------------------
        # Build output paths and save quantized image
        # -------------------
        report(3, "Save BMP…")
        basedir = os.path.dirname(in_path)
        output_basename_without_ext = os.path.splitext(os.path.basename(in_path))[0]

        # Prepare folders if not exist
        convert_dir = os.path.join(basedir, f"{convert_folder}")
        convert_out_dir = os.path.join(convert_dir, f"{output_basename_without_ext}.bmp")
        os.makedirs(convert_dir, exist_ok=True)

        # folder where to store real-world RGB to device RGB images
        device_dir = os.path.join(convert_dir, f"{pic_folder_on_device}_{target_device}")
        device_out_dir = os.path.join(device_dir, f"{output_basename_without_ext}.bmp")
        os.makedirs(device_dir, exist_ok=True)

        raw_out_dir: str = ""
        if export_raw:
            raw_dir = os.path.join(convert_dir, f"{raw_folder}")
            raw_out_dir = os.path.join(raw_dir, f"{output_basename_without_ext}.sp6")
            os.makedirs(raw_dir, exist_ok=True)

        # save preview
        quant_rgb.save(convert_out_dir)

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
        width, height = quant_rgb.size

        raw_bytes = bytearray()
        odd = False
        pending = 0

        for y in reversed(range(height)):
            for x in reversed(range(width)):
                rgb = px[x, y]
                idx = self._rgb_to_index[rgb]
                px[x, y] = self.target_device_map["device_rgb"][idx]
                raw = self.target_device_map["device_index_to_raw"][idx]

                if not odd:
                    if export_raw:
                        pending = raw
                    odd = True
                else:
                    if export_raw:
                        raw_bytes.append((pending << 4) | raw)
                    odd = False

        # save device BMP
        # BMP images intended to be used on devices that takes BMP.
        # They look bad on computer, but should look regular on e-ink screens.
        # For example, with the waveshare stock PhotoPainter firmware, you can copy
        # the BMP files to the SD card.
        quant_rgb.save(device_out_dir)

        # Produce raw image suitable for ACeP/SPECTRA6 use.
        # Raw data (1 pixel = 4 bits, 2 pixels = 1 byte) to be used by
        # low-level device functions. Requires need some coding skills to use they
        # properly. They are 6x smaller than BMPs so they can reduce ESP32 processing
        # time and memory usage, and are more reliable to transmit over Wi-Fi.
        if export_raw:
            report(5, "Saving RAW bytes…")
            with open(raw_out_dir, "wb") as f:
                f.write(raw_bytes)

        print(f"✔ Converted: {in_path}")
        print(f"   → Preview BMP: {convert_out_dir}")
        print(f"   → Device BMP : {device_out_dir}")
        if export_raw:
            print(f"   → Raw image data : {raw_out_dir}")

        report(6 if export_raw else 5, f"Done: {device_out_dir}")

        return convert_out_dir, device_out_dir
