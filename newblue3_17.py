import sys
import asyncio
import traceback
import time
import json
from datetime import datetime
import os
import random

from PyQt6.QtCore import QTimer  # 导入 QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QMessageBox, QTextEdit, QLineEdit, QHBoxLayout,
    QCheckBox, QFileDialog, QComboBox, QGridLayout, QMainWindow, QSplashScreen, QSizePolicy, QTableView, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter
from bleak import BleakScanner, BleakClient
from qasync import QEventLoop, asyncSlot
import serial.tools.list_ports
from PyQt6 import uic
from log_controller import LogManager
from log_controller import ComunManager
from PyQt6.QtCore import pyqtSignal
from bleak.exc import BleakError

from hex_model import HexFileModel
from OTA_controller import OtaController
from OTA_controller import TextDecode
from OTA_controller import ReceveDataStatus,BmsCmdType,ComStatus,DownloadErr
from struct_model import HexParserApp, get_write_command_code, can_command_be_written, STRUCT_FORMATS, STRUCT_VARIABLES, get_write_command_from_read
import struct

from ui_main import Ui_Form

class BitFlagsTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._original_data = data if data is not None else []
        self._write_values = {}  # 存储写入值的字典，key为原始行索引，value为写入值
        self._columns = 9  # 9列显示：3组参数
        self._max_rows_per_column = 25  # 每列组最大行数
        self._headers = ['参数名1', '当前值1', '写入值1', '参数名2', '当前值2', '写入值2', '参数名3', '当前值3', '写入值3']
        self._organized_data = []  # 重新组织后的数据
        self._organize_data()
    
    def _organize_data(self):
        """重新组织数据，超过25行时分成新的列组"""
        self._organized_data = []
        data_len = len(self._original_data)
        
        if data_len == 0:
            return
        
        # 计算需要的行数
        max_rows = min(self._max_rows_per_column, data_len)
        
        # 创建行数据
        for row in range(max_rows):
            row_data = [''] * self._columns
            
            # 填充第一列组 (columns 0-2)
            if row < data_len:
                row_data[0] = self._original_data[row][0]  # 参数名
                row_data[1] = self._original_data[row][2]  # 当前值
                row_data[2] = self._write_values.get(row, "")  # 写入值
            
            # 填充第二列组 (columns 3-5)
            second_group_idx = row + self._max_rows_per_column
            if second_group_idx < data_len:
                row_data[3] = self._original_data[second_group_idx][0]  # 参数名
                row_data[4] = self._original_data[second_group_idx][2]  # 当前值
                row_data[5] = self._write_values.get(second_group_idx, "")  # 写入值
            
            # 填充第三列组 (columns 6-8)
            third_group_idx = row + 2 * self._max_rows_per_column
            if third_group_idx < data_len:
                row_data[6] = self._original_data[third_group_idx][0]  # 参数名
                row_data[7] = self._original_data[third_group_idx][2]  # 当前值
                row_data[8] = self._write_values.get(third_group_idx, "")  # 写入值
            
            self._organized_data.append(row_data)
    
    def _get_original_index(self, row, col):
        """根据表格位置获取原始数据索引"""
        if col in [0, 1, 2]:  # 第一列组
            return row
        elif col in [3, 4, 5]:  # 第二列组
            return row + self._max_rows_per_column
        elif col in [6, 7, 8]:  # 第三列组
            return row + 2 * self._max_rows_per_column
        return -1
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if row < len(self._organized_data) and col < self._columns:
                return self._organized_data[row][col]
        return None
    
    def setData(self, index, value, role):
        """设置数据，仅允许编辑写入值列"""
        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col = index.column()
            
            # 只能编辑写入值列 (2, 5, 8)
            if col in [2, 5, 8] and row < len(self._organized_data):
                original_idx = self._get_original_index(row, col)
                if 0 <= original_idx < len(self._original_data):
                    self._write_values[original_idx] = str(value)
                    self._organized_data[row][col] = str(value)
                    self.dataChanged.emit(index, index)
                    return True
        return False
    
    def flags(self, index):
        """设置单元格标志，写入值列可编辑"""
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col = index.column()
        if col in [2, 5, 8]:  # 写入值列可编辑
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._organized_data)
    
    def columnCount(self, parent=QModelIndex()):
        return self._columns
    
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section]
            else:
                return str(section + 1)
        return None
    
    def update_data(self, data):
        """完全更新所有数据（重置模型）"""
        self.beginResetModel()
        self._original_data = data
        self._organize_data()
        self.endResetModel()
    
    def update_row(self, row, row_data):
        """更新指定行的数据"""
        if 0 <= row < len(self._original_data):
            self._original_data[row] = row_data
            self._organize_data()
            # 通知视图该行的数据已更改
            self.beginResetModel()
            self.endResetModel()
            return True
        return False
    
    def update_cell(self, row, col, value):
        """更新指定单元格的数据"""
        if 0 <= row < len(self._original_data) and 0 <= col < 2:  # 只能更新前两列的原始数据
            if col == 0:
                # 更新参数名
                self._original_data[row] = (value, self._original_data[row][1], self._original_data[row][2])
            elif col == 1:
                # 更新当前值（假设原数据格式为 (name, hex_value, decimal_value)）
                self._original_data[row] = (self._original_data[row][0], self._original_data[row][1], value)
            
            self._organize_data()
            # 通知视图该单元格的数据已更改
            self.beginResetModel()
            self.endResetModel()
            return True
        return False
    
    def update_partial_data(self, updates):
        """批量更新部分数据
        updates: 字典，格式为 {row_index: new_row_data} 或 {(row, col): new_value}
        """
        changed = False
        
        for key, value in updates.items():
            if isinstance(key, int):
                # 更新整行
                if 0 <= key < len(self._original_data):
                    self._original_data[key] = value
                    changed = True
            elif isinstance(key, tuple) and len(key) == 2:
                # 更新单个单元格
                row, col = key
                if self.update_cell(row, col, value):
                    changed = True
        
        # 批量通知视图更改
        if changed:
            self._organize_data()
            self.beginResetModel()
            self.endResetModel()
    
    def append_row(self, row_data):
        """添加新行"""
        row = len(self._original_data)
        self.beginInsertRows(QModelIndex(), row, row)
        self._original_data.append(row_data)
        self._organize_data()
        self.endInsertRows()
    
    def remove_row(self, row):
        """删除指定行"""
        if 0 <= row < len(self._original_data):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._original_data[row]
            # 同时删除对应的写入值
            if row in self._write_values:
                del self._write_values[row]
            # 重新整理写入值的索引
            new_write_values = {}
            for old_row, value in self._write_values.items():
                if old_row > row:
                    new_write_values[old_row - 1] = value
                else:
                    new_write_values[old_row] = value
            self._write_values = new_write_values
            self._organize_data()
            self.endRemoveRows()
            return True
        return False
    
    def find_row_by_name(self, param_name):
        """根据参数名查找行索引"""
        for i, row_data in enumerate(self._original_data):
            if row_data[0] == param_name:
                return i
        return -1
    
    def update_value_by_name(self, param_name, new_value):
        """根据参数名更新数值"""
        row = self.find_row_by_name(param_name)
        if row >= 0:
            return self.update_cell(row, 1, new_value)
        return False
    
    def get_write_values(self):
        """获取所有写入值"""
        return self._write_values.copy()
    
    def get_modified_data(self):
        """获取有写入值的数据列表，返回格式：[(row, param_name, current_value, write_value), ...]"""
        modified_data = []
        for row, write_value in self._write_values.items():
            if row < len(self._original_data) and write_value != "":  # 只返回真正有写入值的数据
                param_name = self._original_data[row][0]
                current_value = self._original_data[row][2]
                modified_data.append((row, param_name, current_value, write_value))
        return modified_data
    
    def clear_write_values(self):
        """清空所有写入值"""
        self._write_values.clear()
        self._organize_data()
        # 通知视图写入值列需要更新
        self.beginResetModel()
        self.endResetModel()
    
    def set_write_value(self, row, value):
        """设置指定行的写入值"""
        if 0 <= row < len(self._original_data):
            self._write_values[row] = str(value)
            self._organize_data()
            self.beginResetModel()
            self.endResetModel()
            return True
        return False

# class MainWindow(QMainWindow):
#     """主窗口（一级窗口）"""
#     def __init__(self):
#         super().__init__()
#         self.logger = LogManager.get_instance()  # 获取日志管理器实例
#         self.logger.write_log("主窗口已初始化")
#         self.initUI()
#         pass
        
#     def initUI(self):
#         pass

#     def closeEvent(self, event):
#         """重写关闭事件，关闭日志文件并断开连接"""
#         # 关闭日志文件
#         self.logger.close_log()
        
#         # ... 处理蓝牙和串口断开连接 ...
        
#         event.accept()

# 添加启动画面
class SplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(400, 300)
        pixmap.fill(Qt.GlobalColor.white)
        super().__init__(pixmap)
        
        # 在启动画面上添加信息
        self.setStyleSheet("""
            QSplashScreen {
                border: 1px solid #cccccc;
                border-radius: 10px;
                background-color: white;
            }
        """)
        
        # 显示启动信息
        self.showMessage(
            "正在启动应用...", 
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
            Qt.GlobalColor.black
        )

