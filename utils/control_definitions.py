import tkinter as tk
from typing import Any


def build_cropper_control_definitions(app: Any, available_option: dict[str, tuple[str, ...]]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    app_settings_def = {
        "save_filelist": {
            "text": "Save image list",
            "command": lambda e=None: app.update_app_settings_checkbox("save_filelist"),
            "enter_tip": "Saves file list of existing images on app exit\nto fileList.txt in export folder(s)\n(landscape & portrait) (Ctrl+Shift+S)",
            "toggle_key": ("<Control-Shift-s>", "<Control-Shift-S>"),
        },
        "save_canvas_zoom": {
            "text": "Remember canvas zoom",
            "command": lambda e=None: app.update_app_settings_checkbox("save_canvas_zoom"),
            "enter_tip": "Saves and restores the current canvas zoom\nvalue in settings.ini between app restarts.\n(Ctrl+Shift+Z)",
            "toggle_key": ("<Control-Shift-z>", "<Control-Shift-Z>"),
        },
        "exit_after_last_image": {
            "text": "Exit after last image",
            "command": lambda e=None: app.update_app_settings_checkbox("exit_after_last_image"),
            "enter_tip": "Close the app after last image in folder was\nprocessed, otherwise open the first image. (Ctrl+X)",
            "toggle_key": ("<Control-Shift-x>", "<Control-Shift-X>"),
        },
    }

    app_button_definitions = {
        "prev": {
            "default_text": "<< Prev",
            "command": app.prev_image,
            "enter_tip": "Previous Image (PAGE_UP)",
            "disabled_if_single_image": True,
            "toggle_key": "<Prior>",
        },
        "next": {
            "default_text": "Next >>",
            "command": app.next_image,
            "enter_tip": "Next Image (PAGE_DOWN)",
            "disabled_if_single_image": True,
            "toggle_key": "<Next>",
        },
        "save": {
            "default_text": "Crop and Convert",
            "command": app.on_confirm,
            "enter_tip": "Crop and Convert (Enter, Ctrl+S)",
            "style_config": {"foreground": "green"},
            "toggle_key": ("<Return>", "<Control-s>", "<Control-S>"),
        },
        "change_folder": {
            "default_text": "Change folder",
            "command": lambda e=None: app.load_folder(),
            "enter_tip": "Change to another folder of images (Ctrl+Shift+L)",
            "underline": 9,
            "toggle_key": ("<Control-Shift-l>", "<Control-Shift-L>"),
        },
        "reload_folder": {
            "default_text": "Reload folder",
            "command": lambda e=None: app.load_folder(False),
            "enter_tip": "Reload this folder of images (Ctrl+Shift+R)",
            "underline": 0,
            "toggle_key": ("<Control-Shift-r>", "<Control-Shift-R>"),
        },
    }

    option_button_def = {
        "orientation": {
            "widget_type": "combobox",
            "default_text": "Orientation",
            "command": app.toggle_orientation,
            "postcommand": lambda e=None: app.set_orientation("orientation"),
            "values": available_option["ORIENTATION"],
            "enter_tip": "Toggle Orientation (Ctrl+O)",
            "fill": tk.X,
            "underline": 0,
            "toggle_key": ("<Control-o>", "<Control-O>"),
        },
        "fill_mode": {
            "widget_type": "combobox",
            "default_text": "Fill",
            "command": app.toggle_fill_mode,
            "postcommand": lambda e=None: app.set_fill_mode("fill_mode"),
            "values": available_option["FILL_MODE"],
            "enter_tip": "Toggle Fill mode (Ctrl+F)",
            "underline": 0,
            "toggle_key": ("<Control-f>", "<Control-F>"),
        },
        "target_device": {
            "widget_type": "combobox",
            "default_text": "Device",
            "command": app.toggle_target_device,
            "postcommand": lambda e=None: app.set_target_device("target_device"),
            "values": available_option["TARGET_DEVICE"],
            "enter_tip": "Toggle Target device (Ctrl+D)",
            "underline": 0,
            "toggle_key": ("<Control-d>", "<Control-D>"),
        },
    }

    enhancer_sliders_def = {
        "brightness": {
            "text": "Brightness",
            "min": 0.1,
            "max": 5.0,
            "resolution": 0.05,
            "tickinterval": 1.0,
            "command": lambda value: app.schedule_slider_update("brightness", value),
            "enter_tip": "Set Brighness",
        },
        "contrast": {
            "text": "Contrast",
            "min": 0.1,
            "max": 5.0,
            "resolution": 0.05,
            "tickinterval": 1.0,
            "command": lambda value: app.schedule_slider_update("contrast", value),
            "enter_tip": "Set Contrast",
        },
        "saturation": {
            "text": "Saturation",
            "min": 0.0,
            "max": 5.0,
            "resolution": 0.05,
            "tickinterval": 1.0,
            "command": lambda value: app.schedule_slider_update("saturation", value),
            "enter_tip": "Set Saturation",
        },
    }

    enhancer_checkboxes_def = {
        "enhancer_edge": {
            "text": "Edge",
            "command": lambda e=None: app.update_image_enhancer_checkbox("enhancer_edge"),
            "enter_tip": "Enhance image by Edgeing (Ctrl+1)",
            "toggle_key": "<Control-Key-1>",
        },
        "enhancer_smooth": {
            "text": "Smooth",
            "command": lambda e=None: app.update_image_enhancer_checkbox("enhancer_smooth"),
            "enter_tip": "Enhance image by Smoothing (Ctrl+2)",
            "toggle_key": "<Control-Key-2>",
        },
        "enhancer_sharpen": {
            "text": "Sharpen",
            "command": lambda e=None: app.update_image_enhancer_checkbox("enhancer_sharpen"),
            "enter_tip": "Enhance image by Sharpening (Ctrl+3)",
            "toggle_key": "<Control-Key-3>",
        },
    }

    return (
        app_settings_def,
        app_button_definitions,
        option_button_def,
        enhancer_sliders_def,
        enhancer_checkboxes_def,
    )


def build_textoverlay_control_definitions(overlay: Any) -> dict[str, dict[str, Any]]:
    return {
        "show_text": {
            "text": "Show text on canvas",
            "variable": overlay.show_var,
            "command": overlay._on_show_change,
            "hover_tip": "Show text on canvas (Ctrl+T)",
            "toggle_key": ("<Control-t>", "<Control-T>"),
            "shortcut_callback": overlay._on_show_text_shortcut,
        },
        "year": {
            "text": "Year",
            "variable": overlay.year_var,
            "command": overlay._on_year_change,
            "hover_tip": "Year from date taken",
        },
        "location": {
            "text": "Location",
            "variable": overlay.location_var,
            "command": overlay._on_location_change,
            "hover_tip": "Location metadata (Ctrl+L)",
            "toggle_key": ("<Control-l>", "<Control-L>"),
            "shortcut_callback": overlay._on_location_shortcut,
        },
        "refresh_location": {
            "text": "Refresh",
            "width": 7,
            "padding": (2, 1),
            "command": overlay.refresh_location_metadata,
        },
        "text_entry": {
            "hover_tip": "Text on Canvas",
        },
        "text_size": {
            "label_prefix": "Text size",
        },
        "text_size_reset": {
            "text": "Reset",
            "width": 6,
            "padding": (2, 1),
            "hover_tip": "Reset to default text size",
            "command": overlay._reset_font_divisor,
        },
        "text_color": {
            "text": "Text color",
            "command": overlay._pick_text_color,
            "hover_tip": "Text color (Ctrl+Shift+T)",
            "toggle_key": ("<Control-Shift-t>", "<Control-Shift-T>"),
            "shortcut_callback": overlay._on_text_color_shortcut,
        },
        "bg_color": {
            "text": "Background color",
            "command": overlay._pick_bg_color,
            "hover_tip": "Background color (Ctrl+Shift+B)",
            "toggle_key": ("<Control-Shift-b>", "<Control-Shift-B>"),
            "shortcut_callback": overlay._on_bg_color_shortcut,
        },
    }
