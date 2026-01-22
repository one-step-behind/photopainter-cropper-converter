import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from typing import Callable, Optional, List

THUMB_SIZE = 80
PADDING = 12

class AsyncThumbnailGallery(tk.Frame):
    thumbs: List[ImageTk.PhotoImage]
    thumb_labels: List[tk.Label]
    selected_index: Optional[int]

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
        ):
        """
        Horizontally scrollable, async-loading thumbnail gallery.
        
        :param self: instance
        :param master: TK instance
        :param image_paths: path for images
        :param on_click: double click handler
        """
        super().__init__(parent, bg=bg)

        self.image_paths: List[str] = image_paths
        self.thumb_size: int = thumb_size
        self.thumbs = []        # list[PhotoImage]
        self.thumb_labels = []  # list[Label]
        self.selected_index: Optional[int] = None
        self._auto_select_first = True

        self.default_bg = bg
        self.image_bg = image_bg
        self.selected_bg = selected_bg   # light blue, or any highlight color you like

        self.on_select = on_select

        self._load_generation = 0

        # ----------------------------
        # Canvas + inner frame
        # ----------------------------
        self.canvas = tk.Canvas(
            self,
            height=self.thumb_size + PADDING,
            highlightthickness=0,
            bg=self.default_bg,
            background=self.default_bg,
        )
        self.canvas.pack(fill=tk.X, expand=True)

        self.inner_frame = tk.Frame(self.canvas, bg=bg)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        self.inner_frame.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize_canvas)

        # Horizontal scrollbar
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self.canvas.xview,
            style="Gallery.Horizontal.TScrollbar",
        )
        # do not pack it yet — auto-hide logic controls that
        #self.scrollbar.pack(fill=tk.X)

        # ----------------------------
        # Scrolling (horizontal only)
        # ----------------------------
        self._scrollable: bool = False
        self.canvas.configure(xscrollcommand=self._on_xscroll)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.xview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.xview_scroll(1, "units"))
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)

        # ----------------------------
        # Async load
        # ----------------------------
        threading.Thread(
            target=self._load_thumbnails_async,
            daemon=True
        ).start()

    def set_images(self, image_paths: List[str]) -> None:
        """
        Replace gallery contents without recreating the widget.
        """
        # Invalidate any running loaders
        self._load_generation += 1
        gen = self._load_generation
        self._auto_select_first = True

        # Clear UI
        for lbl in self.thumb_labels:
            lbl.destroy()

        self.thumbs.clear()
        self.thumb_labels.clear()

        # Reset scroll position
        self.selected_index = None
        self.canvas.xview_moveto(0)

        self.image_paths = image_paths

        # ----------------------------
        # Restart async load
        # ----------------------------
        threading.Thread(
            target=self._load_thumbnails_async,
            args=(gen,),
            daemon=True
        ).start()

    # ============================================================
    # Thumbnail loading
    # ============================================================

    def _load_thumbnails_async(self, generation=None) -> None:
        if generation is None:
            generation = self._load_generation

        for index, path in enumerate(self.image_paths):
            # Abort if a newer generation exists
            if generation != self._load_generation:
                return

            thumb = self._create_thumbnail(path)
            self.after(
                0,
                self._add_thumbnail,
                index,
                thumb,
            )

    def _create_thumbnail(self, path) -> ImageTk.PhotoImage:
        img = self.load_image_by_exiforient(path) # EXIF auto-rotate
        bg = Image.new("RGBA", (self.thumb_size, self.thumb_size), self.default_bg)

        img.thumbnail((self.thumb_size, self.thumb_size), Image.LANCZOS)

        x = (self.thumb_size - img.width) // 2
        y = (self.thumb_size - img.height) // 2
        bg.paste(img, (x, y))

        return ImageTk.PhotoImage(bg)
    
    def load_image_by_exiforient(self, path: str):
        """
        Loads an image and applies EXIF orientation correction (auto-rotate).
        Returns an RGB image with correct orientation.
        """
        try:
            image = Image.open(path).convert("RGB")

            try:
                # modern Pillow: .getexif()
                exif = image.getexif()
                exiforient = exif.get(0x0112, 1)  # EXIF Orientation
            except Exception:
                exiforient = 1

            # Rotate according to EXIF orientation tag
            if exiforient == 3:
                image = image.rotate(180, expand=True)
            elif exiforient == 6:
                image = image.rotate(270, expand=True)  # 90° CW
            elif exiforient == 8:
                image = image.rotate(90, expand=True)   # 90° CCW

            return image

        except Exception as e:
            print("EXIF load/rotation failed:", e)
            return Image.open(path).convert("RGB")

    # ============================================================
    # UI
    # ============================================================

    def _add_thumbnail(self, index: int, thumb: ImageTk.PhotoImage) -> None:
        if index < 0 or index >= len(self.image_paths):
            return

        lbl = tk.Label(
            self.inner_frame,
            image=thumb,
            bg=self.image_bg,
            borderwidth=1,
        )
        lbl.grid(row=0, column=index, padx=2, pady=2)

        self.thumbs.append(thumb)
        self.thumb_labels.append(lbl)

        lbl.bind("<Button-1>", lambda e, i=index: self.select_index(i, scroll=False))
        lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        lbl.bind("<Button-4>", lambda e: self.canvas.xview_scroll(-1, "units"))
        lbl.bind("<Button-5>", lambda e: self.canvas.xview_scroll(1, "units"))

        # Auto-select first thumbnail exactly once
        if index == 0 and self._auto_select_first:
            self._auto_select_first = False
            self.after(0, lambda: self.select_index(0, scroll=False))

    def select_index(self, index: int, scroll: bool = True) -> None:
        if index < 0 or index >= len(self.thumb_labels):
            return

        # Clear previous selection
        if self.selected_index is not None:
            self.thumb_labels[self.selected_index].config(bg=self.image_bg)

        # Apply new selection
        self.selected_index = index
        lbl = self.thumb_labels[index]
        lbl.config(bg=self.selected_bg)

        if scroll:
            self._scroll_index_into_view(index)

        if self.on_select:
            self.on_select(index)

    # ============================================================
    # Scrolling helpers
    # ============================================================

    def _scroll_index_into_view(self, index) -> None:
        self.update_idletasks()

        lbl = self.thumb_labels[index]

        canvas_left = self.canvas.canvasx(0)
        canvas_right = canvas_left + self.canvas.winfo_width()

        item_x = lbl.winfo_x()
        item_width = lbl.winfo_width()

        item_left = item_x
        item_right = item_x + item_width

        if item_left < canvas_left:
            self.canvas.xview_moveto(item_left / self.inner_frame.winfo_width())
        elif item_right > canvas_right:
            offset = item_right - self.canvas.winfo_width()
            self.canvas.xview_moveto(offset / self.inner_frame.winfo_width())

    def _update_scrollregion(self, event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_canvas(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, height=event.height)

    def _on_mouse_wheel(self, event) -> None:
        if not self._scrollable:
            return

        delta = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(delta, "units")

    def _drag_start(self, event) -> None:
        if not self._scrollable:
            return

        self._drag_x = event.x

    def _drag_move(self, event) -> None:
        if not self._scrollable:
            return

        dx = self._drag_x - event.x
        self.canvas.xview_scroll(int(dx / 2), "units")
        self._drag_x = event.x

    def _on_xscroll(self, first: float, last: float) -> None:
        first_f = float(first)
        last_f = float(last)

        # Update scrollbar position
        self.scrollbar.set(first, last)
        scrollable = not (first_f <= 0.0 and last_f >= 1.0)
        self._scrollable = scrollable

        # Auto-hide logic
        if scrollable:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(fill=tk.X)
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()