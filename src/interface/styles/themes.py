from .colors import COLORS
from .fonts import FONTS
from .sizes import SIZES

THEMES = {
    "dark": {
        "name": "dark",
        "colors": COLORS,
        "fonts": FONTS,
        "sizes": SIZES,
    }
}

CURRENT_THEME = THEMES["dark"]


def get_style(style_name: str) -> str:
    """获取预定义样式字符串"""
    styles = {
        # ──────────────────── 容器 ────────────────────
        "container": f"""
            background-color: {COLORS['surface']};
            border: none;
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "container_gradient": f"""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['surface']}, stop:0.6 {COLORS['surface']},
                stop:1 #1A1A38);
            border: none;
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "card_elevated_glass": f"""
            background-color: rgba(38, 38, 80, 0.85);
            border: none;
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "avatar_gradient": f"""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
        """,

        "card_section": f"""
            background-color: rgba(34, 34, 69, 0.5);
            border: none;
            border-radius: {SIZES['radius']['lg']}px;
        """,

        "filter_group_wrapper": f"""
            QWidget {{
                background-color: rgba(34, 34, 69, 0.5);
                border: none;
                border-radius: {SIZES['radius']['lg']}px;
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['base']}px;
            }}
        """,

        "card": f"""
            background-color: {COLORS['card']};
            border: none;
            border-radius: {SIZES['radius']['xl']}px;
        """,

        "card_glass": f"""
            background-color: rgba(38, 38, 80, 0.65);
            border: 1px solid rgba(58, 58, 96, 0.4);
            border-radius: {SIZES['radius']['xl']}px;
        """,

        "frame_sidebar": f"""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['surface']}, stop:0.6 {COLORS['surface']},
                stop:1 #1C1C3F);
            border: none;
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "frame_card": f"""
            background-color: {COLORS['card']};
            border: none;
            border-radius: {SIZES['radius']['xl']}px;
        """,

        "nav_bar_gradient": f"""
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['surface']}, stop:0.5 #1C1C40,
                stop:1 {COLORS['surface']});
            border: none;
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "surface_radial": f"""
            background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.7,
                fx:0.5, fy:0.5,
                stop:0 rgba(122, 92, 255, 0.18),
                stop:0.5 rgba(122, 92, 255, 0.06),
                stop:1 rgba(0, 0, 0, 0));
            border-radius: {SIZES['radius']['xxl']}px;
        """,

        "title_section": f"""
            border-bottom: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['primary']}, stop:1 transparent);
            padding-bottom: {SIZES['spacing']['sm']}px;
        """,

        # ──────────────────── 按钮 ────────────────────
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

        "button_select": f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background-color: #3A3A60;
                border: 1px solid {COLORS['border_light']};
                border-radius: {SIZES['radius']['base']}px;
                height: {SIZES['button']['height']}px;
            }}
            QPushButton:hover {{
                background-color: #46467A;
                border-color: #5A5A90;
            }}
            QPushButton:pressed {{
                background-color: #2E2E50;
            }}
        """,

        "button_secondary": f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background-color: {COLORS['card']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['base']}px;
                height: {SIZES['button']['height']}px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
                border-color: {COLORS['border_light']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['card_elevated']};
            }}
        """,

        "button_danger": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: {COLORS['danger']};
                border: none;
                border-radius: {SIZES['radius']['base']}px;
                height: {SIZES['button']['height']}px;
            }}
            QPushButton:hover {{
                background-color: #FF8080;
            }}
            QPushButton:pressed {{
                background-color: #E55A5A;
            }}
        """,

        "push_button_gradient": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border: none;
                border-radius: {SIZES['radius']['lg']}px;
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

        "button_refresh": f"""
            QPushButton {{
                color: {COLORS['text_hint']};
                background: transparent;
                border: none;
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
            }}
        """,

        "button_glow": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border: none;
                border-radius: {SIZES['radius']['lg']}px;
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_light']}, stop:1 {COLORS['secondary']});
                border: 1px solid rgba(122, 92, 255, 0.4);
            }}
            QPushButton:pressed {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_dark']}, stop:1 {COLORS['primary']});
            }}
        """,

        "mode_button": f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background-color: transparent;
                border: none;
                border-radius: {SIZES['radius']['base']}px;
            }}
            QPushButton:checked {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border-left: 3px solid {COLORS['primary']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['card']};
            }}
        """,

        "mode_button_enhanced": f"""
            QPushButton {{
                color: {COLORS['text_secondary']};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {SIZES['radius']['base']}px;
            }}
            QPushButton:checked {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: 1px solid rgba(122, 92, 255, 0.35);
                border-left: 3px solid {COLORS['primary']};
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: 1px solid rgba(122, 92, 255, 0.18);
            }}
        """,

        # ──────────────────── 输入控件 ────────────────────
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
                border-radius: {SIZES['radius']['sm']}px;
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
            QDateEdit QCalendarWidget {{
                background-color: {COLORS['surface']};
            }}
            QDateEdit QCalendarWidget QTableView {{
                background-color: {COLORS['card']};
                alternate-background-color: {COLORS['card']};
                selection-background-color: {COLORS['primary']};
                selection-color: {COLORS['text']};
            }}
            QDateEdit QCalendarWidget QTableView::item {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
            }}
            QDateEdit QCalendarWidget QTableView::item:selected {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
            }}
            QDateEdit QCalendarWidget QAbstractItemView:enabled {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['primary']};
                selection-color: {COLORS['text']};
            }}
            QDateEdit QCalendarWidget QAbstractItemView:disabled {{
                color: {COLORS['text_disabled']};
            }}
            QDateEdit QCalendarWidget QWidget {{
                color: {COLORS['text']};
            }}
            QDateEdit QCalendarWidget QToolButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: none;
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QDateEdit QCalendarWidget QToolButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
            QCalendarWidget QHeaderView::section {{
                background-color: {COLORS['card']};
                color: {COLORS['text_secondary']};
                padding: {SIZES['spacing']['xs']}px;
                border: none;
            }}
            QDateEdit QCalendarWidget QTableView QHeaderView::section {{
                background-color: {COLORS['card']};
                color: {COLORS['text_secondary']};
                padding: {SIZES['spacing']['xs']}px;
                border: none;
            }}
            QCalendarWidget QTableView QHeaderView::section {{
                background-color: {COLORS['card']};
                color: {COLORS['text_secondary']};
                padding: 4px;
                border: none;
            }}
        """,

        "calendar_popup": f"""
            QCalendarWidget {{
                background-color: {COLORS['surface']};
            }}
            QCalendarWidget QTableView {{
                background-color: {COLORS['card']};
                alternate-background-color: {COLORS['card']};
                selection-background-color: {COLORS['primary']};
                selection-color: {COLORS['text']};
            }}
            QCalendarWidget QTableView::item {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
            }}
            QCalendarWidget QTableView::item:selected {{
                background-color: {COLORS['primary']};
                color: {COLORS['text']};
            }}
            QCalendarWidget QHeaderView::section {{
                background-color: {COLORS['card']};
                color: {COLORS['text_secondary']};
                padding: 4px;
                border: none;
            }}
            QCalendarWidget QToolButton {{
                color: {COLORS['text']};
                background-color: {COLORS['card']};
                border: none;
                border-radius: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {COLORS['card_hover']};
            }}
        """,

        "check_box": f"""
            QCheckBox {{
                color: {COLORS['text']};
            }}
        """,

        "input_field": f"""
            QLineEdit {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border']};
                border-radius: {SIZES['radius']['sm']}px;
                padding: {SIZES['spacing']['sm']}px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """,

        # ──────────────────── 分组 ────────────────────
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

        # ──────────────────── 表格 ────────────────────
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
            QTableWidget::item:selected {{
                background-color: {COLORS['card_elevated']};
                border-left: 3px solid {COLORS['primary']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_secondary']};
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['md']}px;
                border: none;
                border-bottom: {SIZES['border']['width']}px solid {COLORS['border']};
            }}
        """,

        "table_enhanced": f"""
            QTableWidget {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: none;
                border-radius: {SIZES['radius']['lg']}px;
                gridline-color: rgba(34, 34, 74, 0.5);
            }}
            QTableWidget::item {{
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['md']}px;
            }}
            QTableWidget::item:hover {{
                background-color: rgba(122, 92, 255, 0.08);
            }}
            QTableWidget::item:selected {{
                background-color: rgba(122, 92, 255, 0.15);
                color: {COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: rgba(21, 21, 48, 0.8);
                color: {COLORS['text_secondary']};
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['md']}px;
                border: none;
                border-bottom: 1px solid rgba(122, 92, 255, 0.15);
                font-weight: {FONTS['weight']['semibold']};
            }}
        """,

        # ──────────────────── 列表 ────────────────────
        "list_widget": f"""
            QListWidget {{
                background-color: transparent;
                border: none;
            }}
            QListWidget::item {{
                height: 70px;
                margin: 4px 0;
                border-radius: {SIZES['radius']['base']}px;
                padding: 4px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(122, 92, 255, 0.15);
                border-left: 3px solid {COLORS['primary']};
            }}
            QListWidget::item:hover {{
                background-color: rgba(122, 92, 255, 0.08);
            }}
        """,

        # ──────────────────── 文字标签 ────────────────────
        "label_title": f"""
            color: {COLORS['text']};
        """,

        "label_secondary": f"""
            color: {COLORS['text_secondary']};
        """,

        "label_hint": f"""
            color: {COLORS['text_hint']};
        """,

        "label_transparent": f"""
            color: {COLORS['text']};
            background: transparent;
        """,

        "label_section_title": f"""
            color: {COLORS['text_hint']};
            padding-left: {SIZES['spacing']['md']}px;
        """,

        # ──────────────────── 进度条 ────────────────────
        "progress_bar": f"""
            QProgressBar {{
                background-color: rgba(21, 21, 48, 0.6);
                border: none;
                border-radius: {SIZES['radius']['sm']}px;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: {SIZES['radius']['sm']}px;
            }}
        """,

        # ──────────────────── 徽章/标签 ────────────────────
        "badge": f"""
            background-color: {COLORS['card']};
            color: {COLORS['text_secondary']};
            border-radius: {SIZES['radius']['lg']}px;
            padding: {SIZES['spacing']['xs']}px {SIZES['spacing']['md']}px;
        """,

        "badge_success": f"""
            background-color: rgba(0, 224, 128, 0.15);
            color: {COLORS['focus_high']};
            border-radius: {SIZES['radius']['lg']}px;
            padding: {SIZES['spacing']['xs']}px {SIZES['spacing']['md']}px;
        """,

        "badge_danger": f"""
            background-color: rgba(255, 107, 107, 0.15);
            color: {COLORS['danger']};
            border-radius: {SIZES['radius']['lg']}px;
            padding: {SIZES['spacing']['xs']}px {SIZES['spacing']['md']}px;
        """,

        # ──────────────────── 圆点指示器 ────────────────────
        "dot_danger": f"""
            background-color: {COLORS['danger']};
            border-radius: 4px;
        """,

        "dot_success": f"""
            background-color: {COLORS['focus_high']};
            border-radius: 4px;
        """,

        "dot_hint": f"""
            background-color: {COLORS['text_hint']};
            border-radius: 4px;
        """,

        # ──────────────────── 视频 ────────────────────
        "video_placeholder": f"""
            background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
                fx:0.5, fy:0.5,
                stop:0 #1A1A3A, stop:1 {COLORS['background']});
            color: {COLORS['text_hint']};
            border-radius: {SIZES['radius']['xl']}px;
        """,

        "warn_bar": f"""
            background-color: rgba(255, 107, 107, 0.12);
            border-left: 3px solid {COLORS['danger']};
            border-radius: {SIZES['radius']['lg']}px;
        """,

        # ──────────────────── Plot ────────────────────
        "plot_widget": f"""
            background-color: {COLORS['background']};
        """,

        # ──────────────────── 全局 ────────────────────
        "main_window": f"background-color: {COLORS['background']};",

        "splitter": f"""
            QSplitter::handle {{
                background-color: transparent;
                border-radius: {SIZES['radius']['sm']}px;
            }}
            QSplitter::handle:hover {{
                background-color: rgba(122, 92, 255, 0.08);
            }}
            QSplitter::handle:pressed {{
                background-color: rgba(122, 92, 255, 0.15);
            }}
        """,

        # ──────────────────── 滚动条 ────────────────────
        "scroll_bar": f"""
            QScrollBar:vertical {{
                background: {COLORS['background']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['border_light']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """,

        # ──────────────────── 分割线 ────────────────────
        "divider_subtle": f"""
            background-color: rgba(200, 200, 216, 0.12);
            border: none;
            max-height: 1px;
        """,

        "separator": f"""
            background-color: {COLORS['border']};
            border: none;
        """,

        # ──────────────────── 遮罩 ────────────────────
        "overlay": f"""
            background-color: rgba(0, 0, 0, 0.6);
            border: none;
        """,

        # ──────────────────── 工具提示 ────────────────────
        "tooltip": f"""
            QToolTip {{
                background-color: {COLORS['card_elevated']};
                color: {COLORS['text']};
                border: {SIZES['border']['width']}px solid {COLORS['border_light']};
                border-radius: {SIZES['radius']['sm']}px;
                padding: {SIZES['spacing']['xs']}px {SIZES['spacing']['sm']}px;
            }}
        """,

        # ──────────────────── 人脸注册按钮 ────────────────────
        "register_face_button": f"""
            QPushButton {{
                color: {COLORS['text']};
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['secondary']});
                border: 1px solid rgba(122, 92, 255, 0.3);
                border-radius: {SIZES['radius']['base']}px;
                font-weight: {FONTS['weight']['bold']};
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_light']}, stop:1 {COLORS['secondary']});
                border: 1px solid rgba(122, 92, 255, 0.5);
            }}
            QPushButton:pressed {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_dark']}, stop:1 {COLORS['primary']});
            }}
        """,

        # ──────────────────── 完成页按钮 ────────────────────
        "completion_btn_local": f"""
            QPushButton {{
                color: #FFFFFF;
                background-color: #4A7CFF;
                border: none;
                border-radius: {SIZES['radius']['base']}px;
                font-weight: {FONTS['weight']['bold']};
                font-size: {FONTS['size']['base']}px;
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['xl']}px;
            }}
            QPushButton:hover {{
                background-color: #5B8DFF;
            }}
            QPushButton:pressed {{
                background-color: #3960CC;
            }}
        """,

        "completion_btn_temp": f"""
            QPushButton {{
                color: #FFFFFF;
                background-color: #00C853;
                border: none;
                border-radius: {SIZES['radius']['base']}px;
                font-weight: {FONTS['weight']['bold']};
                font-size: {FONTS['size']['base']}px;
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['xl']}px;
            }}
            QPushButton:hover {{
                background-color: #00E070;
            }}
            QPushButton:pressed {{
                background-color: #009940;
            }}
        """,

        "completion_btn_cancel": f"""
            QPushButton {{
                color: #4A7CFF;
                background-color: #FFFFFF;
                border: 1px solid #4A7CFF;
                border-radius: {SIZES['radius']['base']}px;
                font-weight: {FONTS['weight']['medium']};
                font-size: {FONTS['size']['base']}px;
                padding: {SIZES['spacing']['sm']}px {SIZES['spacing']['xl']}px;
            }}
            QPushButton:hover {{
                background-color: #F0F4FF;
            }}
            QPushButton:pressed {{
                background-color: #E0E8F8;
            }}
        """,

        # ──────────────────── 人脸注册弹窗 ────────────────────
        "face_registration_dialog": f"""
            QDialog {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-radius: {SIZES['radius']['xxl']}px;
            }}
        """,

        "face_registration_overlay": f"""
            background-color: rgba(0, 0, 0, 0.65);
            border: none;
        """,

        "pose_guide_label": f"""
            color: {COLORS['text']};
            font-size: {FONTS['size']['xl']}px;
            font-weight: {FONTS['weight']['bold']};
            background: transparent;
        """,

        "input_field_dialog": f"""
            QLineEdit {{
                background-color: {COLORS['card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: {SIZES['radius']['base']}px;
                padding: {SIZES['spacing']['base']}px {SIZES['spacing']['md']}px;
                font-size: {FONTS['size']['md']}px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
            QLineEdit::placeholder {{
                color: {COLORS['text_hint']};
            }}
        """,
    }
    return styles.get(style_name, "")


def get_font(size_key: str = "base", weight_key: str = "normal", family_key: str = "ui") -> tuple:
    """获取字体配置 (family, size, weight)

    Args:
        size_key:  字号键名 (xs, sm, base, md, lg, xl, xxl, title, hero)
        weight_key: 字重键名 (normal, medium, semibold, bold)
        family_key: 字体族角色 (display, ui, data)
    """
    family = FONTS.get(f"family_{family_key}", FONTS.get("family", ""))
    return (
        family,
        FONTS["size"][size_key],
        FONTS["weight"][weight_key],
    )


def get_spacing(key: str) -> int:
    """获取间距值"""
    return SIZES["spacing"][key]


def get_radius(key: str) -> int:
    """获取圆角值"""
    return SIZES["radius"][key]
