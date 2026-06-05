"""UI constants"""

CANVAS_BACKGROUND_COLOR = "#000000"
WINDOW_BACKGROUND_COLOR = "#222222"
BORDER_COLOR = "#333333"        # widget border color
HIGHLIGHT_COLOR = "#339933"     # element highlight color
FOREGROUND_COLOR = "white"        # main foreground color
DISABLED_COLOR = "#666666"      # disabled elements color

DEFAULT_CROP_SIZE = 1             # between 0.1 ... 1
MASK_COLOR = "#000000"          # mask outside crop region
MASK_STIPPLE = "gray50"           # crop marker outside mask pattern (50% transparent)
GRID_COLOR = "#00ff00"          # crop marker grid color
GRID_DARK_COLOR = "#006600"     # crop marker grid color for center lines

ARROW_STEP = 2                    # px for step with arrows
ARROW_STEP_FAST = 10              # px with Shift pressed
ARROW_STEP_SLOW = 0.5             # px with Ctrl+Shift pressed
SCALE_FACTOR = 1.02               # zoom step with normal +/-
SCALE_FACTOR_FAST = 1.10          # zoom step with Shift
SCALE_FACTOR_SLOW = 1.005         # zoom step with Ctrl+Shift (more precise)
CANVAS_ZOOM_STEP = 1.10           # Ctrl+wheel zoom step for canvas image
CANVAS_ZOOM_MIN = 0.25            # minimum relative zoom of fit-to-window scale

SLIDER_WIDTH = 100                # image enhancer slider width in px
LABEL_PADDINGS_X = (5, 5)         # (left/right) padding for labels and sliders
LABEL_PADDINGS_X_SMALL = (2, 1)   # smaller horizontal padding for sliders in options pane
LABEL_PADDINGS_Y = (5, 5)         # (top/bottom) padding for labels and sliders
TOOLTIP_DELAY = 250

GALLERY_THUMB_SIZE = 80           # size of gallery thumbnails in px
GALLERY_THUMB_BORDER_SIZE = 1     # border in px
GALLERY_SHOW_LANDSCAPE = True
GALLERY_SHOW_PORTRAIT = True
GALLERY_SHOW_UNPROCESSED = False
