import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List

from PIL import Image, ImageOps, ImageTk

THUMB_SIZE = 80
PADDING = 12


class AsyncThumbnailGallery(tk.Frame):
    def __init__(
        self,
        parent,
        image_paths: List[str],
        *,
        thumb_size: int = THUMB_SIZE,
        bg: str = "#222222",
        image_bg: str = "#333333",
        selected_bg: str = "#add8e6",
        on_select: Optional[Callable[[int], None]] = None,
        on_layout_change: Optional[Callable[[], None]] = None,
    ):
        """
        Single-row, horizontally scrollable, async-loading thumbnail gallery.
        Rendering is virtualized, so only visible thumbnails are drawn.
        """
        super().__init__(parent, bg=bg)

        self.image_paths: List[str] = image_paths
        self.thumb_size: int = thumb_size
        self.selected_index: Optional[int] = None
        self._auto_select_first = True
        self.default_bg = bg
        self.image_bg = image_bg
        self.selected_bg = selected_bg
        self.on_select = on_select
        self.on_layout_change = on_layout_change

        self._load_generation = 0
        self._thumb_queue: queue.Queue = queue.Queue()

        self._thumb_pad = 2
        self._cell_span = self.thumb_size + (self._thumb_pad * 2)
        self._row_height = self.thumb_size + (self._thumb_pad * 2)

        self._scroll_offset_px = 0
        self._drag_x = 0
        self._scrollable = False

        self._thumb_pil: dict[int, Image.Image] = {}
        self._thumb_tk: dict[int, ImageTk.PhotoImage] = {}
        self._visible_items: dict[int, tuple[int, Optional[int], int]] = {}
        self._sidecar_exists: List[bool] = []

        try:
            if not hasattr(sys, "frozen"):
                resource_path = os.path.join(os.path.dirname(__file__), "../_source/round_check_mark_16.png")
            else:
                resource_path = os.path.join(sys.prefix, "./_source/round_check_mark_16.png")
            self.sidecar_icon = tk.PhotoImage(file=resource_path)
        except Exception:
            self.sidecar_icon = None

        self.canvas = tk.Canvas(
            self,
            height=self._compute_canvas_height(),
            highlightthickness=0,
            bg=self.default_bg,
            background=self.default_bg,
        )
        self.canvas.pack(fill=tk.X, expand=True)

        self.canvas.bind("<Configure>", self._resize_canvas)

        self.scrollbar = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self._on_scrollbar,
            style="Gallery.Horizontal.TScrollbar",
        )

        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._scroll_units(-1))
        self.canvas.bind("<Button-5>", lambda e: self._scroll_units(1))
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)

        self._prepare_sidecar_flags()

        threading.Thread(target=self._load_thumbnails_async, daemon=True).start()
        self.after(10, self._drain_thumbnail_queue)

    def set_images(self, image_paths: List[str]) -> None:
        """
        Replace gallery contents without recreating the widget.
        """
        self._load_generation += 1
        gen = self._load_generation
        self._auto_select_first = True

        self._clear_visible_items()
        self._thumb_pil.clear()
        self._thumb_tk.clear()

        self.image_paths = image_paths
        self._prepare_sidecar_flags()

        self.selected_index = None
        self._scroll_offset_px = 0
        self.canvas.configure(height=self._compute_canvas_height())
        self._update_scrollbar()
        self._render_visible_thumbnails()

        threading.Thread(target=self._load_thumbnails_async, args=(gen,), daemon=True).start()

    # ============================================================
    # Thumbnail loading
    # ============================================================

    def _load_thumbnails_async(self, generation=None) -> None:
        if generation is None:
            generation = self._load_generation

        for index, path in enumerate(self.image_paths):
            if generation != self._load_generation:
                return

            try:
                thumb_image = self._create_thumbnail_image(path)
            except Exception as exc:
                print(f"Thumbnail load failed for '{path}': {exc}")
                thumb_image = Image.new("RGBA", (self.thumb_size, self.thumb_size), self.default_bg)
            self._thumb_queue.put((generation, index, thumb_image))

    def _drain_thumbnail_queue(self) -> None:
        processed = 0
        max_per_tick = 24

        while processed < max_per_tick:
            try:
                generation, index, thumb_image = self._thumb_queue.get_nowait()
            except queue.Empty:
                break

            if generation == self._load_generation:
                self._thumb_pil[index] = thumb_image
                if index in self._visible_items:
                    self._render_thumbnail(index)
                if index == 0 and self._auto_select_first and self.image_paths:
                    self._auto_select_first = False
                    self.after(0, lambda: self.select_index(0, scroll=False))
            processed += 1

        if self.winfo_exists():
            self.after(10, self._drain_thumbnail_queue)

    def _create_thumbnail_image(self, path) -> Image.Image:
        img = self.load_image_by_exiforient(path)
        # Leave 1 px on each side so the rectangle fill remains visible.
        inner = self.thumb_size - 2
        img.thumbnail((inner, inner), Image.Resampling.LANCZOS)
        return img.convert("RGB")

    def load_image_by_exiforient(self, path: str):
        """
        Loads an image and applies EXIF orientation correction (auto-rotate).
        Returns an RGB image with correct orientation.
        """
        with Image.open(path) as image:
            transposed = ImageOps.exif_transpose(image)
            return transposed.convert("RGB")

    # ============================================================
    # Virtualized rendering
    # ============================================================

    def _compute_canvas_height(self) -> int:
        return self._row_height + PADDING

    def _prepare_sidecar_flags(self) -> None:
        self._sidecar_exists = []
        for img_path in self.image_paths:
            sidecar = f"{os.path.splitext(img_path)[0]}_ppcrop.txt"
            self._sidecar_exists.append(os.path.exists(sidecar))

    def _logical_width(self) -> int:
        return len(self.image_paths) * self._cell_span

    def _viewport_width(self) -> int:
        w = self.canvas.winfo_width()
        return w if w > 1 else 1

    def _max_scroll_offset(self) -> int:
        return max(0, self._logical_width() - self._viewport_width())

    def _set_scroll_offset(self, new_offset: int) -> None:
        bounded = max(0, min(new_offset, self._max_scroll_offset()))
        if bounded == self._scroll_offset_px and self._visible_items:
            return

        self._scroll_offset_px = bounded
        self._render_visible_thumbnails()
        self._update_scrollbar()

    def _visible_index_range(self) -> tuple[int, int]:
        total = len(self.image_paths)
        if total == 0:
            return 0, 0

        viewport = self._viewport_width()
        start = self._scroll_offset_px // self._cell_span
        end = (self._scroll_offset_px + viewport) // self._cell_span + 1

        buffer_items = 3
        start = max(0, start - buffer_items)
        end = min(total, end + buffer_items)

        return start, end

    def _clear_visible_items(self) -> None:
        for _, (bg_id, overlay_id, img_id) in list(self._visible_items.items()):
            self.canvas.delete(bg_id)
            self.canvas.delete(img_id)
            if overlay_id is not None:
                self.canvas.delete(overlay_id)
        self._visible_items.clear()
        self._thumb_tk.clear()

    def _render_visible_thumbnails(self) -> None:
        start, end = self._visible_index_range()
        wanted = set(range(start, end))

        for index in list(self._visible_items.keys()):
            if index not in wanted:
                bg_id, overlay_id, img_id = self._visible_items.pop(index)
                self.canvas.delete(bg_id)
                self.canvas.delete(img_id)
                if overlay_id is not None:
                    self.canvas.delete(overlay_id)
                self._thumb_tk.pop(index, None)

        for index in range(start, end):
            self._render_thumbnail(index)

    def _render_thumbnail(self, index: int) -> None:
        if index < 0 or index >= len(self.image_paths):
            return

        cell_left = index * self._cell_span - self._scroll_offset_px
        x0 = cell_left + self._thumb_pad
        y0 = self._thumb_pad
        x1 = x0 + self.thumb_size
        y1 = y0 + self.thumb_size

        fill_color = self.image_bg
        outline_color = self.selected_bg if index == self.selected_index else ""
        outline_width = 1 if index == self.selected_index else 0
        tag = f"thumb-{index}"

        thumb_pil = self._thumb_pil.get(index)
        thumb_tk = self._thumb_tk.get(index)
        if thumb_pil is not None and thumb_tk is None:
            thumb_tk = ImageTk.PhotoImage(thumb_pil)
            self._thumb_tk[index] = thumb_tk

        has_overlay = (
            self.sidecar_icon is not None
            and index < len(self._sidecar_exists)
            and self._sidecar_exists[index]
        )

        if index in self._visible_items:
            bg_id, overlay_id, img_id = self._visible_items[index]
            self.canvas.coords(bg_id, x0, y0, x1, y1)
            self.canvas.itemconfigure(bg_id, fill=fill_color, outline=outline_color, width=outline_width)
            self.canvas.coords(img_id, (x0 + x1) // 2, (y0 + y1) // 2)
            self.canvas.itemconfigure(img_id, image=thumb_tk if thumb_tk is not None else "")

            if has_overlay:
                if overlay_id is None:
                    overlay_id = self.canvas.create_image(x1 - 1, y0 + 1, image=self.sidecar_icon, anchor="ne", tags=(tag,))
                else:
                    self.canvas.coords(overlay_id, x1 - 1, y0 + 1)
                    self.canvas.itemconfigure(overlay_id, image=self.sidecar_icon)
            else:
                if overlay_id is not None:
                    self.canvas.delete(overlay_id)
                    overlay_id = None

            self._visible_items[index] = (bg_id, overlay_id, img_id)
        else:
            bg_id = self.canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=fill_color,
                outline=outline_color,
                width=outline_width,
                tags=(tag,),
            )
            img_id = self.canvas.create_image(
                (x0 + x1) // 2,
                (y0 + y1) // 2,
                image=thumb_tk if thumb_tk is not None else "",
                anchor="center",
                tags=(tag,),
            )
            overlay_id = None
            if has_overlay:
                overlay_id = self.canvas.create_image(x1 - 1, y0 + 1, image=self.sidecar_icon, anchor="ne", tags=(tag,))

            self.canvas.tag_bind(tag, "<Button-1>", lambda e, i=index: self.select_index(i, scroll=True))
            self.canvas.tag_bind(tag, "<Button-4>", lambda e: self._scroll_units(-1))
            self.canvas.tag_bind(tag, "<Button-5>", lambda e: self._scroll_units(1))

            self._visible_items[index] = (bg_id, overlay_id, img_id)

    # ============================================================
    # Selection
    # ============================================================

    def select_index(self, index: int, scroll: bool = True) -> None:
        if index < 0 or index >= len(self.image_paths):
            return

        self.selected_index = index

        if scroll:
            self._scroll_index_into_view(index)
        else:
            self._render_visible_thumbnails()

        if self.on_select:
            self.on_select(index)

    def _scroll_index_into_view(self, index) -> None:
        item_left = index * self._cell_span
        item_right = item_left + self._cell_span
        view_left = self._scroll_offset_px
        view_right = self._scroll_offset_px + self._viewport_width()

        if item_left < view_left:
            self._set_scroll_offset(item_left)
        elif item_right > view_right:
            self._set_scroll_offset(item_right - self._viewport_width())
        else:
            self._render_visible_thumbnails()

    # ============================================================
    # Scrolling
    # ============================================================

    def _resize_canvas(self, event) -> None:
        self.canvas.configure(height=self._compute_canvas_height())
        # Clamp scroll offset in case the viewport grew or shrank.
        self._scroll_offset_px = max(0, min(self._scroll_offset_px, self._max_scroll_offset()))
        # Bypass _set_scroll_offset: its early-return guard blocks re-render on resize.
        self._render_visible_thumbnails()
        self._update_scrollbar()
        if self.on_layout_change:
            self.after_idle(self.on_layout_change)

    def _on_scrollbar(self, action: str, *args) -> None:
        if action == "moveto" and args:
            fraction = float(args[0])
            self._set_scroll_offset(int(round(fraction * self._max_scroll_offset())))
            return

        if action == "scroll" and len(args) >= 2:
            count = int(args[0])
            what = args[1]
            if what == "pages":
                delta = count * self._viewport_width()
            else:
                delta = count * max(1, self._cell_span // 3)
            self._set_scroll_offset(self._scroll_offset_px + delta)

    def _scroll_units(self, units: int) -> None:
        self._set_scroll_offset(self._scroll_offset_px + (units * max(1, self._cell_span // 3)))

    def _on_mouse_wheel(self, event) -> None:
        if not self._scrollable:
            return

        delta_units = -1 if event.delta > 0 else 1
        self._scroll_units(delta_units)

    def _drag_start(self, event) -> None:
        if not self._scrollable:
            return

        self._drag_x = event.x

    def _drag_move(self, event) -> None:
        if not self._scrollable:
            return

        dx = self._drag_x - event.x
        self._set_scroll_offset(self._scroll_offset_px + dx)
        self._drag_x = event.x

    def _update_scrollbar(self) -> None:
        logical_width = self._logical_width()
        viewport = self._viewport_width()

        if logical_width <= 0 or logical_width <= viewport:
            first = 0.0
            last = 1.0
            scrollable = False
        else:
            first = self._scroll_offset_px / logical_width
            last = min(1.0, (self._scroll_offset_px + viewport) / logical_width)
            scrollable = True

        self.scrollbar.set(first, last)

        visibility_changed = scrollable != self._scrollable
        self._scrollable = scrollable

        if scrollable:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(fill=tk.X)
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()

        if visibility_changed and self.on_layout_change:
            self.after_idle(self.on_layout_change)
