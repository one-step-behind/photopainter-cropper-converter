import tkinter as tk
from tkinter import ttk, colorchooser, font

class CanvasTextOverlay:
    def __init__(self, control_frame, canvas_frame, initial_state=None, callback=None):
        """
        :param control_frame: tk.Frame where controls (checkbox, entry, color buttons) will be placed
        :param canvas_frame: tk.Canvas where the text_label will be placed
        :param initial_state: dict with keys: show, text, text_color, bg_color, bottom, right, font_scale_height
        :param callback: function called when any property changes; receives dict with same keys as initial_state
        """
        self.control_frame = control_frame
        self.canvas = canvas_frame
        self.canvas.delete("text_layer")
        self.callback = callback

        self.pil_font_path = "./segoeui.ttf"  # adjust if needed
        self.padding_x = 10
        self.padding_y = 5

        # Default initial state
        self.default_state = {
            "show": False,
            "text": "Sample text",
            "text_color": "#ffffff",
            "bg_color": "#6f6311",
            "bottom": 10,
            "right": 10,
            "font_scale_height": 100,
            "font_scale_divisor": 30,
            "min_font_size": 8,
            "max_font_size": 96,
        }

        if initial_state:
            self.default_state.update(initial_state)

        # State variables
        self.show_var = tk.BooleanVar(value=self.default_state["show"])
        self.text_var = tk.StringVar(value=self.default_state["text"])
        self.text_color = self.default_state["text_color"]
        self.bg_color = self.default_state["bg_color"]
        self.bottom = self.default_state["bottom"]
        self.right = self.default_state["right"]
        self.font_scale_height = self.default_state["font_scale_height"]
        self.font_scale_divisor = self.default_state["font_scale_divisor"]
        self.min_font_size = self.default_state["min_font_size"]
        self.max_font_size = self.default_state["max_font_size"]

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
            padx=self.padding_x,
            pady=self.padding_y,
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

        # Text entry
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

    def set_font_scale_height(self, height):
        self.font_scale_height = height
        self.update_font()

    def update_font(self):
        if self.font_scale_height > 0:
            size = int(max(self.min_font_size, min(self.max_font_size, self.font_scale_height // self.font_scale_divisor)))
            self.font.configure(size=size)

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
        # Font scaling (image-only)
        # --------------------------------------------------
        tk_point_size = max(8, img_height // 20)

        # Convert points → pixels (96 DPI assumed)
        scale = 96 / 72 # 4 / 3
        image_font_px = int(tk_point_size * scale)
        print("tk_point_size / image_font_px", tk_point_size, image_font_px)

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
        padding_x = int(self.padding_x * scale)
        padding_y = int(self.padding_y * scale)

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
                "font_scale_height": self.font_scale_height,
                "font_scale_divisor": self.font_scale_divisor,
            })
