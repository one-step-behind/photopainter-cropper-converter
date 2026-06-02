"""Shared UI sizing constants."""

# Single source of truth for compact slider widths in the options pane.
SLIDER_WIDTH = 100

DEFAULT_CROP_SIZE = 1  # between 0.1 ... 1
MASK_COLOR = "#000000"          # mask outside crop region
MASK_STIPPLE = "gray50"
CANVAS_BACKGROUND_COLOR = "#000000"
WINDOW_BACKGROUND_COLOR = "#222222"
BORDER_COLOR = "#333333"
HIGHLIGHT_COLOR = "#339933"
FOREGROUND_COLOR = "white"

ARROW_STEP = 1                    # px for step with arrows
ARROW_STEP_FAST = 10              # px with Shift pressed
SCALE_FACTOR = 1.01               # zoom step with normal +/-
SCALE_FACTOR_FAST = 1.10          # zoom step with Shift
SCALE_FACTOR_SLOW = 1.002         # zoom step with Ctrl+Shift
CANVAS_ZOOM_STEP = 1.10           # Ctrl+wheel zoom step for canvas image
CANVAS_ZOOM_MIN = 0.25            # minimum relative zoom of fit-to-window scale

LABEL_PADDINGS = (5, 5)
DEFAULT_TOOLTIP_DELAY = 250

GALLERY_THUMB_SIZE = 80
GALLERY_PADDING = 12