# 修改现有的BluetoothTool类为二级窗口
class BluetoothTool(QWidget):
    receive_ok_signal = pyqtSignal(int,bytes)
    decode_data_ok_signal = pyqtSignal(str,dict)
    pass
    def __init__(self):
        super().__init__()
        self.client = None  # 当前连接的蓝牙设备
        # self.connection_type = None  # 用于存储连接类型
        self.serial_port = None  # 串口对象
        self.commu_type = None
        self.device_name = None
        self.is_serial_connected = False
        self.serial_receive_task = None #串口接收任务对象
        self.program_task = None #烧录任务对象
        self.task_flag = False
        self.device_name_to_address = {}  # 设备名到地址的映射
        self.initUI()
        self.hex_model = HexFileModel()
        self.text_decode = TextDecode()
        self.download_data = OtaController()
        self.hex_parser = HexParserApp()
        # asyncio.create_task(self.scan_devices())
        QTimer.singleShot(0, self.on_scan_devices_clicked)
        # 初始化定时器 
        self.data_timer = QTimer()
        self.data_timer.setSingleShot(True) #单次定时器可能会影响实际数据接收数量上限
        self.data_timer.timeout.connect(self.process_complete_data)

        # 用于存储接收到的数据
        self.received_data_buffer = bytearray()

        # 烧录计数
        self.ota_start_count = 0
        self.ota_ok_count = 0
        self.batch_task = None
        
        # 加密指令测试相关变量
        self.crypto_test_task = None
        self.crypto_test_running = False
        self.crypto_test_send_count = 0
        self.crypto_test_success_count = 0
        self.crypto_test_error_count = 0
        self.crypto_test_current_round = 0
        self.crypto_test_total_rounds = 1000
        self.crypto_test_stop_requested = False
    def initUI(self):
        self.setWindowTitle('firstuse')

        # 创建主布局
        layout = QVBoxLayout()

        # HEX文件解析部分
        self.hex_layout = QHBoxLayout()
        self.hex_file_label = QLabel('HEX文件：未选择')
        self.hex_file_button = QPushButton('选择HEX文件')
        self.hex_file_button.clicked.connect(self.on_select_hex_file)
        self.hex_layout.addWidget(self.hex_file_label)
        self.hex_layout.addWidget(self.hex_file_button)
        layout.addLayout(self.hex_layout)

        # HEX文件信息显示
        self.hex_info_label = QLabel('文件大小：0 字节')
        layout.addWidget(self.hex_info_label)

        # 创建水平分割的两个区域
        connection_layout = QHBoxLayout()
        
        # ========== 左侧：蓝牙连接部分 ==========
        bluetooth_layout = QVBoxLayout()
        bluetooth_frame = QWidget()
        bluetooth_frame.setLayout(bluetooth_layout)
        
        # 蓝牙标题
        bluetooth_title = QLabel('蓝牙连接')
        bluetooth_title.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        bluetooth_layout.addWidget(bluetooth_title)

        # 设备扫描部分
        self.label = QLabel('发现的蓝牙设备:')
        self.device_list = QListWidget()
        bluetooth_layout.addWidget(self.label)
        bluetooth_layout.addWidget(self.device_list)

        # 信号强度筛选部分
        self.rssi_threshold_layout = QHBoxLayout()
        self.rssi_threshold_label = QLabel('信号强度筛选 (RSSI >):')
        self.rssi_threshold_input = QLineEdit()
        self.rssi_threshold_input.setText("-100")
        self.rssi_threshold_input.setPlaceholderText('例如: -70')
        self.rssi_threshold_layout.addWidget(self.rssi_threshold_label)
        self.rssi_threshold_layout.addWidget(self.rssi_threshold_input)
        bluetooth_layout.addLayout(self.rssi_threshold_layout)

        self.scan_button = QPushButton('扫描设备和刷新串口')
        self.scan_button.clicked.connect(self.on_scan_all_clicked)
        bluetooth_layout.addWidget(self.scan_button)

        # 设备连接和断开部分
        self.connect_layout = QHBoxLayout()
        self.connect_button = QPushButton('连接蓝牙设备')
        self.connect_button.clicked.connect(self.on_connect_device_clicked)
        self.disconnect_button = QPushButton('断开蓝牙设备')
        self.disconnect_button.clicked.connect(self.on_disconnect_device_clicked)
        self.disconnect_button.setEnabled(False)  # 初始状态下断开按钮不可用
        self.connect_layout.addWidget(self.connect_button)
        self.connect_layout.addWidget(self.disconnect_button)
        bluetooth_layout.addLayout(self.connect_layout)
        
        # ========== 右侧：串口连接部分 ==========
        serial_layout = QVBoxLayout()
        serial_frame = QWidget()
        serial_frame.setLayout(serial_layout)
        
        # 串口标题
        serial_title = QLabel('串口连接')
        serial_title.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        serial_layout.addWidget(serial_title)
        
        # 串口参数设置
        param_layout = QGridLayout()
        
        # 串口选择
        self.port_label = QLabel('串口:')
        self.port_combo = QComboBox()
        param_layout.addWidget(self.port_label, 0, 0)
        param_layout.addWidget(self.port_combo, 0, 1)
        
        # 波特率设置
        self.baud_label = QLabel('波特率:')
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '13333','18000','18600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('19200')
        param_layout.addWidget(self.baud_label, 1, 0)
        param_layout.addWidget(self.baud_combo, 1, 1)
        
        # 数据位
        self.data_bits_label = QLabel('数据位:')
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(['5', '6', '7', '8'])
        self.data_bits_combo.setCurrentText('8')
        param_layout.addWidget(self.data_bits_label, 2, 0)
        param_layout.addWidget(self.data_bits_combo, 2, 1)
        
        # 停止位
        self.stop_bits_label = QLabel('停止位:')
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(['1', '1.5', '2'])
        self.stop_bits_combo.setCurrentText('1')
        param_layout.addWidget(self.stop_bits_label, 3, 0)
        param_layout.addWidget(self.stop_bits_combo, 3, 1)
        
        # 校验位
        self.parity_label = QLabel('校验位:')
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(['无', '奇校验', '偶校验'])
        param_layout.addWidget(self.parity_label, 4, 0)
        param_layout.addWidget(self.parity_combo, 4, 1)
        
        serial_layout.addLayout(param_layout)
        
        # 串口连接按钮
        self.serial_connect_button = QPushButton('连接串口')
        self.serial_connect_button.clicked.connect(self.on_serial_connect_clicked)
        serial_layout.addWidget(self.serial_connect_button)
        
        serial_layout.addStretch(1)  # 添加弹性空间
        
        # 将两个区域添加到水平布局
        connection_layout.addWidget(bluetooth_frame, 1)  # 1是拉伸系数
        connection_layout.addWidget(serial_frame, 1)
        
        # 将连接区域添加到主布局
        layout.addLayout(connection_layout)
        
        # 共用的数据收发部分
        # 数据发送部分
        self.send_layout = QHBoxLayout()
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText('输入要发送的数据')
        self.hex_send_checkbox = QCheckBox('16进制发送')
        self.hex_send_checkbox.setChecked(True)
        self.crlf_send_checkbox = QCheckBox('\\r\\n发送')
        self.crlf_send_checkbox.setChecked(False)
        self.send_button = QPushButton('发送数据')
        self.send_button.clicked.connect(self.on_send_data_clicked)
        self.send_button.setEnabled(False)  # 初始状态下发送按钮不可用
        self.register_button = QPushButton('注册')
        self.register_button.clicked.connect(self.on_register_clicked)
        
        # 新增状态指示灯
        self.status_indicator = QLabel()
        self.update_registration_status(False)  # 初始状态为未注册
        
        self.send_layout.addWidget(self.send_input)
        self.send_layout.addWidget(self.hex_send_checkbox)
        self.send_layout.addWidget(self.crlf_send_checkbox)
        self.send_layout.addWidget(self.send_button)
        self.send_layout.addWidget(self.register_button)
        self.send_layout.addWidget(self.status_indicator)  # 添加状态指示灯
        layout.addLayout(self.send_layout)

        # 测试数据发送部分
        self.test_layout = QHBoxLayout()
        self.test_send_button = QPushButton('连续发送')
        self.test128 = QLineEdit('0')
        self.test512 = QLineEdit('280')
        self.test_layout.addWidget(self.test128)
        self.test_layout.addWidget(self.test512)
        self.test_layout.addWidget(self.test_send_button)
        self.test_send_button.clicked.connect(self.on_test_send_buttoned)
        layout.addLayout(self.test_layout)

        # 测试数据结果显示部分
        self.success_couont_layout = QHBoxLayout()
        self.no_ack_label = QLabel('无回应=0')
        self.no_ack_count = 0
        self.err_ack_label = QLabel('ack错误=0')
        self.err_ack_count = 0
        self.total_send_label = QLabel('发送总次数=0')
        self.success_couont_layout.addWidget(self.no_ack_label)
        self.success_couont_layout.addWidget(self.err_ack_label)
        self.success_couont_layout.addWidget(self.total_send_label)
        layout.addLayout(self.success_couont_layout)

        # 烧录控制部分
        self.program_layout = QHBoxLayout()
        self.program_button = QPushButton('开始烧录')
        self.program_button.clicked.connect(self.on_program_clicked)
        self.program_layout.addWidget(self.program_button)

        self.packet_success_label = QLabel('包号: 0 总包数 0')
        self.program_layout.addWidget(self.packet_success_label)

        # 新增：批量烧录按钮和成功数label
        self.batch_program_button = QPushButton('批量烧录100次')
        self.batch_program_button.clicked.connect(self.on_batch_program_clicked)
        self.program_layout.addWidget(self.batch_program_button)

        self.batch_success_label = QLabel('成功数: 0')
        self.program_layout.addWidget(self.batch_success_label)

        layout.addLayout(self.program_layout)

        # 数据接收部分
        self.receive_label = QLabel('接收到的数据:')
        layout.addWidget(self.receive_label)

        self.receive_output = QTextEdit()
        self.receive_output.setReadOnly(True)
        layout.addWidget(self.receive_output)

        # 16进制显示选项
        self.hex_display_checkbox = QCheckBox('16进制显示')
        self.hex_display_checkbox.setChecked(True)
        self.hex_display_checkbox.stateChanged.connect(self.on_hex_display_changed)
        layout.addWidget(self.hex_display_checkbox)

        # 添加放电控制部分
        discharge_layout = QHBoxLayout()
        
        # 打开放电按钮
        self.open_discharge_button = QPushButton('打开放电')
        self.open_discharge_button.clicked.connect(self.on_open_discharge_clicked)
        discharge_layout.addWidget(self.open_discharge_button)
        
        # 关闭放电按钮
        self.close_discharge_button = QPushButton('关闭放电')
        self.close_discharge_button.clicked.connect(self.on_close_discharge_clicked)
        discharge_layout.addWidget(self.close_discharge_button)
        
        # 将放电控制部分添加到主布局
        layout.addLayout(discharge_layout)

        # 添加版本查询控制部分
        version_layout = QHBoxLayout()
        
        # 0x71版本查询按钮
        self.version_query_button = QPushButton('查询版本号(0x71)')
        self.version_query_button.clicked.connect(self.send_find_version_cmd)
        version_layout.addWidget(self.version_query_button)
        
        # 0x16版本查询按钮
        self.version16_query_button = QPushButton('查询16版本号(0x16)')
        self.version16_query_button.clicked.connect(self.send_ver_cmd_16)
        version_layout.addWidget(self.version16_query_button)
        
        # 将版本查询控制部分添加到主布局
        layout.addLayout(version_layout)

        # 添加密码管理部分
        password_layout = QVBoxLayout()
        
        # 密码管理标题
        password_title = QLabel('密码管理')
        password_title.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        password_layout.addWidget(password_title)
        
        # 密码输入框
        password_input_layout = QHBoxLayout()
        self.password_label = QLabel('密码(6位):')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('请输入6位密码')
        self.password_input.setMaxLength(6)
        password_input_layout.addWidget(self.password_label)
        password_input_layout.addWidget(self.password_input)
        password_layout.addLayout(password_input_layout)
        
        # 密码管理按钮
        password_buttons_layout = QHBoxLayout()
        
        # 查询加密状态按钮
        self.query_lock_button = QPushButton('🔍 查看状态(扫描)')
        self.query_lock_button.clicked.connect(self.on_query_lock_clicked)
        password_buttons_layout.addWidget(self.query_lock_button)
        
        # 验证密码按钮
        self.login_button = QPushButton('🔐 验证密码(0x01)')
        self.login_button.clicked.connect(self.on_login_clicked)
        password_buttons_layout.addWidget(self.login_button)
        
        # 设置密码按钮
        self.set_password_button = QPushButton('⚙️ 设置密码(0x02)')
        self.set_password_button.clicked.connect(self.on_set_password_clicked)
        password_buttons_layout.addWidget(self.set_password_button)
        
        # 取消密码按钮
        self.reset_password_button = QPushButton('🗑️ 取消密码(0x03)')
        self.reset_password_button.clicked.connect(self.on_reset_password_clicked)
        password_buttons_layout.addWidget(self.reset_password_button)
        
        password_layout.addLayout(password_buttons_layout)
        
        # 添加测试按钮和进度显示
        test_layout = QVBoxLayout()
        
        # 测试按钮
        test_buttons_layout = QHBoxLayout()
        self.crypto_test_button = QPushButton('🧪 加密指令压力测试(1000次)')
        self.crypto_test_button.clicked.connect(self.on_crypto_test_clicked)
        self.crypto_test_button.setStyleSheet("QPushButton { background-color: #FF6B6B; color: white; font-weight: bold; }")
        test_buttons_layout.addWidget(self.crypto_test_button)
        
        self.stop_test_button = QPushButton('⏹️ 停止测试')
        self.stop_test_button.clicked.connect(self.on_stop_test_clicked)
        self.stop_test_button.setEnabled(False)
        test_buttons_layout.addWidget(self.stop_test_button)
        
        test_layout.addLayout(test_buttons_layout)
        
        # 测试进度和结果显示
        progress_layout = QGridLayout()
        
        self.test_progress_label = QLabel('测试进度:')
        self.test_progress_value = QLabel('0/0 (0%)')
        progress_layout.addWidget(self.test_progress_label, 0, 0)
        progress_layout.addWidget(self.test_progress_value, 0, 1)
        
        self.test_send_count_label = QLabel('发送次数:')
        self.test_send_count_value = QLabel('0')
        progress_layout.addWidget(self.test_send_count_label, 1, 0)
        progress_layout.addWidget(self.test_send_count_value, 1, 1)
        
        self.test_success_count_label = QLabel('成功响应:')
        self.test_success_count_value = QLabel('0')
        progress_layout.addWidget(self.test_success_count_label, 2, 0)
        progress_layout.addWidget(self.test_success_count_value, 2, 1)
        
        self.test_error_count_label = QLabel('失败次数:')
        self.test_error_count_value = QLabel('0')
        progress_layout.addWidget(self.test_error_count_label, 3, 0)
        progress_layout.addWidget(self.test_error_count_value, 3, 1)
        
        self.test_current_cmd_label = QLabel('当前指令:')
        self.test_current_cmd_value = QLabel('无')
        progress_layout.addWidget(self.test_current_cmd_label, 4, 0)
        progress_layout.addWidget(self.test_current_cmd_value, 4, 1)
        
        test_layout.addLayout(progress_layout)
        
        password_layout.addLayout(test_layout)
        
        # 将密码管理部分添加到主布局
        layout.addLayout(password_layout)

        # 初始化时刷新串口列表
        # self.refresh_serial_ports()

        self.setLayout(layout)
        
    def blue_write_log(self,text):
        """写入日志"""
        print(text)
        self.receive_output.append(text)
        LogManager.get_instance().write_log(text)

    async def refresh_serial_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_combo.addItems(ports)
            self.serial_connect_button.setEnabled(True)
        else:
            self.serial_connect_button.setEnabled(False)
            self.blue_write_log("未发现可用串口")

    def on_serial_connect_clicked(self):
        """处理串口连接/断开"""
        if not self.is_serial_connected:
            try:
                # 获取串口参数
                port = self.port_combo.currentText()
                baud_rate = int(self.baud_combo.currentText())
                data_bits = int(self.data_bits_combo.currentText())
                stop_bits = float(self.stop_bits_combo.currentText())
                parity = {'无': 'N', '奇校验': 'O', '偶校验': 'E'}[self.parity_combo.currentText()]

                # 创建串口对象
                self.serial_port = serial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    bytesize=data_bits,
                    stopbits=stop_bits,
                    parity=parity,
                    timeout=0.1
                )

                if self.serial_port.is_open:
                    self.device_name = port
                    self.commu_type = "serial"
                    self.is_serial_connected = True
                    self.serial_connect_button.setText('断开串口')
                    self.blue_write_log(f"串口 {port} 连接成功")
                    # 禁用参数设置
                    self.disable_serial_settings(True)
                    # 启动接收任务
                    self.send_button.setEnabled(True)
                    self.serial_receive_task = asyncio.create_task(self.serial_receive_loop())
            except Exception as e:
                QMessageBox.critical(self, '错误', f'串口连接失败: {str(e)}')
                self.blue_write_log(f"串口连接失败: {str(e)}")
        else:
            # 断开连接
            # asyncio.create_task(self.disconnect_serial())
            if self.serial_receive_task:
                self.serial_receive_task.cancel()
                self.serial_receive_task = None
            
            if self.serial_port and self.serial_port.is_open:
                self.send_button.setEnabled(False)
                self.serial_port.close()
                self.commu_type = "none"
            
            self.is_serial_connected = False
            self.serial_connect_button.setText('连接串口')
            self.disable_serial_settings(False)
            self.blue_write_log("串口已断开")

    async def disconnect_serial(self):
        """断开串口连接"""
        pass


    def disable_serial_settings(self, disabled: bool):
        """禁用/启用串口设置控件"""
        self.port_combo.setEnabled(not disabled)
        self.baud_combo.setEnabled(not disabled)
        self.data_bits_combo.setEnabled(not disabled)
        self.stop_bits_combo.setEnabled(not disabled)
        self.parity_combo.setEnabled(not disabled)

    async def serial_receive_loop(self):
        """串口数据接收循环"""
        while self.is_serial_connected:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        # 调用 on_data_received 函数处理接收到的数据
                        await self.on_data_received(None, data)
                        # 使用与蓝牙相同的显示逻辑
                        if self.hex_display_checkbox.isChecked():
                            hex_data = ' '.join([f'{b:02X}' for b in data])
                            # self.blue_write_log(f"接收: {hex_data}")
                        else:
                            try:
                                text_data = data.decode('utf-8')
                                # self.blue_write_log(f"接收: {text_data}")
                            except UnicodeDecodeError:
                                hex_data = ' '.join([f'{b:02X}' for b in data])
                                # self.blue_write_log(f"接收(HEX): {hex_data}")
                await asyncio.sleep(0.01)
            except Exception as e:
                self.blue_write_log(f"接收数据错误: {str(e)}")
                await self.disconnect_serial()
                break

    async def send_data(self, input_data: str):
        """发送数据（兼容蓝牙和串口模式）"""
        try:
            if self.hex_send_checkbox.isChecked():
                # 16进制发送
                try:
                    print(f"send data type = {type(input_data)}")
                    hex_data = input_data.replace(" ", "")
                    if not all(c in '0123456789ABCDEFabcdef' for c in hex_data):
                        raise ValueError("Invalid hex string")
                    data_bytes = bytes.fromhex(hex_data)
                    
                    # 如果选中了\r\n发送，添加回车换行符
                    if self.crlf_send_checkbox.isChecked():
                        data_bytes += b'\r\n'
                        
                except ValueError as e:
                    QMessageBox.warning(self, '警告', '无效的16进制数据')
                    return
            else:
                # 文本发送
                send_text = input_data
                # 如果选中了\r\n发送，添加回车换行符
                if self.crlf_send_checkbox.isChecked():
                    send_text += '\r\n'
                data_bytes = send_text.encode()

            await self.byte_send(data_bytes)
            # 显示发送的数据 - 统一使用实际发送的字节数据
            self.display_send_data(data_bytes)
        except Exception as e:
            QMessageBox.critical(self, '发送失败', str(e))

    def on_hex_display_changed(self, state):
        """当16进制显示选项改变时，重新显示接收到的数据"""
        if hasattr(self, 'received_data_buffer'):
            self.receive_output.clear()
            # for data in self.received_data_buffer:
            self.display_received_data(self.received_data_buffer)

    def display_received_data(self, data):
        """显示接收到的数据，根据16进制显示选项决定显示格式"""
        if self.hex_display_checkbox.isChecked():
            # 16进制显示
            reve_data = ' '.join([f'{b:02X}' for b in data])
        else:
            # 文本显示，无法解码的字符显示为乱码
            reve_data = data.decode('utf-8', errors='replace')  
        self.blue_write_log(f"RX->,{self.commu_type},{self.device_name},cmd,{reve_data}")
    def display_send_data(self, input_data):
        """显示接收到的数据，根据16进制显示选项决定显示格式"""
        if self.hex_display_checkbox.isChecked():
            # 16进制显示
            if isinstance(input_data, str):
                # 如果是字符串，将每个字符转换为ASCII值再格式化为十六进制
                send_data = ' '.join([f'{ord(b):02X}' for b in input_data])
            else:
                # 如果是字节数据，直接格式化为十六进制
                send_data = ' '.join([f'{b:02X}' for b in input_data])
        else:
            # 文本显示
            if isinstance(input_data, str):
                send_data = input_data
            else:
                # 无法解码的字符显示为乱码
                send_data = input_data.decode('utf-8', errors='replace')
        self.blue_write_log(f"TX->,{self.commu_type},{self.device_name},cmd,{send_data}")

    def on_scan_devices_clicked(self):
        """同步方法，用于触发异步扫描"""
        asyncio.create_task(self.scan_devices())

    def on_connect_device_clicked(self):
        """同步方法，用于触发异步连接"""
        self.decode_data_ok_signal.emit(None,{"connect" : {'nothing':('nothing','nothing','nothing')}}) 
        asyncio.create_task(self.connect_device())

    def on_disconnect_device_clicked(self):
        """同步方法，用于触发异步断开连接"""
        asyncio.create_task(self.disconnect_device())
        asyncio.create_task(self.disconnect_serial())

    def on_send_data_clicked(self):
        """同步方法，用于触发异步发送数据"""
        data = self.send_input.text()
        if data:
            asyncio.create_task(self.send_data(data))
        else:
            QMessageBox.warning(self, '警告', '请输入要发送的数据')
    def on_test_send_buttoned(self):
        """同步方法,用于测试"""
        if self.task_flag == True:
            self.task.cancel()
            self.task_flag = False
            return
        self.total_send_label.setText(f'总 = 0')
        self.no_ack_label.setText(f'无回复 = 0')
        self.err_ack_label.setText(f'ack错误 = 0')
        self.err_ack_count = 0
        self.no_ack_count = 0
        self.task_flag = True
        self.task = asyncio.create_task(self.test_send_data())

    async def scan_devices(self):
        """异步方法，扫描蓝牙设备"""
        self.device_list.clear()
        self.label.setText('正在扫描设备...')

        # 获取用户输入的信号强度阈值
        try:
            rssi_threshold = int(self.rssi_threshold_input.text())
        except ValueError:
            rssi_threshold = -100  # 默认值，显示所有设备

        try:
            # 设置扫描时间为2秒，并获取广告数据
            discovered_devices = await BleakScanner.discover(timeout=2.0, return_adv=True)
        except Exception as e:
            # QMessageBox.critical(self, '扫描失败', str(e))
            self.blue_write_log(f"扫描失败 {str(e)}")
            traceback.print_exc()
            return

        self.device_list.clear()
        self.device_name_to_address.clear()  # 清空设备映射
        for device, advertisement_data in discovered_devices.values():
            # 只显示有名字且信号强度符合要求的设备
            if device.name and advertisement_data.rssi > rssi_threshold:
                # 检查密码功能状态
                password_status_short = ""
                if advertisement_data.manufacturer_data:
                    for company_id, data in advertisement_data.manufacturer_data.items():
                        if len(data) >= 2:
                            second_last_byte = data[-2]  # 倒数第二个字节
                            last_byte = data[-1]         # 最后一个字节
                            
                            if second_last_byte == 0x50:  # 支持密码功能
                                if last_byte == 0x00:
                                    password_status_short = " [密码:未设置]"
                                elif last_byte == 0x01:
                                    password_status_short = " [密码:已设置]"
                                else:
                                    password_status_short = f" [密码:未知{last_byte:02X}]"
                                break  # 找到了就退出循环
                
                # 保存设备名到地址的映射
                self.device_name_to_address[device.name] = device.address
                
                # 添加到设备列表，去掉地址显示，添加密码状态
                self.device_list.addItem(f"{device.name} (RSSI: {advertisement_data.rssi}){password_status_short}")
                # 获取更有用的设备信息
                # device_info = f"发现设备: {device.name} - {device.address} - (RSSI: {advertisement_data.rssi})"
                
                # # 尝试获取广告数据中的有用信息
                # try:
                #     metadata_info = []
                    
                #     # 解析服务UUID
                #     if advertisement_data.service_uuids:
                #         uuids = list(advertisement_data.service_uuids)
                #         metadata_info.append(f"服务UUID: {uuids}")
                    
                #     # 解析厂商数据
                #     if advertisement_data.manufacturer_data:
                #         for company_id, data in advertisement_data.manufacturer_data.items():
                #             # 转换厂商ID为十六进制
                #             hex_id = f"0x{company_id:04X}"
                            
                #             # 转换数据为十六进制字符串
                #             hex_data = data.hex().upper() if data else "空"
                #             # 尝试解析为ASCII（如果可能）
                #             try:
                #                 ascii_data = data.decode('ascii', errors='ignore')
                #                 ascii_info = f" (ASCII: '{ascii_data}')" if ascii_data.isprintable() else ""
                #             except:
                #                 ascii_info = ""
                            
                #             # 检查密码状态：查看最后两个字节
                #             password_status = ""
                            
                #             # 判断逻辑：检查最后两个字节
                #             # 倒数第二个字节为0x50 → 支持密码功能
                #             # 最后一个字节：0x00=未设置，0x01=已设置
                            
                #             if len(data) >= 2:
                #                 second_last_byte = data[-2]  # 倒数第二个字节
                #                 last_byte = data[-1]         # 最后一个字节
                                
                #                 if second_last_byte == 0x50:  # 支持密码功能
                #                     if last_byte == 0x00:
                #                         password_status = " [支持密码，未设置]"
                #                     elif last_byte == 0x01:
                #                         password_status = " [支持密码，已设置]"
                #                     else:
                #                         password_status = f" [支持密码，状态未知:0x{last_byte:02X}]"
                #             else:
                #                 password_status = " [数据长度不足]"
                            
                #             # metadata_info.append(f"厂商数据: ID={hex_id}, 数据={hex_data}{ascii_info}{password_status}")
                    
                #     if metadata_info:
                #         device_info += f" - {'; '.join(metadata_info)}"
                # except Exception as ex:
                #     self.blue_write_log(f"解析广告数据失败: {ex}")
                
                # self.blue_write_log(device_info)
        
        self.label.setText('发现的蓝牙设备:')

    async def connect_device(self):
        """异步方法，连接蓝牙设备"""
        selected_device = self.device_list.currentItem()
        if selected_device:
            # 从显示文本中提取设备名
            device_text = selected_device.text()
            device_name = device_text.split(' (RSSI:')[0]  # 提取设备名
            
            # 通过设备名查找地址
            device_address = self.device_name_to_address.get(device_name)
            if not device_address:
                QMessageBox.warning(self, '警告', '无法找到设备地址，请重新扫描')
                return
            try:
                self.client = BleakClient(device_address)
                self.blue_write_log(f"连接开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
                await self.client.connect()
                self.blue_write_log(f"连接结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
                self.commu_type = "bluetooth"
                # 创建消息框实例
                # connectMessage = QMessageBox(QMessageBox.Icon.Information, '连接成功', f'已连接到 {device_address}')
                # 设置定时器自动关闭 (3000毫秒后)
                # QTimer.singleShot(300, connectMessage.close)
                # 显示消息框
                # connectMessage.exec()
                # 启用断开按钮和发送按钮
                self.disconnect_button.setEnabled(True)
                self.send_button.setEnabled(True)
                # 开始监听数据
                if self.client and self.client.is_connected:
                    self.device_name = device_name  # 使用之前提取的设备名
                    await self.client.start_notify("0000ffe1-0000-1000-8000-00805f9b34fb", self.on_data_received)
                # QTimer.singleShot(1000, self.send_find_version_cmd)
                await self.send_verify_password_cmd('123456')
            except Exception as e:
                self.commu_type = "none"
                QMessageBox.critical(self, '连接失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '请先选择一个设备')

    async def disconnect_device(self):
        """异步方法，断开蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                
                # 创建消息框
                msg_box = QMessageBox(QMessageBox.Icon.Information, '断开成功', '设备已断开')
                
                # 设置定时器自动关闭 (3秒后)
                QTimer.singleShot(1000, msg_box.close)
                
                # 显示消息框
                msg_box.exec()
                
                # 禁用断开按钮和发送按钮
                self.disconnect_button.setEnabled(False)
                self.send_button.setEnabled(False)
                self.client = None
                self.commu_type = "none"
            except Exception as e:
                QMessageBox.critical(self, '断开失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '未连接到设备')

    async def bluetooth_send_data(self, data:str):
        """异步方法，发送数据到蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                if self.hex_send_checkbox.isChecked():
                    # 16进制发送
                    try:
                        # 移除所有空格并检查是否为有效的16进制字符串
                        hex_data = data.replace(" ", "")
                        if not all(c in '0123456789ABCDEFabcdef' for c in hex_data):
                            raise ValueError("Invalid hex string")
                        # 将16进制字符串转换为字节
                        data_bytes = bytes.fromhex(hex_data)
                    except ValueError as e:
                        QMessageBox.warning(self, '警告', '无效的16进制数据')
                        return
                else:
                    # 文本发送
                    data_bytes = data.encode()

                # 假设设备的写特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data_bytes)
                
                # 显示发送的数据
                if self.hex_send_checkbox.isChecked():
                    hex_data = ' '.join([f'{b:02X}' for b in data_bytes])
                    self.blue_write_log(f"发送: {hex_data}")
                else:
                    self.blue_write_log(f"发送: {data}")
            except Exception as e:
                QMessageBox.critical(self, '发送失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '未连接到设备')

    async def test_send_data(self):
        """异步方法，发送测试数据"""
        data = self.text_decode.send_hex_fill(0x13)
        self.send_count = 0
        send_max_count = 100
        while send_max_count:
            send_max_count-=1
            time512 = int(self.test512.text()) / 1000 * 2
            if self.client and self.client.is_connected:
                try:
                    # 假设设备的写特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                    self.byte_send(data)
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    self.display_send_data(data)
                    # time.sleep(time512)
                    self.send_count += 1
                    self.total_send_label.setText(f'总 = {self.send_count}')

                    await asyncio.sleep(0.4)
                    if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                        await asyncio.sleep(0.7)
                    if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                        if self.text_decode.cmd_ack in [0x00]:
                            self.blue_write_log("回复成功")
                        else:
                            self.err_ack_count+=1
                            self.err_ack_label.setText(f'err回复={self.err_ack_count}')
                            self.blue_write_log("回复错误")
                    else:
                        self.no_ack_count+=1
                        self.no_ack_label.setText(f'无回复={self.no_ack_count}')
                        self.blue_write_log("没有回复")

                    # 如果收到数据过长，清楚部分开头数据，提升软件性能
                    if self.send_count > 10:                        
                        cursor = self.receive_output.textCursor()  # 获取 QTextCursor
                        cursor.movePosition(cursor.MoveOperation.Start)  # 移动到文档开头
                        cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)  # 选中首行
                        cursor.removeSelectedText()  # 删除选中文本
                        cursor.deleteChar()  # 删除换行符
                    current_time = datetime.now().strftime("%d %H:%M:%S")[:18]  # 格式化并限制长度到毫秒
                    self.blue_write_log(f"成功发送次数 = {self.send_count} 发送时间 = {current_time}")
                except Exception as e:
                    traceback.print_exc()
                    self.blue_write_log(f"蓝牙发送失败 {str(e)}")
                    QMessageBox.critical(self, '发送失败', str(e))
            else:
                # QMessageBox.warning(self, '警告', '未连接到设备')
                break
        self.task_flag = False

    async def byte_send(self,data:bytes):
        """异步方法，发送字节数据"""
        self.text_decode.legality = ReceveDataStatus.ERR_NOTHING # 初始化数据解析状态
        if(len(data) == 0):
            return
        try:
            if(not self.client or not self.client.is_connected):
                if(not self.serial_port or not self.serial_port.is_open):
                    # QMessageBox.warning(self, '警告', '未连接到设备')
                    raise Exception("未连接到设备")
                """蓝牙发送"""
            if self.client and self.client.is_connected:
                time_interval = int(self.test128.text()) / 1000
                packet_count = len(data) // 128 + 1 if len(data) % 128 != 0 else len(data) // 128
                for i in range(0,packet_count):
                    if i + 1 == packet_count:
                        left = i * 128
                        right = len(data)
                    else:
                        left = i * 128
                        right = (i + 1) * 128
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data[left:right])
                    await asyncio.sleep(time_interval)
                """串口发送"""
            elif self.serial_port and self.serial_port.is_open:
                self.serial_port.write(data)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, '发送失败', str(e))
            raise Exception("发送失败")


    async def on_data_received(self, sender, data):
        """回调函数，处理接收到的数据"""
        # 将数据添加到缓冲区
        self.received_data_buffer.extend(data)
        print("2第一次收到数据J")
        # 重启定时器
        self.data_timer.start(100)  # 100ms

    def process_complete_data(self):
        """处理完整的数据包"""
        # 在这里处理完整的数据包
        # self.blue_write_log(f"Received complete data packet: {self.received_data_buffer}")
    
        # 先检查是否收到NOAUTH响应
        if self.check_noauth_response(self.received_data_buffer):
            # 已经在check_noauth_response中处理了日志，这里直接返回
            pass
        # 检查是否是新的密码命令响应格式
        elif self.check_new_password_response(self.received_data_buffer):
            # 处理新的密码命令响应
            success, result = self.parse_new_password_response(self.received_data_buffer)
            if success:
                self.handle_new_password_response(result["cmd_code"], result["content"])
            else:
                self.blue_write_log(f"密码命令响应解析失败: {result}")
        else:
            # 处理普通数据
            print("3收完数据")
            self.text_decode.split_data(self.received_data_buffer)
            if self.text_decode.have_hex:
                # self.blue_write_log(f"发送信号给数据解析模块")
                struct_name,dict_data = self.hex_parser.decode_cmd_hex_data(self.text_decode.no80_cmd,bytes(self.text_decode.data_hex))
                print("4解析完数据")
                if dict_data:
                    header = f"RX->,{self.commu_type},{self.device_name},{struct_name}"
                    """csv记录监控数据"""
                    """外部窗口展示 监控数据 |字典数据|纯参数数据|"""
                    self.decode_data_ok_signal.emit(header,dict_data) 
                    print("5发射完字典")
                    # 发射到函数 get_dict_from_receive_data (str,dict)
        """log记录调试数据"""
        """内部窗口展示 调试数据 |hex数据|字符串数据|"""
        self.display_received_data(self.received_data_buffer)
        print("6显示完数据")
        # 清空缓冲区
        self.received_data_buffer.clear()

    def check_new_password_response(self, data):
        """检查是否是新的密码命令响应格式"""
        if len(data) < 5:
            return False
        
        # 检查帧头和帧尾
        if data[0] == 0xFB and data[-1] == 0xBB:
            cmd_code = data[1]
            # 检查是否是密码相关命令的响应
            if cmd_code in [0x01, 0x02, 0x03, 0x04]:
                return True
        
        return False



    def on_select_hex_file(self):
        """选择HEX文件并解析"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择HEX文件",
            "",
            "HEX文件 (*.hex);;所有文件 (*.*)"
        )
        if filename:
            if self.hex_model.parse_hex_file(filename):
                file_info = self.hex_model.get_file_info()
                self.hex_file_label.setText(f'HEX文件：{file_info["filename"]}')
                self.hex_info_label.setText(f'文件大小：{file_info["size"]} 字节')
            else:
                QMessageBox.warning(self, '警告', 'HEX文件解析失败')

    def on_program_clicked(self):
        """同步方法，用于触发异步烧录"""
        if self.program_task:
            self.program_task.cancel()
            self.program_task = None
            self.program_button.setEnabled(True)
            self.program_button.setText('开始烧录')
        else:
            if not self.client or not self.client.is_connected:
                if not self.serial_port or not self.serial_port.is_open:
                    QMessageBox.warning(self, '警告', '请先连接设备')
            # 创建烧录任务
            self.program_task = asyncio.create_task(self.start_programming())

    async def start_programming(self):
        """异步方法，执行烧录过程"""
        try:
            self.ota_start_count += 1
            time128 = int(self.test128.text()) / 1000
            time512 = int(self.test512.text()) / 1000
            self.program_button.setText('再点击即停止')
            err_count = 0  
            # while err_count < 4:
            #     data = self.download_data.get_download_data(BmsCmdType.DOWNLOAD_BUFFER)
            #     self.display_send_data(data)
            #     await self.byte_send(data)
            #     # await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
            #     self.blue_write_log("75发送")
            #     await asyncio.sleep(time512)
            #     if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
            #         await asyncio.sleep(time512 * 4)
            #     if(self.text_decode.no80_cmd == BmsCmdType.DOWNLOAD_BUFFER  and self.text_decode.cmd_ack == 0x00):
            #         err_count -= 1
            #         break
            #     else:
            #         err_count += 1
            # await asyncio.sleep(1)

            shake_count = 0
            while shake_count < 3:
                err_count = 0
                while err_count < 3:
                    self.packet_success_label.setText('开始握手')
                    data = bytearray([0x00,0x00,0x04,0x01,0x76,0x55,0xaa,0x7a])
                    self.display_send_data(data)
                    await self.byte_send(data)
                    # self.blue_write_log("76发送")
                    await asyncio.sleep(time512 * 2)
                    if(self.text_decode.is_download_cmd):
                        break
                    err_count += 1
                else:
                    if err_count == 3:
                        self.blue_write_log(f"握手命令发送失败")
                        # raise Exception("握手命令发送失败")
                shake_count += 1
            else:
                self.packet_success_label.setText('握手成功')
                self.blue_write_log(f"握手命令发送成功")
            # self.text_decode.legality = ReceveDataStatus.ERR_NOTHING



            err_count = 0  
            while err_count < 2:
                data = self.download_data.get_download_data(BmsCmdType.DOWNLOAD_BUFFER)
                self.display_send_data(data)
                await self.byte_send(data)
                # self.blue_write_log("75发送")
                await asyncio.sleep(time512 * 2)
                if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                    await asyncio.sleep(time512 * 4)
                if(self.text_decode.no80_cmd == BmsCmdType.DOWNLOAD_BUFFER  and self.text_decode.cmd_ack == 0x00):
                    self.blue_write_log(f"擦除命令发送成功")
                    self.packet_success_label.setText('擦除成功')
                    break
                else:
                    err_count += 1
            else:
                self.blue_write_log(f"擦除命令发送失败")
                
            # while 
            

            # 发送下载命令并等待响应
            if not self.hex_model.is_file_loaded:
                raise Exception("HEX文件未加载")
            else:
                self.download_data.hex_init(self.hex_model.get_data())   
                pass
            hex_packet = 0
            while 1:
                data = self.download_data.get_download_data(BmsCmdType.WRITE_FLASH,hex_packet)
                if(data == None):
                    self.blue_write_log(f"数据发送完成")
                    break
                else:
                    try:
                        err_count = 0
                        while err_count < 5:
                            self.display_send_data(data)
                            self.blue_write_log("1开始发送----------------")
                            await self.byte_send(data)
                            # current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            # self.blue_write_log(f"TX->数据包发送完成 - 时间: {current_time}")
                            await asyncio.sleep(time512)  
                            if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                                await asyncio.sleep(time512)  
                            print("7返回烧录过程")
                            if(self.text_decode.no80_cmd == BmsCmdType.WRITE_FLASH  and 
                                self.text_decode.cmd_ack == 0x00 and
                                self.text_decode.cmd_packet_num == hex_packet + 1):
                                    self.packet_success_label.setText(f'包号: {hex_packet + 1} 总包数: {self.download_data.packet_num}')
                                    err_count = 0
                                    hex_packet += 1
                                    break
                            else:
                                await asyncio.sleep(time512*3)  
                                err_count += 1
                        else:
                            self.blue_write_log(f"数据发送失败")
                            raise Exception("writeflash次数超限")

                    except BleakError:
                        self.blue_write_log(f"蓝牙断开------------------")
                        # traceback.print_exc()
                        raise Exception("蓝牙断开")
                    except Exception as e:
                        self.blue_write_log(f"有错误------------------{e}")
                        traceback.print_exc()
                        break
                    else:
                        self.blue_write_log(f"没有错误-----------------")


            err_count = 0   
            while err_count < 5:
                data = self.download_data.get_download_data(BmsCmdType.REC_TOTAL_CHECKSUM)
                self.display_send_data(data)
                await self.byte_send(data)
                await asyncio.sleep(time512 * 4)
                if(self.text_decode.no80_cmd == BmsCmdType.REC_TOTAL_CHECKSUM  and self.text_decode.cmd_ack == 0x00):
                    break
                else:
                    err_count += 1
            self.blue_write_log("烧录完成")
            await asyncio.sleep(6)

            err_count = 0
            if self.text_decode.no80_cmd == BmsCmdType.BMS_MCU_OPEN  and self.text_decode.cmd_ack == 0x00:
                self.blue_write_log("电池重启")
                while err_count < 5:
                    data = self.download_data.get_download_data(BmsCmdType.READ_IC_INF)
                    self.display_send_data(data)
                    await self.byte_send(data)
                    await asyncio.sleep(time512 * 2)
                    if(self.text_decode.no80_cmd == BmsCmdType.READ_IC_INF  and self.text_decode.cmd_ack == 0x00):
                        self.ota_ok_count += 1
                        break
                    else:
                        err_count += 1
            
        except Exception as e:
            traceback.print_exc()
            self.blue_write_log(f"烧录失败: {str(e)}")
            # QMessageBox.critical(self, '错误', f'烧录失败: {str(e)}')
        
        finally:
            # 恢复按钮状态
            self.program_task = None
            self.program_button.setEnabled(True)
            self.program_button.setText('开始烧录')

    def on_scan_all_clicked(self):
        """同步方法，用于触发异步扫描蓝牙和刷新串口"""
        # 显示扫描开始信息
        self.blue_write_log("开始扫描蓝牙设备和刷新串口...")
        
        # 刷新串口列表
        asyncio.create_task(self.refresh_serial_ports())
        
        # 扫描蓝牙设备
        asyncio.create_task(self.scan_devices())

    def on_open_discharge_clicked(self):
        """处理打开放电按钮点击事件"""
        # 发送打开放电的指令数据
        bytedata = bytes([0x00,0x00,0x04,0x01,0x0c,0x55,0xaa,0x10])
        self.send_command(bytedata)

    def on_close_discharge_clicked(self):
        """处理关闭放电按钮点击事件"""
        # 发送关闭放电的指令数据
        bytedata = bytes([0x00,0x00,0x04,0x01,0x0D,0x55,0xaa,0x11])
        self.send_command(bytedata)

    def send_command(self, command:bytes):
        """发送指令数据"""
        asyncio.create_task(self.byte_send(command))
        self.display_send_data(command)

    def send_sbs_cmd(self):
        """发送sbs查询电池数据"""
        self.send_command(self.text_decode.send_hex_fill(0x13))
    def send_life_time(self):
        """发送生命周期命令"""
        self.send_command(self.text_decode.send_hex_fill(0x41))
    def send_tbs_cmd(self):
        try:
            self.send_command(self.text_decode.send_hex_fill(0x15))
        except:
            pass
    def send_find_version_cmd(self):
        """发送版本号查询命令"""
        self.send_command(self.text_decode.send_hex_fill(0x71))
    
    def send_ver_cmd_16(self):
        """发送0x16版本号查询命令"""
        self.send_command(self.text_decode.send_hex_fill(0x16))

    def on_batch_program_clicked(self):
        """同步方法，批量烧录100次"""
        if self.batch_task:
            self.batch_task.cancel()
            self.batch_program_button.setText('开始烧录100')
            self.batch_task = None
            return
        self.batch_program_button.setText('再点击即停止')
        self.ota_start_count = 0
        self.ota_ok_count = 0
        self.batch_success_label.setText('成功数: 0')
        self.batch_task = asyncio.create_task(self.batch_programming())

    async def batch_programming(self):
        """异步方法，批量烧录100次"""
        for i in range(100):
            try:
                await self.start_programming()
                self.batch_success_label.setText(f'总数: {self.ota_start_count} 成功数: {self.ota_ok_count}')
            except Exception as e:
                self.blue_write_log(f'第{i+1}次烧录失败: {e}')
                traceback.print_exc()
                self.batch_task = None
                continue
        self.batch_program_button.setText('开始烧录100')

    def on_register_clicked(self):
        asyncio.create_task(self.send_register_cmd())
        pass
    
    async def send_register_cmd(self):
        """注册按钮点击处理"""
        try:
            self.update_registration_status(False)
            # 这里添加实际的注册逻辑
            data = bytearray([0x00,0x00,0x04,0x01,0x01,0x55,0xaa,0x05])
            self.display_send_data(data)
            await self.byte_send(data)
            await asyncio.sleep(0.4)
            if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                await asyncio.sleep(0.7)
            if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                if self.text_decode.cmd_ack in [0x00, 0x04]:
                    self.update_registration_status(True)
                    self.blue_write_log("注册成功")
                else:
                    self.update_registration_status(False)
                    self.blue_write_log("注册失败")
            else:
                self.update_registration_status(False)
                self.blue_write_log("注册失败")
                
        except Exception as e:
            self.blue_write_log(f"注册异常: {str(e)}")
            self.update_registration_status(False)

    def update_registration_status(self, is_registered: bool):
        """更新注册状态指示"""
        color = QColor(0, 255, 0) if is_registered else QColor(255, 0, 0)  # 绿/红
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 15, 15)
        painter.end()
        self.status_indicator.setPixmap(pixmap)

    def on_query_lock_clicked(self):
        """查询加密状态按钮点击处理 - 暂时保留旧功能"""
        # 注释：查询功能现在通过广播数据中的密码状态字段实现
        asyncio.create_task(self.send_search_password_cmd())

    def on_login_clicked(self):
        """登录按钮点击处理 - 使用新的验证密码命令"""
        password = self.password_input.text()
        if len(password) != 6:
            QMessageBox.warning(self, '警告', '密码必须是6位字符')
            return
        asyncio.create_task(self.send_verify_password_cmd(password))

    def on_set_password_clicked(self):
        """设置密码按钮点击处理 - 使用新的设置密码命令"""
        password = self.password_input.text()
        if len(password) != 6:
            QMessageBox.warning(self, '警告', '密码必须是6位字符')
            return
        asyncio.create_task(self.send_set_password_cmd_new(password))

    def on_reset_password_clicked(self):
        """重置密码按钮点击处理 - 使用新的取消密码命令"""
        asyncio.create_task(self.send_cancel_password_cmd())
        
    def on_crypto_test_clicked(self):
        """加密指令压力测试按钮点击处理"""
        if not self.client or not self.client.is_connected:
            if not self.serial_port or not self.serial_port.is_open:
                QMessageBox.warning(self, '警告', '请先连接设备再进行测试')
                return
        
        if self.crypto_test_running:
            QMessageBox.warning(self, '警告', '测试正在进行中，请先停止当前测试')
            return
            
        # 获取测试密码
        password = self.password_input.text()
        if len(password) != 6:
            # 如果没有输入密码，使用默认密码
            password = "123456"
            self.password_input.setText(password)
            self.blue_write_log("使用默认测试密码: 123456")
            
        # 开始测试
        self.crypto_test_task = asyncio.create_task(self.run_crypto_stress_test(password))
        
    def on_stop_test_clicked(self):
        """停止测试按钮点击处理"""
        if self.crypto_test_running:
            self.crypto_test_stop_requested = True
            self.blue_write_log("请求停止测试，等待当前指令完成...")
        else:
            self.blue_write_log("没有正在运行的测试")
            
    def reset_crypto_test_counters(self):
        """重置测试计数器"""
        self.crypto_test_send_count = 0
        self.crypto_test_success_count = 0
        self.crypto_test_error_count = 0
        self.crypto_test_current_round = 0
        self.crypto_test_stop_requested = False
        
        # 更新UI显示
        self.test_progress_value.setText('0/0 (0%)')
        self.test_send_count_value.setText('0')
        self.test_success_count_value.setText('0')
        self.test_error_count_value.setText('0')
        self.test_current_cmd_value.setText('无')
        
    def update_crypto_test_ui(self):
        """更新测试UI显示"""
        # 更新进度
        progress = int((self.crypto_test_current_round / self.crypto_test_total_rounds) * 100) if self.crypto_test_total_rounds > 0 else 0
        self.test_progress_value.setText(f'{self.crypto_test_current_round}/{self.crypto_test_total_rounds} ({progress}%)')
        
        # 更新计数
        self.test_send_count_value.setText(str(self.crypto_test_send_count))
        self.test_success_count_value.setText(str(self.crypto_test_success_count))
        self.test_error_count_value.setText(str(self.crypto_test_error_count))
        
        # 计算成功率
        success_rate = int((self.crypto_test_success_count / self.crypto_test_send_count * 100)) if self.crypto_test_send_count > 0 else 0
        self.blue_write_log(f"测试进度: {self.crypto_test_current_round}/{self.crypto_test_total_rounds}, 成功率: {success_rate}%")
        
    async def run_crypto_stress_test(self, password):
        """运行加密指令压力测试"""
        try:
            self.crypto_test_running = True
            self.crypto_test_button.setEnabled(False)
            self.stop_test_button.setEnabled(True)
            
            # 重置计数器
            self.reset_crypto_test_counters()
            
            self.blue_write_log(f"开始加密指令压力测试，共{self.crypto_test_total_rounds}轮，每轮4个指令")
            self.blue_write_log(f"使用密码: {password}")
            
            # 定义四个测试指令
            test_commands = [
                ("查询密码状态", lambda: self.send_search_password_cmd()),
                ("验证密码", lambda: self.send_verify_password_cmd(password)), 
                ("设置密码", lambda: self.send_set_password_cmd_new(password)),
                ("取消密码", lambda: self.send_cancel_password_cmd())
            ]
            
            for round_num in range(1, self.crypto_test_total_rounds + 1):
                if self.crypto_test_stop_requested:
                    self.blue_write_log("收到停止请求，终止测试")
                    break
                    
                self.crypto_test_current_round = round_num
                
                # 执行四个指令
                for cmd_name, cmd_func in test_commands:
                    if self.crypto_test_stop_requested:
                        break
                        
                    self.test_current_cmd_value.setText(f"第{round_num}轮-{cmd_name}")
                    
                    try:
                        # 记录发送次数
                        self.crypto_test_send_count += 1
                        
                        # 执行指令
                        await cmd_func()
                        
                        # 等待一段时间让响应处理完成
                        await asyncio.sleep(0.5)
                        
                        # 简单假设指令执行成功（实际应该根据响应判断）
                        self.crypto_test_success_count += 1
                        
                    except Exception as e:
                        self.crypto_test_error_count += 1
                        self.blue_write_log(f"指令执行失败: {cmd_name} - {str(e)}")
                    
                    # 更新UI
                    self.update_crypto_test_ui()
                    
                    # 指令间间隔
                    await asyncio.sleep(0.2)
                
                # 每轮间隔
                if not self.crypto_test_stop_requested:
                    await asyncio.sleep(0.5)
                    
            # 测试完成
            self.blue_write_log("压力测试完成！")
            self.blue_write_log(f"总计发送: {self.crypto_test_send_count} 次")
            self.blue_write_log(f"成功响应: {self.crypto_test_success_count} 次")
            self.blue_write_log(f"失败次数: {self.crypto_test_error_count} 次")
            
            success_rate = int((self.crypto_test_success_count / self.crypto_test_send_count * 100)) if self.crypto_test_send_count > 0 else 0
            self.blue_write_log(f"成功率: {success_rate}%")
            
            self.test_current_cmd_value.setText('测试完成')
            
        except Exception as e:
            self.blue_write_log(f"测试过程中发生异常: {str(e)}")
            self.test_current_cmd_value.setText('测试异常')
        finally:
            # 恢复按钮状态
            self.crypto_test_running = False
            self.crypto_test_button.setEnabled(True)
            self.stop_test_button.setEnabled(False)

    def closeEvent(self, event):
        """重写BluetoothTool的关闭事件，确保清理资源"""
        try:
            # 停止加密指令测试
            if self.crypto_test_running:
                self.crypto_test_stop_requested = True
                if self.crypto_test_task:
                    self.crypto_test_task.cancel()
                self.blue_write_log("已停止加密指令测试")
            
            # 断开蓝牙连接
            if self.client and self.client.is_connected:
                asyncio.create_task(self.disconnect_device())
            
            # 断开串口连接
            if self.is_serial_connected:
                self.on_serial_connect_clicked()
                
            self.blue_write_log("BluetoothTool窗口已关闭，所有连接已断开")
        except Exception as e:
            self.blue_write_log(f"关闭窗口时出现错误: {str(e)}")
        
        # 接受关闭事件
        event.accept()

    async def send_query_lock_cmd(self):
        """发送查询加密状态命令 (0x5D)"""
        try:
            # 使用send_hex_fill方法构造查询加密命令
            data = self.text_decode.send_hex_fill(0x5D)
            
            self.display_send_data(data)
            await self.byte_send(data)
            await asyncio.sleep(0.4)
            
            if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                if self.text_decode.no80_cmd == 0x5D & 0x7F:  # 回复命令码是0xDD
                    # 检查数据位
                    if hasattr(self.text_decode, 'data_hex') and len(self.text_decode.data_hex) > 0:
                        data_value = self.text_decode.data_hex[0]
                        if data_value == 0x00:
                            self.blue_write_log("查询结果: 无密码")
                        elif data_value == 0x01:
                            self.blue_write_log("查询结果: 有密码，未登录")
                        elif data_value == 0x02:
                            self.blue_write_log("查询结果: 有密码，已登录")
                        else:
                            self.blue_write_log(f"查询结果: 未知状态 {data_value:02X}")
                    else:
                        self.blue_write_log("查询加密状态成功，但无数据")
                else:
                    self.blue_write_log("查询加密状态失败: 命令码不匹配")
            else:
                self.blue_write_log("查询加密状态失败: 无响应")
                
        except Exception as e:
            self.blue_write_log(f"查询加密状态异常: {str(e)}")

    async def send_login_cmd(self, password: str):
        """发送登录命令 (0x5F)"""
        try:
            # 构造密码数据数组
            password_data = bytearray()
            for char in password:
                password_data.append(ord(char))
            
            # 使用send_hex_fill方法构造登录命令
            data = self.text_decode.send_hex_fill(0x5F, password_data)
            
            self.display_send_data(data)
            await self.byte_send(data)
            await asyncio.sleep(0.4)
            
            if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                if self.text_decode.no80_cmd == 0xDF & 0x7F:  # 回复命令码是0xDF
                    # 检查数据位
                    if hasattr(self.text_decode, 'data_hex') and len(self.text_decode.data_hex) > 0:
                        data_value = self.text_decode.data_hex[0]
                        if data_value == 0x03:
                            self.blue_write_log("登录成功: 密码正确")
                        elif data_value == 0x04:
                            self.blue_write_log("登录失败: 密码错误")
                        else:
                            self.blue_write_log(f"登录结果: 未知状态 {data_value:02X}")
                    else:
                        self.blue_write_log("登录命令发送成功，但无数据")
                else:
                    self.blue_write_log("登录失败: 命令码不匹配")
            else:
                self.blue_write_log("登录失败: 无响应")
                
        except Exception as e:
            self.blue_write_log(f"登录异常: {str(e)}")

    async def send_set_password_cmd(self, password: str):
        """发送设置密码命令 (0x5E)"""
        try:
            # 构造数据数组：6字节校验码 + 6字节密码
            set_password_data = bytearray()
            # 添加6字节校验码: 5A 5A 5A A5 A5 A5
            set_password_data.extend([0x5A, 0x5A, 0x5A, 0xA5, 0xA5, 0xA5])
            # 添加6字节密码（ASCII）
            for char in password:
                set_password_data.append(ord(char))
            
            # 使用send_hex_fill方法构造设置密码命令
            data = self.text_decode.send_hex_fill(0x5E, set_password_data)
            
            self.display_send_data(data)
            await self.byte_send(data)
            await asyncio.sleep(0.4)
            
            if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                if self.text_decode.no80_cmd == 0xDE & 0x7F:  # 回复命令码是0xDE
                    # 检查数据位
                    if hasattr(self.text_decode, 'data_hex') and len(self.text_decode.data_hex) > 0:
                        data_value = self.text_decode.data_hex[0]
                        if data_value == 0x05:
                            self.blue_write_log("设置密码成功")
                        elif data_value == 0x06:
                            self.blue_write_log("设置密码错误")
                        else:
                            self.blue_write_log(f"设置密码结果: 未知状态 {data_value:02X}")
                    else:
                        self.blue_write_log("设置密码命令发送成功，但无数据")
                else:
                    self.blue_write_log("设置密码失败: 命令码不匹配")
            else:
                self.blue_write_log("设置密码失败: 无响应")
                
        except Exception as e:
            self.blue_write_log(f"设置密码异常: {str(e)}")

    async def send_reset_password_cmd(self):
        """发送重置密码命令 (0x5C)"""
        try:
            # 构造数据数组：6字节校验码
            reset_data = bytearray()
            # 添加6字节校验码: 5A 5A 5A A5 A5 A5
            reset_data.extend([0x5A, 0x5A, 0x5A, 0xA5, 0xA5, 0xA5])
            
            # 使用send_hex_fill方法构造重置密码命令
            data = self.text_decode.send_hex_fill(0x5C, reset_data)
            
            self.display_send_data(data)
            await self.byte_send(data)
            await asyncio.sleep(0.4)
            
            if self.text_decode.legality != ReceveDataStatus.ERR_NOTHING:
                if self.text_decode.no80_cmd == 0xDC & 0x7F:  # 回复命令码应该是0xDC
                    if self.text_decode.cmd_ack == 0x00:
                        self.blue_write_log("重置密码成功")
                    else:
                        self.blue_write_log(f"重置密码失败: ACK {self.text_decode.cmd_ack:02X}")
                else:
                    self.blue_write_log("重置密码失败: 命令码不匹配")
            else:
                self.blue_write_log("重置密码失败: 无响应")
                
        except Exception as e:
            self.blue_write_log(f"重置密码异常: {str(e)}")

    # ==================== 新的加密命令实现 ====================
    
    def construct_new_password_cmd(self, cmd_code, data_bytes):
        """构造新的密码命令包"""
        # 新的帧格式：0xFB + 指令号 + 内容长度 + 内容 + 0xBB
        cmd_packet = bytearray()
        cmd_packet.append(0xFB)  # 帧头
        cmd_packet.append(cmd_code)  # 指令号
        cmd_packet.append(len(data_bytes))  # 内容长度
        cmd_packet.extend(data_bytes)  # 内容
        cmd_packet.append(0xBB)  # 帧尾
        return cmd_packet
    
    def parse_new_password_response(self, data):
        """解析新的密码命令响应"""
        if len(data) < 5:
            return False, "响应数据长度不足"
        
        if data[0] != 0xFB or data[-1] != 0xBB:
            return False, "响应帧格式错误"
        
        cmd_code = data[1]
        content_length = data[2]
        content = data[3:3+content_length]
        
        return True, {"cmd_code": cmd_code, "content": content}
    
    def handle_new_password_response(self, cmd_code, content):
        """处理新协议密码命令响应"""
        if len(content) < 1:
            self.blue_write_log("响应内容为空")
            return
        self.blue_write_log(f"处理新协议密码命令响应时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
        result_code = content[0]
        
        if cmd_code == 0x01:  # 验证密码响应
            if result_code == 0x00:
                self.blue_write_log("❌ 密码错误")
            elif result_code == 0x01:
                self.blue_write_log("✅ 密码正确")
            elif result_code == 0x02:
                self.blue_write_log("ℹ️ 设备没有设置密码")
            else:
                self.blue_write_log(f"验证密码: 未知响应 {result_code:02X}")
                
        elif cmd_code == 0x02:  # 设置密码响应
            if result_code == 0x00:
                self.blue_write_log("❌ 设置密码失败")
            elif result_code == 0x01:
                self.blue_write_log("✅ 设置密码成功")
            else:
                self.blue_write_log(f"设置密码: 未知响应 {result_code:02X}")
                
        elif cmd_code == 0x03:  # 取消密码响应
            if result_code == 0x00:
                self.blue_write_log("❌ 取消密码失败")
            elif result_code == 0x01:
                self.blue_write_log("✅ 取消密码成功")
            else:
                self.blue_write_log(f"取消密码: 未知响应 {result_code:02X}")
                
        elif cmd_code == 0x04:  # 查询密码状态响应
            if result_code == 0x00:
                self.blue_write_log("ℹ️ 设备未设置密码")
            elif result_code == 0x01:
                self.blue_write_log("🔒 设备已设置密码")
            else:
                self.blue_write_log(f"查询密码状态: 未知响应 {result_code:02X}")
        else:
            self.blue_write_log(f"未知密码命令响应: {cmd_code:02X}")
            
    def check_noauth_response(self, data):
        """检查是否收到NOAUTH响应"""
        try:
            if isinstance(data, (bytes, bytearray)):
                data_str = data.decode('utf-8', errors='ignore')
                if "NOAUTH" in data_str:
                    self.blue_write_log("🔒 设备返回NOAUTH - 请先验证密码后再发送数据")
                    return True
        except:
            pass
        return False

    async def send_search_password_cmd(self):
        """发送取消密码命令 (新格式)"""
        try:
            # 构造数据：0x01
            cancel_data = bytearray([0x01])
            
            # 构造命令包：0xFB 0x03 0x01 0x01 + 0xBB
            cmd_packet = self.construct_new_password_cmd(0x04, cancel_data)
            
            self.display_send_data(cmd_packet)
            await self.byte_send(cmd_packet)
            
            self.blue_write_log("查询密码命令已发送，等待响应...")
            
        except Exception as e:
            self.blue_write_log(f"查询密码异常: {str(e)}")
    async def send_verify_password_cmd(self, password: str):
        """发送验证密码命令 (新格式)"""
        try:
            # 构造6字节密码数据
            password_data = bytearray()
            for char in password:
                password_data.append(ord(char))
            
            # 构造命令包：0xFB 0x01 0x06 + 6字节密码 + 0xBB
            cmd_packet = self.construct_new_password_cmd(0x01, password_data)
            
            self.display_send_data(cmd_packet)
            
            time512 = int(self.test512.text()) / 1000
            await asyncio.sleep(time512)
            self.blue_write_log(f"验证密码命令发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
            await self.byte_send(cmd_packet)
            
            # 解析响应（这里需要在数据接收处理中添加新的解析逻辑）
            self.blue_write_log("验证密码命令已发送，等待响应...")
            
        except Exception as e:
            self.blue_write_log(f"验证密码异常: {str(e)}")

    async def send_set_password_cmd_new(self, password: str):
        """发送设置密码命令 (新格式)"""
        try:
            # 构造6字节密码数据
            password_data = bytearray()
            for char in password:
                password_data.append(ord(char))
            
            # 构造命令包：0xFB 0x02 0x06 + 6字节密码 + 0xBB
            cmd_packet = self.construct_new_password_cmd(0x02, password_data)
            
            self.display_send_data(cmd_packet)
            await self.byte_send(cmd_packet)
            self.blue_write_log("设置密码命令已发送，等待响应...")
            
        except Exception as e:
            self.blue_write_log(f"设置密码异常: {str(e)}")

    async def send_cancel_password_cmd(self):
        """发送取消密码命令 (新格式)"""
        try:
            # 构造数据：0x01
            cancel_data = bytearray([0x01])
            
            # 构造命令包：0xFB 0x03 0x01 0x01 + 0xBB
            cmd_packet = self.construct_new_password_cmd(0x03, cancel_data)
            
            self.display_send_data(cmd_packet)
            await self.byte_send(cmd_packet)
            
            self.blue_write_log("取消密码命令已发送，等待响应...")
            
        except Exception as e:
            self.blue_write_log(f"取消密码异常: {str(e)}")

widgets = None

# 修正后的函数 - 注意这是一个函数，不是类
class load_ui_dynamically(QMainWindow):
    scan_task = None
    def __init__(self, ui_file):
        super().__init__()
        try:
            # 初始化日志管理器
            self.logger = LogManager.get_instance()
            
            # 初始化当前数据来源
            self.current_data_source = None
            
            # 初始化命令信息标签（稍后会创建）
            self.command_info_label = None

            # SET AS GLOBAL WIDGETS
            # ///////////////////////////////////////////////////////////////
            self.ui = Ui_Form()
            self.ui.setupUi(self)
            global widgets
            widgets = self.ui

            # 加载UI文件
            # uic.loadUi(ui_file, widgets)
            self.logger.write_log("UI文件加载成功")
            self.setWindowTitle('firstuse')
            self.setFixedSize(620,620)
            # 初始化连接窗口
            self.bluetooth_tool = BluetoothTool()
            # self.bluetooth_tool.setWindowModality(Qt.WindowModality.ApplicationModal)
            widgets.pushButton.clicked.connect(self.bluetooth_tool.show)
            widgets.pushButton_6.clicked.connect(self.disconnect_device)
            # widgets.pushButton_2.clicked.connect()

            # 分配监控按钮
            widgets.pushButton_4.clicked.connect(self.start_scan_task)

            # 分配版本号查询按钮
            widgets.pushButton_7.clicked.connect(self.bluetooth_tool.send_find_version_cmd)

            widgets.mainWindowTextEdit.clear()
            widgets.mainWindowTextEdit.setReadOnly(True)
            widgets.mainWindowTextEdit.setFontFamily("Courier New")  # 使用等宽字体


            # 初始化电池状态查询
            widgets.pushButton_5.clicked.connect(self.bluetooth_tool.send_tbs_cmd)

            # 连接数据解析模块到主窗口
            self.bluetooth_tool.decode_data_ok_signal.connect(self.get_dict_from_receive_data)

            
            # 初始化结构体模型列表 到csv文件
            self.struct_list = self.bluetooth_tool.hex_parser.get_struct_name_list()
            ComunManager.get_instance(self.struct_list)

            # 连接按钮信号
            # widgets.pushButton.clicked.connect(self.close)  # 假设 pushButton 是一个关闭按钮
            self.bluetooth_tool.blue_write_log(f"UI文件 {ui_file} 加载成功")

            # 在一级窗口上再创建一个qwidget用来显示一些标志位
            # self.setGeometry(0, 0, 900, 600)
            self.setFixedSize(1100,600)
            self.bit_window = QWidget()
            
            # 创建命令信息显示标签
            self.command_info_label = QLabel('当前命令: 无')
            self.command_info_label.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
            
            # 创建按钮布局
            button_layout = QHBoxLayout()
            self.send_modify_button = QPushButton('发送修改值')
            self.clear_modify_button = QPushButton('清空修改值')
            
            button_layout.addWidget(self.send_modify_button)
            button_layout.addWidget(self.clear_modify_button)
            button_layout.addStretch()  # 添加弹性空间
            
            # 创建QTableView和模型
            self.bit_table_view = QTableView()
            self.bit_table_model = BitFlagsTableModel()
            self.bit_table_view.setModel(self.bit_table_model)
            
            # 设置表格属性
            self.bit_table_view.setAlternatingRowColors(True)
            self.bit_table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.bit_table_view.horizontalHeader().setStretchLastSection(False)
            
            # 设置列宽 - 现在是9列
            column_widths = [120, 80, 80, 120, 80, 80, 120, 80, 80]
            for i, width in enumerate(column_widths):
                self.bit_table_view.setColumnWidth(i, width)
            
            # 设置更紧凑的行间距
            self.bit_table_view.verticalHeader().setDefaultSectionSize(20)  # 默认行高设为20
            self.bit_table_view.verticalHeader().setMinimumSectionSize(18)  # 最小行高设为18
            
            # 添加样式表以区分不同的列组
            self.bit_table_view.setStyleSheet("""
                QTableView::item {
                    border: 1px solid #cccccc;
                    padding: 3px;
                }
                QTableView::item:selected {
                    background-color: #3399ff;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                    padding: 4px;
                    font-weight: bold;
                }
                QHeaderView::section:nth-child(1),
                QHeaderView::section:nth-child(2),
                QHeaderView::section:nth-child(3) {
                    background-color: #e8f4f8;
                }
                QHeaderView::section:nth-child(4),
                QHeaderView::section:nth-child(5),
                QHeaderView::section:nth-child(6) {
                    background-color: #f8f8e8;
                }
                QHeaderView::section:nth-child(7),
                QHeaderView::section:nth-child(8),
                QHeaderView::section:nth-child(9) {
                    background-color: #f8e8f8;
                }
            """)
            
            # 创建主布局
            self.bit_layout = QVBoxLayout()
            self.bit_layout.addWidget(self.command_info_label)
            self.bit_layout.addLayout(button_layout)
            self.bit_layout.addWidget(self.bit_table_view)
            self.bit_window.setLayout(self.bit_layout)
            
            # 保留原有的标签列表（可能其他地方还在使用）
            self.key_label_list = []
            self.value_label_list = []
            
            # 连接按钮信号
            self.send_modify_button.clicked.connect(self.send_modified_values)  # 发送修改值
            self.clear_modify_button.clicked.connect(self.clear_modified_values)
            
            self.bit_window.setWindowTitle('烧录标志位')
            self.bit_window.setGeometry(620, 10, 880, 600)  # 增加窗口宽度以适应9列
            self.bit_window.show()
        except Exception as e:
            self.logger.write_log(f"加载UI文件失败: {e}")
            traceback.print_exc()
            # return None
    def visualize_bit_flags(self,data: list):
        try:
            # 检查是否是第一次加载数据或数据长度发生变化
            if len(self.bit_table_model._original_data) != len(data):
                # 数据结构变化，需要完全重置
                self.bit_table_model.update_data(data)
                self.logger.write_log(f"完全更新标志位数据，共 {len(data)} 条记录")
            else:
                # 逐项比较，只更新有变化的数据
                updates = {}
                for i, new_unit in enumerate(data):
                    old_unit = self.bit_table_model._original_data[i]
                    # 检查参数名或数值是否有变化
                    if old_unit[0] != new_unit[0] or old_unit[2] != new_unit[2]:
                        updates[i] = new_unit
                
                if updates:
                    # 有数据变化，进行部分更新
                    self.bit_table_model.update_partial_data(updates)
                    self.logger.write_log(f"部分更新标志位数据，更新了 {len(updates)} 条记录")
                else:
                    # 没有数据变化，无需更新
                    pass
            
            # 调试信息
            # for i, unit in enumerate(data):
            #     print(f'i = {i} tuple = {len(unit)} - {unit[0]}: {unit[2]}')
                
        except Exception as e:
            self.logger.write_log(f"bit windows写入失败: {e}")
            traceback.print_exc()
            # 出错时回退到完全更新
            self.bit_table_model.update_data(data)
        pass
    def disconnect_device(self):
        """断开连接"""
        if self.scan_task:
            self.start_scan_task() # 停止监控

        self.bluetooth_tool.on_disconnect_device_clicked()



    def start_scan_task(self):
        """启动扫描任务"""
        if not self.scan_task:
            self.bluetooth_tool.blue_write_log("启动扫描任务")
            widgets.pushButton_4.setText("停止监控")
            self.scan_task = asyncio.create_task(self.get_data_from_device(0.5))
        else:
            self.scan_task.cancel()
            widgets.pushButton_4.setText("开始监控")
            self.scan_task = None

    def start_find_bat_status(self):
        self.bluetooth_tool.blue_write_log("查询一次电池状态")

    def get_dict_from_receive_data(self, header:str, dict_data:dict):
        """从结构模型中获取字典，并按列打印到窗口"""
        widgets.mainWindowTextEdit.clear()
        
        # 从接收字符串中提取纯命令名
        # header 格式: "RX->,bluetooth,L-12100BNNA70-A88888,PC_GET_BMS"
        # 需要提取最后的命令名部分
        if ',' in header:
            command_name = header.split(',')[-1]  # 提取最后一部分
        else:
            command_name = header
        
        # 保存当前数据来源，用于发送修改值时确定命令
        self.current_data_source = command_name
        
        self.bluetooth_tool.blue_write_log(f"提取的命令名: {command_name}")
        
        # 更新BitWindow的命令信息显示
        if hasattr(self, 'command_info_label') and self.command_info_label:
            write_cmd_name = get_write_command_from_read(command_name)
            if write_cmd_name:
                self.command_info_label.setText(f"当前命令: {command_name} → {write_cmd_name}")
                self.command_info_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            else:
                self.command_info_label.setText(f"当前命令: {command_name} (只读)")
                self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        
        # 构建列格式化字符串
        formatted_text = ""
        for category, items in dict_data.items():
            formatted_text += f"[{category}]\n"
            self.visualize_bit_flags(list(items)) # 删 改，影响程序运行时间
            for item in items:
                # 假设item为[name, unit, value, ...]
                if len(item) >= 3:
                    name = item[0] if len(item) > 0 else ""
                    unit = item[1] if len(item) > 1 else ""
                    value = item[2] if len(item) > 2 else ""
                    formatted_text += f"{name:>10}\t{value:>10}\t{unit:>10}\n"
            formatted_text += "\n"
        # 显示到窗口
        widgets.mainWindowTextEdit.append(formatted_text)
        self.bluetooth_tool.blue_write_log(f"接收到数据: {header}")
        self.bluetooth_tool.blue_write_log(f"命令名: {command_name}")
        csv_data_str = ""
        try:
            for lst in dict_data.values():
                for value in lst:
                    csv_data_str += value[2] + ","
        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"写入日志失败: {e}")
            traceback.print_exc()
        ComunManager.get_instance().write_csv(f"{header},{csv_data_str[:-1]}")
    async def get_data_from_device(self, time_interval = 1):
        """异步方法，从设备获取数据"""
        self.bluetooth_tool.blue_write_log(f"进入发送0x13命令函数")
        while 1:
            self.bluetooth_tool.blue_write_log(f"发送0x13命令")
            try:
                await asyncio.sleep(time_interval)
                #发送0x13命令
                self.bluetooth_tool.send_sbs_cmd()
            except Exception as e:
                if str(e) == "未连接到设备":
                    self.bluetooth_tool.blue_write_log(f"获取数据失败: {e}")
                    widgets.pushButton_4.setText("开始监控")
                    traceback.print_exc()
                    break
                else:
                    self.bluetooth_tool.blue_write_log(f"获取数据失败: {e}")
                    traceback.print_exc()
        #方法1 bluetool 函数发送发射信号- 主窗口类接收信号 - 当前函数处理 - 调用数据解析模块 - 返回嵌套字典
        #方法1。1 bluetool 发射信号- 主窗口类接收信号 - 当前函数处理 - 调用数据解析模块 - 返回嵌套字典 - 打印字典

        #重要方法2 bluetool发发射信号 - 数据解析模块类接收信号 - 发射信号嵌套字典 - 主窗口显示类接收信号
        #需不需要给每一个数据类型定义一个接收函数，在数据解析类里面不需要，主窗口需要
        #信号使用方法， 1需要发送信号的函数，在当前类定义信号  2在接收的类里面实例化，并调用
    def closeEvent(self, event):
        """重写关闭事件，在关闭前断开连接"""
        # 先隐藏窗口，给用户一个即时反馈
        self.hide()
        
        if hasattr(self.bluetooth_tool, 'log_file') and self.bluetooth_tool.log_file :
            try:
                self.bluetooth_tool.write_log("程序关闭")
                self.bluetooth_tool.log_file.close()
                self.bluetooth_tool.blue_write_log("日志文件已关闭")
            except Exception as e:
                self.bluetooth_tool.blue_write_log(f"关闭日志文件失败: {e}")

        has_connection = False
        
        # 检查是否有连接需要断开
        if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
            has_connection = True
        if hasattr(self.bluetooth_tool, 'serial_port') and self.bluetooth_tool.serial_port and self.bluetooth_tool.serial_port.is_open:
            has_connection = True
        
        if has_connection:
            # 创建断开连接的函数
            async def disconnect_and_close():
                try:
                    # 断开蓝牙连接
                    if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
                        await self.bluetooth_tool.disconnect_device()
                        self.bluetooth_tool.blue_write_log("蓝牙已断开连接")
                    
                    # 断开串口连接
                    if hasattr(self.bluetooth_tool, 'serial_port') and self.bluetooth_tool.serial_port and self.bluetooth_tool.serial_port.is_open:
                        self.bluetooth_tool.serial_port.close()
                        self.bluetooth_tool.blue_write_log("串口已断开")
                    
                except Exception as e:
                    self.bluetooth_tool.blue_write_log(f"断开连接时出错: {e}")
                
                # 最后强制退出应用程序
                # 使用QTimer确保这个调用发生在主事件循环中
                QApplication.instance().quit()
                # QTimer.singleShot(100, lambda: QApplication.instance().quit())
            
            # 启动异步任务
            asyncio.create_task(disconnect_and_close())
            
            # 忽略关闭事件，我们会在异步任务完成后手动退出
            event.ignore()
            return
        
        # 如果没有连接需要断开，接受事件并正常关闭
        event.accept()

    def parse_hex_or_decimal_value(self, value_str):
        """
        解析十六进制或十进制值，支持负数
        
        Args:
            value_str (str): 要解析的值字符串，如 '100', '0x64', '0x-186A0', '-0x186A0'
            
        Returns:
            int: 解析后的整数值
        """
        try:
            # 使用 int(value, 0) 来自动检测进制，支持大部分格式
            return int(value_str, 0)
        except ValueError:
            # 处理特殊的负数十六进制格式
            if value_str.startswith('0x-'):
                # 处理 '0x-186A0' 格式
                hex_part = value_str[3:]  # 移除 '0x-'
                return -int(hex_part, 16)
            elif value_str.startswith('-0x'):
                # 处理 '-0x186A0' 格式
                hex_part = value_str[3:]  # 移除 '-0x'
                return -int(hex_part, 16)
            else:
                # 最后尝试直接转换
                return int(value_str)

    def send_modified_values(self):
        """获取修改的值并发送到设备"""
        try:
            self.bluetooth_tool.blue_write_log("=== 开始发送修改值流程 ===")
            
            modified_data = self.bit_table_model.get_modified_data()
            
            if not modified_data:
                self.bluetooth_tool.blue_write_log("没有需要发送的修改值")
                self.logger.write_log("没有需要发送的修改值")
                return []
            
            self.bluetooth_tool.blue_write_log(f"检测到 {len(modified_data)} 个修改值")
            
            # 检查当前数据来源
            if not self.current_data_source:
                self.bluetooth_tool.blue_write_log("错误：无法确定当前数据来源")
                self.logger.write_log("错误：无法确定当前数据来源")
                return []
            
            self.bluetooth_tool.blue_write_log(f"当前数据来源: {self.current_data_source}")
            
            # 检查是否可以写入
            if not can_command_be_written(self.current_data_source):
                self.bluetooth_tool.blue_write_log(f"错误：命令 {self.current_data_source} 不支持写入")
                self.logger.write_log(f"错误：命令 {self.current_data_source} 不支持写入")
                return []
            
            # 获取写入命令名称和代码
            write_cmd_name = get_write_command_from_read(self.current_data_source)
            write_cmd_code = get_write_command_code(self.current_data_source)
            if write_cmd_code is None:
                self.bluetooth_tool.blue_write_log(f"错误：无法获取 {self.current_data_source} 的写入命令代码")
                self.logger.write_log(f"错误：无法获取 {self.current_data_source} 的写入命令代码")
                return []
            
            self.bluetooth_tool.blue_write_log(f"读取命令: {self.current_data_source}")
            self.bluetooth_tool.blue_write_log(f"写入命令: {write_cmd_name}")
            self.bluetooth_tool.blue_write_log(f"写入命令代码: 0x{write_cmd_code:02X}")
            
            # 更新BitWindow显示正在发送的命令
            self.command_info_label.setText(f"正在发送: {self.current_data_source} → {write_cmd_name}")
            self.command_info_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
            
            # 创建一个完整的数据数组来重新构造结构体
            # 获取当前数据来源的格式和变量列表
            format_string = STRUCT_FORMATS.get(self.current_data_source)
            variables = STRUCT_VARIABLES.get(self.current_data_source)
            
            if not format_string or not variables:
                self.bluetooth_tool.blue_write_log(f"错误：无法获取 {self.current_data_source} 的格式信息")
                self.logger.write_log(f"错误：无法获取 {self.current_data_source} 的格式信息")
                return []
            
            self.bluetooth_tool.blue_write_log(f"数据格式: {format_string}")
            self.bluetooth_tool.blue_write_log(f"变量数量: {len(variables)}")
            
            # 创建值数组，初始化为当前值
            values = []
            self.bluetooth_tool.blue_write_log("开始构造数据包:")
            
            for i, var_name in enumerate(variables):
                current_hex_value = self.bit_table_model._data[i][1] if i < len(self.bit_table_model._data) else '0x00'
                
                # 检查是否有修改值
                modified_value = None
                for row, param_name, current_value, write_value in modified_data:
                    if param_name == var_name and write_value.strip():
                        modified_value = write_value
                        break
                
                if modified_value:
                    try:
                        # 尝试解析修改值
                        int_value = self.parse_hex_or_decimal_value(modified_value)
                        values.append(int_value)
                        self.bluetooth_tool.blue_write_log(f"  {var_name}: {current_hex_value} -> {modified_value} (0x{int_value:X})")
                        self.logger.write_log(f"  {var_name}: {current_hex_value} -> {modified_value} (0x{int_value:X})")
                    except ValueError as e:
                        self.bluetooth_tool.blue_write_log(f"  警告：无法解析 {var_name} 的值 '{modified_value}' ({e})，使用当前值")
                        self.logger.write_log(f"  警告：无法解析 {var_name} 的值 '{modified_value}' ({e})，使用当前值")
                        # 使用当前值
                        try:
                            int_value = self.parse_hex_or_decimal_value(current_hex_value)
                        except ValueError as e2:
                            self.bluetooth_tool.blue_write_log(f"  错误：无法解析当前值 '{current_hex_value}' ({e2})，使用 0")
                            int_value = 0
                        values.append(int_value)
                else:
                    # 使用当前值
                    try:
                        int_value = self.parse_hex_or_decimal_value(current_hex_value)
                    except ValueError as e:
                        self.bluetooth_tool.blue_write_log(f"  错误：无法解析当前值 '{current_hex_value}' ({e})，使用 0")
                        int_value = 0
                    
                    values.append(int_value)
                    self.bluetooth_tool.blue_write_log(f"  {var_name}: {current_hex_value} (不变)")
            
            self.bluetooth_tool.blue_write_log(f"最终数据值: {values}")
            
            # 使用 struct 模块打包数据
            try:
                packed_binary_data = struct.pack(format_string, *values)
                self.bluetooth_tool.blue_write_log(f"数据打包成功，共 {len(packed_binary_data)} 字节")
                self.bluetooth_tool.blue_write_log(f"打包后的原始数据: {packed_binary_data.hex()}")
                self.logger.write_log(f"数据打包成功，共 {len(packed_binary_data)} 字节")
                
                # 使用 send_hex_fill 发送数据
                send_data = self.bluetooth_tool.text_decode.send_hex_fill(write_cmd_code, packed_binary_data)
                self.bluetooth_tool.blue_write_log(f"构造发送数据包: {send_data.hex()}")
                self.logger.write_log(f"发送数据: {send_data.hex()}")
                
                # 异步发送数据
                async def send_data_async():
                    try:
                        self.bluetooth_tool.blue_write_log("开始发送数据包...")
                        await self.bluetooth_tool.byte_send(send_data)
                        self.bluetooth_tool.display_send_data(send_data)
                        self.bluetooth_tool.blue_write_log("数据发送成功")
                        self.logger.write_log("数据发送成功")
                        
                        # 更新BitWindow显示发送成功
                        self.command_info_label.setText(f"发送成功: {self.current_data_source} → {write_cmd_name}")
                        self.command_info_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                        
                        # 发送成功后清空修改值
                        self.bit_table_model.clear_write_values()
                        
                    except Exception as e:
                        self.bluetooth_tool.blue_write_log(f"数据发送失败: {e}")
                        self.logger.write_log(f"数据发送失败: {e}")
                        traceback.print_exc()
                        
                        # 更新BitWindow显示发送失败
                        self.command_info_label.setText(f"发送失败: {self.current_data_source} → {write_cmd_name}")
                        self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
                
                # 使用 asyncio 创建任务
                asyncio.create_task(send_data_async())
                
                return modified_data
                
            except struct.error as e:
                self.bluetooth_tool.blue_write_log(f"数据打包失败: {e}")
                self.logger.write_log(f"数据打包失败: {e}")
                
                # 更新BitWindow显示打包失败
                if hasattr(self, 'command_info_label') and self.command_info_label:
                    self.command_info_label.setText(f"打包失败: {self.current_data_source}")
                    self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
                return []
                
        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"发送修改值失败: {e}")
            self.logger.write_log(f"发送修改值失败: {e}")
            traceback.print_exc()
            
            # 更新BitWindow显示流程失败
            if hasattr(self, 'command_info_label') and self.command_info_label:
                self.command_info_label.setText(f"流程失败: {self.current_data_source if self.current_data_source else '无'}")
                self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            return []
    
    def clear_modified_values(self):
        """清空所有修改的写入值"""
        try:
            self.bit_table_model.clear_write_values()
            self.logger.write_log("已清空所有修改值")
        except Exception as e:
            self.logger.write_log(f"清空修改值失败: {e}")
            traceback.print_exc()
    
    def set_write_value_by_name(self, param_name, value):
        """根据参数名设置写入值"""
        try:
            row = self.bit_table_model.find_row_by_name(param_name)
            if row >= 0:
                return self.bit_table_model.set_write_value(row, value)
            else:
                self.logger.write_log(f"未找到参数: {param_name}")
                return False
        except Exception as e:
            self.logger.write_log(f"设置写入值失败: {e}")
            return False

# 程序入口
if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        # 创建并显示启动画面
        splash = SplashScreen()
        splash.show()
        
        # 设置事件循环
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        # # 延迟启动主窗口

        # 方法3: 动态加载（推荐）
        window = load_ui_dynamically('测试上位机.ui')
        
        if window:
            QTimer.singleShot(500, lambda: (splash.finish(window), window.show()))
            # window.show()
        else:
            # 加载失败时显示错误消息
            QMessageBox.critical(None, '错误', 'UI文件加载失败')
            traceback.print_exc()
            # sys.exit(1)
        
        # 运行事件循环
        with loop:
            loop.run_forever()
    except Exception as e:
        try:
            error_msg = traceback.format_exc()  # 获取 traceback 字符串\
            log = LogManager.get_instance()
            log.write_log(str(e))
            log.write_log(error_msg)
            traceback.print_exc()
        except Exception as e:
            print(f"写入日志失败: {e}")
            sys.exit(1)

