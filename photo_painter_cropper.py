#encoding: utf-8
#!/usr/bin/env python3

import os
import sys
import math
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageFilter # pyright: ignore[reportMissingImports]

# ====== CONFIG ======
APP_TITLE = "PhotoPainterCropper"
DEFAULT_TARGET_SIZE = (800, 480)           # exact JPG output
DEFAULT_RATIO = DEFAULT_TARGET_SIZE[0] / DEFAULT_TARGET_SIZE[1]
WINDOW_MIN = (1024, 768)
JPEG_QUALITY = 90
DIRECTION = "landscape" # landscape | portrait
FILL_MODE = "blur" # white | blur
CONVERT_DITHER = 3 # NONE(0) or FLOYDSTEINBERG(3)

CROP_BORDER_COLOR = "#00ff00"   # green rectangle border
GRID_COLOR = "#00ff00"          # grid lines
MASK_COLOR = "#000000"          # mask outside crop region
MASK_STIPPLE = "gray50"
WINDOW_BACKGROUND_COLOR = "#222222"

ARROW_STEP = 1                      # px for step with arrows
ARROW_STEP_FAST = 10                # px with Shift pressed
SCALE_FACTOR = 1.01                 # zoom step with normal +/-
SCALE_FACTOR_FAST = 1.10            # zoom step with Shift

LABEL_PADDINGS = (5, 5)

EXPORT_FOLDER = "cropped" # folder where to store cropped images
EXPORT_FILENAME_SUFFIX = "_pp"
STATE_SUFFIX = "_ppcrop.txt"        # file status next to the source image
CONVERT_FOLDER = "dithered" # folder where to store converted/dithered images
DEVICE_FOLDER = "device" # folder where to store real-world RGB to device RGB images
RAW_FOLDER = "raw" # folder where to store raw images
EXPORT_RAW = False # should export raw image suitable for SPECTRA6 use?

def resource_path(relative_path):    
    #try:
    #    base_path = sys.prefix
    #except Exception:
    #    base_path = os.path.abspath(".")

    if not hasattr(sys, "frozen"):
        base_path = os.path.dirname(__file__)
    else:
        base_path = sys.prefix

    return os.path.join(base_path, relative_path)

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

