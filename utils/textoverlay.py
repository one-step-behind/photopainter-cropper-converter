import tkinter as tk
from tkinter import ttk, colorchooser, font
import re
from typing import Any, cast
from geopy.geocoders import Nominatim
from PIL import Image, ExifTags
from utils.textoverlay_defaults import TEXT_OVERLAY_DEFAULTS, FONT_DIVISOR_MIN, FONT_DIVISOR_MAX
from utils.keybinds import bind_toggle_keys

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
        self.location_var = tk.BooleanVar(value=self.state.get("use_location", False))
        self.text_var = tk.StringVar(value=self.state["text"])
        self.text_color = self.state["text_color"]
        self.bg_color = self.state["bg_color"]
        self.location_text = ""
        self._last_applied_location_text = ""
        self.derived_location_name = None
        self.current_image_path = None
        self.has_exif_data = False
        self.current_year = None
        self._reverse_geocode_cache = {}
        self._geolocator = Nominatim(user_agent="PhotoPainterCropper/1.0")
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
        self._create_canvas_textlabel()

        # Bind entry changes
        self.text_var.trace_add("write", self._on_text_change)

        # Apply initial scaling
        self.update_font()

    # ----------------------
    # Control creation
    # ----------------------
    def _create_controls(self):

        ttk.Separator(self.control_frame).pack(fill=tk.X, pady=5)

        # Text on Canvas checkbox
        self.checkbox = ttk.Checkbutton(
            self.control_frame,
            text="Show text on canvas",
            variable=self.show_var,
            command=self._on_show_change
        )
        self.checkbox.pack(fill=tk.X, padx=5)

        self.location_checkbox_style = "OverlayLocation.TCheckbutton"
        self.control_style = ttk.Style(self.control_frame)
        self.control_style.map(
            self.location_checkbox_style,
            foreground=[("disabled", "#666666")],
        )

        self.location_checkbox = ttk.Checkbutton(
            self.control_frame,
            text="Location",
            variable=self.location_var,
            command=self._on_location_change,
            style=self.location_checkbox_style,
        )
        self.location_checkbox.pack(fill=tk.X, padx=5)

        self.location_refresh_btn = ttk.Button(
            self.control_frame,
            text="Refresh location",
            command=self.refresh_location_metadata,
            takefocus=0,
        )
        self.location_refresh_btn.pack(fill=tk.X, padx=5)

        # Text field
        ttk.Label(self.control_frame, text="Text:", justify=tk.LEFT).pack(fill=tk.X, padx=5, pady=(5, 0))
        self.entry = ttk.Entry(self.control_frame, textvariable=self.text_var, width=30)
        self.entry.pack()

        # Text size slider. Higher divisors mean smaller text, so the slider
        # runs from high to low to make left=smaller and right=bigger.
        self.slider_label_var = tk.StringVar()
        self.slider_label = ttk.Label(self.control_frame, textvariable=self.slider_label_var, justify=tk.LEFT)
        self.slider_label.pack(fill=tk.X, padx=5, pady=(5, 0))
        self.slider = tk.Scale(
            self.control_frame,
            from_=FONT_DIVISOR_MAX,
            to=FONT_DIVISOR_MIN,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            showvalue=False,
            takefocus=0,
            command=self._on_slider_change,
        )
        self.slider.pack(fill=tk.X, padx=5, pady=0)
        self._set_slider_from_divisor(self.font_divisor)
        self._update_slider_label(self.font_divisor)

        self.slider_hint_frame = ttk.Frame(self.control_frame)
        self.slider_hint_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Label(self.slider_hint_frame, text="Smaller").pack(side=tk.LEFT)
        ttk.Label(self.slider_hint_frame, text="Bigger").pack(side=tk.RIGHT)

        self.color_button_row = ttk.Frame(self.control_frame)
        self.color_button_row.pack(fill=tk.X, padx=5, pady=5)

        # Text and background color buttons share one row.
        self.text_color_btn = ttk.Button(
            self.color_button_row,
            text="Text color",
            command=self._pick_text_color
        )
        self.text_color_btn.pack(side=tk.LEFT, padx=0)

        self.bg_color_btn = ttk.Button(
            self.color_button_row,
            text="Background color",
            command=self._pick_bg_color
        )
        self.bg_color_btn.pack(side=tk.RIGHT, padx=0)

        ttk.Separator(self.control_frame).pack(fill=tk.X, pady=5)

        # Keyboard shortcut: Ctrl+B opens background color picker.
        bind_toggle_keys(
            self.control_frame.winfo_toplevel(),
            {"toggle_key": ("<Control-b>", "<Control-B>")},
            self._on_bg_color_shortcut,
        )

        # Initial state
        self._update_controls_state()


    # ----------------------
    # Text on canvas creation
    # ----------------------
    def _create_canvas_textlabel(self):
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
        self.canvas.tag_raise("text_layer")

    # ----------------------
    # Event handlers
    # ----------------------
    def _on_show_change(self):
        state = "normal" if self.show_var.get() else "hidden"
        self.canvas.itemconfigure(self.text_window, state=state)

        if self.show_var.get() and self.location_var.get():
            self._refresh_location_for_current_context(force_refresh=False)

        self._update_controls_state()
        self._trigger_callback()

    def _on_location_change(self):
        if self.location_var.get() and self.show_var.get():
            self._refresh_location_for_current_context(force_refresh=False)

        if self.location_var.get() and self.location_text:
            self._apply_location_text(force=True)
        self._update_controls_state()
        self._trigger_callback()

    def _on_text_change(self, *args):
        self.text_label.config(text=self.text_var.get())
        self._trigger_callback()

    def _on_slider_change(self, value):
        if self._syncing_slider:
            return
        self.font_divisor = self._clamp_font_divisor(value)
        self._update_slider_label(self.font_divisor)
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

    def _on_bg_color_shortcut(self, _event=None):
        if str(self.bg_color_btn.cget("state")) != "disabled":
            self.bg_color_btn.invoke()
        return "break"

    def _update_controls_state(self):
        state = "normal" if self.show_var.get() else "disabled"
        self.entry.config(state=state)
        self.slider.config(state=state)
        self.text_color_btn.config(state=state)
        self.bg_color_btn.config(state=state)
        location_state = state if self.has_exif_data else "disabled"
        self.location_checkbox.config(state=location_state)
        refresh_state = state if (self.current_image_path and self.location_var.get()) else "disabled"
        self.location_refresh_btn.config(state=refresh_state)

    def _clamp_font_divisor(self, divisor):
        return float(min(FONT_DIVISOR_MAX, max(FONT_DIVISOR_MIN, float(divisor))))

    def _set_slider_from_divisor(self, divisor):
        self._syncing_slider = True
        try:
            clamped = self._clamp_font_divisor(divisor)
            self.slider.set(clamped)
            self._update_slider_label(clamped)
        finally:
            self._syncing_slider = False

    def _update_slider_label(self, divisor):
        self.slider_label_var.set(f"Text size: {float(divisor):.1f}")

    def _apply_location_text(self, force=False):
        if not self.location_text:
            return

        current_text = self.text_var.get().strip()
        auto_values = {"", TEXT_OVERLAY_DEFAULTS["text"], self._last_applied_location_text.strip()}
        if force or current_text in auto_values:
            self._last_applied_location_text = self.location_text
            self.text_var.set(self.location_text)

    # ----------------------
    # Public API
    # ----------------------
    def set_all(self, payload):
        # print("textoverlay set all", payload)
        self.set_show(payload["show"])
        self.set_use_location(payload.get("use_location", False))
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

    def set_use_location(self, use_location: bool):
        self.location_var.set(use_location)
        if use_location and self.show_var.get():
            self._refresh_location_for_current_context(force_refresh=False)

        if use_location and self.location_text:
            self._apply_location_text(force=False)
        self._update_controls_state()

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
        self.font_divisor = self._clamp_font_divisor(divisor)
        if hasattr(self, 'slider'):
            self._set_slider_from_divisor(self.font_divisor)

    def set_font_px(self, target_px, preview_px):
        self.font_target_height = float(max(1.0, target_px))
        self.font_preview_height = float(max(1.0, preview_px))
        self.update_font()

    def set_location_metadata(self, location_text):
        previous_text = self.location_text
        self.location_text = location_text or ""
        current_text = self.text_var.get().strip()
        auto_values = {"", TEXT_OVERLAY_DEFAULTS["text"], previous_text.strip(), self._last_applied_location_text.strip()}

        if self.location_var.get() and self.location_text:
            if current_text in auto_values:
                self._apply_location_text(force=True)
        elif current_text in auto_values:
            # Reset auto-populated text when switching images with no metadata.
            self._last_applied_location_text = ""
            self.text_var.set("")

        self._update_controls_state()

    def reset_for_new_image(self, image_path):
        self.current_image_path = image_path
        self.has_exif_data = False
        self.derived_location_name = None
        self.set_location_metadata(None)

    def set_image_context(self, image_path, cached_location=None, force_refresh=False):
        self.current_image_path = image_path
        do_lookup = bool(self.show_var.get() and self.location_var.get())
        location_text, location_name, has_exif_data, year = self._derive_overlay_text(
            image_path,
            cached_location=cached_location,
            force_refresh=force_refresh,
            do_lookup=do_lookup,
        )
        self.has_exif_data = has_exif_data
        self.current_year = year
        self.derived_location_name = location_name
        self.set_location_metadata(location_text)
        return self.derived_location_name

    def refresh_location_metadata(self):
        if not self.current_image_path:
            return

        if not (self.show_var.get() and self.location_var.get()):
            return

        self.set_image_context(self.current_image_path, cached_location=None, force_refresh=True)
        if self.location_var.get() and self.location_text:
            self._apply_location_text(force=True)
        self._trigger_callback()

    def _refresh_location_for_current_context(self, force_refresh=False):
        if not self.current_image_path:
            return

        self.set_image_context(
            self.current_image_path,
            cached_location=self.derived_location_name,
            force_refresh=force_refresh,
        )

    def _derive_overlay_text(self, image_path, cached_location=None, force_refresh=False, do_lookup=False):
        location_name = None
        year = None
        has_exif_data = False

        try:
            with Image.open(image_path) as image:
                exif_data = image.getexif()
                has_exif_data = self._has_geolocation_exif(exif_data)
                if has_exif_data:
                    year = self._get_exif_year(exif_data)
                    if cached_location and not force_refresh:
                        location_name = self._sanitize_cached_location_name(cached_location)
                    elif do_lookup:
                        location_name = self._get_exif_location_name(exif_data, force_refresh=force_refresh)
        except Exception as exc:
            print(f"Unable to derive EXIF overlay text for {image_path}: {exc}")

        overlay_text = " ".join(part for part in (location_name, year) if part)
        return (overlay_text or None, location_name, has_exif_data, year)

    def _has_geolocation_exif(self, exif_data):
        return self._get_gps_coordinates(exif_data) is not None

    def _sanitize_cached_location_name(self, value):
        if not value:
            return None

        # Backward compatibility: strip trailing years from old cached values.
        cleaned = re.sub(r"(?:\s+\d{4})+$", "", str(value).strip())
        return cleaned or None

    def _get_exif_year(self, exif_data):
        date_taken = exif_data.get(36867) or exif_data.get(306)
        if not date_taken:
            return None

        year = str(date_taken).split(":", 1)[0]
        return year if year.isdigit() and len(year) == 4 else None

    def _get_exif_location_name(self, exif_data, force_refresh=False):
        coordinates = self._get_gps_coordinates(exif_data)
        if coordinates is None:
            return None

        latitude, longitude = coordinates

        return self._reverse_geocode_location(latitude, longitude, force_refresh=force_refresh)

    def _get_gps_coordinates(self, exif_data):
        if not exif_data:
            return None

        gps_tag = next((tag for tag, name in ExifTags.TAGS.items() if name == "GPSInfo"), 34853)
        gps_info = None

        if hasattr(exif_data, "get_ifd"):
            try:
                gps_info = exif_data.get_ifd(gps_tag)
            except KeyError:
                gps_info = None

        if gps_info is None:
            gps_info = exif_data.get(gps_tag)

        if not gps_info:
            return None

        gps_named = {ExifTags.GPSTAGS.get(key, key): value for key, value in gps_info.items()}
        latitude = self._gps_to_decimal(gps_named.get("GPSLatitude"), gps_named.get("GPSLatitudeRef"))
        longitude = self._gps_to_decimal(gps_named.get("GPSLongitude"), gps_named.get("GPSLongitudeRef"))

        if latitude is None or longitude is None:
            return None
        return (latitude, longitude)

    def _gps_to_decimal(self, coords, ref):
        if not coords or not ref:
            return None

        try:
            degrees = self._gps_part_to_float(coords[0])
            minutes = self._gps_part_to_float(coords[1])
            seconds = self._gps_part_to_float(coords[2])
        except (IndexError, TypeError, ValueError, ZeroDivisionError):
            return None

        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if str(ref).upper() in ("S", "W"):
            decimal *= -1.0
        return decimal

    def _gps_part_to_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            numerator, denominator = value
            return float(numerator) / float(denominator)

    def _normalize_state_name(self, state_value):
        if not state_value:
            return None

        state_text = str(state_value).strip()
        return re.sub(r"^region\s+", "", state_text, flags=re.IGNORECASE).strip() or None

    def _extract_address_from_location(self, location):
        raw_location = location.raw if location else {}
        return raw_location.get("address", {})

    def _build_location_parts(self, address):
        state = self._normalize_state_name(address.get("state"))
        return [
            address.get("city"),
            address.get("town"),
            address.get("village"),
            address.get("hamlet"),
            state,
            address.get("country"),
        ]

    def _dedupe_and_clean_location_parts(self, location_parts):
        # Preserve order, drop empty entries, and avoid duplicated labels.
        normalized_seen = set()
        ordered_parts = []
        for part in location_parts:
            if not part:
                continue
            cleaned_part = str(part).strip()
            normalized = cleaned_part.casefold()
            if not normalized or normalized in normalized_seen:
                continue
            normalized_seen.add(normalized)
            ordered_parts.append(cleaned_part)
        return ordered_parts

    def _reverse_geocode_location(self, latitude, longitude, force_refresh=False):
        cache_key = (round(latitude, 5), round(longitude, 5))
        if not force_refresh and cache_key in self._reverse_geocode_cache:
            return self._reverse_geocode_cache[cache_key]

        location_text = None
        try:
            geolocator = cast(Any, self._geolocator)
            location = geolocator.reverse(
                (latitude, longitude),
                exactly_one=True,
                language="de",
                zoom=10,
                addressdetails=True,
            )
            address = self._extract_address_from_location(location)
            state = self._normalize_state_name(address.get("state"))
            location_parts = self._build_location_parts(address)
            ordered_parts = self._dedupe_and_clean_location_parts(location_parts)

            print(f"Reverse geocoding result for {latitude}, {longitude}: city={address.get('city')}, town={address.get('town')}, village={address.get('village')}, hamlet={address.get('hamlet')}, state={state}, country='{address.get('country')}'")
            location_text = " / ".join(ordered_parts) if ordered_parts else None
        except Exception as exc:
            print(f"Reverse geocoding failed for {latitude}, {longitude}: {exc}")

        self._reverse_geocode_cache[cache_key] = location_text
        return location_text

    def set_image_dpi_scale(self, scale):
        """Adjust the DPI scale factor for image rendering (0.8-1.5 typical range)"""
        self.image_dpi_scale = scale

    def update_font(self):
        if self.font_preview_height > 0:
            # Convert absolute preview pixel size to font points using system DPI
            pts_float = self.font_preview_height / self.system_dpi_scale
            pts = int(max(self.min_font_size, min(self.max_font_size, round(pts_float))))
            self.font.configure(size=pts)
            # print(f"Canvas font set to: {pts}pt (preview_px {self.font_preview_height:.2f}, sys_dpi {self.system_dpi_scale:.3f})")

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
                "use_location": self.location_var.get(),
                "derived_location": self.derived_location_name,
                "text": self.text_var.get(),
                "text_color": self.text_color,
                "bg_color": self.bg_color,
                "bottom": self.bottom,
                "right": self.right,
                "font_divisor": self.font_divisor,
                "image_dpi_scale": self.image_dpi_scale,
            })
