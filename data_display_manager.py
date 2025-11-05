"""
数据显示管理器 - 统一管理bit_window和status_widget
可独立运行用于调试和测试
"""
import sys
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# 导入显示组件（从独立模块，避免循环导入）
try:
    from display_widgets import BitFlagsTableModel, StatusBitsWidget
except ImportError as e:
    print(f"警告：无法导入BitFlagsTableModel和StatusBitsWidget: {e}")
    print("请确保display_widgets.py在同一目录下")
    BitFlagsTableModel = None
    StatusBitsWidget = None

from struct_model import get_all_status_bits_for_display, parse_all_status_from_sbs


class BitWindowManager:
    """位标志窗口管理器"""

    def __init__(self, parent=None):
        self.parent = parent
        self.widget = QWidget(parent)
        self.table_view = None
        self.table_model = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 创建布局
        layout = QVBoxLayout()

        # 创建标题
        title_label = QLabel('位标志参数配置窗口')
        title_label.setStyleSheet("QLabel { color: blue; font-weight: bold; font-size: 12px; }")
        layout.addWidget(title_label)

        # 创建按钮
        button_layout = QHBoxLayout()
        self.send_button = QPushButton('发送修改')
        self.clear_button = QPushButton('清空修改')
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 创建表格视图
        if BitFlagsTableModel:
            self.table_view = QTableView()
            self.table_model = BitFlagsTableModel()
            self.table_view.setModel(self.table_model)

            # 设置表格属性
            self.table_view.setAlternatingRowColors(True)
            self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table_view.horizontalHeader().setStretchLastSection(False)

            # 设置列宽
            column_widths = [80, 60, 60, 80, 60, 60, 80, 60, 60]
            for i, width in enumerate(column_widths):
                self.table_view.setColumnWidth(i, width)

            layout.addWidget(self.table_view)
        else:
            error_label = QLabel('错误：无法加载BitFlagsTableModel')
            error_label.setStyleSheet("QLabel { color: red; }")
            layout.addWidget(error_label)

        self.widget.setLayout(layout)

        # 连接信号
        if self.clear_button:
            self.clear_button.clicked.connect(self.clear_write_values)

    def update_data(self, data):
        """更新数据"""
        if self.table_model:
            self.table_model.update_data(data)

    def get_modified_data(self):
        """获取修改的数据"""
        if self.table_model:
            return self.table_model.get_modified_data()
        return []

    def clear_write_values(self):
        """清空写入值"""
        if self.table_model:
            self.table_model.clear_write_values()

    def show(self):
        """显示窗口"""
        self.widget.show()

    def hide(self):
        """隐藏窗口"""
        self.widget.hide()

    def set_geometry(self, x, y, width, height):
        """设置窗口位置和大小"""
        self.widget.setGeometry(x, y, width, height)


class StatusWindowManager:
    """状态位窗口管理器"""

    def __init__(self, parent=None, logger=None):
        self.parent = parent
        self.logger = logger

        if StatusBitsWidget:
            self.widget = StatusBitsWidget(parent=parent, logger=logger)
        else:
            # 备用方案：创建简单的错误显示
            self.widget = QWidget(parent)
            layout = QVBoxLayout()
            error_label = QLabel('错误：无法加载StatusBitsWidget')
            error_label.setStyleSheet("QLabel { color: red; }")
            layout.addWidget(error_label)
            self.widget.setLayout(layout)

    def update_status_bits(self, status_list):
        """更新状态位
        Args:
            status_list: 列表，每项格式为 {'name': str, 'value': int}
        """
        if hasattr(self.widget, 'update_status_bits'):
            self.widget.update_status_bits(status_list)

    def clear_status_bits(self):
        """清空状态位"""
        if hasattr(self.widget, 'clear_status_bits'):
            self.widget.clear_status_bits()

    def show(self):
        """显示窗口"""
        self.widget.show()

    def hide(self):
        """隐藏窗口"""
        self.widget.hide()

    def set_geometry(self, x, y, width, height):
        """设置窗口位置和大小"""
        self.widget.setGeometry(x, y, width, height)


