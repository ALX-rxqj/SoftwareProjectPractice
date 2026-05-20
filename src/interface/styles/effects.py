"""阴影效果工具 — 紫色环境色投影"""

import re
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor
from .colors import COLORS
from .sizes import SIZES


def _parse_rgba(rgba_str: str) -> QColor:
    """解析 'rgba(R, G, B, A)' 字符串为 QColor"""
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", rgba_str)
    if m:
        r, g, b, a = int(m[1]), int(m[2]), int(m[3]), float(m[4])
        return QColor(r, g, b, int(a * 255))
    return QColor(122, 92, 255, 38)


def create_card_shadow(elevated: bool = False) -> QGraphicsDropShadowEffect:
    """创建紫色调卡片投影。

    Args:
        elevated: True 表示高浮层（更大模糊、更远偏移、更深颜色）
    """
    shadow = QGraphicsDropShadowEffect()
    blur = SIZES["shadow"]["blur_elevated" if elevated else "blur_card"]
    offset_y = SIZES["shadow"]["offset_y_elevated" if elevated else "offset_y_card"]
    color_key = "shadow_color_deep" if elevated else "shadow_color"

    shadow.setBlurRadius(blur)
    shadow.setXOffset(0)
    shadow.setYOffset(offset_y)
    shadow.setColor(_parse_rgba(COLORS[color_key]))
    return shadow
