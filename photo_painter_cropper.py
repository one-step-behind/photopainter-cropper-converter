#encoding: utf-8
#!/usr/bin/env python3

import os
import sys
import math
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageFilter, ImageEnhance
from converter import Converter

# ====== CONFIG ======
APP_TITLE = "PhotoPainterCropper"
DEFAULT_TARGET_SIZE = (800, 480)           # exact JPG output
DEFAULT_RATIO = DEFAULT_TARGET_SIZE[0] / DEFAULT_TARGET_SIZE[1]
WINDOW_MIN = (1024, 768)
JPEG_QUALITY = 90
ORIENTATION = "landscape" # AVAILABLE_ORIENTATIONS
FILL_MODE = "blur" # AVAILABLE_FILL_MODES
DITHER_METHOD = 3 # NONE(0) or FLOYDSTEINBERG(3)
TARGET_DEVICE = "acep" # ACEP | SPECTRA6

defaults = {
    "BRIGHTNESS": 1.0, # 1.0: no change
    "CONTRAST": 1.0, # 1.0: no change
    "SATURATION": 1.0, # 1.0: no change
}

AVAILABLE_ORIENTATIONS = ("landscape", "portrait")
AVAILABLE_FILL_MODES = ("blur", "white")
AVAILABLE_TARGET_DEVICES = ("acep", "spectra6")

CROP_BORDER_COLOR = "#00ff00"   # green rectangle border
DEFAULT_CROP_SIZE = 1 # between 0.1 ... 1
GRID_COLOR = "#00ff00"          # grid lines
MASK_COLOR = "#000000"          # mask outside crop region
MASK_STIPPLE = "gray50"
WINDOW_BACKGROUND_COLOR = "#222222"
HIGHLIGHT_COLOR = "#339933"

ARROW_STEP = 1                      # px for step with arrows
ARROW_STEP_FAST = 10                # px with Shift pressed
SCALE_FACTOR = 1.01                 # zoom step with normal +/-
SCALE_FACTOR_FAST = 1.10            # zoom step with Shift

LABEL_PADDINGS = (5, 5)

EXPORT_FOLDER = "cropped" # folder where to store cropped images
EXPORT_FILENAME_SUFFIX = "_pp"
STATE_SUFFIX = "_ppcrop.txt"        # file status next to the source image
CONVERT_FOLDER = "dithered" # folder where to store converted/dithered images
RAW_FOLDER = "raw" # folder where to store raw images
EXPORT_RAW = False # should export raw image suitable for SPECTRA6 use?
SAVE_FILELIST=True

class DynamicButtonVar:
    def __init__(self, default_text):
        self.default_text = default_text
        self.var = tk.StringVar(value=default_text)

    def update(self, extra_text):
        """Set button text to: Base: extra"""
        if extra_text is None or extra_text == "":
            self.var.set(self.default_text)
        else:
            self.var.set(f"{self.default_text}: {extra_text.upper()}")

class DynamicSliderVar:
    def __init__(self, default_text):
        self.default_text = default_text
        self.var = tk.StringVar(value=default_text)

    def update(self, extra_text):
        """Set slider text to: Base: extra"""
        if extra_text is None or extra_text == "":
            self.var.set(self.default_text)
        else:
            self.var.set(f"{self.default_text}: {extra_text}")