class DataDisplayManager(QMainWindow):
    """
    数据显示管理器 - 统一管理所有数据显示窗口
    可作为独立窗口运行用于调试
    """

    def __init__(self, parent=None, logger=None, standalone=False):
        """
        Args:
            parent: 父窗口（嵌入模式时使用）
            logger: 日志记录器
            standalone: 是否独立窗口模式
        """
        super().__init__(parent)
        self.logger = logger
        self.standalone = standalone

        # 窗口管理器
        self.bit_window_manager = None
        self.status_window_manager = None

        if standalone:
            self.init_standalone_ui()
        else:
            self.init_embedded_mode()

    def init_standalone_ui(self):
        """初始化独立窗口UI"""
        self.setWindowTitle('数据显示管理器 - 调试模式')
        self.setGeometry(100, 100, 1200, 650)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout()

        # 创建控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # 创建数据窗口容器
        windows_container = QWidget()
        windows_layout = QHBoxLayout()

        # 创建bit_window
        self.bit_window_manager = BitWindowManager(parent=windows_container)
        self.bit_window_manager.widget.setMinimumSize(580, 580)
        windows_layout.addWidget(self.bit_window_manager.widget)

        # 创建status_widget
        self.status_window_manager = StatusWindowManager(parent=windows_container, logger=self.logger)
        self.status_window_manager.widget.setMinimumSize(390, 580)
        windows_layout.addWidget(self.status_window_manager.widget)

        windows_container.setLayout(windows_layout)
        main_layout.addWidget(windows_container)

        central_widget.setLayout(main_layout)

        # 连接信号
        if self.bit_window_manager and hasattr(self.bit_window_manager, 'send_button'):
            self.bit_window_manager.send_button.clicked.connect(self.on_send_modified)

    def create_control_panel(self):
        """创建控制面板（用于独立调试）"""
        panel = QWidget()
        layout = QHBoxLayout()

        # 标题
        title_label = QLabel('🎛️ 数据显示管理器控制面板')
        title_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
        layout.addWidget(title_label)

        layout.addStretch()

        # 测试按钮
        test_bit_btn = QPushButton('📊 测试位标志数据')
        test_bit_btn.clicked.connect(self.test_bit_data)
        layout.addWidget(test_bit_btn)

        test_status_btn = QPushButton('🚦 测试状态位数据')
        test_status_btn.clicked.connect(self.test_status_data)
        layout.addWidget(test_status_btn)

        clear_all_btn = QPushButton('🗑️ 清空所有')
        clear_all_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_all_btn)

        panel.setLayout(layout)
        panel.setStyleSheet("""
            QWidget {
                background-color: #ecf0f1;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)

        return panel

    def init_embedded_mode(self):
        """初始化嵌入模式（在主程序中使用）"""
        # 在嵌入模式下，窗口由外部创建和管理
        pass

    # ==================== 窗口创建接口 ====================

    def create_windows(self, parent_widget):
        """创建所有窗口（嵌入模式使用）

        Args:
            parent_widget: 父窗口部件
        """
        self.bit_window_manager = BitWindowManager(parent=parent_widget)
        self.status_window_manager = StatusWindowManager(parent=parent_widget, logger=self.logger)

    def setup_windows_geometry(self, bit_geom, status_geom):
        """设置窗口位置和大小

        Args:
            bit_geom: (x, y, width, height) 元组
            status_geom: (x, y, width, height) 元组
        """
        if self.bit_window_manager:
            self.bit_window_manager.set_geometry(*bit_geom)
        if self.status_window_manager:
            self.status_window_manager.set_geometry(*status_geom)

    def show_windows(self):
        """显示所有窗口"""
        if self.bit_window_manager:
            self.bit_window_manager.show()
        if self.status_window_manager:
            self.status_window_manager.show()

    def hide_windows(self):
        """隐藏所有窗口"""
        if self.bit_window_manager:
            self.bit_window_manager.hide()
        if self.status_window_manager:
            self.status_window_manager.hide()

    # ==================== 数据输入接口 ====================

    def update_bit_data(self, parsed_data):
        """更新位标志数据

        Args:
            parsed_data: 解析后的数据列表，格式：[(name, hex_value, dec_value), ...]
        """
        if self.bit_window_manager:
            self.bit_window_manager.update_data(parsed_data)
            if self.logger:
                self.logger.write_log(f"更新位标志数据: {len(parsed_data)} 行")

    def update_status_data(self, sbs_data_dict):
        """更新状态位数据（从SBS数据字典）

        Args:
            sbs_data_dict: PC_GET_SBS解析后的字典
        """
        if self.status_window_manager:
            # 使用struct_model中的函数解析状态位
            status_bits = get_all_status_bits_for_display(sbs_data_dict)
            self.status_window_manager.update_status_bits(status_bits)
            if self.logger:
                self.logger.write_log(f"更新状态位数据: {len(status_bits)} 个状态位")

    def update_status_bits_direct(self, status_list):
        """直接更新状态位数据（已解析格式）

        Args:
            status_list: 状态位列表，格式：[{'name': str, 'value': int}, ...]
        """
        if self.status_window_manager:
            self.status_window_manager.update_status_bits(status_list)

    # ==================== 数据输出接口 ====================

    def get_modified_values(self):
        """获取修改的值

        Returns:
            list: [(row, param_name, current_value, write_value), ...]
        """
        if self.bit_window_manager:
            return self.bit_window_manager.get_modified_data()
        return []

    def get_write_values_dict(self):
        """获取写入值字典

        Returns:
            dict: {row: write_value, ...}
        """
        if self.bit_window_manager and self.bit_window_manager.table_model:
            return self.bit_window_manager.table_model.get_write_values()
        return {}

    # ==================== 控制接口 ====================

    def clear_bit_write_values(self):
        """清空位标志的写入值"""
        if self.bit_window_manager:
            self.bit_window_manager.clear_write_values()

    def clear_status_bits(self):
        """清空状态位"""
        if self.status_window_manager:
            self.status_window_manager.clear_status_bits()

    def clear_all(self):
        """清空所有数据"""
        self.clear_bit_write_values()
        self.clear_status_bits()
        if self.logger:
            self.logger.write_log("已清空所有数据")

    # ==================== 信号回调 ====================

    def on_send_modified(self):
        """发送修改值按钮回调"""
        modified = self.get_modified_values()
        if not modified:
            QMessageBox.information(self, '提示', '没有修改的数据')
            return

        msg = f"准备发送 {len(modified)} 个修改的参数：\n\n"
        for row, name, current, write in modified[:5]:  # 只显示前5个
            msg += f"{name}: {current} → {write}\n"
        if len(modified) > 5:
            msg += f"\n... 还有 {len(modified) - 5} 个参数"

        QMessageBox.information(self, '修改的参数', msg)

    # ==================== 测试功能（独立模式使用）====================

    def test_bit_data(self):
        """生成测试位标志数据"""
        test_data = []
        param_names = [
            'ulPack_OVP_Threshold', 'ulPack_OVP_Resume', 'ulBatt_OVP_Threshold',
            'ulBatt_OVP_Resume', 'ulCell_OVP_Threshold', 'ulCell_OVP_Resume',
            'ulPack_UVP_Threshold', 'ulPack_UVP_Resume', 'ulBatt_UVP_Threshold',
            'ulBatt_UVP_Resume', 'lCHG_OCP_Threshold', 'lDIS_OCP_Threshold',
            'sCHG_OTP_Threshold', 'sCHG_OTP_Resume', 'sDIS_OTP_Threshold',
            'sDIS_OTP_Resume', 'sCHG_UTP_Threshold', 'sCHG_UTP_Resume',
            'usCell_OVA_Threshold', 'usCell_UVA_Threshold'
        ]

        for i, name in enumerate(param_names):
            value = random.randint(1000, 9999)
            test_data.append((name, f"0x{value:04X}", value))

        self.update_bit_data(test_data)
        if self.logger:
            self.logger.write_log(f"生成测试位标志数据: {len(test_data)} 行")

    def test_status_data(self):
        """生成测试状态位数据"""
        test_data = []

        # 生成测试数据（告警）
        for i in range(14):
            test_data.append({
                'name': f'告_测试{i:02d}',
                'value': random.randint(0, 1)
            })

        # 生成测试数据（保护）
        for i in range(21):
            test_data.append({
                'name': f'护_测试{i:02d}',
                'value': random.randint(0, 1)
            })

        # 生成测试数据（失效）
        for i in range(12):
            test_data.append({
                'name': f'错_测试{i:02d}',
                'value': random.randint(0, 1)
            })

        # 生成测试数据（其他）
        for i in range(21):
            test_data.append({
                'name': f'另_测试{i:02d}',
                'value': random.randint(0, 1)
            })

        self.update_status_bits_direct(test_data)
        if self.logger:
            self.logger.write_log(f"生成测试状态位数据: {len(test_data)} 个")


# ==================== 独立运行（用于调试）====================

class SimpleLogger:
    """简单的日志记录器（用于独立模式）"""
    def write_log(self, message):
        print(f"[LOG] {message}")


def main():
    """独立运行主函数"""
    app = QApplication(sys.argv)

    # 创建简单日志
    logger = SimpleLogger()

    # 创建数据显示管理器（独立模式）
    manager = DataDisplayManager(logger=logger, standalone=True)
    manager.show()

    # 自动生成测试数据
    QTimer.singleShot(500, manager.test_bit_data)
    QTimer.singleShot(1000, manager.test_status_data)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

