"""
导出控制器 - Export Controller

从 MainWindow 中提取的报告导出逻辑。
零 widget 耦合，仅依赖 unified_data_manager 和 export_report_util。
"""

from PyQt5.QtWidgets import QMenu, QFileDialog, QMessageBox

from .styles import COLORS, message_box_style
from .unified_data_manager import unified_data_manager
from .export_report_util import export_to_excel, export_to_pdf


def _msg(parent, level: str, title: str, text: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStyleSheet(message_box_style())
    box.exec_()


def _menu_style() -> str:
    return f"""
        QMenu {{
            background-color: {COLORS['card']};
            color: {COLORS['text']};
            border: 1px solid {COLORS['border_light']};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 32px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {COLORS['primary']};
        }}
    """


def export_report(session_data: dict, records: list, parent) -> None:
    """弹出导出菜单 → 选择格式 → 导出报告

    Args:
        session_data: 会话数据 dict
        records: 专注度评分记录列表
        parent: QWidget 父窗口（用于 QFileDialog 和 QMessageBox）
    """
    session_id = session_data.get("session_id", "")
    if not session_id or not records:
        _msg(parent, "warning", "提示", "无有效数据可供导出")
        return

    alerts = unified_data_manager.generate_alarm_events(session_id)

    menu = QMenu(parent)
    menu.setStyleSheet(_menu_style())

    excel_action = menu.addAction("导出 Excel (.xlsx)")
    pdf_action = menu.addAction("导出 PDF (.pdf)")

    chosen = menu.exec_(parent.cursor().pos())
    if not chosen:
        return

    if chosen == excel_action:
        filepath, _ = QFileDialog.getSaveFileName(
            parent, "导出 Excel 报告",
            f"{session_id}_report.xlsx",
            "Excel 文件 (*.xlsx)",
        )
        if filepath:
            try:
                export_to_excel(session_data, records, alerts, filepath)
                _msg(parent, "info", "成功", f"报告已导出至:\n{filepath}")
            except Exception as e:
                _msg(parent, "critical", "错误", f"导出失败: {str(e)}")

    elif chosen == pdf_action:
        filepath, _ = QFileDialog.getSaveFileName(
            parent, "导出 PDF 报告",
            f"{session_id}_report.pdf",
            "PDF 文件 (*.pdf)",
        )
        if filepath:
            try:
                export_to_pdf(session_data, records, alerts, filepath)
                _msg(parent, "info", "成功", f"报告已导出至:\n{filepath}")
            except Exception as e:
                _msg(parent, "critical", "错误", f"导出失败: {str(e)}")