class CropperApp:
    def __init__(self, window):
        # ---------- Load settings ----------
        self.app_settings = self.load_app_settings_or_defaults()
        self.image_preferences = {}

        # ---------- UI ----------
        self._resize_pending = False
        self._slider_update_pending = None
        self.window = window
        w, h = self.app_settings["window_min"].split(',')
        self.window.minsize(w, h)
        resource_path = os.path.join(os.path.dirname(__file__), "./_source/icon.ico") if not hasattr(sys, "frozen") else os.path.join(sys.prefix, "./_source/icon.ico")
        self.window.iconbitmap(default=resource_path)
        self.window.tk_setPalette(WINDOW_BACKGROUND_COLOR)
        self.window.title(f"{APP_TITLE} – "
            "Drag/Arrows=move (Shift=+fast)  •  "
            "Scroll/+/-=resize (Shift=+fast)  •  "
            "Esc=skip"
        )

        top = ttk.Frame(self.window)
        top.pack(fill=tk.X, side=tk.TOP)

        self.button_bar = ttk.Frame(top)
        self.button_bar.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], anchor=tk.W, fill=tk.X, side=tk.TOP)

        canvas_with_options = ttk.Frame(window)
        canvas_with_options.pack(fill=tk.BOTH, side=tk.TOP, expand=True)

        # set the attribute "highlightthickness=0" in Canvas will no longer display the border around it
        self.canvas = tk.Canvas(canvas_with_options, highlightthickness=0, bg=WINDOW_BACKGROUND_COLOR)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        self.options_frame = tk.Frame(canvas_with_options, highlightthickness=0)
        self.options_frame.pack(padx=LABEL_PADDINGS[0], fill=tk.Y, side=tk.RIGHT)

        bottom_bar = ttk.Frame(self.window)#, relief=tk.SUNKEN)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # ---------- Theme ----------
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background=WINDOW_BACKGROUND_COLOR, foreground="white")
        self.style.configure('TLabel', background=WINDOW_BACKGROUND_COLOR, foreground="white")
        self.style.configure('TButton', background=WINDOW_BACKGROUND_COLOR, foreground="white", bordercolor=WINDOW_BACKGROUND_COLOR)
        self.style.map('TButton', 
            background=[('active', HIGHLIGHT_COLOR)], # When 'active' (hovered), use 'darkgreen'
            foreground=[('pressed', 'red')], # When 'pressed' (clicked), use 'red'
        )
        # Remove the "Focus Ring" from Buttons
        #self.style.layout('TButton',  [
        #    ('Button.padding', {
        #        'sticky': 'nswe', 'children': [
        #            ('Button.label', {'sticky': 'nswe'})
        #        ]
        #    })
        #])

        # ---------- Button UI ----------
        # Define buttons with text variable, command, optional params, styling, and optional hover tip
        self.option_button_definitions = {
            "orientation": {
                "default_text": "Orientation",
                "command": self.toggle_orientation,
                "enter_tip": "Toggle Orientation (D)",
                #"width": 23,
                "fill": tk.X,
                "underline": 0,
            },
            "fill_mode": {
                "default_text": "Fill",
                "command": self.toggle_fill_mode,
                "enter_tip": "Toggle Fill mode (F)",
                #"width": 10,
                "underline": 0,
            },
            "target_device": {
                "default_text": "Device",
                "command": self.toggle_target_device,
                "enter_tip": "Toggle Target device (T)",
                #"width": 17,
                "underline": 0,
            },
        }
        
        self.app_button_definitions = {
            "prev": {
                "default_text": "<< Prev",
                "command": self.prev_image,
                "enter_tip": "Previous Image (PAGE_UP)",
            },
            "next": {
                "default_text": "Next >>",
                "command": self.next_image,
                "enter_tip": "Next Image (PAGE_DOWN)",
            },
            "save": {
                "default_text": "Save",
                "command": self.on_confirm,
                "enter_tip": "Crop and Convert (Enter/S)",
                "style_config": {"foreground": "green"},
            },
        }

        self.enhancer_sliders = {
            "brightness": {
                "text": "Brightness",
                "command": lambda value: self.schedule_slider_update("brightness", value),
            },
            "contrast": {
                "text": "Contrast",
                "command": lambda value: self.schedule_slider_update("contrast", value),
            },
            "saturation": {
                "text": "Saturation",
                "command": lambda value: self.schedule_slider_update("saturation", value),
            },
        }

        # Store the actual Button widgets
        self.button_vars = {} # DynamicButtonVar objects
        self.buttons = {}

        # Store the actual Sliders widgets
        self.slider_vars = {} # DynamicButtonVar objects
        self.sliders = {}

        # Build buttons
        self.create_buttons(self.app_button_definitions, self.button_bar, tk.HORIZONTAL)
        # create image options buttons
        self.create_buttons(self.option_button_definitions, self.options_frame, tk.VERTICAL)
        tk.Label(self.options_frame, width=22, height=1).pack() # spacer

        # Status and button hover text
        self.status_var_default_text = "Ready"
        self.status_var = tk.StringVar(value=self.status_var_default_text)
        self.status = ttk.Label(self.button_bar, textvariable=self.status_var, anchor=tk.W)
        self.status.pack(side=tk.RIGHT)

        # Output dimension size label
        self.size_lbl_var = tk.StringVar(value="")
        self.size_lbl = ttk.Label(self.button_bar, textvariable=self.size_lbl_var)
        self.size_lbl.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], anchor=tk.W)

        # Status bar elements
        self.status_label_var = tk.StringVar(value="Select folder with images…")
        self.status_label = ttk.Label(bottom_bar, textvariable=self.status_label_var, anchor=tk.W)
        self.status_label.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], anchor=tk.W, fill=tk.X, side=tk.LEFT)

        self.status_count = ttk.Label(bottom_bar, text="0/0")
        self.status_count.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], side=tk.RIGHT)
        
        # Mouse events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)     # mac/win
        self.canvas.bind("<Button-4>", self.on_wheel_linux) # linux up
        self.canvas.bind("<Button-5>", self.on_wheel_linux) # linux down

        # Keyboard events
        self.window.bind("<Return>", self.on_confirm)
        self.window.bind_all("<Tab>", self.on_confirm_tab)    # Tab intercept (prevent focus change)
        self.window.bind("<s>", self.on_confirm)
        self.window.bind("<S>", self.on_confirm)
        self.window.bind("<Prior>", self.prev_image) # PAGE UP
        self.window.bind("<Next>", self.next_image) # PAGE DOWN
        self.window.bind("<Escape>", self.on_skip)

        # Keyboard events (movement)
        self.window.bind("<Left>",  lambda e: self.on_arrow(e, -1,  0))
        self.window.bind("<Right>", lambda e: self.on_arrow(e,  1,  0))
        self.window.bind("<Up>",    lambda e: self.on_arrow(e,  0, -1))
        self.window.bind("<Down>",  lambda e: self.on_arrow(e,  0,  1))

        # Keyboard events (resize)
        for ks in ("<plus>", "<KP_Add>", "<equal>"):  # '+' It's often Shift+'='; include '=' for convenience
            self.window.bind(ks, self.on_plus)
        for ks in ("<minus>", "<KP_Subtract>"):
            self.window.bind(ks, self.on_minus)

        # Various
        self.window.bind("<Configure>", self.on_resize)
        self.window.bind("<o>", self.toggle_orientation)
        self.window.bind("<O>", self.toggle_orientation)
        self.window.bind("<f>", self.toggle_fill_mode)
        self.window.bind("<F>", self.toggle_fill_mode)
        self.window.bind("<d>", self.toggle_target_device)
        self.window.bind("<D>", self.toggle_target_device)

        # State
        self.original_img: Image = None
        self.display_img: Image = None # image to display in window
        self.tk_img: ImageTk.PhotoImage = None
        self.image_id = None
        self.image_paths = []
        self.idx = 0

        self.scale = 1.0
        self.img_off = (0, 0)
        self.disp_size = (0, 0)

        self.target_size = DEFAULT_TARGET_SIZE  # will be updated dynamically
        self.ratio = DEFAULT_RATIO
        self.rect_w = 0
        self.rect_h = 0
        self.rect_center = (0, 0)
        self.dragging = False
        self.drag_offset = (0, 0)

        self.window.after(200, self.delayed_start)

    # ---------- UI helpers ----------
    def delayed_start(self):
        # ensure window is fully realized
        self.window.update()
        self.canvas.focus_set()       # keyboard focus works now
        self.load_folder()

    def update_size_lbl(self):
        w, h = self.target_size
        self.size_lbl_var.set(f"Crop: {w}x{h}")

    def create_buttons(self, button_definition, target, orientation):
        # Create buttons dynamically
        for name, info in button_definition.items():

            # 1) Create helper var object
            dyn = DynamicButtonVar(info["default_text"])
            self.button_vars[name] = dyn

            # 2) Collect optional settings for ttk.Button
            btn_kwargs = {
                "textvariable": dyn.var,
                "takefocus": 0,
            }

            if "width" in info:
                btn_kwargs["width"] = info["width"]

            if "underline" in info:
                btn_kwargs["underline"] = info["underline"]

            if "style_config" in info:
                style_name = f"{name}.Custom.TButton"
                self.style.configure(style_name, **info["style_config"])
                btn_kwargs["style"] = style_name

            # 3) Create the button - COMMAND MUST BE PASSED DIRECTLY!!!
            btn = ttk.Button(target, command=info["command"], name=f"btn_{name}", **btn_kwargs)
            btn.pack(side=tk.LEFT if orientation=="horizontal" else tk.TOP, fill=tk.X)
            self.buttons[name] = btn

            # 4) Bind hover tooltip events if enter_tip exists
            if "enter_tip" in info:
                btn.bind("<Enter>", lambda e, tip=info["enter_tip"]: self.show_tip(tip))
                btn.bind("<Leave>", lambda e: self.show_tip())

    def update_button_text(self, button_name, extra_text):
        """
        Update button text dynamically, preserving base text
        
        :param self: Beschreibung
        :param button_name: Beschreibung
        :param extra_text: Beschreibung
        """
        if button_name in self.button_vars:
            self.button_vars[button_name].update(extra_text)
        else:
            print(f"No button found for '{button_name}'")

    def show_tip(self, msg: str = ""):
        """
        Show tooltip text (hover)
        
        :param self: Beschreibung
        :param msg: Beschreibung
        :type msg: str
        """
        if msg:
            self.status_var.set(msg)
        else:
            self.status_var.set(self.status_var_default_text)
    
    def create_image_enhancer_sliders(self):
        i = 0
        for name, info in self.enhancer_sliders.items():
            value = self.image_preferences[name]

            # if sliders already exists, just update value
            if len(self.slider_vars) == len(self.enhancer_sliders.items()):
                self.schedule_slider_update(name, value)
                self.sliders[name][1].set(value)
                continue

            # 1) Create helper var object
            dyn = DynamicSliderVar(info["text"])
            self.slider_vars[name] = dyn

            # 2) Collect optional settings for ttk.Scale
            slider_kwargs = {
                "name": f"slider_{name}",
                "takefocus": 0,
                "from_": 0.0,
                "to": 2.0,
                "resolution": 0.1,
                "tickinterval": 1.0,
                "orient": tk.HORIZONTAL,
                "showvalue": False,
            }

            # 3) Create the slider - COMMAND MUST BE PASSED DIRECTLY!!!
            slider_label = ttk.Label(self.options_frame, textvariable=dyn.var, justify=tk.LEFT)
            slider_label.pack(fill=tk.X)
            slider = tk.Scale(self.options_frame, command=info["command"], **slider_kwargs)
            slider.set(value)
            slider.pack(fill=tk.X)
            self.sliders[name] = [slider_label, slider]
            i += 2

    # -------------------------------------------------------------------------
    # Debounced processing for sliders
    # -------------------------------------------------------------------------
    def schedule_slider_update(self, slider_label, value):
        if self._slider_update_pending:
            self.window.after_cancel(self._slider_update_pending)
        self._slider_update_pending = self.window.after(10, self.update_slider_value_and_label(slider_label, value))

    def update_slider_value_and_label(self, slider_label, value):
        if slider_label in self.enhancer_sliders:
            self.image_preferences[slider_label] = float(value)
            self.slider_vars[slider_label].update(value)

            self.update_image()
        else:
            print(f"No slider found for '{slider_label}'")

    def update_status_label(self, msg):
        """Set status message immediately."""
        self.status_label_var.set(msg)
        #self.root.update_idletasks()  # forces GUI update

    # ---------- File loading ----------
    def load_folder(self):
        """
        Load images from given folder. Called once on app start.
        
        :param self: instance
        """
        folder = filedialog.askdirectory(title="Select source folder with photos")

        if not folder:
            self.window.after(50, self.window.destroy) #quit)
            return

        supported_formats = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp")
        self.image_paths = [
            os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.lower().endswith(supported_formats)
        ]

        if not self.image_paths:
            messagebox.showerror("No image", "The folder contains no images.")
            self.window.after(50, self.window.destroy) #quit)
            return

        self.show_image()

    def show_image(self):
        if self.idx >= len(self.image_paths):
        #    messagebox.showinfo("Done", "All images have been processed.")
        #    self.root.after(50, self.root.destroy) #quit)
        #    return
            self.idx = 0

        if self.idx < 0:
            self.idx = len(self.image_paths)-1

        current_image_path = self.image_paths[self.idx]

        # Load saved preferences BEFORE loading the image
        pref_loaded = self.load_image_preferences_or_defaults(current_image_path)

        try:
            self.image_id = None
            self.original_img = self.load_image_by_exif_orientation(current_image_path) # EXIF auto-rotate
            self.display_img = self.original_img.copy()
        except Exception as e:
            messagebox.showwarning("Image error", f"Unable to open:\n{current_image_path}\n{e}\nWe move on to the next one.")
            self.next_image()
            return

        self.create_image_enhancer_sliders() # create image options sliders
        self.resize_image_and_center_in_window()

        # restore state if exists; otherwise initial pane
        if not pref_loaded or not self.apply_saved_state():
            self.init_crop_rectangle()

        self.status_count.config(text=f"{self.idx+1}/{len(self.image_paths)}")
        self.update_size_lbl() # after loading state
        self.update_status_label(f"{current_image_path}")
        self.draw_crop_marker_grid() # create crop marker

    def load_image_by_exif_orientation(self, path: str) -> Image:
        """
        Loads an image and applies EXIF orientation correction (auto-rotate).
        Returns an RGB image with correct orientation.
        """
        try:
            image = Image.open(path).convert("RGB")

            try:
                # modern Pillow: .getexif()
                exif = image.getexif()
                orientation = exif.get(0x0112, 1)  # EXIF Orientation
            except Exception:
                orientation = 1

            # Rotate according to EXIF orientation tag
            if orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)  # 90° CW
            elif orientation == 8:
                image = image.rotate(90, expand=True)   # 90° CCW

            return image

        except Exception as e:
            print("EXIF load/rotation failed:", e)
            return Image.open(path)

    # ---------- Layout & Drawing ----------
    def canvas_size(self):
        # Return REAL canvas size (never force minimum)
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def resize_image_and_center_in_window(self):
        cw, ch = self.canvas_size()
        iw, ih = self.original_img.size
        self.scale = min(cw / iw, ch / ih)
        disp_w = max(1, int(iw * self.scale))
        disp_h = max(1, int(ih * self.scale))
        self.disp_size = (disp_w, disp_h)
        self.display_img = self.original_img.resize((disp_w, disp_h), Image.LANCZOS)
        self.img_off = ((cw - disp_w) // 2, (ch - disp_h) // 2)

    def update_image(self):
        """Apply all enhancements and update the image display."""
        # Initial image
        img = self.enhance_image(self.display_img)
        self.tk_img = ImageTk.PhotoImage(img)

        # Draw or update image on canvas
        if self.image_id is None:
            self.image_id = self.canvas.create_image(self.img_off[0], self.img_off[1], anchor="nw", image=self.tk_img)
        else: # Update the existing canvas
            self.canvas.itemconfig(self.image_id, image=self.tk_img)

        self._slider_update_pending = None

    def init_crop_rectangle(self):
        """
        Initialize crop rectangle
        """
        dw, dh = self.disp_size
        rw = int(dw * DEFAULT_CROP_SIZE) # default cropper size
        rh = int(rw / self.ratio)

        if rh > dh:
            rh = int(dh * DEFAULT_CROP_SIZE) # default cropper size
            rw = int(rh * self.ratio)

        self.rect_w, self.rect_h = max(20, rw), max(20, rh)
        cx = self.img_off[0] + dw // 2
        cy = self.img_off[1] + dh // 2
        self.rect_center = (cx, cy)
        self.clamp_crop_rectangle_to_canvas()

    def rect_coords(self):
        cx, cy = self.rect_center
        w2 = self.rect_w // 2
        h2 = self.rect_h // 2

        return (cx - w2, cy - h2, cx + w2, cy + h2)

    def clamp_crop_rectangle_to_canvas(self):
        # Keep the rectangle within the edges of the canvas (it can go outside the PHOTO)
        x1, y1, x2, y2 = self.rect_coords()
        cw, ch = self.canvas_size()
        dx = dy = 0
        if x1 < 0: dx = -x1
        if y1 < 0: dy = -y1
        if x2 > cw: dx = cw - x2 if dx == 0 else dx
        if y2 > ch: dy = ch - y2 if dy == 0 else dy
        cx, cy = self.rect_center
        self.rect_center = (cx + dx, cy + dy)

        # Size limits: at least 64px wide, maximum canvas maintaining ratio
        max_w = min(cw, int(ch * self.ratio))
        self.rect_w = max(64, min(self.rect_w, max_w))
        self.rect_h = int(self.rect_w / self.ratio)

    def draw_crop_marker_grid(self):
        # snap to have straight lines (no sub-pixels)
        def snap(v): return int(round(v))

        self.canvas.delete("all") # remove everything from Canvas
        self.image_id = None
        self.update_image() # rebuild image

        # crop rectangle
        x1f, y1f, x2f, y2f = self.rect_coords()
        x1: int = snap(x1f)
        y1: int = snap(y1f)
        x2: int = snap(x2f)
        y2: int = snap(y2f)

        # off-crop mask
        cw, ch = self.canvas_size()
        self.canvas.create_rectangle(0, 0, cw, y1, fill=MASK_COLOR, stipple=MASK_STIPPLE, width=0)
        self.canvas.create_rectangle(0, y2, cw, ch, fill=MASK_COLOR, stipple=MASK_STIPPLE, width=0)
        self.canvas.create_rectangle(0, y1, x1, y2, fill=MASK_COLOR, stipple=MASK_STIPPLE, width=0)
        self.canvas.create_rectangle(x2, y1, cw, y2, fill=MASK_COLOR, stipple=MASK_STIPPLE, width=0)

        # crop edge
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=CROP_BORDER_COLOR, width=1)

        # grid (thirds) with straight lines
        v1 = snap(x1 + (x2 - x1) / 3.0)
        v2 = snap(x1 + 2 * (x2 - x1) / 3.0)
        h1 = snap(y1 + (y2 - y1) / 3.0)
        h2 = snap(y1 + 2 * (y2 - y1) / 3.0)
        dash_pat = (3, 3)
        self.canvas.create_line(v1, y1, v1, y2, fill=GRID_COLOR, dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(v2, y1, v2, y2, fill=GRID_COLOR, dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(x1, h1, x2, h1, fill=GRID_COLOR, dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")
        self.canvas.create_line(x1, h2, x2, h2, fill=GRID_COLOR, dash=dash_pat, width=1, capstyle="butt", joinstyle="miter")

    # ---------- Mouse ----------
    def on_click(self, e):
        x1, y1, x2, y2 = self.rect_coords()
        if x1 <= e.x <= x2 and y1 <= e.y <= y2:
            self.dragging = True
            self.drag_offset = (e.x - self.rect_center[0], e.y - self.rect_center[1])
        else:
            self.rect_center = (e.x, e.y)
            self.clamp_crop_rectangle_to_canvas()
            self.draw_crop_marker_grid()

    def on_drag(self, e):
        if not self.dragging:
            return

        self.rect_center = (e.x - self.drag_offset[0], e.y - self.drag_offset[1])
        self.clamp_crop_rectangle_to_canvas()
        self.draw_crop_marker_grid()

    def on_release(self, _e):
        self.dragging = False

    def on_wheel(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        self.resize_rect_mouse(1 if e.delta > 0 else -1, fast)

    def on_wheel_linux(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        self.resize_rect_mouse(1 if e.num == 4 else -1, fast)

    def resize_rect_mouse(self, orientation, fast):
        speed = SCALE_FACTOR_FAST if fast else SCALE_FACTOR
        factor = speed if orientation > 0 else (1 / speed)
        self.apply_resize_factor(factor)

    # ---------- Keyboard ----------
    def on_confirm_tab(self):
        self.next_image()

        return "break"  # avoid changing Tab focus

    def on_arrow(self, e, dx, dy):
        step = ARROW_STEP_FAST if (e.state & 0x0001) else ARROW_STEP  # Shift accelerates
        self.rect_center = (self.rect_center[0] + dx*step, self.rect_center[1] + dy*step)
        self.clamp_crop_rectangle_to_canvas()
        self.draw_crop_marker_grid()

    def on_plus(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        factor = SCALE_FACTOR_FAST if fast else SCALE_FACTOR
        self.apply_resize_factor(factor)

    def on_minus(self, e):
        fast = bool(e.state & 0x0001)
        factor = (1 / SCALE_FACTOR_FAST) if fast else (1 / SCALE_FACTOR)
        self.apply_resize_factor(factor)

    def apply_resize_factor(self, factor):
        cw, ch = self.canvas_size()
        max_w = min(cw, int(ch * self.ratio))
        new_w = int(self.rect_w * factor)
        new_w = max(64, min(new_w, max_w))
        self.rect_w = new_w
        self.rect_h = int(self.rect_w / self.ratio)
        self.clamp_crop_rectangle_to_canvas()
        self.draw_crop_marker_grid()

    def on_resize(self, _e):
        """
        Window resize
        
        :param self: instance
        """
        if self.original_img is None:
            return

        if self._resize_pending:
            return

        self._resize_pending = True
        self.window.after(30, self._apply_resize)

    def _apply_resize(self):
        """
        Apply resize
        
        :param self: instance
        """
        self._resize_pending = False

        if self.original_img is None:
            return
        
        rect_img_raw = self.rect_in_image_coords_raw()
        self.resize_image_and_center_in_window()
        x1i, y1i, x2i, y2i = rect_img_raw
        self.calculate_display_coordiantes(x1i, y1i, x2i, y2i)
        self.clamp_crop_rectangle_to_canvas()
        self.draw_crop_marker_grid()

    def calculate_display_coordiantes(self, x1i, y1i, x2i, y2i):
        x1d = self.img_off[0] + int(x1i * self.scale)
        y1d = self.img_off[1] + int(y1i * self.scale)
        x2d = self.img_off[0] + int(x2i * self.scale)
        y2d = self.img_off[1] + int(y2i * self.scale)

        #self.rect_w = max(1, x2d - x1d)
        #self.rect_h = int(self.rect_w / self.ratio)
        #self.rect_center = ((x1d + x2d)//2, (y1d + y2d)//2)

        # reconstruct rectangle while maintaining a fixed ratio
        w = x2d - x1d
        h = y2d - y1d
        # ensure based on ratio
        if abs(w / h - self.ratio) > 0.001:
            h = int(w / self.ratio)

        self.rect_w = w
        self.rect_h = h
        cx = (x1d + x2d) // 2
        cy = (y1d + y2d) // 2
        self.rect_center = (cx, cy)

        return x1d, y1d, x2d, y2d

    # ---------- Toggles ----------
    def toggle_orientation(self, _e=None):
        # Switch internal state
        self.image_preferences["orientation"] = AVAILABLE_ORIENTATIONS[0] if self.image_preferences["orientation"] == AVAILABLE_ORIENTATIONS[1] else AVAILABLE_ORIENTATIONS[1]

        # Update target_size and ratio for new orientation
        self.update_targetsize_and_ratio()

        # Resize crop rect to respect the new ratio
        old_rect_h = self.rect_h  # preserve height (stable dimension)
        new_rect_w = int(old_rect_h * self.ratio)
        new_rect_h = old_rect_h

        # Clamp to canvas
        cw, ch = self.canvas_size()
        
        # If new crop rect width is larger than canvas → shrink using height
        if new_rect_w > cw:
            new_rect_w = int(cw * 0.8)
            new_rect_h = int(new_rect_w / self.ratio)

        # If new crop rect height larger than canvas → shrink using width
        if new_rect_h > ch:
            new_rect_h = int(ch * 0.8)
            new_rect_w = int(new_rect_h * self.ratio)

        # Apply new dims
        self.rect_w = new_rect_w
        self.rect_h = new_rect_h

        # Keep centered and inside canvas
        self.clamp_crop_rectangle_to_canvas()

        # Update title + label + redraw
        self.update_size_lbl() # after orientation toggle
        self.update_button_text("orientation", self.image_preferences["orientation"])
        self.draw_crop_marker_grid()

    def toggle_fill_mode(self, _e=None):
        self.image_preferences["fill_mode"] = AVAILABLE_FILL_MODES[0] if self.image_preferences["fill_mode"] == AVAILABLE_FILL_MODES[1] else AVAILABLE_FILL_MODES[1]
        self.update_button_text("fill_mode", self.image_preferences["fill_mode"])

    def toggle_target_device(self, _e=None):
        self.image_preferences["target_device"] = AVAILABLE_TARGET_DEVICES[0] if self.image_preferences["target_device"] == AVAILABLE_TARGET_DEVICES[1] else AVAILABLE_TARGET_DEVICES[1]
        self.update_button_text("target_device", self.image_preferences["target_device"])

    def update_targetsize_and_ratio(self):
        if self.image_preferences["orientation"] == "portrait":
            self.ratio = DEFAULT_TARGET_SIZE[1] / DEFAULT_TARGET_SIZE[0]
            self.target_size = (DEFAULT_TARGET_SIZE[1], DEFAULT_TARGET_SIZE[0])
        else:
            self.ratio = DEFAULT_TARGET_SIZE[0] / DEFAULT_TARGET_SIZE[1]
            self.target_size = DEFAULT_TARGET_SIZE

    # ---------- Coordinate helpers ----------
    def rect_in_image_coords_raw(self):
        """
        Converts rectangle (display) -> ORIGINAL image coordinates
        without clamping: they can be negative or > size (out-of-bounds).
        """
        x1d, y1d, x2d, y2d = self.rect_coords()
        ox, oy = self.img_off
        x1i = (x1d - ox) / self.scale
        y1i = (y1d - oy) / self.scale
        x2i = (x2d - ox) / self.scale
        y2i = (y2d - oy) / self.scale

        return (x1i, y1i, x2i, y2i)

    # ---------- Crop & Save ----------
    def on_confirm(self, _e=None):
        in_path = self.image_paths[self.idx]

        # 1) raw coordinates (may go outside the borders)
        x1i, y1i, x2i, y2i = self.rect_in_image_coords_raw()
        if x2i <= x1i or y2i <= y1i:
            messagebox.showerror("Invalid selection", "The selection box is empty.")
            return

        sel_w_orig = x2i - x1i
        sel_h_orig = y2i - y1i
        if sel_w_orig <= 1 or sel_h_orig <= 1:
            messagebox.showerror("Invalid selection", "Selection too small.")
            return

        # 2) intersection with the original image
        iw, ih = self.original_img.size
        ix1 = max(0, math.floor(x1i))
        iy1 = max(0, math.floor(y1i))
        ix2 = min(iw, math.ceil(x2i))
        iy2 = min(ih, math.ceil(y2i))

        # 3) scala orig->target
        sx = self.target_size[0] / sel_w_orig
        sy = self.target_size[1] / sel_h_orig

        # 4) background base (white or blur) + paste sharp part if intersection exists
        if ix2 <= ix1 or iy2 <= iy1:
            out = self.background_only(None)
        else:
            int_w_orig = ix2 - ix1
            int_h_orig = iy2 - iy1
            int_w_tgt = max(1, int(round(int_w_orig * sx)))
            int_h_tgt = max(1, int(round(int_h_orig * sy)))
            region_scaled = self.original_img.crop((ix1, iy1, ix2, iy2)).resize((int_w_tgt, int_h_tgt), Image.LANCZOS)
            out = self.background_only(region_scaled)

            dx_tgt = int(round((ix1 - x1i) * sx))
            dy_tgt = int(round((iy1 - y1i) * sy))

            src_x1 = max(0, -dx_tgt)
            src_y1 = max(0, -dy_tgt)
            dst_x1 = max(0, dx_tgt)
            dst_y1 = max(0, dy_tgt)

            width  = min(self.target_size[0] - dst_x1, region_scaled.width  - src_x1)
            height = min(self.target_size[1] - dst_y1, region_scaled.height - src_y1)

            if width > 0 and height > 0:
                sub = region_scaled.crop((src_x1, src_y1, src_x1 + width, src_y1 + height))
                out.paste(sub, (dst_x1, dst_y1))

        # 5) enhance image by given values
        out = self.enhance_image(out)

        # 6) save image
        self.save_output(out)

        # 7) save state (txt) next to the source
        self.save_state(in_path, x1i, y1i, x2i, y2i)

        # 8) convert to 24 bit BMP
        self.convert_to_bmp(in_path)

        # 9) next image
        self.next_image()

    def enhance_image(self, img):
        # Add edge enhancement
        #enhanced_image = img.filter(ImageFilter.EDGE_ENHANCE)

        # Add noise reduction
        #enhanced_image = enhanced_image.filter(ImageFilter.SMOOTH)

        # Add sharpening for better detail visibility
        enhanced_image = img.filter(ImageFilter.SHARPEN)

        if (
            float(self.image_preferences["brightness"]) == float(defaults["BRIGHTNESS"]) and
            float(self.image_preferences["contrast"]) == float(defaults["CONTRAST"]) and
            float(self.image_preferences["saturation"]) == float(defaults["SATURATION"])
        ):
            return enhanced_image

        # Add brightness enhancement
        enhancer = ImageEnhance.Brightness(enhanced_image)
        enhanced_image = enhancer.enhance(float(self.image_preferences["brightness"]))

        # Add contrast enhancement
        enhancer = ImageEnhance.Contrast(enhanced_image)
        enhanced_image = enhancer.enhance(float(self.image_preferences["contrast"]))

        # Add saturation enhancement
        enhancer = ImageEnhance.Color(enhanced_image)
        enhanced_image = enhancer.enhance(float(self.image_preferences["saturation"]))

        return enhanced_image

    def background_only(self, region_scaled_or_none):
        if self.image_preferences["fill_mode"] == "white" or region_scaled_or_none is None:
            return Image.new("RGB", self.target_size, "white")
        else: # blur
            base = region_scaled_or_none.resize(self.target_size, Image.LANCZOS)
            return base.filter(ImageFilter.GaussianBlur(radius=25))

    def export_folder_with_orientation(self):
        return EXPORT_FOLDER + '_' + self.image_preferences["orientation"]
    
    def save_output(self, out_img):
        print(f"→ Source: {self.image_paths[self.idx]}")
        in_path = self.image_paths[self.idx]
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_dir = os.path.join(os.path.dirname(in_path), f"{self.export_folder_with_orientation()}")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base}{EXPORT_FILENAME_SUFFIX}_{self.image_preferences['orientation']}.jpg")
        out_img.save(out_path, format="JPEG", quality=self.app_settings["image_quality"], optimize=True, progressive=True)
        print(f"✔ Crop saved: {out_path}")

    # ---------- Persist state ----------
    def image_state_path(self, img_path: str) -> str:
        dirname = os.path.dirname(img_path)
        basename = os.path.splitext(os.path.basename(img_path))[0]
        return os.path.join(dirname, f"{basename}{STATE_SUFFIX}")

    def save_state(self, img_path: str, x1i: int, y1i: int, x2i: int, y2i: int):
        path = self.image_state_path(img_path)
        iw, ih = self.original_img.size
        nx1 = x1i / iw
        ny1 = y1i / ih
        nx2 = x2i / iw
        ny2 = y2i / ih
        lines = [
            "# PhotoPainter state",
            f"timestamp={int(time.time())}",
            f"image_name={os.path.basename(img_path)}",
            f"image_w={iw}",
            f"image_h={ih}",
            f"rect_x1={x1i:.4f}",
            f"rect_y1={y1i:.4f}",
            f"rect_x2={x2i:.4f}",
            f"rect_y2={y2i:.4f}",
            f"rect_nx1={nx1:.6f}",
            f"rect_ny1={ny1:.6f}",
            f"rect_nx2={nx2:.6f}",
            f"rect_ny2={ny2:.6f}",
            f"target_w={self.target_size[0]}",
            f"target_h={self.target_size[1]}",
            f"ratio={self.ratio:.6f}",
            f"orientation={self.image_preferences['orientation']}",
            f"fill_mode={self.image_preferences['fill_mode']}",
            f"target_device={self.image_preferences['target_device']}",
            f"brightness={self.image_preferences['brightness']}",
            f"contrast={self.image_preferences['contrast']}",
            f"saturation={self.image_preferences['saturation']}",
        ]

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

            print(f"✔ State saved: {path}")

            return img_path
        except Exception as e:
            print(f"[WARN] Unable to save state: {e}")

    def load_keyvalues(self, path: str):
        """
        loads image sidecar file
        
        :param self: Beschreibung
        :param path: state_path_for_image
        :type path: str
        """
        data = {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
        except Exception:
            return None

        return data

    def load_app_settings_or_defaults(self):
        settings_path = "./settings.ini"

        if not os.path.exists(settings_path):
            return False

        settings = {}

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    k, v = line.split("=", 1)
                    settings[k.strip()] = v.strip()
        except Exception:
            return settings

        if settings:
            settings["image_quality"] = int(settings["image_quality"])
        
        else: # DEFAULTS
            settings["window_min"]=WINDOW_MIN
            settings["save_filelist"]=SAVE_FILELIST
            settings["image_target_size"]=DEFAULT_TARGET_SIZE
            settings["image_quality"]=JPEG_QUALITY
            settings["orientation"]=ORIENTATION
            settings["fill_mode"]=FILL_MODE
            settings["target_device"]=TARGET_DEVICE
            settings["crop_border_color"]=CROP_BORDER_COLOR
            settings["export_folder"]=EXPORT_FOLDER
            settings["export_filename_suffix"]=EXPORT_FILENAME_SUFFIX
            settings["state_suffix"]=STATE_SUFFIX
            settings["convert_folder"]=CONVERT_FOLDER
            settings["raw_folder"]=RAW_FOLDER
            settings["export_raw"]=EXPORT_RAW

        print("Settings", settings)
        return settings

    def load_image_preferences_or_defaults(self, img_path: str) -> bool:
        self.image_preferences = {} # reset to default to prevent usage of old data
        kv_path = self.image_state_path(img_path)

        if os.path.exists(kv_path):
            self.image_preferences = self.load_keyvalues(kv_path)

            if not self.image_preferences:
                return False

        #needed_options = ("orientation", "fill_mode", "target_device", "brightness", "contrast", "saturation")

        if not self.image_preferences: # use app defaults
            print("SET DEFAULT IMAGE PREFS", self.image_preferences, "FROM", self.app_settings)
            self.image_preferences["orientation"] = self.app_settings["orientation"]
            self.image_preferences["fill_mode"] = self.app_settings["fill_mode"]
            self.image_preferences["target_device"] = self.app_settings["target_device"]
            self.image_preferences["brightness"] = defaults["BRIGHTNESS"]
            self.image_preferences["contrast"] = defaults["CONTRAST"]
            self.image_preferences["saturation"] = defaults["SATURATION"]

        # safe values
        if "orientation" in self.image_preferences and (self.image_preferences["orientation"] not in AVAILABLE_ORIENTATIONS):
            print("NO ORIENTATION AVAILABLE")
            self.image_preferences["orientation"] = ORIENTATION

        # Update target_size and ratio for new orientation
        self.update_targetsize_and_ratio()

        if "fill_mode" in self.image_preferences and self.image_preferences["fill_mode"] not in AVAILABLE_FILL_MODES:
            self.image_preferences["fill_mode"] = FILL_MODE

        if "target_device" in self.image_preferences and self.image_preferences["target_device"] not in AVAILABLE_TARGET_DEVICES:
            self.image_preferences["target_device"] = TARGET_DEVICE

        # update button labels
        for name, info in self.option_button_definitions.items():
            self.update_button_text(name, self.image_preferences[name])

        # get safe values and update slider values
        for name, info in self.enhancer_sliders.items():
            if not name in self.image_preferences or (name in self.image_preferences and not (0 <= float(self.image_preferences[name]) <= 2)):
                self.image_preferences[name] = defaults[name.upper()]
            #self.update_slider_value_and_label(name, self.image_preferences[name])

        return True

    def apply_saved_state(self) -> bool:
        keyvalues = self.image_preferences

        # prefer absolute coordinates if the dimensions match
        iw, ih = self.original_img.size

        try:
            saved_w = int(keyvalues.get("image_w", iw))
            saved_h = int(keyvalues.get("image_h", ih))
        except ValueError:
            saved_w, saved_h = iw, ih

        if saved_w == iw and saved_h == ih: # saved values matches real values
            try:
                x1i: float = float(keyvalues["rect_x1"])
                y1i: float = float(keyvalues["rect_y1"])
                x2i: float = float(keyvalues["rect_x2"])
                y2i: float = float(keyvalues["rect_y2"])
            except Exception:
                x1i, y1i, x2i, y2i = self._coords_from_relative_values(keyvalues, iw, ih)
        else:
            x1i, y1i, x2i, y2i = self._coords_from_relative_values(keyvalues, iw, ih)

        if None in (x1i, y1i, x2i, y2i):
            return False

        # convert to display coordinates
        self.calculate_display_coordiantes(x1i, y1i, x2i, y2i)
        self.clamp_crop_rectangle_to_canvas()

        return True

    def _coords_from_relative_values(self, keyvalues, iw: float, ih: float):
        """
        Get percentage values from saved preferences, otherwise return None
        
        :param self: instance
        :param keyvalues: key/values
        :param iw: real image witdh
        :type iw: float
        :param ih: real image height
        :type ih: float
        """
        try:
            nx1: float = float(keyvalues["rect_nx1"])
            ny1: float = float(keyvalues["rect_ny1"])
            nx2: float = float(keyvalues["rect_nx2"])
            ny2: float = float(keyvalues["rect_ny2"])
            return (nx1 * iw, ny1 * ih, nx2 * iw, ny2 * ih)
        except Exception:
            return (None, None, None, None)

    # ---------- Progress ----------
    def next_image(self, _e=None):
        self.idx += 1
        self.show_image()

    def prev_image(self, _e=None):
        self.idx -= 1
        self.show_image()

    def on_skip(self, _e=None):
        print(f"skipped: {self.image_paths[self.idx]}")
        self.next_image()

    def convert_to_bmp(self, in_path: str):
        def progress(step, msg):
            self.update_status_label(f"[{step}/5] {msg}")
            self.window.update_idletasks()

        base = os.path.splitext(os.path.basename(in_path))[0]
        out_dir = os.path.join(os.path.dirname(in_path), f"{self.export_folder_with_orientation()}")
        out_path = os.path.join(out_dir, f"{base}{EXPORT_FILENAME_SUFFIX}_{self.image_preferences['orientation']}.jpg").replace('\\', '/') # complete source path & file of cropped image for convert

        self.update_status_label("Starting conversion…")        # <— start message
        self.window.update_idletasks()          # <— force GUI update before blocking

        converter = Converter() # instantiate Converter class

        try:
            converter.convert(
                in_path=out_path,
                orientation=self.image_preferences["orientation"],
                target_device=self.image_preferences["target_device"],
                dither_method=DITHER_METHOD,
                convert_folder=CONVERT_FOLDER,
                raw_folder=RAW_FOLDER,
                export_raw=EXPORT_RAW,
                progress_callback=progress,
            )
            #self.flash_status(f"Done: {os.path.basename(device_path)}")
        except Exception as e:
            self.update_status_label(f"Conversion failed: {e}")
            raise

def on_closing():
    if messagebox.askokcancel("Quit", "Do you really want to quit?"):
        window.destroy()

if __name__ == "__main__":
    window = tk.Tk()
    app = CropperApp(window)
    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()

    # For future reference:
    # If you want to exit and close the program completely, you should use 
    # root.destroy(), as it stops the mainloop() and destroys the window
    # and all its widgets.
    # If you want to run some infinite loop and don't want to destroy your Tkinter 
    # window and want to execute some code after the root.mainloop() line, you should use
    # root.quit()

    # do something
