"""
数据显示管理器 - 统一管理bit_window和status_widget
可独立运行用于调试和测试，支持数据解析功能
"""
import sys
import random
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableView, QAbstractItemView, QMessageBox,
    QTextEdit, QSplitter, QGroupBox, QCheckBox
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

from struct_model import (
    get_all_status_bits_for_display, parse_all_status_from_sbs,
    HexParserApp, STRUCT_COMMANDS
)

# 导入数据解析器
try:
    from OTA_controller import TextDecode
except ImportError as e:
    print(f"警告：无法导入TextDecode: {e}")
    TextDecode = None


class DataParserManager:
    """数据解析管理器 - 封装数据解析逻辑"""

    def __init__(self, logger=None):
        self.logger = logger
        self.text_decoder = TextDecode() if TextDecode else None
        self.hex_parser = HexParserApp() if HexParserApp else None

    def parse_hex_string(self, hex_string):
        """解析十六进制字符串

        Args:
            hex_string: 十六进制字符串，如 "00 00 07 01 97 55 AA 8A 00 88"

        Returns:
            (success, result) 元组
            success: bool - 是否成功
            result: dict或str - 成功时返回解析结果字典，失败时返回错误信息
        """
        try:
            # 清理输入字符串
            hex_string = hex_string.strip().replace(' ', '').replace('\n', '').replace('\r', '')

            # 检查是否为有效的十六进制字符串
            if not hex_string:
                return False, "输入为空"

            if not all(c in '0123456789ABCDEFabcdef' for c in hex_string):
                return False, "包含非十六进制字符"

            # 转换为bytearray
            if len(hex_string) % 2 != 0:
                return False, "十六进制字符串长度必须为偶数"

            data_bytes = bytearray.fromhex(hex_string)

            if self.logger:
                self.logger.write_log(f"开始解析数据: {len(data_bytes)} 字节")

            # 使用TextDecode分割数据
            if not self.text_decoder:
                return False, "TextDecode未初始化"

            self.text_decoder.split_data(data_bytes)

            if not self.text_decoder.have_hex:
                return False, f"数据格式错误: {self.text_decoder.legality}"

            # 使用HexParser解析数据
            if not self.hex_parser:
                return False, "HexParserApp未初始化"

            struct_name, dict_data = self.hex_parser.decode_cmd_hex_data(
                self.text_decoder.no80_cmd,
                bytes(self.text_decoder.data_hex)
            )

            if not dict_data:
                return False, f"无法解析命令 0x{self.text_decoder.no80_cmd:02X}"

            if self.logger:
                self.logger.write_log(f"解析成功: {struct_name}")

            return True, {
                'struct_name': struct_name,
                'cmd': self.text_decoder.no80_cmd,
                'data': dict_data,
                'raw_bytes': data_bytes
            }

        except Exception as e:
            error_msg = f"解析失败: {str(e)}\n{traceback.format_exc()}"
            if self.logger:
                self.logger.write_log(error_msg)
            return False, error_msg


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
    可作为独立窗口运行用于调试，支持数据解析功能
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

        # 数据解析管理器
        self.data_parser = DataParserManager(logger=logger)

        if standalone:
            self.init_standalone_ui()
        else:
            self.init_embedded_mode()

    def init_standalone_ui(self):
        """初始化独立窗口UI"""
        self.setWindowTitle('数据显示管理器 - 调试模式（支持数据解析）')
        self.setGeometry(100, 100, 1400, 800)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout()

        # 创建控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # 创建分割器（上下分割）
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ========== 上半部分：数据输入和解析 ==========
        parse_panel = self.create_parse_panel()
        splitter.addWidget(parse_panel)

        # ========== 下半部分：数据显示窗口 ==========
        display_panel = QWidget()
        display_layout = QHBoxLayout()

        # 创建bit_window
        self.bit_window_manager = BitWindowManager(parent=display_panel)
        self.bit_window_manager.widget.setMinimumSize(580, 400)
        display_layout.addWidget(self.bit_window_manager.widget)

        # 创建status_widget
        self.status_window_manager = StatusWindowManager(parent=display_panel, logger=self.logger)
        self.status_window_manager.widget.setMinimumSize(390, 400)
        display_layout.addWidget(self.status_window_manager.widget)

        display_panel.setLayout(display_layout)
        splitter.addWidget(display_panel)

        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)
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
        # 联系信息
        contact_label = QLabel('有疑问请联系郭学成')
        contact_label.setStyleSheet("QLabel { font-size: 11px; color: #7f8c8d; margin-left: 15px; }")
        layout.addWidget(contact_label)
        # 32串/16串配置切换
        self.cell_32_checkbox = QCheckBox('32电芯配置')
        self.cell_32_checkbox.setToolTip('勾选：32电芯+15温度传感器\n不勾选：16电芯+SBS 5温度+KB 8温度')
        self.cell_32_checkbox.stateChanged.connect(self.on_cell_config_changed)
        layout.addWidget(self.cell_32_checkbox)

        layout.addStretch()

        # 测试按钮
        test_bit_btn = QPushButton('📊 测试位标志')
        test_bit_btn.clicked.connect(self.test_bit_data)
        layout.addWidget(test_bit_btn)

        test_status_btn = QPushButton('🚦 测试状态位')
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

    def create_parse_panel(self):
        """创建数据解析面板"""
        group_box = QGroupBox("📡 数据解析调试工具")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QVBoxLayout()

        # 输入区域
        input_layout = QHBoxLayout()
        input_label = QLabel('输入数据 (十六进制):')
        input_layout.addWidget(input_label)

        self.hex_input = QTextEdit()
        self.hex_input.setMaximumHeight(80)
        self.hex_input.setPlaceholderText("输入十六进制字符串，例如：\n00 00 0C 01 93 55 AA 86 00 00 00 00 00 02 00 B4")
        self.hex_input.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        input_layout.addWidget(self.hex_input)

        # 解析按钮
        parse_btn = QPushButton('🔍 解析数据')
        parse_btn.setMinimumWidth(120)
        parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        parse_btn.clicked.connect(self.parse_input_data)
        input_layout.addWidget(parse_btn)

        layout.addLayout(input_layout)

        # 快捷示例按钮
        example_layout = QHBoxLayout()
        example_label = QLabel('快捷示例:')
        example_layout.addWidget(example_label)

        # PC_GET_BMS示例
        bms_btn = QPushButton('BMS数据')
        bms_btn.clicked.connect(lambda: self.hex_input.setText('00 00 0C 01 93 55 AA 86 00 00 00 00 00 02 00 B4'))
        example_layout.addWidget(bms_btn)

        # PC_GET_SBS示例
        sbs_btn = QPushButton('SBS数据')
        sbs_btn.clicked.connect(lambda: self.hex_input.setText('00 00 1A 01 B3 55 AA A6 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1D'))
        example_layout.addWidget(sbs_btn)

        example_layout.addStretch()
        layout.addLayout(example_layout)

        # 输出区域
        output_label = QLabel('解析结果:')
        layout.addWidget(output_label)

        self.parse_output = QTextEdit()
        self.parse_output.setReadOnly(True)
        self.parse_output.setMaximumHeight(150)
        self.parse_output.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.parse_output)

        group_box.setLayout(layout)
        return group_box

    def parse_input_data(self):
        """解析输入的数据"""
        hex_string = self.hex_input.toPlainText()

        if not hex_string.strip():
            self.parse_output.setText("❌ 错误：输入为空")
            return

        self.parse_output.append(f"\n{'='*60}")
        self.parse_output.append(f"⏳ 开始解析数据...")
        self.parse_output.append(f"{'='*60}\n")

        # 解析数据
        success, result = self.data_parser.parse_hex_string(hex_string)

        if success:
            # 解析成功
            struct_name = result['struct_name']
            cmd = result['cmd']
            dict_data = result['data']
            raw_bytes = result['raw_bytes']

            self.parse_output.append(f"✅ 解析成功！")
            self.parse_output.append(f"📋 命令名称: {struct_name}")
            self.parse_output.append(f"🔢 命令代码: 0x{cmd:02X}")
            self.parse_output.append(f"📦 数据长度: {len(raw_bytes)} 字节")
            self.parse_output.append(f"")

            # 处理解析结果
            self.process_parsed_data(struct_name, dict_data)

            # 显示详细数据
            self.parse_output.append(f"📊 详细数据:")
            self.parse_output.append(f"{'-'*60}")

            for category, items in dict_data.items():
                self.parse_output.append(f"\n[{category}]")
                for item in items:
                    if len(item) >= 3:
                        name, unit, value = item[0], item[1], item[2]
                        self.parse_output.append(f"  {name:<30} = {value:>15}  {unit}")

        else:
            # 解析失败
            self.parse_output.append(f"❌ 解析失败！")
            self.parse_output.append(f"")
            self.parse_output.append(f"错误信息:")
            self.parse_output.append(f"{result}")

        # 滚动到底部
        self.parse_output.verticalScrollBar().setValue(
            self.parse_output.verticalScrollBar().maximum()
        )

    def process_parsed_data(self, struct_name, dict_data):
        """处理解析后的数据，更新显示窗口"""
        try:
            # 格式化数据为bit_window需要的格式
            formatted_data = []
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        name, unit, value = item[0], item[1], item[2]
                        formatted_data.append((name, value, value))  # (名称, 十六进制, 十进制)

            # 更新bit_window
            if formatted_data:
                self.update_bit_data(formatted_data)
                if hasattr(self, 'parse_output'):
                    self.parse_output.append(f"📈 已更新位标志窗口: {len(formatted_data)} 个参数")

            # 如果是SBS数据，更新状态位
            if struct_name == 'PC_GET_SBS':
                # 将dict_data转换为flat_dict
                flat_dict = {}
                for category, items in dict_data.items():
                    for item in items:
                        if len(item) >= 3:
                            name = item[0]
                            value_str = item[2]
                            try:
                                if isinstance(value_str, str) and value_str.startswith('0x'):
                                    flat_dict[name] = int(value_str, 16)
                                else:
                                    flat_dict[name] = int(value_str)
                            except (ValueError, TypeError):
                                flat_dict[name] = value_str

                # 更新状态位
                status_bits = get_all_status_bits_for_display(flat_dict)
                if status_bits:
                    self.update_status_bits_direct(status_bits)
                    if hasattr(self, 'parse_output'):
                        self.parse_output.append(f"🚦 已更新状态位窗口: {len(status_bits)} 个状态位")

        except Exception as e:
            if hasattr(self, 'parse_output'):
                self.parse_output.append(f"⚠️ 更新显示窗口时出错: {str(e)}")
            if self.logger:
                self.logger.write_log(f"处理解析数据失败: {e}\n{traceback.format_exc()}")

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

    def parse_raw_data(self, hex_bytes):
        """解析原始数据（供主程序调用）

        Args:
            hex_bytes: bytearray或bytes对象

        Returns:
            (success, result) 元组
        """
        hex_string = hex_bytes.hex()
        return self.data_parser.parse_hex_string(hex_string)

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
    def on_cell_config_changed(self, state):
        """处理32电芯配置checkbox状态变化"""
        try:
            if state == Qt.CheckState.Checked.value:
                self.data_parser.hex_parser.set_struct_to_cell_32()
                if self.logger:
                    self.logger.write_log("已切换到32串配置（32电芯 + 15温度传感器）")
            else:
                self.data_parser.hex_parser.set_struct_to_cell_16()
                if self.logger:
                    self.logger.write_log("已切换到16串配置（16电芯 + SBS:5温度 + KB:8温度）")
        except Exception as e:
            if self.logger:
                self.logger.write_log(f"切换配置失败: {str(e)}")


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
