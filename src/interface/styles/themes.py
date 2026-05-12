from .colors import COLORS
from .fonts import FONTS
from .sizes import SIZES

THEMES = {
    "dark": {
        "name": "dark",
        "colors": COLORS,
        "fonts": FONTS,
        "sizes": SIZES
    }
}

CURRENT_THEME = THEMES["dark"]

def get_style(style_name: str) -> str:
    """获取预定义样式字符串"""
    styles = {
        "container": f"""
            background-color: {COLORS['background_sidebar']};
            border-radius: {SIZES['radius']['lg']}px;
        """,
        
        "card": f"""
            background-color: {COLORS['card']};
            border: {SIZES['border']['width']}px solid {COLORS['border']};
            border-radius: {SIZES['radius']['base']}px;
        """,
        
        "button_primary": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border: none;
                border-radius: {SIZES['radius']['base']}px;
                height: {SIZES['button']['height']}px;
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {COLORS['primary_light']}, stop:1 {COLORS['secondary']});
            }}
            QPushButton:pressed {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {COLORS['primary_dark']}, stop:1 {COLORS['primary']});
            }}
        """,
        
        "combo_box": f"""
            QComboBox {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['sm']}px;
                padding: {SIZES['spacing']['sm']}px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                selection-background-color: {COLORS['card_hover']};
            }}
        """,
        
        "spin_box": f"""
            QSpinBox {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['sm']}px;
                padding: {SIZES['spacing']['xs']}px;
            }}
        """,
        
        "date_edit": f"""
            QDateEdit {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['sm']}px;
                padding: {SIZES['spacing']['xs']}px;
            }}
        """,
        
        "check_box": f"""
            QCheckBox {{
                color: {COLORS['text']};
            }}
        """,
        
        "group_box": f"""
            QGroupBox {{
                color: {COLORS['text']};
                font-size: {FONTS['size']['sm']}px;
                font-weight: {FONTS['weight']['bold']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['sm']}px;
                margin-top: {SIZES['spacing']['sm']}px;
                padding-top: {SIZES['spacing']['sm']}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 6px;
                padding: 0 2px;
            }}
        """,
        
        "table": f"""
            QTableWidget {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['base']}px;
                gridline-color: {COLORS['border']};
            }}
            QTableWidget::item {{
                padding: {SIZES['spacing']['sm']}px;
            }}
            QTableWidget::item:hover {{
                background-color: {COLORS['card_hover']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['background_sidebar']};
                color: {COLORS['text']};
                padding: {SIZES['spacing']['sm']}px;
                border: none;
            }}
        """,
        
        "label_title": f"""
            color: {COLORS['text']};
        """,
        
        "label_hint": f"""
            color: {COLORS['text_hint']};
        """,
        
        "frame_sidebar": f"""
            background-color: {COLORS['background_sidebar']};
            border-radius: {SIZES['radius']['lg']}px;
        """,
        
        "frame_card": f"""
            background-color: {COLORS['card']};
            border-radius: {SIZES['radius']['base']}px;
        """,
        
        "progress_bar": f"""
            QProgressBar {{
                background-color: {COLORS['card']};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border-radius: 3px;
            }}
        """,
        
        "push_button_gradient": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border: none;
                border-radius: {SIZES['radius']['lg']}px;
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary_light']}, stop:1 {COLORS['secondary']});
            }}
            QPushButton:pressed {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['primary_dark']}, stop:1 {COLORS['primary']});
            }}
        """,
        
        "mode_button": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: none;
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QPushButton:checked {{
                background-color: {COLORS['card_hover']};
                border: {SIZES['border']['width']}px solid {COLORS['primary_light']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
        """,
        
        "list_widget": f"""
            QListWidget {{
                background-color: transparent;
                border: none;
            }}
            QListWidget::item {{
                height: 70px;
                margin: 4px 0;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['card_hover']};
                border-left: 4px solid {COLORS['primary']};
                border-radius: {SIZES['radius']['sm']}px;
            }}
        """,
        
        "plot_widget": f"""
            background-color: {COLORS['background']};
        """,

        "main_window": f"background-color: {COLORS['background']};",

        "splitter": f"""
            QSplitter::handle {{
                background-color: {COLORS['card_hover']};
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS['handle_hover']};
            }}
            QSplitter::handle:pressed {{
                background-color: {COLORS['handle_pressed']};
            }}
        """,
    }
    return styles.get(style_name, "")

def get_font(size_key: str = "base", weight_key: str = "normal") -> tuple:
    """获取字体配置 (family, size, weight)"""
    return (
        FONTS["family"],
        FONTS["size"][size_key],
        FONTS["weight"][weight_key]
    )

def get_spacing(key: str) -> int:
    """获取间距值"""
    return SIZES["spacing"][key]

def get_radius(key: str) -> int:
    """获取圆角值"""
    return SIZES["radius"][key]
