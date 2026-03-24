import tkinter as tk
from tkinter import ttk, colorchooser, font
from utils.textoverlay_defaults import TEXT_OVERLAY_DEFAULTS, FONT_DIVISOR_MIN, FONT_DIVISOR_MAX

class CanvasTextOverlay:
    def __init__(self, control_frame, canvas_frame, callback=None):
        """
        :param control_frame: tk.Frame where controls (checkbox, entry, color buttons) will be placed
        :param canvas_frame: tk.Canvas where the text_label will be placed
        :param callback: function called when any property changes; receives dict with the same keys as TEXT_OVERLAY_DEFAULTS
        """
        self.control_frame = control_frame
        self.canvas = canvas_frame
        self.canvas.delete("text_layer")
        self.callback = callback

        self.pil_font_path = "./segoeui.ttf" # adjust if needed
        self.padding_x = TEXT_OVERLAY_DEFAULTS["padding_x"]
        self.padding_y = TEXT_OVERLAY_DEFAULTS["padding_y"]

        # Get system DPI dynamically from Tkinter
        # winfo_fpixels('1p') returns the point-to-pixel conversion for the current system
        self.system_dpi_scale = self.canvas.winfo_fpixels('1p')
        print(f"System DPI scale detected: {self.system_dpi_scale:.3f} (Tkinter winfo_fpixels)")

        # State from shared defaults.
        self.state = TEXT_OVERLAY_DEFAULTS.copy()

        # State variables
        self.show_var = tk.BooleanVar(value=self.state["show"])
        self.text_var = tk.StringVar(value=self.state["text"])
        self.text_color = self.state["text_color"]
        self.bg_color = self.state["bg_color"]
        self.bottom = self.state["bottom"]
        self.right = self.state["right"]
        self.padding_x = self.state["padding_x"]
        self.padding_y = self.state["padding_y"]
        self.font_divisor = self._clamp_font_divisor(self.state["font_divisor"])
        self.font_target_height = 0.0
        self.font_preview_height = 0.0
        self.min_font_size = self.state["min_font_size"]
        self.max_font_size = self.state["max_font_size"]
        self.image_dpi_scale = self.state["image_dpi_scale"]
        self._syncing_slider = False

        # Font configuration
        self.font_face = "Segoe UI"
        self.font = font.Font(family=self.font_face, size=10)

        # --- Controls ---
        self._create_controls()

        # --- Text label on canvas ---
        self.text_label = tk.Label(
            self.canvas,
            text=self.text_var.get(),
            font=self.font,
            fg=self.text_color,
            bg=self.bg_color,
            padx=int(self.padding_x * self.system_dpi_scale),
            pady=int(self.padding_y * self.system_dpi_scale),
        )
        self.text_window = self.canvas.create_window(
            self.right,
            self.bottom,
            window=self.text_label,
            anchor="se",
            state="normal" if self.show_var.get() else "hidden",
            tags=("text_layer"),
        )
        # Ensure text_window is on top
        self.canvas.tag_raise(self.text_window)

        # Bind entry changes
        self.text_var.trace_add("write", self._on_text_change)

        # Apply initial scaling
        self.update_font()

    # ----------------------
    # Control creation
    # ----------------------
    def _create_controls(self):
        # Checkbox
        self.checkbox = ttk.Checkbutton(
            self.control_frame,
            text="Show text on canvas",
            variable=self.show_var,
            command=self._on_show_change
        )
        self.checkbox.pack(fill=tk.X)

        # Text field
        ttk.Label(self.control_frame, text="Text:").pack(padx=(10, 2))
        self.entry = ttk.Entry(self.control_frame, textvariable=self.text_var, width=30)
        self.entry.pack()

        # Text color button
        self.text_color_btn = ttk.Button(
            self.control_frame,
            text="Text color",
            command=self._pick_text_color
        )
        self.text_color_btn.pack(padx=5)

        # Background color button
        self.bg_color_btn = ttk.Button(
            self.control_frame,
            text="Background color",
            command=self._pick_bg_color
        )
        self.bg_color_btn.pack()

        # Initial state
        self._update_controls_state()

    # ----------------------
    # Event handlers
    # ----------------------
    def _on_show_change(self):
        state = "normal" if self.show_var.get() else "hidden"
        self.canvas.itemconfigure(self.text_window, state=state)
        self._update_controls_state()
        self._trigger_callback()

    def _on_text_change(self, *args):
        self.text_label.config(text=self.text_var.get())
        self._trigger_callback()

    def _pick_text_color(self):
        color = colorchooser.askcolor(initialcolor=self.text_color)[1]
        if color:
            self.text_color = color
            self.text_label.config(fg=color)
            self._trigger_callback()

    def _pick_bg_color(self):
        color = colorchooser.askcolor(initialcolor=self.bg_color)[1]
        if color:
            self.bg_color = color
            self.text_label.config(bg=color)
            self._trigger_callback()

    def _update_controls_state(self):
        state = "normal" if self.show_var.get() else "disabled"
        self.entry.config(state=state)
        self.text_color_btn.config(state=state)
        self.bg_color_btn.config(state=state)

    # ----------------------
    # Public API
    # ----------------------
    def set_all(self, payload):
        print("set all", payload)
        self.set_show(payload["show"])
        self.set_text(payload["text"])
        self.set_colors(text_color = payload["text_color"], bg_color=payload["bg_color"])
        if "font_divisor" in payload:
            self.set_font_divisor(payload["font_divisor"])
        if "image_dpi_scale" in payload:
            self.set_image_dpi_scale(payload["image_dpi_scale"])

    def set_text(self, text):
        self.text_var.set(text)

    def set_show(self, show: bool):
        self.show_var.set(show)
        self._on_show_change()

    def set_colors(self, text_color=None, bg_color=None):
        if text_color:
            self.text_color = text_color
            self.text_label.config(fg=text_color)
        if bg_color:
            self.bg_color = bg_color
            self.text_label.config(bg=bg_color)
        self._trigger_callback()

    def set_position(self, bottom=None, right=None):
        if bottom is not None:
            self.bottom = bottom
        if right is not None:
            self.right = right
        self.canvas.coords(self.text_window, self.right, self.bottom)

    def set_font_divisor(self, divisor):
        """Set relative divisor: target text px = min(target_w,target_h)/divisor."""
        self.font_divisor = float(max(1.0, divisor))

    def set_font_px(self, target_px, preview_px):
        self.font_target_height = float(max(1.0, target_px))
        self.font_preview_height = float(max(1.0, preview_px))
        self.update_font()

    def set_image_dpi_scale(self, scale):
        """Adjust the DPI scale factor for image rendering (0.8-1.5 typical range)"""
        self.image_dpi_scale = scale

    def update_font(self):
        if self.font_preview_height > 0:
            # Convert absolute preview pixel size to font points using system DPI
            pts_float = self.font_preview_height / self.system_dpi_scale
            pts = int(max(self.min_font_size, min(self.max_font_size, round(pts_float))))
            self.font.configure(size=pts)
            print(f"Canvas font set to: {pts}pt (preview_px {self.font_preview_height:.2f}, sys_dpi {self.system_dpi_scale:.3f})")

    def render_text_overlay_on_image(self, image):
        """
        Render the current text overlay state onto a PIL Image.
        All sizes and positions are recalculated exclusively
        from the image dimensions.
        """

        if not self.show_var.get():
            return image

        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(image)
        img_width, img_height = image.size

        # --------------------------------------------------
        # Font scaling (image-only): use absolute final image pixel height.
        # --------------------------------------------------
        image_font_px = int(max(self.min_font_size, min(self.max_font_size, round(self.font_target_height * self.image_dpi_scale))))
        print(f"Font scaling: target_px={self.font_target_height:.2f}, final_px={image_font_px}, image_dpi_scale={self.image_dpi_scale:.3f}")

        font = ImageFont.truetype(self.pil_font_path, image_font_px)

        # --------------------------------------------------
        # Text and colors
        # --------------------------------------------------
        text = self.text_var.get()
        text_color = self.text_color
        bg_color = self.bg_color

        # --------------------------------------------------
        # Padding (derived from font size)
        # --------------------------------------------------
        padding_x = int(self.padding_x * self.image_dpi_scale)
        padding_y = int(self.padding_y * self.image_dpi_scale)

        # --------------------------------------------------
        # Measure text
        # --------------------------------------------------
        bbox = draw.textbbox((0, 0), text, font=font)

        left, top, right, bottom = bbox
        ascent, descent = font.getmetrics()

        text_width  = right - left
        text_height = ascent + descent

        box_width = text_width + 2 * padding_x
        box_height = text_height + 2 * padding_y

        # --------------------------------------------------
        # Bottom-right anchoring (image space)
        # --------------------------------------------------
        x1 = img_width
        y1 = img_height
        x0 = x1 - box_width
        y0 = y1 - box_height

        # --------------------------------------------------
        # Draw background
        # --------------------------------------------------
        draw.rectangle((x0, y0, x1, y1), fill=bg_color)

        # --------------------------------------------------
        # Draw text
        # --------------------------------------------------
        text_x = x0 + padding_x - left
        text_y = y0 + padding_y

        draw.text(
            (
                text_x,
                text_y + ascent
            ),
            text,
            fill=text_color,
            font=font,
            anchor="ls"
        )

        return image

    # ----------------------
    # Callback trigger
    # ----------------------
    def _trigger_callback(self):
        if self.callback:
            self.callback({
                "show": self.show_var.get(),
                "text": self.text_var.get(),
                "text_color": self.text_color,
                "bg_color": self.bg_color,
                "bottom": self.bottom,
                "right": self.right,
                "font_divisor": self.font_divisor,
                "image_dpi_scale": self.image_dpi_scale,
            })
