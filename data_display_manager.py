"""
数据显示管理器 - 统一管理battery_window和bit_window
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
    from display_widgets import BatteryTableModel, BitFlagsWidget, MultiColumnBitFlagsWidget
except ImportError as e:
    print(f"警告：无法导入BatteryTableModel和BitFlagsWidget: {e}")
    print("请确保display_widgets.py在同一目录下")
    BatteryTableModel = None
    BitFlagsWidget = None
    MultiColumnBitFlagsWidget = None

from struct_model import (
    get_all_status_bits_for_display, parse_all_status_from_sbs,
    HexParserApp, STRUCT_COMMANDS
)
# SN码解析规则映射表
SN_PRODUCT_TYPE = {'B': '电池', 'C': '充电器', 'M': 'MPPT', 'D': 'DCDC', 'H': '逆充控', 'A': '逆充', 'I': '纯逆变器'}
SN_FACTORY = {'A': '安培时代新能源', 'D': '安培时代数字能源', 'S': '坪山一厂', 'H': '坪山二厂', 'W': '东莞一厂'}
SN_BRAND = {'L': 'Li Time', 'P': 'Power queen', 'T': 'Time USB', 'R': 'Redodo', 'S': 'Starrysea'}
SN_CELL_BRAND = {'P': '鹏辉', 'G': '国轩', 'Y': '亿纬', 'R': '瑞浦', 'X': '欣旺达', 'H': '中航', 'B': '比亚迪', 'F': '赣锋', 'A': '安驰', 'U': '玉皇', 'Z': '中比', 'N': '宁德时代'}
SN_FUNCTION = {'G': '高尔夫球车', 'S': '启动电池', 'B': '蓝牙款', 'C': '并机通讯', 'L': '低温款', 'H': '加热款', 'P': 'Plus', 'E': '串联', 'M': '信率款', 'D': '两用启动', 'I': '逆变器通讯', 'R': '外接显示屏', 'N': '空位符'}
SN_INSTALL = {'Z': '正面不能朝下', 'F': '反面不能朝下', 'L': '左面不能朝下', 'R': '右面不能朝下', 'A': '正面+反面不能朝下', 'B': '正面+左面不能朝下', 'C': '正面+右面不能朝下', 'D': '反面+左面不能朝下', 'E': '反面+右面不能朝下', 'G': '左面+右面不能朝下', 'H': '只有默认顶面不能朝下'}
SN_BMS = {'Y': '自研硬件板', 'R': '自研软件板', 'S': '赛航', 'W': '唯美', 'J': '嘉佰达', 'P': '沛城'}

# 导入数据解析器
try:
    from OTA_controller import TextDecode
except ImportError as e:
    print(f"警告：无法导入TextDecode: {e}")
    TextDecode = None


class SNCodeParser:
    """SN码解析器 - 支持电池和核心部件SN码"""
    
    def parse_sn_code(self, sn_code):
        """自动识别并解析SN码
        Args:
            sn_code: SN码字符串
        Returns:
            (success, result) 元组
        """
        try:
            sn_code = sn_code.strip().upper()
            if not sn_code:
                return False, "输入为空"
            first_char = sn_code[0]
            if first_char == 'B' and len(sn_code) == 27:
                return self.parse_battery_sn(sn_code)
            elif first_char in 'CDIMAH' and len(sn_code) >= 25:
                return self.parse_core_component_sn(sn_code)
            else:
                return False, f"无法识别的SN码格式（首字符: {first_char}, 长度: {len(sn_code)}）"
        except Exception as e:
            return False, f"解析失败: {str(e)}"
    
    def parse_battery_sn(self, sn_code):
        """解析电池SN码（27位）"""
        try:
            if sn_code[9] != '-' or sn_code[13] != '-' or sn_code[22] != '-':
                return False, f"电池SN码格式错误：分隔符位置不正确"
            result = {}
            result['SN码类型'] = '电池'
            result['产品品类'] = SN_PRODUCT_TYPE.get(sn_code[0], f'未知({sn_code[0]})')
            result['生产工厂'] = SN_FACTORY.get(sn_code[1], f'未知({sn_code[1]})')
            result['产品品牌'] = SN_BRAND.get(sn_code[2], f'未知({sn_code[2]})')
            result['电芯品牌'] = SN_CELL_BRAND.get(sn_code[3], f'未知({sn_code[3]})')
            model_str = sn_code[4:9]
            if 'N' in model_str:
                voltage = model_str[:model_str.index('N')] + '.' + model_str[model_str.index('N')+1:]
                capacity = ''
            else:
                voltage = model_str[:2]
                capacity = model_str[2:].lstrip('0') or '0'
            result['型号'] = f"{voltage}V {capacity}Ah" if capacity else voltage
            func_str = sn_code[10:13]
            functions = []
            for c in func_str:
                func = SN_FUNCTION.get(c, '')
                if func and func != '空位符':
                    functions.append(func)
            result['功能'] = '+'.join(functions) if functions else '基础款'
            result['打包日期'] = self._parse_date(sn_code[14:17])
            result['序列号'] = sn_code[17:21]
            result['安装方式识别号'] = SN_INSTALL.get(sn_code[21], f'未知({sn_code[21]})')
            shell_code = sn_code[23:26]
            if shell_code.startswith('A'):
                result['壳体型号'] = shell_code
            elif shell_code[0] in 'HS':
                result['壳体型号'] = shell_code
            else:
                result['壳体型号'] = 'A' + shell_code
            result['BMS板厂家'] = SN_BMS.get(sn_code[26], f'未知({sn_code[26]})')
            return True, result
        except Exception as e:
            return False, f"电池SN码解析失败: {str(e)}"
    
    def parse_core_component_sn(self, sn_code):
        """解析核心部件SN码（25-27位）"""
        try:
            result = {}
            result['SN码类型'] = '核心部件'
            product_types = {'C': 'AC-DC充电器', 'D': 'DC-DC充电器', 'I': '逆变器', 'M': 'MPPT太阳能控制器', 'A': '逆充一体机', 'H': '逆充控一体机'}
            product_type = sn_code[0]
            result['产品品类'] = product_types.get(product_type, f'未知({product_type})')
            result['供应商代码'] = sn_code[1]
            brands = {'L': 'Li Time', 'A': 'Ampere Time', 'P': 'Power Queen', 'R': 'REDODO', 'T': 'Time USB', 'S': 'Starry Sea'}
            result['产品品牌'] = brands.get(sn_code[2], f'未知({sn_code[2]})')
            specs = {'U': '美规', 'E': '欧规', 'J': '日规', 'R': '其他'}
            result['出口规格'] = specs.get(sn_code[3], f'未知({sn_code[3]})')
            if product_type == 'C':
                result['型号'] = self._parse_charger_model(sn_code[4:9])
                result['功能配置'] = self._parse_charger_functions(sn_code[10:13])
            elif product_type == 'D':
                result['型号'] = self._parse_dcdc_model(sn_code[4:9])
                result['功能配置'] = self._parse_dcdc_functions(sn_code[10:13])
            elif product_type == 'I':
                result['型号'] = self._parse_inverter_model(sn_code[4:9])
                result['功能配置'] = self._parse_inverter_functions(sn_code[10:13])
            elif product_type == 'M':
                result['型号'] = self._parse_mppt_model(sn_code[4:9])
                result['功能配置'] = self._parse_mppt_functions(sn_code[10:13])
            elif product_type == 'A':
                result['型号'] = self._parse_inverter_charger_model(sn_code[4:9])
                result['功能配置'] = self._parse_inverter_charger_functions(sn_code[10:13])
            elif product_type == 'H':
                result['型号'] = self._parse_hybrid_model(sn_code[4:9])
                result['功能配置'] = self._parse_hybrid_functions(sn_code[10:13])
            result['打包日期'] = self._parse_date(sn_code[14:17])
            result['序列号'] = sn_code[17:21]
            result['特殊功能'] = sn_code[21] if len(sn_code) > 21 else '-'
            if len(sn_code) >= 25:
                if product_type in ['A', 'H']:
                    result['AC配置'] = sn_code[23:] if len(sn_code) > 23 else '-'
                else:
                    result['扩展信息'] = sn_code[23:] if len(sn_code) > 23 else '-'
            return True, result
        except Exception as e:
            return False, f"核心部件SN码解析失败: {str(e)}"
    
    def _parse_date(self, date_str):
        """解析打包日期"""
        year_char, month_char, day_char = date_str[0], date_str[1], date_str[2]
        year = 2024 + (ord(year_char) - ord('A'))
        month_map = {'1':'01','2':'02','3':'03','4':'04','5':'05','6':'06','7':'07','8':'08','9':'09','A':'10','B':'11','C':'12'}
        month = month_map.get(month_char, '??')
        day_map = {'1':'01','2':'02','3':'03','4':'04','5':'05','6':'06','7':'07','8':'08','9':'09','A':'10','B':'11','C':'12','D':'13','E':'14','F':'15','G':'16','H':'17','I':'18','J':'19','K':'20','L':'21','M':'22','N':'23','O':'24','P':'25','Q':'26','R':'27','S':'28','T':'29','U':'30','V':'31'}
        day = day_map.get(day_char, '??')
        return f"{year}-{month}-{day}"
    
    def _parse_charger_model(self, model_str):
        """解析AC-DC充电器型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        current = model_str[1:3]
        app_map = {'B': '蓝牙', 'W': 'WIFI', 'M': '蓝牙+WIFI', 'N': '无APP'}
        app = app_map.get(model_str[4], '未知')
        return f"{voltage} {current}A {app}"
    
    def _parse_dcdc_model(self, model_str):
        """解析DC-DC充电器型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        current = int(model_str[1:3])
        app_map = {'B': '蓝牙', 'W': 'WIFI', 'N': '无APP'}
        app = app_map.get(model_str[4], '未知')
        return f"{voltage} {current}A {app}"
    
    def _parse_inverter_model(self, model_str):
        """解析逆变器型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        power = int(model_str[1:3]) * 100
        return f"{voltage} {power}W"
    
    def _parse_mppt_model(self, model_str):
        """解析MPPT型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        current = int(model_str[1:3])
        app_map = {'B': '蓝牙', 'W': 'WIFI', 'N': '无APP'}
        app = app_map.get(model_str[4], '未知')
        return f"{voltage} {current}A {app}"
    
    def _parse_inverter_charger_model(self, model_str):
        """解析逆充一体机型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        power = int(model_str[1:3]) * 100
        charge_current = int(model_str[3:5])
        return f"{voltage} {power}W 充电{charge_current}A"
    
    def _parse_hybrid_model(self, model_str):
        """解析逆充控一体机型号"""
        voltage_map = {'A': '12V', 'B': '24V', 'C': '36V', 'D': '48V', 'E': '72V'}
        voltage = voltage_map.get(model_str[0], '未知')
        power = int(model_str[1:3]) * 100
        pv_voltage = 'PV低压' if model_str[3] == 'L' else 'PV高压'
        app_map = {'B': '蓝牙', 'W': 'WIFI', 'M': '蓝牙+WIFI', 'N': '无APP'}
        app = app_map.get(model_str[4], '无APP')
        return f"{voltage} {power}W {pv_voltage} {app}"
    
    def _parse_charger_functions(self, func_str):
        """解析充电器功能配置"""
        functions = []
        if func_str[0] == 'P': functions.append('PFC')
        if func_str[1] == 'F': functions.append('风冷散热')
        elif func_str[1] == 'N': functions.append('自然散热')
        if func_str[2] == 'W': functions.append('防水')
        return '+'.join(functions) if functions else '标准配置'
    
    def _parse_dcdc_functions(self, func_str):
        """解析DC-DC功能配置"""
        functions = []
        if func_str[0] == 'E': functions.append('发电机')
        if func_str[1] == 'L': functions.append('锂电池模式')
        if func_str[2] != 'N': functions.append(f'通讯-{func_str[2]}')
        return '+'.join(functions) if functions else '标准配置'
    
    def _parse_inverter_functions(self, func_str):
        """解析逆变器功能配置"""
        functions = []
        if func_str[0] == 'H': functions.append('高频')
        elif func_str[0] == 'F': functions.append('工频')
        screen_map = {'B': '内置屏', 'E': '外置屏', 'N': '无屏'}
        functions.append(screen_map.get(func_str[1], '未知'))
        if func_str[2] == 'S': functions.append('远程开关')
        return '+'.join(functions)
    
    def _parse_mppt_functions(self, func_str):
        """解析MPPT功能配置"""
        functions = []
        if func_str[0] == 'F': functions.append('负载端口')
        if func_str[1] == 'L': functions.append('低温保护')
        if func_str[2] == 'W': functions.append('防水')
        return '+'.join(functions) if functions else '标准配置'
    
    def _parse_inverter_charger_functions(self, func_str):
        """解析逆充一体机功能配置"""
        functions = []
        if func_str[0] == 'H': functions.append('高频')
        elif func_str[0] == 'F': functions.append('工频')
        screen_map = {'B': '内置屏', 'E': '外置屏', 'N': '无屏'}
        functions.append(screen_map.get(func_str[1], '未知'))
        if func_str[2] == 'S': functions.append('远程开关')
        return '+'.join(functions)
    
    def _parse_hybrid_functions(self, func_str):
        """解析逆充控一体机功能配置"""
        functions = []
        if func_str[0] == 'H': functions.append('高频')
        elif func_str[0] == 'F': functions.append('工频')
        comm_map = {'C': 'CAN', '4': 'RS485', '2': 'RS232', 'N': '无通讯'}
        functions.append(comm_map.get(func_str[1], '未知'))
        parallel = func_str[2]
        if parallel != '1':
            functions.append(f'可并机{parallel}台')
        return '+'.join(functions)
