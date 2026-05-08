import pyqtgraph as pg

from .styles import COLORS, FONTS, SIZES


WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
LEFT_BAR_WIDTH = SIZES["sidebar"]["width"]
RIGHT_PANEL_WIDTH = 400
TOP_NAV_HEIGHT = SIZES["toolbar"]["height"]

pg.setConfigOption('foreground', 'w')
FONT_FAMILY = FONTS["family"]
FONT_SIZE_SMALL = FONTS["size"]["sm"]
FONT_SIZE_NORMAL = FONTS["size"]["base"]
FONT_SIZE_LARGE = FONTS["size"]["lg"]
FONT_SIZE_XLARGE = FONTS["size"]["xxl"]