class CropperApp:
    def __init__(self, root):
        self._resize_pending = False
        self.root = root
        self.root.minsize(*WINDOW_MIN)
        self.root.iconbitmap(default=resource_path("./_source/icon.ico"))
        self.root.title(f"{APP_TITLE} – "
            "Drag/Arrows=move (Shift=+fast)  •  "
            "Scroll/+/-=resize (Shift=+fast)  •  "
            "Esc=skip"
        )

        self.style = ttk.Style()

        top = ttk.Frame(root)
        top.pack(fill=tk.X, side=tk.TOP)

        self.canvas = tk.Canvas(root, bg=WINDOW_BACKGROUND_COLOR)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # ---------- Button UI ----------
        self.button_bar = ttk.Frame(top)
        self.button_bar.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], anchor=tk.W, fill=tk.X, side=tk.TOP)

        # Define buttons with text variable, command, optional params, styling, and optional hover tip
        self.btn_defs = {
            "direction": {
                "default_text": "Direction",
                "command": self.toggle_direction,
                "enter_tip": "Toggle Direction (D)",
                "width": 22,
                "underline": 0, 
            },
            "fillmode": {
                "default_text": "Fill Mode",
                "command": self.toggle_fill_mode,
                "enter_tip": "Toggle Fill mode (F)",
                "width": 22,
                "underline": 0, 
            },
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

        # Store the actual Button widgets
        self.button_vars = {} # DynamicButtonVar objects
        self.buttons = {}

        # Build buttons
        self.create_buttons()

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
        self.bottom_bar = ttk.Frame(self.root)
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label_var = tk.StringVar(value="Select folder with images…")
        self.status_label = ttk.Label(self.bottom_bar, textvariable=self.status_label_var, anchor=tk.W)
        self.status_label.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], anchor=tk.W, fill=tk.X, side=tk.LEFT)

        self.status_count = ttk.Label(self.bottom_bar, text="0/0")
        self.status_count.pack(padx=LABEL_PADDINGS[0], pady=LABEL_PADDINGS[1], side=tk.RIGHT)
        
        # Mouse events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)     # mac/win
        self.canvas.bind("<Button-4>", self.on_wheel_linux) # linux up
        self.canvas.bind("<Button-5>", self.on_wheel_linux) # linux down

        # Keyboard events
        self.root.bind("<Return>", self.on_confirm)
        self.root.bind_all("<Tab>", self.on_confirm_tab)    # Tab intercept (prevent focus change)
        self.root.bind("<s>", self.on_confirm)
        self.root.bind("<S>", self.on_confirm)
        self.root.bind("<Prior>", self.prev_image) # PAGE UP
        self.root.bind("<Next>", self.next_image) # PAGE DOWN
        self.root.bind("<Escape>", self.on_skip)

        # Keyboard events (movement)
        self.root.bind("<Left>",  lambda e: self.on_arrow(e, -1,  0))
        self.root.bind("<Right>", lambda e: self.on_arrow(e,  1,  0))
        self.root.bind("<Up>",    lambda e: self.on_arrow(e,  0, -1))
        self.root.bind("<Down>",  lambda e: self.on_arrow(e,  0,  1))

        # Keyboard events (resize)
        for ks in ("<plus>", "<KP_Add>", "<equal>"):  # '+' It's often Shift+'='; include '=' for convenience
            self.root.bind(ks, self.on_plus)
        for ks in ("<minus>", "<KP_Subtract>"):
            self.root.bind(ks, self.on_minus)

        # Various
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<f>", self.toggle_fill_mode)
        self.root.bind("<F>", self.toggle_fill_mode)
        self.root.bind("<d>", self.toggle_direction)
        self.root.bind("<D>", self.toggle_direction)

        # State
        self.direction = DIRECTION
        self.fill_mode = FILL_MODE

        self.img: Image = None
        self.disp_img = None
        self.tk_img = None
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

        self.root.after(200, self.delayed_start)

    # ---------- UI helpers ----------
    def delayed_start(self):
        # ensure window is fully realized
        self.root.update()
        self.canvas.focus_set()       # keyboard focus works now
        self.load_folder()

    def update_size_lbl(self):
        w, h = self.target_size
        self.size_lbl_var.set(f"Crop {w}x{h}")

    def create_buttons(self):
        # Create buttons dynamically
        for name, info in self.btn_defs.items():

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

            # 3) Create the button
            #    COMMAND MUST BE PASSED DIRECTLY!!!
            btn = ttk.Button(self.button_bar, command=info["command"], **btn_kwargs)
            btn.pack(side=tk.LEFT, padx=5)
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
        if button_name in self.btn_defs:
            self.button_vars[button_name].update(extra_text)
        else:
            print(f"No button variable found for '{button_name}'")

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
            self.root.after(50, self.root.quit)
            return

        self.image_paths = [
            os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"))
        ]

        if not self.image_paths:
            messagebox.showerror("No image", "The folder contains no images.")
            self.root.after(50, self.root.quit)
            return

        self.show_image()

    def show_image(self):
        if self.idx >= len(self.image_paths):
            messagebox.showinfo("Done", "All images have been processed.")
            self.root.after(50, self.root.quit)
            return

        if self.idx < 0:
            self.idx = len(self.image_paths)-1

        current_image_path = self.image_paths[self.idx]

        try:
            self.img = self.load_image_by_exif_orientation(current_image_path) # EXIF auto-rotate
        except Exception as e:
            messagebox.showwarning("Image error", f"Unable to open:\n{current_image_path}\n{e}\nWe move on to the next one.")
            self.idx += 1
            self.show_image()
            return

        self.layout_image()

        # restore state if it exists; otherwise initial pane
        if not self.load_saved_state(current_image_path):
            self.init_rect()

        self.status_count.config(text=f"{self.idx+1}/{len(self.image_paths)}")
        self.update_size_lbl() # after loading state
        self.update_status_label(f"{current_image_path}")
        self.draw_crop_marker_grid()

    def load_image_by_exif_orientation(self, path: str) -> Image:
        """
        Loads an image and applies EXIF orientation correction (auto-rotate).
        Returns an RGB image with correct orientation.
        """
        try:
            im = Image.open(path)

            try:
                # modern Pillow: .getexif()
                exif = im.getexif()
                orientation = exif.get(0x0112, 1)  # EXIF Orientation
            except Exception:
                orientation = 1

            # Rotate according to EXIF orientation tag
            if orientation == 3:
                im = im.rotate(180, expand=True)
            elif orientation == 6:
                im = im.rotate(270, expand=True)  # 90° CW
            elif orientation == 8:
                im = im.rotate(90, expand=True)   # 90° CCW

            # Convert only after orientation repair
            return im.convert("RGB")

        except Exception as e:
            print("EXIF load/rotation failed:", e)
            return Image.open(path).convert("RGB")

    # ---------- Layout & Drawing ----------
    def canvas_size(self):
        # Return REAL canvas size (never force minimum)
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def layout_image(self):
        cw, ch = self.canvas_size()
        iw, ih = self.img.size
        self.scale = min(cw / iw, ch / ih)
        disp_w = max(1, int(iw * self.scale))
        disp_h = max(1, int(ih * self.scale))
        self.disp_size = (disp_w, disp_h)
        self.disp_img = self.img.resize((disp_w, disp_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        self.img_off = ((cw - disp_w) // 2, (ch - disp_h) // 2)

    def init_rect(self):
        """
        Initialize crop rectangle
        """
        dw, dh = self.disp_size
        rw = int(dw)# * 0.8) # cropper size 80% of image size
        rh = int(rw / self.ratio)
        if rh > dh:
            rh = int(dh)# * 0.8) # cropper size 80% of image size
            rw = int(rh * self.ratio)
        self.rect_w, self.rect_h = max(20, rw), max(20, rh)
        cx = self.img_off[0] + dw // 2
        cy = self.img_off[1] + dh // 2
        self.rect_center = (cx, cy)
        self.clamp_rect_to_canvas()

    def rect_coords(self):
        cx, cy = self.rect_center
        w2 = self.rect_w // 2
        h2 = self.rect_h // 2

        return (cx - w2, cy - h2, cx + w2, cy + h2)

    def clamp_rect_to_canvas(self):
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

        self.canvas.delete("all") # remove previous grid

        # image
        self.canvas.create_image(self.img_off[0], self.img_off[1], anchor="nw", image=self.tk_img)

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
            self.clamp_rect_to_canvas()
            self.draw_crop_marker_grid()

    def on_drag(self, e):
        if not self.dragging:
            return

        self.rect_center = (e.x - self.drag_offset[0], e.y - self.drag_offset[1])
        self.clamp_rect_to_canvas()
        self.draw_crop_marker_grid()

    def on_release(self, _e):
        self.dragging = False

    def on_wheel(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        self.resize_rect_mouse(1 if e.delta > 0 else -1, fast)

    def on_wheel_linux(self, e):
        fast = bool(e.state & 0x0001)  # Shift
        self.resize_rect_mouse(1 if e.num == 4 else -1, fast)

    def resize_rect_mouse(self, direction, fast):
        speed = SCALE_FACTOR_FAST if fast else SCALE_FACTOR
        factor = speed if direction > 0 else (1 / speed)
        self.apply_resize_factor(factor)

    # ---------- Keyboard ----------
    def on_confirm_tab(self):
        self.next_image()

        return "break"  # avoid changing Tab focus

    def on_arrow(self, e, dx, dy):
        step = ARROW_STEP_FAST if (e.state & 0x0001) else ARROW_STEP  # Shift accelerates
        self.rect_center = (self.rect_center[0] + dx*step, self.rect_center[1] + dy*step)
        self.clamp_rect_to_canvas()
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
        self.clamp_rect_to_canvas()
        self.draw_crop_marker_grid()

    def on_resize(self, _e):
        """
        Window resize
        
        :param self: instance
        """
        if self.img is None:
            return

        if self._resize_pending:
            return

        self._resize_pending = True
        self.root.after(30, self._apply_resize)

    def _apply_resize(self):
        """
        Apply resize
        
        :param self: instance
        """
        self._resize_pending = False

        if self.img is None:
            return
        
        rect_img_raw = self.rect_in_image_coords_raw()
        self.layout_image()
        x1i, y1i, x2i, y2i = rect_img_raw
        x1d = self.img_off[0] + int(x1i * self.scale)
        y1d = self.img_off[1] + int(y1i * self.scale)
        x2d = self.img_off[0] + int(x2i * self.scale)
        y2d = self.img_off[1] + int(y2i * self.scale)
        self.rect_w = max(1, x2d - x1d)
        self.rect_h = int(self.rect_w / self.ratio)
        self.rect_center = ((x1d + x2d)//2, (y1d + y2d)//2)
        self.clamp_rect_to_canvas()
        self.draw_crop_marker_grid()

    # ---------- Toggles ----------
    def toggle_fill_mode(self, _e=None):
        self.fill_mode = "blur" if self.fill_mode == "white" else "white"
        self.update_button_text("fillmode", self.fill_mode)

    def toggle_direction(self, _e=None):
        # Switch internal state
        self.direction = "portrait" if self.direction == "landscape" else "landscape"

        # Update target_size and ratio for new direction
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
        self.clamp_rect_to_canvas()

        # Update title + label + redraw
        self.update_size_lbl() # after direction toggle
        self.update_button_text("direction", self.direction)
        self.draw_crop_marker_grid()

    def update_targetsize_and_ratio(self):
        if self.direction == "portrait":
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
        iw, ih = self.img.size
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
            region_scaled = self.img.crop((ix1, iy1, ix2, iy2)).resize((int_w_tgt, int_h_tgt), Image.LANCZOS)
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

        # 5) save image
        self.save_output(out)

        # 6) save state (txt) next to the source
        self.save_state(in_path, x1i, y1i, x2i, y2i)

        # 7) convert to 24 bit BMP
        self.convert_to_bmp(in_path)

        # 8) next image
        self.next_image()

    def background_only(self, region_scaled_or_none):
        if self.fill_mode == "white" or region_scaled_or_none is None:
            return Image.new("RGB", self.target_size, "white")
        else:
            base = region_scaled_or_none.resize(self.target_size, Image.LANCZOS)
            return base.filter(ImageFilter.GaussianBlur(radius=25))

    def export_folder_with_direction(self):
        return EXPORT_FOLDER + '_' + self.direction
    
    def save_output(self, out_img):
        print(f"→ Source: {self.image_paths[self.idx]}")
        in_path = self.image_paths[self.idx]
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_dir = os.path.join(os.path.dirname(in_path), f"{self.export_folder_with_direction()}")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base}{EXPORT_FILENAME_SUFFIX}_{self.direction}.jpg")
        out_img.save(out_path, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        print(f"✔ Crop saved: {out_path}")

    # ---------- Persist state ----------
    def image_state_path(self, img_path: str) -> str:
        dirname = os.path.dirname(img_path)
        basename = os.path.splitext(os.path.basename(img_path))[0]
        return os.path.join(dirname, f"{basename}{STATE_SUFFIX}")

    def save_state(self, img_path: str, x1i: int, y1i: int, x2i: int, y2i: int):
        path = self.image_state_path(img_path)
        iw, ih = self.img.size
        nx1 = x1i / iw
        ny1 = y1i / ih
        nx2 = x2i / iw
        ny2 = y2i / ih
        lines = [
            "# PhotoPainter crop state",
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
            f"fill_mode={self.fill_mode}",
            f"direction={self.direction}",
        ]

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            print(f"✔ State saved: {path}")
            return img_path
        except Exception as e:
            print(f"[WARN] Unable to save state: {e}")

    def convert_to_bmp(self, in_path: str):
        def progress(step, msg):
            self.update_status_label(f"[{step}/5] {msg}")
            self.root.update_idletasks()

        base = os.path.splitext(os.path.basename(in_path))[0]
        out_dir = os.path.join(os.path.dirname(in_path), f"{self.export_folder_with_direction()}")
        out_path = os.path.join(out_dir, f"{base}{EXPORT_FILENAME_SUFFIX}_{self.direction}.jpg").replace('\\', '/') # complete source path & file of cropped image for convert

        self.update_status_label("Starting conversion…")        # <— start message
        self.root.update_idletasks()          # <— force GUI update before blocking

        conv = Converter() # instantiate Converter class

        try:
            preview_path, device_path = conv.convert(
                in_path=out_path,
                direction=self.direction,
                dither=CONVERT_DITHER,
                progress_callback=progress
            )
            #self.flash_status(f"Done: {os.path.basename(device_path)}")
        except Exception as e:
            self.update_status_label(f"Conversion failed: {e}")
            raise

    def load_keyvalues(self, path: str):
        """
        loads crops state from sidecar file
        
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

    def load_saved_state(self, img_path: str) -> bool:
        kv_path = self.image_state_path(img_path)

        if not os.path.exists(kv_path):
            return False

        keyvalues = self.load_keyvalues(kv_path)

        if not keyvalues:
            return False

        iw, ih = self.img.size

        # reports direction if present
        if keyvalues.get("direction") in ("landscape", "portrait"):
            # 1) apply direction from state file
            self.direction = keyvalues["direction"]


            # 2) Update target_size and ratio for new direction
            self.update_targetsize_and_ratio()

            # 3) update label
            self.update_button_text("direction", self.direction)

        # reports fill mode if present
        if keyvalues.get("fill_mode") in ("white", "blur"):
            self.fill_mode = keyvalues["fill_mode"]
            self.update_button_text("fillmode", self.fill_mode)

        # prefer absolute coordinates if the dimensions match
        try:
            saved_w = int(keyvalues.get("image_w", iw))
            saved_h = int(keyvalues.get("image_h", ih))
        except ValueError:
            saved_w, saved_h = iw, ih

        if saved_w == iw and saved_h == ih:
            try:
                x1i: float = float(keyvalues["rect_x1"])
                y1i: float = float(keyvalues["rect_y1"])
                x2i: float = float(keyvalues["rect_x2"])
                y2i: float = float(keyvalues["rect_y2"])
            except Exception:
                x1i, y1i, x2i, y2i = self._coords_from_normalized(keyvalues, iw, ih)
        else:
            x1i, y1i, x2i, y2i = self._coords_from_normalized(keyvalues, iw, ih)

        if None in (x1i, y1i, x2i, y2i):
            return False

        # convert to display coordinates
        x1d = self.img_off[0] + int(x1i * self.scale)
        y1d = self.img_off[1] + int(y1i * self.scale)
        x2d = self.img_off[0] + int(x2i * self.scale)
        y2d = self.img_off[1] + int(y2i * self.scale)

        # reconstruct rectangle while maintaining a fixed ratio
        w = x2d - x1d
        h = y2d - y1d
        # ensure based on ratio
        if abs(w / h - self.ratio) > 0.001:
            h = int(w / self.ratio)
        cx = (x1d + x2d) // 2
        cy = (y1d + y2d) // 2

        self.rect_w = w
        self.rect_h = h
        self.rect_center = (cx, cy)
        self.clamp_rect_to_canvas()

        return True

    def _coords_from_normalized(self, kv, iw: float, ih: float):
        try:
            nx1: float = float(kv["rect_nx1"])
            ny1: float = float(kv["rect_ny1"])
            nx2: float = float(kv["rect_nx2"])
            ny2: float = float(kv["rect_ny2"])
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

# =======================
#  IMAGE CONVERTER
# =======================

class Converter:
    """
    Integrated converter for ESP32-S3 PhotoPainter.
    No CLI, no sys.exit(), completely embeddable.
    Call Converter.convert() directly from your Tkinter app.
    Supports progress callbacks.
    """

    ACEP_REAL_WORLD_RGB = [
        (25, 30, 33), # BLACK #191E21
        (241, 241, 241), # WHITE #F1F1F1
        (243, 207, 17), # YELLOW #F3CF11
        (210, 14, 19),# RED #D20E13
        (49, 49, 143),# BLUE #31318F
        (83, 164, 40), # GREEN #53A428
        (184, 94, 28), # ORANGE #B85E1C
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

    def __init__(self):
        # constant-time lookup table: Faster mapping: real_world_color → index
        self._rgb_to_index = {
            rgb: i for i, rgb in enumerate(self.ACEP_REAL_WORLD_RGB)
        }

        # prebuild palette
        palette = (
            tuple(v for rgb in self.ACEP_REAL_WORLD_RGB for v in rgb) + self.ACEP_REAL_WORLD_RGB[0] * 249
        )

        self._palette_image = Image.new("P", (1, 1))
        self._palette_image.putpalette(palette)

    # -----------------------
    # main API
    # -----------------------
    def convert(self, in_path: str, direction: str=DIRECTION, dither=Image.FLOYDSTEINBERG, progress_callback=None):
        """
        Converts one RGB image into:
        - quantized preview BMP
        - quantized device BMP

        Returns (bmp_out, dev_out)

        progress_callback(step:int, message:str) is optional.
        
        :param self: instance
        :param in_path: image path
        :type in_path: str
        :param direction: landscape | portrait
        :type direction: str
        :param dither: dither method
        :param progress_callback: callback for progress
        """

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
        quant = img.quantize(dither=dither, palette=self._palette_image)
        quant_rgb = quant.convert("RGB")

        # -------------------
        # Build output paths and save quantized image
        # -------------------
        report(3, "Save BMP…")
        basedir = os.path.dirname(in_path)
        output_basename_without_ext = os.path.splitext(os.path.basename(in_path))[0]

        # Prepare folders if not exist
        convert_dir = os.path.join(basedir, f"{CONVERT_FOLDER}")
        convert_out_dir = os.path.join(convert_dir, f"{output_basename_without_ext}_{direction}.bmp")
        os.makedirs(convert_dir, exist_ok=True)

        device_dir = os.path.join(convert_dir, f"{DEVICE_FOLDER}")
        device_out_dir = os.path.join(device_dir, f"{output_basename_without_ext}_{direction}.bmp")
        os.makedirs(device_dir, exist_ok=True)

        raw_out_dir: str = ""
        if EXPORT_RAW:
            raw_dir = os.path.join(convert_dir, f"{RAW_FOLDER}")
            raw_out_dir = os.path.join(raw_dir, f"{output_basename_without_ext}_{direction}.sp6")
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
                px[x, y] = self.ACEP_DEVICE_RGB[idx]
                raw = self.ACEP_DEVICE_INDEX_TO_RAW[idx]

                if not odd:
                    if EXPORT_RAW:
                        pending = raw
                    odd = True
                else:
                    if EXPORT_RAW:
                        raw_bytes.append((pending << 4) | raw)
                    odd = False

        # save device BMP
        # BMP images intended to be used on devices that takes BMP.
        # They look bad on computer, but should look regular on e-ink screens.
        # For example, with the waveshare stock PhotoPainter firmware, you can copy
        # the BMP files to the SD card.
        quant_rgb.save(device_out_dir)

        # Produce raw image suitable for SPECTRA6 use.
        # Raw data (1 pixel = 4 bits, 2 pixels = 1 byte) to be used by
        # low-level device functions. Requires need some coding skills to use they
        # properly. They are 6x smaller than BMPs so they can reduce ESP32 processing
        # time and memory usage, and are more reliable to transmit over Wi-Fi.
        if EXPORT_RAW:
            report(5, "Saving RAW bytes…")
            with open(raw_out_dir, "wb") as f:
                f.write(raw_bytes)

        print(f"✔ Converted: {in_path}")
        print(f"   → Preview BMP: {convert_out_dir}")
        print(f"   → Device BMP : {device_out_dir}")
        if EXPORT_RAW:
            print(f"   → Raw image data : {raw_out_dir}")

        report(6 if EXPORT_RAW else 5, f"Done: {device_out_dir}")

        return convert_out_dir, device_out_dir

if __name__ == "__main__":
    root = tk.Tk()
    app = CropperApp(root)
    root.mainloop()