class DataParserManager:
    """数据解析管理器 - 封装数据解析逻辑"""

    def __init__(self, logger=None):
        self.logger = logger
        self.text_decoder = TextDecode() if TextDecode else None
        self.hex_parser = HexParserApp() if HexParserApp else None
        self.sn_parser = SNCodeParser()

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


class BatteryWindowManager:
    """电池参数窗口管理器"""

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
        title_label = QLabel('电池参数配置窗口')
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(12)
        title_label.setFont(font)
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
        if BatteryTableModel:
            self.table_view = QTableView()
            self.table_model = BatteryTableModel()
            self.table_view.setModel(self.table_model)

            # 设置表格属性
            self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table_view.horizontalHeader().setStretchLastSection(False)

            # 设置列宽
            column_widths = [80, 60, 60, 80, 60, 60, 80, 60, 60]
            for i, width in enumerate(column_widths):
                self.table_view.setColumnWidth(i, width)

            layout.addWidget(self.table_view)
        else:
            error_label = QLabel('错误：无法加载BatteryTableModel')
            font = error_label.font()
            font.setBold(True)
            error_label.setFont(font)
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


class BitWindowManager:
    """位标志窗口管理器"""

    def __init__(self, parent=None, logger=None, multi_column=False):
        self.parent = parent
        self.logger = logger
        self.multi_column = multi_column

        if multi_column and MultiColumnBitFlagsWidget:
            self.widget = MultiColumnBitFlagsWidget(parent=parent, logger=logger)
        elif BitFlagsWidget:
            self.widget = BitFlagsWidget(parent=parent, logger=logger)
        else:
            # 备用方案：创建简单的错误显示
            self.widget = QWidget(parent)
            layout = QVBoxLayout()
            error_label = QLabel('错误：无法加载BitFlagsWidget')
            font = error_label.font()
            font.setBold(True)
            error_label.setFont(font)
            layout.addWidget(error_label)
            self.widget.setLayout(layout)

    def update_status_bits(self, status_list):
        """更新位标志
        Args:
            status_list: 列表，每项格式为 {'name': str, 'value': int}
        """
        if hasattr(self.widget, 'update_status_bits'):
            self.widget.update_status_bits(status_list)

    def clear_status_bits(self):
        """清空位标志"""
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

    def __init__(self, parent=None, logger=None, standalone=False, device_id=None, device_name=None):
        """
        Args:
            parent: 父窗口（嵌入模式时使用）
            logger: 日志记录器
            standalone: 是否独立窗口模式
            device_id: 设备ID（多设备模式使用）
            device_name: 设备名称（多设备模式使用）
        """
        super().__init__(parent)
        self.logger = logger
        self.standalone = standalone
        self.device_id = device_id or "default"
        self.device_name = device_name or "默认设备"

        # 窗口管理器
        self.battery_window_manager = None
        self.bit_window_manager = None

        # 数据解析管理器（每个设备独立）
        self.data_parser = DataParserManager(logger=logger)

        # 统计信息
        self.data_count = 0
        self.last_update_time = None

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
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # ========== 上半部分：数据输入和解析（再次垂直分割）==========
        parse_splitter = QSplitter(Qt.Orientation.Horizontal)
        parse_panel = self.create_parse_panel()
        parse_splitter.addWidget(parse_panel)
        sn_panel = self.create_sn_parse_panel()
        parse_splitter.addWidget(sn_panel)
        parse_splitter.setStretchFactor(0, 1)
        parse_splitter.setStretchFactor(1, 1)
        main_splitter.addWidget(parse_splitter)

        # ========== 下半部分：数据显示窗口 ==========
        display_panel = QWidget()
        display_layout = QHBoxLayout()

        # 创建battery_window（电池参数窗口）
        self.battery_window_manager = BatteryWindowManager(parent=display_panel)
        self.battery_window_manager.widget.setMinimumSize(400, 400)
        display_layout.addWidget(self.battery_window_manager.widget)

        # 创建bit_window（位标志窗口 - 独立模式使用多列显示）
        self.bit_window_manager = BitWindowManager(parent=display_panel, logger=self.logger, multi_column=True)
        self.bit_window_manager.widget.setMinimumSize(600, 400)
        display_layout.addWidget(self.bit_window_manager.widget)

        display_panel.setLayout(display_layout)
        main_splitter.addWidget(display_panel)

        # 设置分割器比例
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(main_splitter)
        central_widget.setLayout(main_layout)

        # 连接信号
        if self.battery_window_manager and hasattr(self.battery_window_manager, 'send_button'):
            self.battery_window_manager.send_button.clicked.connect(self.on_send_modified)

    def create_control_panel(self):
        """创建控制面板（用于独立调试）"""
        panel = QWidget()
        layout = QHBoxLayout()

        # 标题
        title_label = QLabel('🎛️ 数据显示管理器控制面板')
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(14)
        title_label.setFont(font)
        layout.addWidget(title_label)
        # 联系信息
        contact_label = QLabel('有疑问请联系郭学成')
        font = contact_label.font()
        font.setPointSize(11)
        contact_label.setFont(font)
        contact_label.setContentsMargins(15, 0, 0, 0)
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
        layout.setContentsMargins(10, 10, 10, 10)

        return panel

    def create_parse_panel(self):
        """创建数据解析面板"""
        group_box = QGroupBox("📡 数据解析调试工具")
        font = group_box.font()
        font.setBold(True)
        font.setPointSize(13)
        group_box.setFont(font)

        layout = QVBoxLayout()

        # 输入区域
        input_layout = QHBoxLayout()
        input_label = QLabel('输入数据 (十六进制):')
        input_layout.addWidget(input_label)

        self.hex_input = QTextEdit()
        self.hex_input.setMaximumHeight(80)
        self.hex_input.setPlaceholderText("输入十六进制字符串，例如：\n00 00 0C 01 93 55 AA 86 00 00 00 00 00 02 00 B4")
        font = self.hex_input.font()
        font.setFamily('Consolas, Courier New, monospace')
        font.setPointSize(11)
        self.hex_input.setFont(font)
        input_layout.addWidget(self.hex_input)

        # 解析按钮
        parse_btn = QPushButton('🔍 解析数据')
        parse_btn.setMinimumWidth(120)
        font = parse_btn.font()
        font.setBold(True)
        parse_btn.setFont(font)
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
        font = self.parse_output.font()
        font.setFamily('Consolas, Courier New, monospace')
        font.setPointSize(10)
        self.parse_output.setFont(font)
        layout.addWidget(self.parse_output)

        group_box.setLayout(layout)
        return group_box
    def create_sn_parse_panel(self):
        """创建SN码解析面板"""
        group_box = QGroupBox("🏷️ SN码解析工具")
        font = group_box.font()
        font.setBold(True)
        font.setPointSize(13)
        group_box.setFont(font)
        layout = QVBoxLayout()
        input_layout = QVBoxLayout()
        input_label = QLabel('输入SN码:')
        input_label_font = input_label.font()
        input_label_font.setPointSize(10)
        input_label_font.setBold(True)
        input_label.setFont(input_label_font)
        input_layout.addWidget(input_label)
        self.sn_input = QTextEdit()
        self.sn_input.setMaximumHeight(60)
        self.sn_input.setPlaceholderText("输入SN码（自动识别电池或核心部件）\n例如：BALP12100-NNN-A110001A-100Y")
        font = self.sn_input.font()
        font.setFamily('Consolas, Courier New, monospace')
        font.setPointSize(12)
        self.sn_input.setFont(font)
        input_layout.addWidget(self.sn_input)
        button_layout = QHBoxLayout()
        parse_sn_btn = QPushButton('🔍 解析SN码')
        parse_sn_btn.setMinimumWidth(150)
        parse_sn_btn.setMinimumHeight(35)
        font = parse_sn_btn.font()
        font.setBold(True)
        font.setPointSize(11)
        parse_sn_btn.setFont(font)
        parse_sn_btn.clicked.connect(self.parse_sn_code)
        button_layout.addWidget(parse_sn_btn)
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        example_layout = QHBoxLayout()
        example_label = QLabel('电池示例:')
        example_layout.addWidget(example_label)
        example1_btn = QPushButton('12V100Ah')
        example1_btn.clicked.connect(lambda: self.sn_input.setText('BALP12100-NNN-A110001A-100Y'))
        example_layout.addWidget(example1_btn)
        example2_btn = QPushButton('蓝牙款')
        example2_btn.clicked.connect(lambda: self.sn_input.setText('BALP12100-BNN-A110001A-100Y'))
        example_layout.addWidget(example2_btn)
        example_layout.addStretch()
        input_layout.addLayout(example_layout)
        example_layout2 = QHBoxLayout()
        example_label2 = QLabel('核心部件示例:')
        example_layout2.addWidget(example_label2)
        example3_btn = QPushButton('充电器')
        example3_btn.clicked.connect(lambda: self.sn_input.setText('CHLRA2030B-PFN-A110001R-NNN'))
        example_layout2.addWidget(example3_btn)
        example4_btn = QPushButton('逆变器')
        example4_btn.clicked.connect(lambda: self.sn_input.setText('IHLRA3000N-HEN-A110001R-NNN'))
        example_layout2.addWidget(example4_btn)
        example5_btn = QPushButton('MPPT')
        example5_btn.clicked.connect(lambda: self.sn_input.setText('MHLRB030B-FLN-A110001R-N4RR'))
        example_layout2.addWidget(example5_btn)
        example_layout2.addStretch()
        input_layout.addLayout(example_layout2)
        layout.addLayout(input_layout)
        output_label = QLabel('解析结果:')
        output_label_font = output_label.font()
        output_label_font.setPointSize(10)
        output_label_font.setBold(True)
        output_label.setFont(output_label_font)
        layout.addWidget(output_label)
        self.sn_output = QTextEdit()
        self.sn_output.setReadOnly(True)
        self.sn_output.setMinimumHeight(250)
        font = self.sn_output.font()
        font.setFamily('Consolas, Courier New, monospace')
        font.setPointSize(11)
        self.sn_output.setFont(font)
        layout.addWidget(self.sn_output, 1)
        group_box.setLayout(layout)
        return group_box
    def parse_sn_code(self):
        """解析SN码"""
        sn_code = self.sn_input.toPlainText().strip()
        if not sn_code:
            self.sn_output.setText("❌ 错误：输入为空")
            return
        self.sn_output.append(f"\n{'='*60}")
        self.sn_output.append(f"⏳ 开始解析SN码...")
        self.sn_output.append(f"{'='*60}\n")
        success, result = self.data_parser.sn_parser.parse_sn_code(sn_code)
        if success:
            sn_type = result.get('SN码类型', '未知')
            type_emoji = '🔋' if sn_type == '电池' else '⚡'
            self.sn_output.append(f"✅ 解析成功！")
            self.sn_output.append(f"{type_emoji} SN码类型: {sn_type}")
            self.sn_output.append(f"📋 SN码: {sn_code}")
            self.sn_output.append(f"")
            self.sn_output.append(f"📊 详细信息:")
            self.sn_output.append(f"{'-'*60}")
            max_label_len = 8
            for key, value in result.items():
                if key == 'SN码类型':
                    continue
                key_len = len(key)
                padding = '　' * (max_label_len - key_len)
                self.sn_output.append(f"  {key}{padding} : {value}")
        else:
            self.sn_output.append(f"❌ 解析失败！")
            self.sn_output.append(f"")
            self.sn_output.append(f"错误信息:")
            self.sn_output.append(f"{result}")
        self.sn_output.verticalScrollBar().setValue(
            self.sn_output.verticalScrollBar().maximum()
        )

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
            # 格式化数据为battery_window需要的格式
            formatted_data = []
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        name, unit, value = item[0], item[1], item[2]
                        formatted_data.append((name, value, value))  # (名称, 十六进制, 十进制)

            # 更新battery_window
            if formatted_data:
                self.update_bit_data(formatted_data)
                if hasattr(self, 'parse_output'):
                    self.parse_output.append(f"📈 已更新电池参数窗口: {len(formatted_data)} 个参数")

            # 如果是SBS数据，更新位标志
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

                # 更新位标志
                status_bits = get_all_status_bits_for_display(flat_dict)
                if status_bits:
                    self.update_status_bits_direct(status_bits)
                    if hasattr(self, 'parse_output'):
                        self.parse_output.append(f"🚦 已更新位标志窗口: {len(status_bits)} 个位标志")

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
        self.battery_window_manager = BatteryWindowManager(parent=parent_widget)
        self.bit_window_manager = BitWindowManager(parent=parent_widget, logger=self.logger)

    def setup_windows_geometry(self, battery_geom, bit_geom):
        """设置窗口位置和大小

        Args:
            battery_geom: (x, y, width, height) 元组 - 电池参数窗口
            bit_geom: (x, y, width, height) 元组 - 位标志窗口
        """
        if self.battery_window_manager:
            self.battery_window_manager.set_geometry(*battery_geom)
        if self.bit_window_manager:
            self.bit_window_manager.set_geometry(*bit_geom)

    def show_windows(self):
        """显示所有窗口"""
        if self.battery_window_manager:
            self.battery_window_manager.show()
        if self.bit_window_manager:
            self.bit_window_manager.show()

    def hide_windows(self):
        """隐藏所有窗口"""
        if self.battery_window_manager:
            self.battery_window_manager.hide()
        if self.bit_window_manager:
            self.bit_window_manager.hide()

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

    def parse_and_update_displays(self, hex_bytes):
        """一站式：解析数据并自动更新显示

        Args:
            hex_bytes: bytearray或bytes对象

        Returns:
            (success, result) 元组
        """
        success, result = self.parse_raw_data(hex_bytes)
        if success:
            self.process_parsed_data(result['struct_name'], result['data'])
            # 更新统计
            self.data_count += 1
            import time
            self.last_update_time = time.time()
        return success, result

    def get_parser_info(self):
        """获取解析器信息（用于调试）"""
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'data_count': self.data_count,
            'last_update': self.last_update_time
        }

    def update_bit_data(self, parsed_data):
        """更新电池参数数据

        Args:
            parsed_data: 解析后的数据列表，格式：[(name, hex_value, dec_value), ...]
        """
        if self.battery_window_manager:
            self.battery_window_manager.update_data(parsed_data)
            if self.logger:
                self.logger.write_log(f"更新电池参数数据: {len(parsed_data)} 行")

    def update_status_data(self, sbs_data_dict):
        """更新位标志数据（从SBS数据字典）

        Args:
            sbs_data_dict: PC_GET_SBS解析后的字典
        """
        if self.bit_window_manager:
            # 使用struct_model中的函数解析位标志
            status_bits = get_all_status_bits_for_display(sbs_data_dict)
            self.bit_window_manager.update_status_bits(status_bits)
            if self.logger:
                self.logger.write_log(f"更新位标志数据: {len(status_bits)} 个位标志")

    def update_status_bits_direct(self, status_list):
        """直接更新位标志数据（已解析格式）

        Args:
            status_list: 位标志列表，格式：[{'name': str, 'value': int}, ...]
        """
        if self.bit_window_manager:
            self.bit_window_manager.update_status_bits(status_list)

    # ==================== 数据输出接口 ====================

    def get_modified_values(self):
        """获取修改的值

        Returns:
            list: [(row, param_name, current_value, write_value), ...]
        """
        if self.battery_window_manager:
            return self.battery_window_manager.get_modified_data()
        return []

    def get_write_values_dict(self):
        """获取写入值字典

        Returns:
            dict: {row: write_value, ...}
        """
        if self.battery_window_manager and self.battery_window_manager.table_model:
            return self.battery_window_manager.table_model.get_write_values()
        return {}

    # ==================== 控制接口 ====================

    def clear_bit_write_values(self):
        """清空电池参数的写入值"""
        if self.battery_window_manager:
            self.battery_window_manager.clear_write_values()

    def clear_status_bits(self):
        """清空位标志"""
        if self.bit_window_manager:
            self.bit_window_manager.clear_status_bits()

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
        alarm_names = ['Pack过压', 'Batt过压', '电芯过压', 'Pack欠压', 'Batt欠压', '电芯欠压', '充电过流', '放电过流', '充电高温', '放电高温', '充电低温', '放电低温', 'MOS高温', 'Batt高温']
        protect_names = ['Pack过压', 'Batt过压', '电芯过压', 'Pack欠压', 'Batt欠压', '电芯欠压', '充电过流', '放电过流', '充电高温', '放电高温', '充电低温', '放电低温', 'MOS高温', 'Batt高温', '短路保护', '放电欠温', '充电欠温', '预放失效', '预充失效', '低电关机', '充电MOSOP']
        fault_names = ['电芯检测', '温度检测', '电流检测', '电压检测', '温差检测', '均衡异常', '过流监控', '充电MOS', '放电MOS', '预放MOS', '预充MOS', 'NTC异常']
        info_names = ['充电MOSST', '放电MOSST', '预放MOS状态', '预充MOS状态', '充电中', '放电中', 'FullCharge', 'Empty', '无连接', '电池停用', 'Pack欠压告警', '告警可清除', 'Pack超温告警', 'Pack低温告警', '单体超温告警', '单体低温告警', '充电状态', '放电状态', 'Volt检测', 'Curr检测', 'Temp检测']
        for name in alarm_names:
            test_data.append({'name': name, 'value': random.randint(0, 1), 'type': 'alarm'})
        for name in protect_names:
            test_data.append({'name': name, 'value': random.randint(0, 1), 'type': 'protect'})
        for name in fault_names:
            test_data.append({'name': name, 'value': random.randint(0, 1), 'type': 'fault'})
        for name in info_names:
            test_data.append({'name': name, 'value': random.randint(0, 1), 'type': 'info'})
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
    
    # 应用系统主题自适应
    from display_widgets import is_dark_theme
    if is_dark_theme():
        from PyQt6.QtGui import QPalette, QColor
        # 深色主题调色板
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(dark_palette)
        app.setStyle("Fusion")
    
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
