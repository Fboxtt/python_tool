import sys
import asyncio
import traceback
import time
import json
from datetime import datetime
import os
import random
from enum import Enum
from typing import Optional, Callable

from PyQt6.QtCore import QTimer  # 导入 QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QMessageBox, QTextEdit, QLineEdit, QHBoxLayout,
    QCheckBox, QFileDialog, QComboBox, QGridLayout, QMainWindow, QSplashScreen, QSizePolicy, QTableView, QHeaderView, QAbstractItemView,
    QStyledItemDelegate, QStyle, QDoubleSpinBox, QTabWidget, QGroupBox
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
from struct_model import (
    HexParserApp, get_write_command_code, can_command_be_written,
    STRUCT_FORMATS, STRUCT_VARIABLES, get_write_command_from_read,
    get_all_status_bits_for_display, parse_all_status_from_sbs
)
import struct

from ui_main import Ui_Form
from data_display_manager import DataDisplayManager  # ⭐ 导入数据显示管理器


# ═══════════════════════════════════════════════════════════════════════════
# 连接管理架构 - 枚举和类定义
# ═══════════════════════════════════════════════════════════════════════════

class ConnectionType(Enum):
    """连接类型枚举"""
    NONE = "none"
    BLUETOOTH = "bluetooth"
    SERIAL = "serial"


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"  # 断开
    CONNECTING = "connecting"      # 正在连接
    CONNECTED = "connected"        # 已连接


class ConnectionManager:
    """连接管理器 - 统一管理蓝牙和串口连接状态
    
    职责:
    - 跟踪当前连接类型和状态
    - 提供统一的状态查询接口
    - 管理连接锁，防止并发连接
    """
    
    def __init__(self):
        self.bluetooth_state = ConnectionState.DISCONNECTED
        self.serial_state = ConnectionState.DISCONNECTED
        self.is_connecting = False  # 全局连接锁
        
    def get_bluetooth_state(self) -> ConnectionState:
        """获取蓝牙连接状态"""
        return self.bluetooth_state
    
    def set_bluetooth_state(self, state: ConnectionState):
        """设置蓝牙连接状态"""
        self.bluetooth_state = state
        
    def get_serial_state(self) -> ConnectionState:
        """获取串口连接状态"""
        return self.serial_state
    
    def set_serial_state(self, state: ConnectionState):
        """设置串口连接状态"""
        self.serial_state = state
    
    def is_bluetooth_connected(self) -> bool:
        """检查蓝牙是否已连接"""
        return self.bluetooth_state == ConnectionState.CONNECTED
    
    def is_serial_connected(self) -> bool:
        """检查串口是否已连接"""
        return self.serial_state == ConnectionState.CONNECTED
    
    def is_any_connected(self) -> bool:
        """检查是否有任何连接（蓝牙或串口）"""
        return self.is_bluetooth_connected() or self.is_serial_connected()
    
    def acquire_connection_lock(self) -> bool:
        """尝试获取连接锁
        
        Returns:
            bool: True=成功获取，False=已被占用
        """
        if self.is_connecting:
            return False
        self.is_connecting = True
        return True
    
    def release_connection_lock(self):
        """释放连接锁"""
        self.is_connecting = False
    
    def reset(self):
        """重置所有状态"""
        self.bluetooth_state = ConnectionState.DISCONNECTED
        self.serial_state = ConnectionState.DISCONNECTED
        self.release_connection_lock()
# ============== 重复的类定义已移除 ==============
# 以下类已移至 display_widgets.py：
# - BatteryTableModel (电池参数表格模型)
# - BitFlagsTableModel (位标志表格模型)
# - StatusBitsDelegate (状态位委托)
# - BitFlagsWidget (位标志显示组件)
# 请通过 data_display_manager 使用这些组件


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
    def __init__(self):
        super().__init__()
        # ==================== 连接管理 ====================
        self.connection_manager = ConnectionManager()  # 统一连接管理器
        
        # 蓝牙相关
        self.client = None  # 当前连接的蓝牙设备
        self.device_name = None
        self.device_address = None  # 当前连接的设备MAC地址
        self.device_name_to_address = {}  # 设备名到地址的映射
        
        # 串口相关
        self.serial_port = None  # 串口对象
        self.is_serial_connected = False
        self.serial_receive_task = None #串口接收任务对象
        
        # 通信类型（兼容旧代码）
        self.commu_type = None
        
        # 其他任务
        self.program_task = None #烧录任务对象
        self.task_flag = False
        
        # 初始化UI
        self.initUI()
        
        # 初始化业务模块
        self.hex_model = HexFileModel()
        self.text_decode = TextDecode()
        self.download_data = OtaController()
        self.hex_parser = HexParserApp()
        
        # 初始化定时器
        self.data_timer = QTimer()
        self.data_timer.setSingleShot(True) #单次定时器可能会影响实际数据接收数量上限
        self.data_timer.timeout.connect(self.process_complete_data)

        # 用于存储接收到的数据
        self.received_data_buffer = bytearray()
        # 注册响应标志（用于 send_register_cmd 检测）
        self.register_response = None  # None=未收到, True=成功, False=失败
        # 烧录计数
        self.ota_start_count = 0
        self.ota_ok_count = 0
        self.batch_task = None
        # 响应状态标志（用于test_send_data等功能，基于信号机制）
        self.last_response_status = None  # None=未收到, True=已收到
        self.last_response_ack = None  # 响应的ACK码

        # 连接receive_ok_signal到内部槽函数
        self.receive_ok_signal.connect(self._on_receive_response)

        # 自动连接相关
        self.auto_connect_enabled = False
        self.auto_connect_device_name = ""
        self.auto_connect_mac_address = ""
        self.is_auto_reconnecting = False  # 防止重连循环
        self.is_auto_scanning = False  # 自动扫描标志
        
        # 自动连接定时器（定期尝试连接）
        self.auto_connect_timer = QTimer()
        self.auto_connect_timer.timeout.connect(self.on_auto_connect_timer)
        self.auto_connect_retry_interval = 5000  # 5秒尝试一次
        
        # 加载自动连接配置
        self.load_auto_connect_config()

        # 检测当前配置并设置checkbox状态（不触发信号）
        self.detect_and_set_cell_config()
    def initUI(self):
        self.setWindowTitle('firstuse - 蓝牙调试工具')

        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 创建左侧TabWidget（连接和控制）
        left_tabs = QTabWidget()
        left_tabs.setMaximumWidth(450)  # 限制左侧宽度
        
        # ==================== Tab 1: 连接设置 ====================
        connection_tab = QWidget()
        connection_layout = QVBoxLayout(connection_tab)
        connection_layout.setSpacing(3)
        connection_layout.setContentsMargins(5, 5, 5, 5)
        
        # 自动连接配置（紧凑）
        auto_group = self._create_compact_group("自动连接")
        auto_layout = QVBoxLayout()
        auto_layout.setSpacing(2)
        
        self.auto_connect_checkbox = QCheckBox('启用')
        self.auto_connect_checkbox.setStyleSheet("font-size: 10px;")
        self.auto_connect_checkbox.stateChanged.connect(self.on_auto_connect_changed)
        auto_layout.addWidget(self.auto_connect_checkbox)
        
        # 设备名称和MAC地址合并为一行
        device_row1 = QHBoxLayout()
        device_row1.addWidget(QLabel('名称:'))
        self.auto_connect_name_input = QLineEdit()
        self.auto_connect_name_input.setPlaceholderText('设备名称')
        self.auto_connect_name_input.setStyleSheet("font-size: 10px;")
        self.auto_connect_name_input.textChanged.connect(self.on_auto_connect_config_changed)
        device_row1.addWidget(self.auto_connect_name_input)
        auto_layout.addLayout(device_row1)
        
        device_row2 = QHBoxLayout()
        device_row2.addWidget(QLabel('MAC:'))
        self.auto_connect_mac_input = QLineEdit()
        self.auto_connect_mac_input.setPlaceholderText('MAC地址(可选)')
        self.auto_connect_mac_input.setStyleSheet("font-size: 10px;")
        self.auto_connect_mac_input.textChanged.connect(self.on_auto_connect_config_changed)
        device_row2.addWidget(self.auto_connect_mac_input)
        auto_layout.addLayout(device_row2)
        
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel('间隔:'))
        self.auto_connect_interval_spinbox = QDoubleSpinBox()
        self.auto_connect_interval_spinbox.setMinimum(1.0)
        self.auto_connect_interval_spinbox.setMaximum(60.0)
        self.auto_connect_interval_spinbox.setValue(5.0)
        self.auto_connect_interval_spinbox.setDecimals(0)
        self.auto_connect_interval_spinbox.setStyleSheet("font-size: 10px;")
        self.auto_connect_interval_spinbox.setFixedWidth(60)
        self.auto_connect_interval_spinbox.valueChanged.connect(self.on_retry_interval_changed)
        interval_row.addWidget(self.auto_connect_interval_spinbox)
        interval_row.addWidget(QLabel('秒'))
        interval_row.addStretch()
        auto_layout.addLayout(interval_row)
        
        auto_group.setLayout(auto_layout)
        connection_layout.addWidget(auto_group)
        
        # 蓝牙连接（紧凑）
        bt_group = self._create_compact_group("蓝牙连接")
        bt_layout = QVBoxLayout()
        bt_layout.setSpacing(3)
        
        self.label = QLabel('设备列表:')
        self.label.setStyleSheet("font-size: 10px;")
        bt_layout.addWidget(self.label)
        
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(100)
        self.device_list.setStyleSheet("font-size: 10px;")
        self.device_list.itemDoubleClicked.connect(self.on_device_double_clicked)
        bt_layout.addWidget(self.device_list)
        
        # 保存布局引用
        self.bluetooth_layout = bt_layout
        self.device_list_index = bt_layout.count() - 1
        
        # RSSI筛选
        rssi_row = QHBoxLayout()
        rssi_row.addWidget(QLabel('RSSI >'))
        self.rssi_threshold_input = QLineEdit()
        self.rssi_threshold_input.setText("-100")
        self.rssi_threshold_input.setFixedWidth(50)
        self.rssi_threshold_input.setStyleSheet("font-size: 10px;")
        rssi_row.addWidget(self.rssi_threshold_input)
        rssi_row.addStretch()
        bt_layout.addLayout(rssi_row)
        self.rssi_threshold_layout = rssi_row
        
        # 连接/断开按钮（合并为一个按钮，文字切换）
        self.bt_connect_button = self._create_compact_button('连接', '#27ae60')
        self.bt_connect_button.clicked.connect(self.on_bt_connect_clicked)
        bt_layout.addWidget(self.bt_connect_button)

        # 扫描按钮
        self.scan_button = QPushButton('🔍 扫描并刷新')
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 4px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.scan_button.setFixedHeight(26)
        self.scan_button.clicked.connect(self.on_scan_all_clicked)
        bt_layout.addWidget(self.scan_button)

        # 状态标签
        self.bluetooth_status_label = QLabel()
        bt_layout.addWidget(self.bluetooth_status_label)
        
        bt_group.setLayout(bt_layout)
        connection_layout.addWidget(bt_group)
        
        # 串口连接（紧凑）
        serial_group = self._create_compact_group("串口连接")
        serial_layout = QGridLayout()
        serial_layout.setSpacing(2)
        
        self.port_combo = QComboBox()
        self.port_combo.setStyleSheet("font-size: 10px;")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(['9600', '13333', '18000', '18600', '19200', '38400', '57600', '115200'])
        self.baud_combo.setCurrentText('19200')
        self.baud_combo.setStyleSheet("font-size: 10px;")
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(['5', '6', '7', '8'])
        self.data_bits_combo.setCurrentText('8')
        self.data_bits_combo.setStyleSheet("font-size: 10px;")
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(['1', '1.5', '2'])
        self.stop_bits_combo.setCurrentText('1')
        self.stop_bits_combo.setStyleSheet("font-size: 10px;")
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(['无', '奇校验', '偶校验'])
        self.parity_combo.setStyleSheet("font-size: 10px;")
        
        serial_layout.addWidget(QLabel('串口:'), 0, 0)
        serial_layout.addWidget(self.port_combo, 0, 1)
        serial_layout.addWidget(QLabel('波特率:'), 1, 0)
        serial_layout.addWidget(self.baud_combo, 1, 1)
        serial_layout.addWidget(QLabel('数据位:'), 2, 0)
        serial_layout.addWidget(self.data_bits_combo, 2, 1)
        serial_layout.addWidget(QLabel('停止位:'), 3, 0)
        serial_layout.addWidget(self.stop_bits_combo, 3, 1)
        serial_layout.addWidget(QLabel('校验位:'), 4, 0)
        serial_layout.addWidget(self.parity_combo, 4, 1)
        
        self.serial_connect_button = self._create_compact_button('连接串口', '#3498db')
        self.serial_connect_button.clicked.connect(self.on_serial_connect_clicked)
        serial_layout.addWidget(self.serial_connect_button, 5, 0, 1, 2)
        
        # 监控间隔
        monitor_row = QHBoxLayout()
        monitor_row.addWidget(QLabel('监控间隔:'))
        self.monitor_interval_spinbox = QDoubleSpinBox()
        self.monitor_interval_spinbox.setMinimum(0.5)
        self.monitor_interval_spinbox.setMaximum(100.0)
        self.monitor_interval_spinbox.setValue(1.0)
        self.monitor_interval_spinbox.setDecimals(1)
        self.monitor_interval_spinbox.setFixedWidth(60)
        self.monitor_interval_spinbox.setStyleSheet("font-size: 10px;")
        monitor_row.addWidget(self.monitor_interval_spinbox)
        monitor_row.addWidget(QLabel('秒'))
        monitor_row.addStretch()
        serial_layout.addLayout(monitor_row, 6, 0, 1, 2)
        
        serial_group.setLayout(serial_layout)
        connection_layout.addWidget(serial_group)

        connection_layout.addStretch()
        left_tabs.addTab(connection_tab, "连接")
        
        # ==================== Tab 2: 设备控制 ====================
        control_tab = QWidget()
        control_layout = QVBoxLayout(control_tab)
        control_layout.setSpacing(3)
        control_layout.setContentsMargins(5, 5, 5, 5)
        
        # 充放电控制
        mos_group = self._create_compact_group("MOS控制")
        mos_layout = QGridLayout()
        mos_layout.setSpacing(2)
        
        self.open_charge_button = self._create_compact_button('充电开', '#27ae60')
        self.open_charge_button.clicked.connect(self.on_open_charge_clicked)
        self.close_charge_button = self._create_compact_button('充电关', '#e74c3c')
        self.close_charge_button.clicked.connect(self.on_close_charge_clicked)
        self.open_discharge_button = self._create_compact_button('放电开', '#27ae60')
        self.open_discharge_button.clicked.connect(self.on_open_discharge_clicked)
        self.close_discharge_button = self._create_compact_button('放电关', '#e74c3c')
        self.close_discharge_button.clicked.connect(self.on_close_discharge_clicked)
        
        mos_layout.addWidget(self.open_charge_button, 0, 0)
        mos_layout.addWidget(self.close_charge_button, 0, 1)
        mos_layout.addWidget(self.open_discharge_button, 1, 0)
        mos_layout.addWidget(self.close_discharge_button, 1, 1)
        
        mos_group.setLayout(mos_layout)
        control_layout.addWidget(mos_group)
        
        # 保电控制
        store_group = self._create_compact_group("保电控制")
        store_layout = QHBoxLayout()
        store_layout.setSpacing(2)
        
        self.open_store_power_button = self._create_compact_button('保电开', '#27ae60')
        self.open_store_power_button.clicked.connect(self.on_open_store_power_clicked)
        self.close_store_power_button = self._create_compact_button('保电关', '#e74c3c')
        self.close_store_power_button.clicked.connect(self.on_close_store_power_clicked)
        
        store_layout.addWidget(self.open_store_power_button)
        store_layout.addWidget(self.close_store_power_button)
        
        store_group.setLayout(store_layout)
        control_layout.addWidget(store_group)
        
        # 限流控制（仅工厂模式下显示）
        chglimit_group = self._create_compact_group("限流控制")
        chglimit_layout = QHBoxLayout()
        chglimit_layout.setSpacing(2)

        self.open_chglimit_button = self._create_compact_button('限流开', '#27ae60')
        self.open_chglimit_button.clicked.connect(self.on_open_chglimit_clicked)
        self.close_chglimit_button = self._create_compact_button('限流关', '#e74c3c')
        self.close_chglimit_button.clicked.connect(self.on_close_chglimit_clicked)

        chglimit_layout.addWidget(self.open_chglimit_button)
        chglimit_layout.addWidget(self.close_chglimit_button)

        chglimit_group.setLayout(chglimit_layout)
        control_layout.addWidget(chglimit_group)

        # 加热模式
        heating_group = self._create_compact_group("加热模式")
        heating_layout = QHBoxLayout()
        heating_layout.setSpacing(2)
        
        self.self_heating_button = self._create_compact_button('自加热', '#e74c3c')
        self.self_heating_button.clicked.connect(self.on_self_heating_clicked)
        self.charger_heating_button = self._create_compact_button('充电器加热', '#3498db')
        self.charger_heating_button.clicked.connect(self.on_charger_heating_clicked)
        
        heating_layout.addWidget(self.self_heating_button)
        heating_layout.addWidget(self.charger_heating_button)
        
        heating_group.setLayout(heating_layout)
        control_layout.addWidget(heating_group)
        
        # RT控制
        rt_group = self._create_compact_group("RT控制")
        rt_layout = QGridLayout()
        rt_layout.setSpacing(2)
        
        self.rt0_enable_button = self._create_compact_button('RT0开', '#27ae60')
        self.rt0_enable_button.clicked.connect(self.on_rt0_enable_clicked)
        self.rt1_enable_button = self._create_compact_button('RT1开', '#27ae60')
        self.rt1_enable_button.clicked.connect(self.on_rt1_enable_clicked)
        self.rt2_enable_button = self._create_compact_button('RT2开', '#27ae60')
        self.rt2_enable_button.clicked.connect(self.on_rt2_enable_clicked)
        self.rt0_disable_button = self._create_compact_button('RT0关', '#e74c3c')
        self.rt0_disable_button.clicked.connect(self.on_rt0_disable_clicked)
        self.rt1_disable_button = self._create_compact_button('RT1关', '#e74c3c')
        self.rt1_disable_button.clicked.connect(self.on_rt1_disable_clicked)
        self.rt2_disable_button = self._create_compact_button('RT2关', '#e74c3c')
        self.rt2_disable_button.clicked.connect(self.on_rt2_disable_clicked)
        
        rt_layout.addWidget(self.rt0_enable_button, 0, 0)
        rt_layout.addWidget(self.rt1_enable_button, 0, 1)
        rt_layout.addWidget(self.rt2_enable_button, 0, 2)
        rt_layout.addWidget(self.rt0_disable_button, 1, 0)
        rt_layout.addWidget(self.rt1_disable_button, 1, 1)
        rt_layout.addWidget(self.rt2_disable_button, 1, 2)
        
        rt_group.setLayout(rt_layout)
        control_layout.addWidget(rt_group)
        
        # 其他控制
        other_group = self._create_compact_group("其他控制")
        other_layout = QVBoxLayout()
        other_layout.setSpacing(2)
        
        self.shutdown_button = self._create_compact_button('🔌 设备关机', '#95a5a6')
        self.shutdown_button.clicked.connect(self.on_shutdown_clicked)
        other_layout.addWidget(self.shutdown_button)
        
        # 蓝牙名称修改
        bt_name_row = QHBoxLayout()
        bt_name_row.addWidget(QLabel('名称:'))
        self.bt_name_input = QLineEdit()
        self.bt_name_input.setPlaceholderText('输入新蓝牙名称')
        self.bt_name_input.setMaxLength(20)  # 限制20个字符
        self.bt_name_input.setStyleSheet("font-size: 10px;")
        bt_name_row.addWidget(self.bt_name_input)
        other_layout.addLayout(bt_name_row)
        
        self.bt_name_button = self._create_compact_button('修改蓝牙名称', '#3498db')
        self.bt_name_button.clicked.connect(self.on_change_bt_name_clicked)
        other_layout.addWidget(self.bt_name_button)
        
        other_group.setLayout(other_layout)
        control_layout.addWidget(other_group)
        
        control_layout.addStretch()
        left_tabs.addTab(control_tab, "控制")
        
        # ==================== Tab 3: 密码&烧录 ====================
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setSpacing(3)
        advanced_layout.setContentsMargins(5, 5, 5, 5)
        
        # HEX文件部分（紧凑）
        hex_group = self._create_compact_group("HEX文件")
        hex_layout = QVBoxLayout()
        hex_layout.setSpacing(2)
        
        # 选择按钮单独一行
        hex_btn_row = QHBoxLayout()
        self.hex_file_button = QPushButton('选择HEX文件')
        self.hex_file_button.setFixedHeight(22)
        self.hex_file_button.clicked.connect(self.on_select_hex_file)
        hex_btn_row.addWidget(self.hex_file_button)
        hex_btn_row.addStretch()
        hex_layout.addLayout(hex_btn_row)
        
        # 文件名标签单独一行，支持换行
        self.hex_file_label = QLabel('未选择文件')
        self.hex_file_label.setStyleSheet("font-size: 10px; color: #333; padding: 2px;")
        self.hex_file_label.setWordWrap(True)  # 允许自动换行
        self.hex_file_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.hex_file_label.setMaximumWidth(400)  # 限制最大宽度，确保换行
        hex_layout.addWidget(self.hex_file_label)
        
        # 文件大小信息
        self.hex_info_label = QLabel('大小: 0B')
        self.hex_info_label.setStyleSheet("font-size: 9px; color: #666;")
        hex_layout.addWidget(self.hex_info_label)
        
        self.cell_32_checkbox = QCheckBox('32电芯配置')
        self.cell_32_checkbox.setStyleSheet("font-size: 10px;")
        self.cell_32_checkbox.setToolTip('勾选：32电芯+15温度\n不勾选：16电芯+SBS 5温度+KB 8温度')
        self.cell_32_checkbox.stateChanged.connect(self.on_cell_config_changed)
        hex_layout.addWidget(self.cell_32_checkbox)
        
        hex_group.setLayout(hex_layout)
        advanced_layout.addWidget(hex_group)
        
        # 密码管理
        password_group = self._create_compact_group("密码管理")
        password_layout = QVBoxLayout()
        password_layout.setSpacing(2)
        
        pwd_input_row = QHBoxLayout()
        pwd_input_row.addWidget(QLabel('密码:'))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('6位密码')
        self.password_input.setMaxLength(6)
        self.password_input.setStyleSheet("font-size: 10px;")
        pwd_input_row.addWidget(self.password_input)
        password_layout.addLayout(pwd_input_row)
        
        pwd_btn_layout = QGridLayout()
        pwd_btn_layout.setSpacing(2)
        
        self.query_lock_button = self._create_compact_button('查询', '#3498db')
        self.query_lock_button.clicked.connect(self.on_query_lock_clicked)
        self.login_button = self._create_compact_button('验证', '#27ae60')
        self.login_button.clicked.connect(self.on_login_clicked)
        self.set_password_button = self._create_compact_button('设置', '#f39c12')
        self.set_password_button.clicked.connect(self.on_set_password_clicked)
        self.reset_password_button = self._create_compact_button('取消', '#e74c3c')
        self.reset_password_button.clicked.connect(self.on_reset_password_clicked)
        
        pwd_btn_layout.addWidget(self.query_lock_button, 0, 0)
        pwd_btn_layout.addWidget(self.login_button, 0, 1)
        pwd_btn_layout.addWidget(self.set_password_button, 1, 0)
        pwd_btn_layout.addWidget(self.reset_password_button, 1, 1)
        password_layout.addLayout(pwd_btn_layout)
        
        password_group.setLayout(password_layout)
        advanced_layout.addWidget(password_group)
        
        # 烧录控制
        program_group = self._create_compact_group("烧录控制")
        program_layout = QVBoxLayout()
        program_layout.setSpacing(2)
        
        self.program_button = self._create_compact_button('开始烧录', '#e67e22')
        self.program_button.clicked.connect(self.on_program_clicked)
        program_layout.addWidget(self.program_button)
        
        self.packet_success_label = QLabel('包号: 0 / 0')
        self.packet_success_label.setStyleSheet("font-size: 9px; color: #666;")
        program_layout.addWidget(self.packet_success_label)
        
        self.batch_program_button = self._create_compact_button('批量烧录', '#d35400')
        self.batch_program_button.clicked.connect(self.on_batch_program_clicked)
        program_layout.addWidget(self.batch_program_button)
        
        self.batch_success_label = QLabel('成功: 0')
        self.batch_success_label.setStyleSheet("font-size: 9px; color: #666;")
        program_layout.addWidget(self.batch_success_label)
        
        program_group.setLayout(program_layout)
        advanced_layout.addWidget(program_group)
        
        advanced_layout.addStretch()
        left_tabs.addTab(advanced_tab, "高级")
        
        # ==================== Tab 4: 测试 ====================
        test_tab = QWidget()
        test_layout = QVBoxLayout(test_tab)
        test_layout.setSpacing(3)
        test_layout.setContentsMargins(5, 5, 5, 5)
        
        # 数据发送测试
        send_test_group = self._create_compact_group("发送测试")
        send_test_layout = QVBoxLayout()
        send_test_layout.setSpacing(2)
        
        send_row1 = QHBoxLayout()
        send_row1.addWidget(QLabel('输入:'))
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText('发送数据')
        self.send_input.setStyleSheet("font-size: 10px;")
        send_row1.addWidget(self.send_input)
        send_test_layout.addLayout(send_row1)
        
        send_row2 = QHBoxLayout()
        self.hex_send_checkbox = QCheckBox('HEX')
        self.hex_send_checkbox.setChecked(True)
        self.hex_send_checkbox.setStyleSheet("font-size: 10px;")
        self.crlf_send_checkbox = QCheckBox('\\r\\n')
        self.crlf_send_checkbox.setStyleSheet("font-size: 10px;")
        send_row2.addWidget(self.hex_send_checkbox)
        send_row2.addWidget(self.crlf_send_checkbox)
        send_row2.addStretch()
        send_test_layout.addLayout(send_row2)
        
        send_row3 = QHBoxLayout()
        self.send_button = self._create_compact_button('发送', '#3498db')
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.on_send_data_clicked)
        self.register_button = self._create_compact_button('注册', '#27ae60')
        self.register_button.clicked.connect(self.on_register_clicked)
        self.status_indicator = QLabel()
        self.update_registration_status(False)
        send_row3.addWidget(self.send_button)
        send_row3.addWidget(self.register_button)
        send_row3.addWidget(self.status_indicator)
        send_row3.addStretch()
        send_test_layout.addLayout(send_row3)
        
        send_test_group.setLayout(send_test_layout)
        test_layout.addWidget(send_test_group)
        
        # 连续发送测试
        continuous_group = self._create_compact_group("连续发送")
        continuous_layout = QVBoxLayout()
        continuous_layout.setSpacing(2)
        
        test_row1 = QHBoxLayout()
        test_row1.addWidget(QLabel('间隔1:'))
        self.test128 = QLineEdit('0')
        self.test128.setFixedWidth(50)
        self.test128.setStyleSheet("font-size: 10px;")
        test_row1.addWidget(self.test128)
        test_row1.addWidget(QLabel('间隔2:'))
        self.test512 = QLineEdit('280')
        self.test512.setFixedWidth(50)
        self.test512.setStyleSheet("font-size: 10px;")
        test_row1.addWidget(self.test512)
        test_row1.addStretch()
        continuous_layout.addLayout(test_row1)
        
        self.test_send_button = self._create_compact_button('开始连续发送', '#9b59b6')
        self.test_send_button.clicked.connect(self.on_test_send_buttoned)
        continuous_layout.addWidget(self.test_send_button)
        
        self.no_ack_label = QLabel('无回应=0')
        self.no_ack_label.setStyleSheet("font-size: 9px; color: #666;")
        self.no_ack_count = 0
        self.err_ack_label = QLabel('ack错误=0')
        self.err_ack_label.setStyleSheet("font-size: 9px; color: #666;")
        self.err_ack_count = 0
        self.total_send_label = QLabel('总次数=0')
        self.total_send_label.setStyleSheet("font-size: 9px; color: #666;")
        
        continuous_layout.addWidget(self.no_ack_label)
        continuous_layout.addWidget(self.err_ack_label)
        continuous_layout.addWidget(self.total_send_label)
        
        continuous_group.setLayout(continuous_layout)
        test_layout.addWidget(continuous_group)
        
        test_layout.addStretch()
        left_tabs.addTab(test_tab, "测试")
        
        # ==================== 右侧：接收窗口 ====================
        right_layout = QVBoxLayout()
        right_layout.setSpacing(3)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        self.receive_label = QLabel('接收数据:')
        self.receive_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        right_layout.addWidget(self.receive_label)
        
        self.receive_output = QTextEdit()
        self.receive_output.setReadOnly(True)
        self.receive_output.setStyleSheet("font-size: 9px; font-family: 'Consolas', 'Courier New';")
        right_layout.addWidget(self.receive_output)
        
        # 接收控制
        rx_control_layout = QHBoxLayout()
        self.hex_display_checkbox = QCheckBox('HEX显示')
        self.hex_display_checkbox.setChecked(True)
        self.hex_display_checkbox.setStyleSheet("font-size: 10px;")
        self.hex_display_checkbox.stateChanged.connect(self.on_hex_display_changed)
        self.clear_receive_button = self._create_compact_button('清空', '#95a5a6')
        self.clear_receive_button.clicked.connect(lambda: self.receive_output.clear())
        rx_control_layout.addWidget(self.hex_display_checkbox)
        rx_control_layout.addWidget(self.clear_receive_button)
        rx_control_layout.addStretch()
        right_layout.addLayout(rx_control_layout)
        
        # 添加到主布局
        main_layout.addWidget(left_tabs)
        main_layout.addLayout(right_layout, 1)
        
        self.setLayout(main_layout)
        self.resize(850, 550)  # 紧凑的窗口尺寸
        
        # 初始化UI状态为断开（所有UI组件创建完成后）
        self.update_bluetooth_status('断开')
        
        # 初始化时自动扫描
        QTimer.singleShot(100, self.on_scan_all_clicked)
    
    def _create_compact_group(self, title):
        """创建紧凑的分组框"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 10px;
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 3px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
        """)
        return group
    
    def _create_compact_button(self, text, color='#3498db'):
        """创建紧凑的按钮（按钮高度和padding减半）"""
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 10px;
                min-height: 20px;
                max-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.8)};
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
            }}
        """)
        return button
    
    def _darken_color(self, hex_color, factor=0.9):
        """使颜色变暗"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def _get_button_style(self, color):
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 3px 6px;
                border-radius: 3px;
                font-size: 10px;
                min-height: 20px;
                max-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.8)};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
        """

    def blue_write_log(self, text, color=None):
        """写入日志
        
        Args:
            text: 要写入的文本
            color: 可选，文字颜色（如 'red', 'blue', '#FF5733' 等）
        """
        print(text)
        
        # 如果指定了颜色，使用 QTextCursor 精确控制
        if color:
            from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
            
            cursor = self.receive_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            
            # 保存原始默认格式（自适应系统颜色）
            default_fmt = QTextCharFormat()
            default_fmt.setForeground(self.receive_output.palette().color(self.receive_output.palette().ColorRole.Text))
            
            # 设置文本格式（颜色）
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            
            # 插入带颜色的文本
            cursor.insertText(text + '\n')
            
            # 恢复为系统默认颜色（自适应深色/浅色主题）
            cursor.setCharFormat(default_fmt)
            
            # 更新光标位置
            self.receive_output.setTextCursor(cursor)
        else:
            self.receive_output.append(text)
        
        # 日志文件仍然记录原始文本（不带颜色）
        LogManager.get_instance().write_log(text)
    
    def process_print_command(self, data_buffer):
        """处理 PRINT 指令（0x14 PC_A_PRINT 或 0x94 MCU_A_PRINT）
        
        Args:
            data_buffer: 完整的数据包
            
        Returns:
            bool: 是否成功处理
        """
        try:
            if len(data_buffer) < 9:
                return False
            
            cmd_code = data_buffer[4] & 0x7F
            if cmd_code not in [0x14, 0x94]:
                return False
            
            cmd_name = "PC_A_PRINT" if cmd_code == 0x14 else "MCU_A_PRINT"
            
            # 提取数据部分（跳过帧头8字节，去掉校验1字节）
            data_start = 8
            data_end = len(data_buffer) - 1
            
            if data_end <= data_start:
                return False
            
            raw_data = data_buffer[data_start:data_end]
            # 过滤不可打印字符，转成 ASCII
            filtered_bytes = bytes([b for b in raw_data if 0x20 <= b <= 0x7E])
            ascii_string = filtered_bytes.decode('ascii', errors='ignore')
            
            if not ascii_string:
                return False
            
            # 打印彩色 ASCII
            self.blue_write_log(f"[ASCII] {ascii_string}", color='#00CED1')
            
            # 记录 CSV
            header = f"RX->,{self.commu_type},{self.device_name},{cmd_name}"
            ComunManager.get_instance().write_csv(f"{header},{ascii_string}")
            
            # 发射信号
            self.receive_ok_signal.emit(cmd_code, data_buffer)
            
            return True
            
        except Exception as e:
            self.blue_write_log(f"处理 PRINT 指令失败: {str(e)}")
            return False

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
            # 使用异步方法避免UI阻塞
            try:
                asyncio.create_task(self.connect_serial_async())
            except Exception as e:
                self.blue_write_log(f"创建串口连接任务失败: {str(e)}")
                traceback.print_exc()
        else:
            # 断开连接
            if self.serial_receive_task:
                self.serial_receive_task.cancel()
                self.serial_receive_task = None

            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.commu_type = "none"

            self.is_serial_connected = False
            self.serial_connect_button.setText('连接串口')
            self.disable_serial_settings(False)
            
            # 更新共享按钮状态（考虑蓝牙连接状态）
            self.update_shared_buttons()
            
            self.blue_write_log("串口已断开")
            
            # 主动断开串口时，取消自动连接勾选并停止定时器
            if self.auto_connect_enabled:
                self.auto_connect_checkbox.setChecked(False)
                self.auto_connect_enabled = False
                self.stop_auto_connect_timer()
                self.save_auto_connect_config()  # 保存配置
                self.blue_write_log("ℹ️ 主动断开串口，已自动取消自动连接")
            else:
                self.blue_write_log("ℹ️ 主动断开串口")

    async def connect_serial_async(self):
        """异步串口连接，避免UI阻塞"""
        try:
            # 获取串口参数
            port = self.port_combo.currentText()
            baud_rate = int(self.baud_combo.currentText())
            data_bits = int(self.data_bits_combo.currentText())
            stop_bits = float(self.stop_bits_combo.currentText())
            parity = {'无': 'N', '奇校验': 'O', '偶校验': 'E'}[self.parity_combo.currentText()]

            # 在线程池中执行阻塞的串口连接操作
            loop = asyncio.get_event_loop()
            self.serial_port = await loop.run_in_executor(
                None,
                lambda: serial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    bytesize=data_bits,
                    stopbits=stop_bits,
                    parity=parity,
                    timeout=0.1
                )
            )

            if self.serial_port.is_open:
                self.device_name = port
                self.commu_type = "serial"
                self.is_serial_connected = True
                self.serial_connect_button.setText('断开串口')
                self.blue_write_log(f"串口 {port} 连接成功")
                
                # 禁用参数设置
                self.disable_serial_settings(True)
                
                # 更新共享按钮状态（考虑蓝牙连接状态）
                self.update_shared_buttons()
                
                # 启动接收任务
                self.serial_receive_task = asyncio.create_task(self.serial_receive_loop())
                
                # 串口连接成功后，停止自动连接定时器
                if self.auto_connect_enabled:
                    self.stop_auto_connect_timer()
                    self.blue_write_log("✅ 串口连接成功，自动连接定时器已停止")
            else:
                self.blue_write_log(f"串口 {port} 未能成功打开")
                
        except Exception as e:
            self.blue_write_log(f"串口连接失败: {str(e)}")

    async def disconnect_serial(self):
        """断开串口连接"""
        await self.handle_serial_disconnect()

    async def handle_serial_disconnect(self):
        """处理串口意外断开"""
        # 取消接收任务
        if self.serial_receive_task:
            self.serial_receive_task.cancel()
            self.serial_receive_task = None
        # 关闭串口
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception as e:
                self.blue_write_log(f"关闭串口时出错: {str(e)}")
        # 重置状态
        self.is_serial_connected = False
        self.commu_type = "none"
        self.serial_port = None
        # 更新UI
        self.serial_connect_button.setText('连接串口')
        self.disable_serial_settings(False)
        
        # 更新共享按钮状态（考虑蓝牙连接状态）
        self.update_shared_buttons()

        self.blue_write_log("串口连接已断开")
        
        # 如果启用了自动连接，重启定时器
        if self.auto_connect_enabled:
            self.blue_write_log("🔄 串口断开，启动自动连接定时器...")
            self.start_auto_connect_timer()


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
                # 在线程池中检查串口是否有数据等待
                loop = asyncio.get_event_loop()
                in_waiting = await loop.run_in_executor(None, lambda: self.serial_port.in_waiting)
                
                if in_waiting:
                    # 在线程池中执行阻塞的串口读取操作
                    data = await loop.run_in_executor(None, self.serial_port.read, in_waiting)
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
            except (serial.SerialException, PermissionError, OSError) as e:
                # 串口异常，自动断开
                self.blue_write_log(f"串口异常: {type(e).__name__} - {str(e)}")
                await self.handle_serial_disconnect()
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.blue_write_log(f"接收数据错误: {str(e)}")
                await self.handle_serial_disconnect()
                break

    async def send_data(self, input_data: str):
        """发送数据（兼容蓝牙和串口模式）"""
        try:
            if self.hex_send_checkbox.isChecked():
                # 16进制发送
                try:
                    self.blue_write_log(f"send data type = {type(input_data)}")
                    # 只保留数字和字母（0-9, A-F, a-f），移除所有其他字符
                    import re
                    hex_data = re.sub(r'[^0-9A-Fa-f]', '', input_data)
                    if not hex_data:
                        raise ValueError("没有有效的十六进制字符")
                    if len(hex_data) % 2 != 0:
                        raise ValueError("十六进制字符数必须为偶数")
                    data_bytes = bytes.fromhex(hex_data)

                    # 如果选中了\r\n发送，添加回车换行符
                    if self.crlf_send_checkbox.isChecked():
                        data_bytes += b'\r\n'

                except ValueError as e:
                    self.blue_write_log(f"无效的16进制数据: {e}")
                    QMessageBox.warning(self, '警告', f'无效的16进制数据\n{str(e)}')
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

    def restore_device_list(self):
        """恢复device_list到原窗口的布局中"""
        if self.device_list.parent() != self:
            # device_list不在原窗口中，需要恢复
            # 先从当前父级移除
            current_parent = self.device_list.parent()
            if current_parent:
                layout = current_parent.layout()
                if layout:
                    layout.removeWidget(self.device_list)
            # 重新添加到原布局
            self.bluetooth_layout.insertWidget(self.device_list_index, self.device_list)
    
    def on_scan_devices_clicked(self):
        """同步方法，用于触发异步扫描"""
        asyncio.create_task(self.scan_devices())

    def on_bt_connect_clicked(self):
        """蓝牙连接/断开按钮点击处理（合并逻辑）"""
        bluetooth_connected = bool(self.client and self.client.is_connected)
        
        if not bluetooth_connected:
            # 当前未连接，执行连接
            asyncio.create_task(self.connect_device())
        else:
            # 当前已连接，执行断开
            asyncio.create_task(self.disconnect_device())
    
    def on_connect_device_clicked(self):
        """同步方法，用于触发异步连接（兼容性保留）"""
        asyncio.create_task(self.connect_device())

    def on_disconnect_device_clicked(self):
        """同步方法，断开所有连接（用于主窗口调用）"""
        bluetooth_connected = bool(self.client and self.client.is_connected)
        serial_connected = bool(self.is_serial_connected and self.serial_port and self.serial_port.is_open)
        
        # 断开所有已连接的通道
        if bluetooth_connected:
            asyncio.create_task(self.disconnect_device())
        if serial_connected:
            asyncio.create_task(self.disconnect_serial())
        
        if not bluetooth_connected and not serial_connected:
            self.blue_write_log("⚠️ 当前没有活动连接")

    def on_device_double_clicked(self, item):
        """双击设备列表项时触发连接"""
        asyncio.create_task(self.connect_device())

    def on_send_data_clicked(self):
        """同步方法，用于触发异步发送数据"""
        data = self.send_input.text()
        if data:
            asyncio.create_task(self.send_data(data))
        else:
            QMessageBox.warning(self, '警告', '请输入要发送的数据')

    def update_ui_state(self, state='disconnected', device_name=None, device_address=None):
        """统一更新UI控件状态
        
        Args:
            state: 连接状态 'disconnected'/'connecting'/'connected'
            device_name: 设备名称（可选）
            device_address: 设备MAC地址（可选）
        
        注意: 此方法只管理蓝牙相关的UI状态，不影响串口功能
        """
        # 检查串口是否已连接（串口和蓝牙可以同时工作）
        serial_connected = self.is_serial_connected and self.serial_port and self.serial_port.is_open
        bluetooth_connected = (state == 'connected')
        
        if state == 'connected':
            # ========== 蓝牙已连接状态 ==========
            # 状态显示 - 绿色
            color = '#28a745'
            bg_color = '#d4edda'
            if device_name and device_address:
                status_text = f'🔗 已连接\n📱 {device_name}\n📍 {device_address}'
            elif device_name:
                status_text = f'🔗 已连接\n📱 {device_name}'
            else:
                status_text = '🔗 已连接'
            
            # 蓝牙按钮状态
            self.scan_button.setEnabled(False)  # 禁用扫描
            self.device_list.setEnabled(False)  # 禁用设备列表
            self.bt_connect_button.setEnabled(True)  # 启用按钮（用于断开）
            self.bt_connect_button.setText('断开')  # 改为"断开"
            self.bt_connect_button.setStyleSheet(self._get_button_style('#e74c3c'))  # 红色
            
        elif state == 'connecting':
            # ========== 蓝牙正在连接状态 ==========
            # 状态显示 - 橙色
            color = '#ff8c00'
            bg_color = '#fff3cd'
            status_text = '🔄 正在连接...'
            
            # 蓝牙按钮 - 连接中禁用
            self.scan_button.setEnabled(False)
            self.device_list.setEnabled(False)
            self.bt_connect_button.setEnabled(False)  # 禁用按钮
            
        else:  # 'disconnected'
            # ========== 蓝牙断开状态 ==========
            # 状态显示 - 灰色
            color = '#999'
            bg_color = '#f5f5f5'
            status_text = '⭕ 断开'
            
            # 蓝牙按钮状态
            self.scan_button.setEnabled(True)  # 启用扫描
            self.device_list.setEnabled(True)  # 启用设备列表
            self.bt_connect_button.setEnabled(True)  # 启用按钮（用于连接）
            self.bt_connect_button.setText('连接')  # 改为"连接"
            self.bt_connect_button.setStyleSheet(self._get_button_style('#27ae60'))  # 绿色
        
        # 更新蓝牙状态标签
        self.bluetooth_status_label.setText(status_text)
        self.bluetooth_status_label.setStyleSheet(f"""
            QLabel {{
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: {bg_color};
                color: {color};
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        
        # 更新共享按钮状态（发送、断开按钮）
        self.update_shared_buttons()
    
    def update_shared_buttons(self):
        """更新共享的发送按钮状态
        
        规则:
        - 如果蓝牙或串口任一连接，发送按钮可用
        - 如果都未连接，发送按钮禁用
        """
        # 显式转换为 bool，避免 Bleak 的 _DeprecatedIsConnectedReturn 类型错误
        bluetooth_connected = bool(self.client and self.client.is_connected)
        serial_connected = bool(self.is_serial_connected and self.serial_port and self.serial_port.is_open)
        
        any_connected = bluetooth_connected or serial_connected
        
        self.send_button.setEnabled(any_connected)
    
    def update_bluetooth_status(self, status='断开', device_name=None, device_address=None):
        """更新蓝牙连接状态显示（兼容旧接口）
        
        Args:
            status: 状态文本 '断开'/'正在连接'/'已连接'
            device_name: 设备名称（可选）
            device_address: 设备MAC地址（可选）
        """
        # 映射状态文本到新的状态值
        state_map = {
            '断开': 'disconnected',
            '正在连接': 'connecting',
            '已连接': 'connected'
        }
        state = state_map.get(status, 'disconnected')
        self.update_ui_state(state, device_name, device_address)

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
    async def ensure_bluetooth_radio_enabled(self):
        """确保Windows蓝牙Radio被启用和初始化"""
        try:
            import winrt.windows.devices.radios as radios
            import winrt.windows.devices.bluetooth as windows_bluetooth
        except ImportError:
            self.blue_write_log("⚠️ winrt模块不可用，跳过蓝牙Radio检查（需要安装 winrt-Windows.Devices.Radios）")
            return True
        try:
            self.blue_write_log("正在检查并初始化蓝牙适配器...")
            radio_access = await radios.Radio.request_access_async()
            if radio_access != radios.RadioAccessStatus.ALLOWED:
                self.blue_write_log(f"⚠️ 蓝牙访问权限被拒绝: {radio_access}")
                return False
            all_radios = await radios.Radio.get_radios_async()
            bluetooth_radio = None
            for radio in all_radios:
                if radio.kind == radios.RadioKind.BLUETOOTH:
                    bluetooth_radio = radio
                    break
            if bluetooth_radio is None:
                self.blue_write_log("⚠️ 未找到蓝牙适配器")
                return False
            current_state = bluetooth_radio.state
            self.blue_write_log(f"蓝牙适配器当前状态: {current_state}")
            if current_state == radios.RadioState.OFF:
                self.blue_write_log("蓝牙适配器已关闭，正在尝试开启...")
                result = await bluetooth_radio.set_state_async(radios.RadioState.ON)
                if result == radios.RadioAccessStatus.ALLOWED:
                    self.blue_write_log("✅ 蓝牙适配器已成功开启")
                    await asyncio.sleep(1)
                    return True
                else:
                    self.blue_write_log(f"⚠️ 无法开启蓝牙适配器: {result}")
                    return False
            elif current_state == radios.RadioState.ON:
                self.blue_write_log("✅ 蓝牙适配器已开启")
                return True
            else:
                self.blue_write_log(f"⚠️ 蓝牙适配器状态异常: {current_state}")
                return False
        except Exception as e:
            self.blue_write_log(f"⚠️ 初始化蓝牙适配器时出错: {str(e)}")
            traceback.print_exc()
            return False
    async def scan_devices(self):
        """异步方法，扫描蓝牙设备"""
        self.device_list.clear()
        self.label.setText('正在扫描设备...')
        radio_ok = await self.ensure_bluetooth_radio_enabled()
        if not radio_ok:
            self.label.setText('蓝牙适配器未就绪，请检查系统蓝牙设置')
            self.blue_write_log("⚠️ 蓝牙适配器检查失败，继续尝试扫描...")
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
        # 先收集所有符合条件的设备
        device_info_list = []
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

                # 收集设备信息
                device_info_list.append({
                    'name': device.name,
                    'rssi': advertisement_data.rssi,
                    'password_status': password_status_short
                })
        # 按信号强度降序排序（从强到弱）
        device_info_list.sort(key=lambda x: x['rssi'], reverse=True)
        # 添加到设备列表
        for device_info in device_info_list:
            self.device_list.addItem(f"{device_info['name']} (RSSI: {device_info['rssi']}){device_info['password_status']}")
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
        
        # 如果是手动扫描且启用了自动连接，尝试自动连接
        if self.auto_connect_enabled and not self.is_auto_scanning and not self.is_connecting:
            self.blue_write_log("🔄 手动扫描完成，尝试自动连接...")
            # 设置连接锁
            self.is_connecting = True
            asyncio.create_task(self._try_connect_after_scan())

    async def connect_device(self, is_auto=False):
        """异步方法，连接蓝牙设备
        
        Args:
            is_auto: 是否为自动连接（True=自动连接，False=手动连接）
        """
        # ========== 1. 防止重复连接 ==========
        if not self.connection_manager.acquire_connection_lock():
            self.blue_write_log("⚠️ 正在连接中，请勿重复操作")
            return
        
        # ========== 2. 检查是否已连接 ==========
        if self.client and self.client.is_connected:
            self.blue_write_log("✅ 设备已连接")
            return
        
        # ========== 3. 获取目标设备信息 ==========
        selected_device = self.device_list.currentItem()
        if not selected_device:
            if not is_auto:  # 手动连接时提示
                QMessageBox.warning(self, '警告', '请先选择一个设备')
            return
        
        device_text = selected_device.text()
        device_name = device_text.split(' (RSSI:')[0]
        device_address = self.device_name_to_address.get(device_name)
        
        if not device_address:
            if not is_auto:
                QMessageBox.warning(self, '警告', '无法找到设备地址，请重新扫描')
            return
        
        # ========== 4. 手动连接：停止自动连接 ==========
        if not is_auto and self.auto_connect_enabled:
            self.blue_write_log("ℹ️ 手动连接，停止自动连接...")
            self.auto_connect_checkbox.setChecked(False)
            # on_auto_connect_changed 会自动调用停止定时器和保存配置
        
        # ========== 5. 开始连接 ==========
        try:
            # 更新状态：正在连接
            self.update_bluetooth_status('正在连接')
            self.blue_write_log(f"🔄 {'自动' if is_auto else '手动'}连接: {device_name} ({device_address})")
            
            # 清理旧连接
            if self.client:
                try:
                    if self.client.is_connected:
                        await self.client.disconnect()
                        await asyncio.sleep(0.5)
                except:
                    pass
                self.client = None
            
            # 创建新客户端并连接
            self.client = BleakClient(device_address, disconnected_callback=self.on_bluetooth_disconnected, timeout=10.0)
            await asyncio.wait_for(self.client.connect(), timeout=10.0)
            
            # 等待服务发现完成
            await asyncio.sleep(1.0)
            
            # 设置连接信息
            self.commu_type = "bluetooth"
            self.device_name = device_name
            self.device_address = device_address
            
            # 更新状态：已连接
            self.update_bluetooth_status('已连接', device_name=device_name, device_address=device_address)
            
            # 记录连接成功
            log_prefix = "🤖" if is_auto else "👆"
            self.blue_write_log(f"{log_prefix} 连接成功: {device_name} ({device_address})")
            
            # 手动连接时显示消息框
            if not is_auto:
                connectMessage = QMessageBox(QMessageBox.Icon.Information, '连接成功', 
                                            f'已连接到\n{device_name}\n{device_address}')
                QTimer.singleShot(300, connectMessage.close)
                connectMessage.exec()
            
            # 开始监听数据
            if self.client and self.client.is_connected:
                try:
                    await self.client.start_notify("0000ffe1-0000-1000-8000-00805f9b34fb", self.on_data_received)
                except Exception as notify_error:
                    self.blue_write_log(f"⚠️ 启动通知失败: {str(notify_error)}")
                    # 通知失败不影响连接，继续执行
            
            # 连接成功后，停止自动连接定时器
            if self.auto_connect_enabled:
                self.stop_auto_connect_timer()
                self.blue_write_log("✅ 连接成功，自动连接定时器已停止")
            
            # 连接成功后，自动保存该设备信息（如果配置为空或不同）
            if not self.auto_connect_device_name or self.auto_connect_device_name != device_name:
                self.blue_write_log(f"📝 自动保存设备信息: {device_name} ({device_address})")
                self.auto_connect_name_input.setText(device_name)
                self.auto_connect_mac_input.setText(device_address)
                self.auto_connect_device_name = device_name
                self.auto_connect_mac_address = device_address
                self.save_auto_connect_config()
            
            QTimer.singleShot(1000, self.send_find_version_cmd)
        except asyncio.TimeoutError:
            # 连接超时
            self.commu_type = "none"
            self.client = None
            self.device_name = None
            self.device_address = None
            self.update_bluetooth_status('断开')
            self.blue_write_log(f"❌ {'自动' if is_auto else '手动'}连接超时")
            
        except Exception as e:
            # 连接失败
            self.commu_type = "none"
            self.client = None
            self.device_name = None
            self.device_address = None
            self.update_bluetooth_status('断开')
            self.blue_write_log(f"❌ {'自动' if is_auto else '手动'}连接失败: {str(e)}")
            
        finally:
            # ========== 6. 清理连接标志 ==========
            self.connection_manager.release_connection_lock()

    async def disconnect_device(self):
        """异步方法，断开蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                
                # 清理连接状态
                self.client = None
                self.device_name = None
                self.device_address = None
                self.commu_type = "none"
                
                # 更新UI状态：断开（会自动设置按钮状态）
                self.update_bluetooth_status('断开')
                
                # 主动断开时，取消自动连接勾选并停止定时器
                if self.auto_connect_enabled:
                    self.auto_connect_checkbox.setChecked(False)
                    # on_auto_connect_changed 会自动调用停止定时器和保存配置
                    self.blue_write_log("ℹ️ 主动断开蓝牙，已自动取消自动连接")
                else:
                    self.blue_write_log("✅ 蓝牙已断开")
                
            except Exception as e:
                QMessageBox.critical(self, '断开失败', str(e))
        else:
            self.blue_write_log("⚠️ 蓝牙未连接")

    async def bluetooth_send_data(self, data:str):
        """异步方法，发送数据到蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                if self.hex_send_checkbox.isChecked():
                    # 16进制发送
                    try:
                        # 只保留数字和字母（0-9, A-F, a-f），移除所有其他字符
                        import re
                        hex_data = re.sub(r'[^0-9A-Fa-f]', '', data)
                        if not hex_data:
                            raise ValueError("没有有效的十六进制字符")
                        if len(hex_data) % 2 != 0:
                            raise ValueError("十六进制字符数必须为偶数")
                        # 将16进制字符串转换为字节
                        data_bytes = bytes.fromhex(hex_data)
                    except ValueError as e:
                        QMessageBox.warning(self, '警告', f'无效的16进制数据\n{str(e)}')
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
        send_max_count = 10000
        while send_max_count:
            send_max_count-=1
            time512 = int(self.test512.text()) / 1000 * 2
            if self.client and self.client.is_connected:
                try:
                    # 重置响应状态（基于信号机制，解耦text_decode.legality）
                    self.last_response_status = None
                    self.last_response_ack = None
                    
                    # 假设设备的写特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                    self.byte_send(data)
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    self.display_send_data(data)
                    time.sleep(time512)
                    self.send_count += 1
                    self.total_send_label.setText(f'总 = {self.send_count}')

                    # 等待响应（基于信号机制）
                    await asyncio.sleep(0.4)
                    if self.last_response_status is None:
                        await asyncio.sleep(0.7)
                    
                    # 检查响应状态（基于信号机制，不再依赖text_decode.legality）
                    if self.last_response_status is True:
                        if self.last_response_ack in [0x00]:
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
                    # QMessageBox.critical(self, '发送失败', str(e))
            else:
                # QMessageBox.warning(self, '警告', '未连接到设备')
                break
        self.task_flag = False

    async def byte_send(self,data:bytes):
        """异步方法，发送字节数据"""
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
                # 检查串口连接状态
                if not self.is_serial_connected:
                    raise Exception("串口连接已断开")
                
                self.blue_write_log(f"byte_send: 向串口写入 {len(data)} 字节...")
                # 在线程池中执行阻塞的串口写入操作
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.serial_port.write, data)
        except (serial.SerialException, PermissionError) as e:
            # 串口异常，自动断开
            await self.handle_serial_disconnect()
            raise Exception("串口发送失败，连接已断开")
        except Exception as e:
            self.blue_write_log(f"发送失败: {str(e)}")
            raise Exception("发送失败")

    def on_bluetooth_disconnected(self, client):
        """蓝牙断开连接回调函数（从机主动断开）"""
        self.blue_write_log("⚠️ 蓝牙设备已断开连接（从机主动断开）", color='red')
        self.blue_write_log(f"蓝牙断开: 设备={self.device_name}, 时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 清理连接状态
        self.client = None
        self.device_name = None
        self.device_address = None
        self.commu_type = "none"
        self.connection_manager.release_connection_lock()  # 清理连接标志
        self.connection_manager.set_bluetooth_state(ConnectionState.DISCONNECTED)
        
        # 更新UI状态：断开（会自动设置按钮状态）
        self.update_bluetooth_status('断开')
        
        # 如果启用了自动连接，重启定时器持续尝试重连
        if self.auto_connect_enabled:
            self.blue_write_log("🔄 检测到自动连接已启用，启动定时器持续尝试重连...")
            # 延迟3秒后立即尝试一次重连
            if not self.is_auto_reconnecting:
                self.is_auto_reconnecting = True
                QTimer.singleShot(3000, lambda: asyncio.create_task(self.auto_reconnect()))
            # 启动定时器持续尝试
            self.start_auto_connect_timer()
        else:
            # 弹出提示消息
            QMessageBox.warning(self, '连接已断开', '蓝牙设备已断开连接')
    
    def _on_receive_response(self, cmd_code, data):
        """内部槽函数：处理接收到的响应（用于test_send_data等功能）
        
        通过信号机制更新响应状态，解耦数据解析器和业务逻辑
        
        Args:
            cmd_code: 命令码
            data: 响应数据
        """
        if len(data) >= 8:
            self.last_response_status = True
            self.last_response_ack = data[7]
        else:
            self.last_response_status = True
            self.last_response_ack = 0x00

    async def on_data_received(self, sender, data):
        """回调函数，处理接收到的数据"""
        # 将数据添加到缓冲区
        self.received_data_buffer.extend(data)
        # 🔥 立即检测注册响应（不等定时器，提高响应速度）
        try:
            if len(self.received_data_buffer) >= 8 and self.received_data_buffer[4] == 0x81:
                cmd_ack = self.received_data_buffer[7]
                if cmd_ack in [0x00, 0x04]:
                    self.register_response = True
                else:
                    self.register_response = False
        except (IndexError, Exception):
            pass  # 数据不完整或异常，忽略
        # 重启定时器
        self.data_timer.start(120)  # 20ms - 减少延迟，更快处理数据包

    def is_ota_command(self, data):
        """判断是否为OTA编程命令
        
        OTA命令特征：
        - 长度 >= 9
        - data[0] = 0x00 (地址)
        - data[4] 的高位为1 (响应标志)，低7位为OTA命令码
        - OTA命令码：0x76(握手), 0x75(擦除), 0x77(写入), 0x78(校验), 0x71(查询), 0x01(注册)等
        """
        if len(data) < 9:
            return False
        
        # 检查是否符合OTA协议格式
        if data[0] != 0x00:  # 地址字段
            return False
        
        if data[5] != 0x55 or data[6] != 0xAA:  # 协议标识
            return False
        
        # 提取命令码（去除最高位的响应标志）
        cmd = data[4] & 0x7F
        
        # OTA相关的命令码列表
        ota_commands = [
            0x76,  # 握手命令
            0x75,  # 擦除命令  
            0x77,  # 写入Flash
            0x78,  # 总校验和
            0x71,  # 读取IC信息
            0x01,  # 注册命令（也用于OTA流程）
        ]
        
        return cmd in ota_commands
    
    def process_complete_data(self):
        """处理完整的数据包（自动路由到OTA或普通数据解析器）"""
        if self.check_new_password_response(self.received_data_buffer):
            self.handle_new_password_response(self.received_data_buffer)
        else:
            # 🔥 自动判断：根据数据特征选择解析器
            if self.is_ota_command(self.received_data_buffer):
                # OTA指令：使用 text_decode 解析
                self.text_decode.split_data(self.received_data_buffer)
            # 正常数据指令：使用 data_display_mgr 解析
            elif hasattr(self, 'data_display_mgr') and hasattr(self.data_display_mgr, 'parse_and_update_displays'):
                # 一站式：解析 + 自动更新显示（方案A优化）
                success, result = self.data_display_mgr.parse_and_update_displays(self.received_data_buffer)
                if success:
                    # 只需处理CSV记录
                    struct_name = result['struct_name']
                    dict_data = result['data']
                    header = f"RX->,{self.commu_type},{self.device_name},{struct_name}"
                    csv_data = ",".join([item[2] for items in dict_data.values() for item in items if len(item) >= 3])
                    ComunManager.get_instance().write_csv(f"{header},{csv_data}")
                else:
                    self.blue_write_log(f"数据解析失败: {result}")
            else:
                self.blue_write_log("错误：data_display_mgr未初始化")
        self.display_received_data(self.received_data_buffer)
        self.received_data_buffer.clear()

    def check_new_password_response(self, data):
        """检查是否是新的密码命令响应格式"""
        if len(data) < 5:
            return False

        # 检查帧头和帧尾
        if data[0] == 0xFB and data[-1] == 0xBB:
            cmd_code = data[1]
            # 检查是否是密码相关命令的响应
            if cmd_code in [0x01, 0x02, 0x03]:
                return True

        return False

    def handle_new_password_response(self, data):
        """处理新的密码命令响应"""
        try:
            success, result = self.parse_new_password_response(data)

            if not success:
                self.blue_write_log(f"密码命令响应解析失败: {result}")
                return

            cmd_code = result["cmd_code"]
            content = result["content"]

            if cmd_code == 0x01:  # 验证密码响应
                if len(content) >= 1:
                    if content[0] == 0x00:
                        self.blue_write_log("密码验证失败: 密码错误")
                    elif content[0] == 0x01:
                        self.blue_write_log("密码验证成功: 密码正确")
                    else:
                        self.blue_write_log(f"密码验证响应: 未知状态 {content[0]:02X}")
                else:
                    self.blue_write_log("密码验证响应: 数据长度不足")

            elif cmd_code == 0x02:  # 设置密码响应
                if len(content) >= 1:
                    if content[0] == 0x00:
                        self.blue_write_log("设置密码失败")
                    elif content[0] == 0x01:
                        self.blue_write_log("设置密码成功")
                    else:
                        self.blue_write_log(f"设置密码响应: 未知状态 {content[0]:02X}")
                else:
                    self.blue_write_log("设置密码响应: 数据长度不足")

            elif cmd_code == 0x03:  # 取消密码响应
                if len(content) >= 1:
                    if content[0] == 0x00:
                        self.blue_write_log("取消密码失败")
                    elif content[0] == 0x01:
                        self.blue_write_log("取消密码成功")
                    else:
                        self.blue_write_log(f"取消密码响应: 未知状态 {content[0]:02X}")
                else:
                    self.blue_write_log("取消密码响应: 数据长度不足")

        except Exception as e:
            self.blue_write_log(f"处理密码命令响应异常: {str(e)}")

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
                # 显示文件名，支持自动换行
                self.hex_file_label.setText(f'📄 {file_info["filename"]}')
                self.hex_info_label.setText(f'大小: {file_info["size"]} 字节')
                self.blue_write_log(f"已选择HEX文件: {file_info['filename']}")
            else:
                self.hex_file_label.setText('❌ 文件解析失败')
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
                    await asyncio.sleep(time512 * 2)
                    if(self.text_decode.is_download_cmd):
                        self.blue_write_log(f"✅ 握手命令发送成功")
                        shake_success = True
                        break
                    self.blue_write_log(f"❌ 握手未成功，继续重试 (err_count={err_count})")
                    err_count += 1
                else:
                    if err_count == 3:
                        self.blue_write_log(f"握手失败")
                shake_count += 1
            else:
                self.packet_success_label.setText('握手成功')
                self.blue_write_log(f"握手最终成功")
            # self.text_decode.legality = ReceveDataStatus.ERR_NOTHING



            err_count = 0
            while err_count < 2:
                data = self.download_data.get_download_data(BmsCmdType.DOWNLOAD_BUFFER)
                self.display_send_data(data)
                await self.byte_send(data)
                self.blue_write_log(f"擦除命令发送")
                await asyncio.sleep(time512 * 2)
                if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                    await asyncio.sleep(time512 * 4)
                if(self.text_decode.no80_cmd == BmsCmdType.DOWNLOAD_BUFFER  and self.text_decode.cmd_ack == 0x00):
                    self.blue_write_log(f"✅ 擦除命令发送成功")
                    self.packet_success_label.setText('擦除成功')
                    break
                else:
                    self.blue_write_log(f"❌ 擦除未成功，继续重试 (err_count={err_count})")
                    err_count += 1
            else:
                self.blue_write_log(f"擦除失败")

            # while


            # 发送下载命令并等待响应
            if not self.hex_model.is_file_loaded:
                self.hex_file_label.setText('HEX文件：未加载')
                # raise Exception("HEX文件未加载")
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
                            await self.byte_send(data)
                            await asyncio.sleep(time512)
                            if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                                await asyncio.sleep(time512)
                            if(self.text_decode.no80_cmd == BmsCmdType.WRITE_FLASH  and
                                self.text_decode.cmd_ack == 0x00 and
                                self.text_decode.cmd_packet_num == hex_packet + 1):
                                    self.blue_write_log(f"✅ 包{hex_packet + 1}发送成功")
                                    self.packet_success_label.setText(f'包号: {hex_packet + 1} 总包数: {self.download_data.packet_num}')
                                    err_count = 0
                                    hex_packet += 1
                                    break
                            else:
                                self.blue_write_log(f"❌ 包{hex_packet + 1}未成功，重试 (err_count={err_count})")
                                await asyncio.sleep(time512*3)
                                err_count += 1
                        else:
                            self.blue_write_log(f"包{hex_packet + 1}发送失败")
                            raise Exception("烧录失败")

                    except BleakError:
                        # traceback.print_exc()
                        raise Exception("蓝牙断开")
                    except Exception as e:
                        traceback.print_exc()
                        break
                    else:
                        pass


            err_count = 0
            while err_count < 5:
                data = self.download_data.get_download_data(BmsCmdType.REC_TOTAL_CHECKSUM)
                self.display_send_data(data)
                await self.byte_send(data)
                await asyncio.sleep(time512 * 4)
                if(self.text_decode.no80_cmd == BmsCmdType.REC_TOTAL_CHECKSUM  and self.text_decode.cmd_ack == 0x00):
                    self.blue_write_log(f"✅ 总校验和验证成功")
                    break
                else:
                    self.blue_write_log(f"❌ 总校验和未成功，重试 (err_count={err_count})")
                    err_count += 1
            self.blue_write_log("烧录完成")
            await asyncio.sleep(6)

            err_count = 0
            await asyncio.sleep(5)
            if self.text_decode.no80_cmd == BmsCmdType.BMS_MCU_OPEN  and self.text_decode.cmd_ack == 0x00:
                self.blue_write_log("电池重启")
            await asyncio.sleep(3)
            while err_count < 5:
                data = self.download_data.get_download_data(BmsCmdType.READ_IC_INF)
                self.display_send_data(data)
                await self.byte_send(data)
                await asyncio.sleep(time512 * 3)
                if(self.text_decode.no80_cmd == BmsCmdType.READ_IC_INF  and self.text_decode.cmd_ack == 0x00):
                    self.blue_write_log(f"✅ 71指令查询成功，烧录完成")
                    self.ota_ok_count += 1
                    break
                else:
                    self.blue_write_log(f"❌ 71指令查询失败，重试 (err_count={err_count})")
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

    def on_open_charge_clicked(self):
        """处理打开充电按钮点击事件"""
        # 发送打开充电的指令数据
        bytedata = bytes([0x00,0x00,0x04,0x01,0x0A,0x55,0xaa,0x0E])
        self.send_command(bytedata)

    def on_close_charge_clicked(self):
        """处理关闭充电按钮点击事件"""
        # 发送关闭充电的指令数据
        bytedata = bytes([0x00,0x00,0x04,0x01,0x0B,0x55,0xaa,0x0F])
        self.send_command(bytedata)

    def on_open_chglimit_clicked(self):
        """处理开启限流按钮点击事件"""
        # 发送开启充电限流的指令 (0x27)
        data = self.text_decode.send_hex_fill(0x27)
        self.send_command(data)
        self.blue_write_log("发送开启充电限流指令")

    def on_close_chglimit_clicked(self):
        """处理关闭限流按钮点击事件"""
        # 发送关闭充电限流的指令 (0x28)
        data = self.text_decode.send_hex_fill(0x28)
        self.send_command(data)
        self.blue_write_log("发送关闭充电限流指令")

    def on_open_store_power_clicked(self):
        """处理打开保电按钮点击事件"""
        # 发送打开保电的指令数据: 00 00 08 01 19 55 AA AA AA AA AA C9
        bytedata = bytes([0x00, 0x00, 0x08, 0x01, 0x19, 0x55, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xC9])
        self.send_command(bytedata)
        self.blue_write_log("已发送开启保电指令 (0x00210000)")

    def on_close_store_power_clicked(self):
        """处理关闭保电按钮点击事件"""
        # 发送关闭保电的指令数据: 00 00 08 01 19 55 AA 55 55 55 55 75
        bytedata = bytes([0x00, 0x00, 0x08, 0x01, 0x19, 0x55, 0xAA, 0x55, 0x55, 0x55, 0x55, 0x75])
        self.send_command(bytedata)
        self.blue_write_log("已发送关闭保电指令 (0x00010000)")

    def on_rt0_enable_clicked(self):
        """处理RT0使能按钮点击事件"""
        # 发送RT0使能指令 (0x31)
        self.send_command(self.text_decode.send_hex_fill(0x31))
        self.blue_write_log("发送RT0使能指令")

    def on_rt1_enable_clicked(self):
        """处理RT1使能按钮点击事件"""
        # 发送RT1使能指令 (0x32)
        self.send_command(self.text_decode.send_hex_fill(0x32))
        self.blue_write_log("发送RT1使能指令")

    def on_rt2_enable_clicked(self):
        """处理RT2使能按钮点击事件"""
        # 发送RT2使能指令 (0x33)
        self.send_command(self.text_decode.send_hex_fill(0x33))
        self.blue_write_log("发送RT2使能指令")

    def on_rt0_disable_clicked(self):
        """处理RT0关闭按钮点击事件"""
        # 发送RT0关闭指令 (0x34)
        self.send_command(self.text_decode.send_hex_fill(0x34))
        self.blue_write_log("发送RT0关闭指令")

    def on_rt1_disable_clicked(self):
        """处理RT1关闭按钮点击事件"""
        # 发送RT1关闭指令 (0x35)
        self.send_command(self.text_decode.send_hex_fill(0x35))
        self.blue_write_log("发送RT1关闭指令")

    def on_rt2_disable_clicked(self):
        """处理RT2关闭按钮点击事件"""
        # 发送RT2关闭指令 (0x36)
        self.send_command(self.text_decode.send_hex_fill(0x36))
        self.blue_write_log("发送RT2关闭指令")

    def on_change_bt_name_clicked(self):
        """处理修改蓝牙名称按钮点击事件"""
        new_name = self.bt_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, '警告', '请输入新的蓝牙名称')
            return
        
        # 弹出确认窗口
        reply = QMessageBox.question(
            self,
            '确认修改',
            f'确定要将蓝牙名称修改为 "{new_name}" 吗？，修改成功，\n蓝牙会自动断开连接，如果用有线修改要接到蓝牙的串口上\n0023版本无法通过蓝牙修改20位名称，0026可以',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 构造AT指令（不带\r\n）
            at_command = f"AT+NAME={new_name}"
            self.blue_write_log(f"准备发送AT指令: {at_command}")
            
            # 发送指令
            asyncio.create_task(self.send_bt_name_command(at_command))
        else:
            self.blue_write_log("取消修改蓝牙名称")

    async def send_bt_name_command(self, at_command: str):
        """异步发送蓝牙名称修改指令（支持蓝牙和串口）"""
        try:
            # 检查连接状态
            if not self.client or not self.client.is_connected:
                if not self.serial_port or not self.serial_port.is_open:
                    QMessageBox.warning(self, '警告', '请先连接蓝牙或串口设备')
                    self.blue_write_log("错误：未连接到任何设备")
                    return
            
            # 判断使用蓝牙还是串口发送
            if self.client and self.client.is_connected:
                # 蓝牙连接：不加\r\n
                data_bytes = at_command.encode('utf-8')
                uuid_ffe3 = "0000ffe3-0000-1000-8000-00805f9b34fb"
                await self.client.write_gatt_char(uuid_ffe3, data_bytes)
                self.blue_write_log(f"✅ 蓝牙名称修改指令已发送 (蓝牙 UUID: FFE3，不加\\r\\n)")
                self.blue_write_log("提示：修改成功后蓝牙会自动断开连接")
            elif self.serial_port and self.serial_port.is_open:
                # 串口连接：加\r\n
                data_bytes = (at_command + '\r\n').encode('utf-8')
                await self.byte_send(data_bytes)
                self.blue_write_log(f"✅ 蓝牙名称修改指令已发送 (串口，加\\r\\n)")
                self.blue_write_log("提示：修改成功后蓝牙模块可能会重启")
            
            # 显示发送的数据
            self.display_send_data(data_bytes)
            
        except Exception as e:
            self.blue_write_log(f"发送错误，但是修改可能成功，因为成功会立马断开蓝牙: {str(e)}")
            QMessageBox.critical(self, '发送错误，但是修改可能成功，因为成功会立马断开蓝牙', f'发送失败: {str(e)}')
            traceback.print_exc()

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

    def on_shutdown_clicked(self):
        """处理关机按钮点击事件"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            '确认关机',
            '确定要关闭设备吗？\n设备将进入关机状态。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.send_shutdown_cmd()
            self.blue_write_log("已发送关机指令 (0x60)")

    def send_shutdown_cmd(self):
        """发送关机指令"""
        self.send_command(self.text_decode.send_hex_fill(0x60))

    def on_self_heating_clicked(self):
        """处理自加热模式按钮点击事件"""
        # 发送自加热模式指令: 00 00 08 01 17 55 AA 02 00 00 00 21
        bytedata = bytes([0x00, 0x00, 0x08, 0x01, 0x17, 0x55, 0xAA, 0x02, 0x00, 0x00, 0x00, 0x21])
        self.send_command(bytedata)
        self.blue_write_log("已发送自加热模式指令 (0x00210000)")

    def on_charger_heating_clicked(self):
        """处理充电器加热模式按钮点击事件"""
        # 发送充电器加热模式指令: 00 00 08 01 17 55 AA 01 00 00 00 20
        bytedata = bytes([0x00, 0x00, 0x08, 0x01, 0x17, 0x55, 0xAA, 0x01, 0x00, 0x00, 0x00, 0x20])
        self.send_command(bytedata)
        self.blue_write_log("已发送充电器加热模式指令 (0x00010000)")

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

    async def send_register_cmd(self):
        """注册按钮点击处理"""
        try:
            self.update_registration_status(False)
            # 清空注册响应标志
            self.register_response = None
            # 发送注册命令
            data = bytearray([0x00,0x00,0x04,0x01,0x01,0x55,0xaa,0x05])
            self.display_send_data(data)
            await self.byte_send(data)
            # 等待接收响应（总共等待1.5秒）
            for _ in range(15):
                await asyncio.sleep(0.1)
                if self.register_response is not None:
                    break
            # 检查注册响应标志
            if self.register_response is True:
                self.update_registration_status(True)
                self.blue_write_log("注册成功")
            elif self.register_response is False:
                self.update_registration_status(False)
                self.blue_write_log("注册失败")
            else:
                self.update_registration_status(False)
                self.blue_write_log("注册失败：未收到响应")

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
        self.blue_write_log("提示: 密码状态可通过设备扫描时的广播数据查看 [无密码]/[有密码] 标识")
        # asyncio.create_task(self.send_query_lock_cmd())

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

    def detect_and_set_cell_config(self):
        """检测当前配置是16串还是32串，并设置checkbox状态"""
        try:
            # 调用 HexParserApp 的方法检测当前配置
            cell_count = self.hex_parser.get_current_cell_config()

            # 暂时阻止信号，避免触发配置切换
            self.cell_32_checkbox.blockSignals(True)

            if cell_count == 32:
                self.cell_32_checkbox.setChecked(True)
                self.blue_write_log("检测到当前配置：32串配置")
            elif cell_count == 16:
                self.cell_32_checkbox.setChecked(False)
                self.blue_write_log("检测到当前配置：16串配置")
            else:
                self.cell_32_checkbox.setChecked(False)
                self.blue_write_log(f"警告：未知的电芯配置，默认使用16串配置")

            # 恢复信号
            self.cell_32_checkbox.blockSignals(False)

        except Exception as e:
            self.blue_write_log(f"检测配置失败: {str(e)}")
            traceback.print_exc()

    def on_cell_config_changed(self, state):
        """处理32电芯配置checkbox状态变化"""
        try:
            if state == Qt.CheckState.Checked.value:
                # 切换到32串配置
                self.blue_write_log("正在切换到32串配置...")
                self.hex_parser.set_struct_to_cell_32()
                self.blue_write_log("已切换到32串配置（32电芯 + 15温度传感器）")
            else:
                # 切换到16串配置
                self.blue_write_log("正在切换到16串配置...")
                self.hex_parser.set_struct_to_cell_16()
                self.blue_write_log("已切换到16串配置（16电芯 + SBS:5温度 + KB:8温度）")
            
            # 同步到主界面（如果主界面存在）
            try:
                # 尝试找到主界面窗口
                from PyQt6.QtWidgets import QApplication
                for widget in QApplication.topLevelWidgets():
                    if hasattr(widget, 'cell_32_checkbox') and widget != self:
                        # 找到主界面，同步配置
                        widget.cell_32_checkbox.blockSignals(True)
                        widget.cell_32_checkbox.setChecked(state == Qt.CheckState.Checked.value)
                        widget.cell_32_checkbox.blockSignals(False)
                        break
            except Exception as sync_error:
                # 同步失败不影响主要功能
                pass
                
        except Exception as e:
            self.blue_write_log(f"切换配置失败: {str(e)}")
            traceback.print_exc()

    def on_auto_connect_changed(self, state):
        """处理自动连接checkbox状态变化"""
        try:
            self.auto_connect_enabled = (state == Qt.CheckState.Checked.value)
            
            if self.auto_connect_enabled:
                # 验证配置
                if not self.auto_connect_name_input.text().strip():
                    self.blue_write_log("⚠️ 请先配置设备名称")
                    self.auto_connect_checkbox.setChecked(False)
                    return
                
                self.blue_write_log(f"✅ 自动连接已启用: {self.auto_connect_name_input.text()}")
                self.blue_write_log(f"🔄 将每{self.auto_connect_retry_interval/1000}秒尝试连接一次...")
                # 自动保存配置
                self.save_auto_connect_config()
                
                # 如果没有正在连接，立即触发一次扫描和连接
                if not self.connection_manager.is_connecting:
                    asyncio.create_task(self.auto_scan_and_connect())
                else:
                    self.blue_write_log("⏳ 当前正在连接，等待连接完成...")
                
                # 启动定时器，持续尝试连接
                self.start_auto_connect_timer()
            else:
                self.blue_write_log("❌ 自动连接已禁用")
                self.is_auto_reconnecting = False
                # 停止定时器
                self.stop_auto_connect_timer()
                # 自动保存配置
                self.save_auto_connect_config()
                
        except Exception as e:
            self.blue_write_log(f"自动连接状态切换失败: {str(e)}")
            traceback.print_exc()

    def on_auto_connect_config_changed(self):
        """自动连接配置输入变化 - 自动保存"""
        # 实时更新配置
        self.auto_connect_device_name = self.auto_connect_name_input.text().strip()
        self.auto_connect_mac_address = self.auto_connect_mac_input.text().strip()
        
        # 自动保存配置（延迟500ms，避免频繁保存）
        if hasattr(self, '_save_timer'):
            self._save_timer.stop()
        else:
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self.save_auto_connect_config)
        
        self._save_timer.start(500)  # 500ms后保存

    def on_retry_interval_changed(self, value):
        """重试间隔变化"""
        try:
            # 更新间隔（转换为毫秒）
            new_interval = int(value * 1000)
            self.auto_connect_retry_interval = new_interval
            
            # 如果定时器正在运行，重启以应用新间隔
            if self.auto_connect_timer.isActive():
                self.auto_connect_timer.stop()
                self.auto_connect_timer.start(self.auto_connect_retry_interval)
                self.blue_write_log(f"⏰ 重试间隔已更新: {value}秒")
            
            # 自动保存配置
            self.save_auto_connect_config()
            
        except Exception as e:
            self.blue_write_log(f"更新重试间隔失败: {str(e)}")
            traceback.print_exc()

    def save_auto_connect_config(self, show_message=False):
        """保存自动连接配置到JSON文件
        
        Args:
            show_message: 是否显示保存成功的消息（手动保存时显示，自动保存时不显示）
        """
        try:
            config = {
                'enabled': self.auto_connect_enabled,
                'device_name': self.auto_connect_name_input.text().strip(),
                'mac_address': self.auto_connect_mac_input.text().strip(),
                'retry_interval': self.auto_connect_retry_interval / 1000  # 保存为秒
            }
            
            config_file = os.path.join(os.getcwd(), 'auto_connect_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            if show_message:
                self.blue_write_log(f"✅ 自动连接配置已保存: {config_file}")

            self.blue_write_log(f"自动连接配置已保存: {config}")
            
        except Exception as e:
            self.blue_write_log(f"保存配置失败: {str(e)}")
            traceback.print_exc()

    def load_auto_connect_config(self):
        """从JSON文件加载自动连接配置"""
        try:
            config_file = os.path.join(os.getcwd(), 'auto_connect_config.json')
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                self.auto_connect_enabled = config.get('enabled', False)
                self.auto_connect_device_name = config.get('device_name', '')
                self.auto_connect_mac_address = config.get('mac_address', '')

                # 加载重试间隔（转换为毫秒）
                retry_interval_sec = config.get('retry_interval', 5.0)
                self.auto_connect_retry_interval = int(retry_interval_sec * 1000)

                # 延迟加载UI配置（等待UI初始化完成）
                QTimer.singleShot(200, lambda: self._apply_loaded_config(config))

                self.blue_write_log(f"已加载自动连接配置: {config}")
            else:
                self.blue_write_log("未找到自动连接配置文件，使用默认配置")
                
        except Exception as e:
            self.blue_write_log(f"加载配置失败: {str(e)}")
            traceback.print_exc()

    def _apply_loaded_config(self, config):
        """应用加载的配置到UI"""
        try:
            # 阻止信号触发
            self.auto_connect_checkbox.blockSignals(True)
            self.auto_connect_name_input.blockSignals(True)
            self.auto_connect_mac_input.blockSignals(True)
            self.auto_connect_interval_spinbox.blockSignals(True)
            
            # 设置UI值
            self.auto_connect_checkbox.setChecked(config.get('enabled', False))
            self.auto_connect_name_input.setText(config.get('device_name', ''))
            self.auto_connect_mac_input.setText(config.get('mac_address', ''))
            self.auto_connect_interval_spinbox.setValue(config.get('retry_interval', 5.0))
            
            # 恢复信号
            self.auto_connect_checkbox.blockSignals(False)
            self.auto_connect_name_input.blockSignals(False)
            self.auto_connect_mac_input.blockSignals(False)
            self.auto_connect_interval_spinbox.blockSignals(False)
            
            self.blue_write_log(f"📋 已加载自动连接配置: {config.get('device_name', '')} (间隔: {config.get('retry_interval', 5.0)}秒)")
            
            # 如果启用了自动连接，启动定时器（不立即连接，让初始化完成）
            if self.auto_connect_enabled and config.get('device_name'):
                self.blue_write_log(f"🔄 自动连接已启用，将在扫描后自动连接...")
                # 延迟启动定时器，避免与初始扫描冲突
                QTimer.singleShot(2000, self.start_auto_connect_timer)
                
        except Exception as e:
            self.blue_write_log(f"应用配置失败: {str(e)}")
            traceback.print_exc()

    async def auto_scan_and_connect(self):
        """自动扫描并连接设备"""
        # 检查连接锁
        if not self.connection_manager.acquire_connection_lock():
            self.blue_write_log("⏳ 已有连接任务在执行，跳过")
            return
        
        try:
            self.is_auto_scanning = True  # 标记为自动扫描
            self.blue_write_log("🔍 开始自动扫描设备...")
            
            # 执行扫描
            await self.scan_devices()
            
            # 等待扫描完成
            await asyncio.sleep(0.5)
            
            # 尝试自动连接
            if self.auto_connect_enabled:
                await self.try_auto_connect()
                
        except Exception as e:
            self.blue_write_log(f"自动扫描连接失败: {str(e)}")
            traceback.print_exc()
        finally:
            self.connection_manager.release_connection_lock()  # 释放连接锁
            self.is_auto_scanning = False  # 清除自动扫描标志

    async def _try_connect_after_scan(self):
        """扫描后尝试连接（带连接锁管理）"""
        try:
            await self.try_auto_connect()
        finally:
            self.connection_manager.release_connection_lock()

    async def try_auto_connect(self):
        """尝试自动连接匹配的设备"""
        try:
            target_name = self.auto_connect_device_name
            target_mac = self.auto_connect_mac_address
            
            if not target_name:
                self.blue_write_log("⚠️ 未配置目标设备名称")
                return
            
            self.blue_write_log(f"🔍 查找目标设备: 名称={target_name}, MAC={target_mac if target_mac else '任意'}")
            
            # 查找匹配的设备
            matched_device = None
            for i in range(self.device_list.count()):
                item_text = self.device_list.item(i).text()
                device_name = item_text.split(' (RSSI:')[0]
                device_address = self.device_name_to_address.get(device_name)
                
                # 检查名称匹配
                name_match = (device_name == target_name)
                
                # 检查MAC地址匹配（如果配置了MAC）
                mac_match = True
                if target_mac:
                    mac_match = (device_address and device_address.upper() == target_mac.upper())
                
                if name_match and mac_match:
                    matched_device = (device_name, device_address, i)
                    self.blue_write_log(f"✅ 找到匹配设备: {device_name} ({device_address})")
                    break
                elif name_match and not mac_match:
                    self.blue_write_log(f"⚠️ 发现同名设备但MAC不匹配: {device_name} ({device_address}) != {target_mac}")
                    self.blue_write_log(f"设备MAC不匹配: 扫描到={device_address}, 期望={target_mac}")
            
            if matched_device:
                device_name, device_address, item_index = matched_device
                
                # 检查是否已经连接到该设备
                if self.client and self.client.is_connected:
                    self.blue_write_log(f"✅ 已连接到设备，跳过重复连接")
                    return
                
                # 选中设备并连接
                self.device_list.setCurrentRow(item_index)
                self.blue_write_log(f"自动连接: 设备={device_name}, MAC={device_address}, 时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # 连接前等待一下，避免快速重复连接
                await asyncio.sleep(0.3)
                await self.connect_device(is_auto=True)  # 标记为自动连接
            else:
                self.blue_write_log(f"❌ 未找到匹配的设备: {target_name}")
                self.blue_write_log(f"自动连接失败: 未找到设备 {target_name}")
                
        except Exception as e:
            self.blue_write_log(f"自动连接失败: {str(e)}")
            traceback.print_exc()

    async def auto_reconnect(self):
        """自动重连"""
        # 检查是否正在连接
        if self.connection_manager.is_connecting:
            self.blue_write_log("⏳ 已有连接任务在执行，跳过重连")
            self.is_auto_reconnecting = False
            return
            
        try:
            self.blue_write_log("🔄 开始自动重连...")
            self.blue_write_log(f"开始自动重连: 时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 执行自动扫描和连接
            await self.auto_scan_and_connect()
            
            # 重置重连标志
            self.is_auto_reconnecting = False
            
        except Exception as e:
            self.blue_write_log(f"自动重连失败: {str(e)}")
            self.is_auto_reconnecting = False
            traceback.print_exc()

    def start_auto_connect_timer(self):
        """启动自动连接定时器"""
        try:
            if not self.auto_connect_timer.isActive():
                self.auto_connect_timer.start(self.auto_connect_retry_interval)
                self.blue_write_log(f"⏰ 自动连接定时器已启动 (间隔: {self.auto_connect_retry_interval/1000}秒)")
        except Exception as e:
            self.blue_write_log(f"启动定时器失败: {str(e)}")
            traceback.print_exc()

    def stop_auto_connect_timer(self):
        """停止自动连接定时器"""
        try:
            if self.auto_connect_timer.isActive():
                self.auto_connect_timer.stop()
                self.blue_write_log("⏹️ 自动连接定时器已停止")
        except Exception as e:
            self.blue_write_log(f"停止定时器失败: {str(e)}")
            traceback.print_exc()

    def on_auto_connect_timer(self):
        """定时器触发 - 尝试自动连接"""
        try:
            # 检查是否已经连接
            if self.client and self.client.is_connected:
                self.blue_write_log("✅ 设备已连接，停止自动连接定时器")
                self.stop_auto_connect_timer()
                return
            
            # 检查串口是否已连接
            if self.serial_port and self.serial_port.is_open:
                self.blue_write_log("✅ 串口已连接，停止自动连接定时器")
                self.stop_auto_connect_timer()
                return
            
            # 检查是否启用自动连接
            if not self.auto_connect_enabled:
                self.stop_auto_connect_timer()
                return
            
            # 检查是否正在连接中
            if self.connection_manager.is_connecting:
                self.blue_write_log("⏳ 正在连接中，跳过本次尝试")
                return
            
            # 触发扫描和连接
            current_time = datetime.now().strftime("%H:%M:%S")
            self.blue_write_log(f"🔍 [{current_time}] 定时器触发 - 尝试自动连接...")
            asyncio.create_task(self.auto_scan_and_connect())
            
        except Exception as e:
            self.blue_write_log(f"定时器回调失败: {str(e)}")
            traceback.print_exc()

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
            widgets.pushButton.clicked.connect(self.show_bluetooth_tool_on_top)
            widgets.pushButton_6.clicked.connect(self.disconnect_device)
            # widgets.pushButton_2.clicked.connect()

            # 分配监控按钮
            widgets.pushButton_4.clicked.connect(self.start_scan_task)

            # 分配版本号查询按钮
            widgets.pushButton_7.clicked.connect(self.bluetooth_tool.send_find_version_cmd)

            widgets.mainWindowTextEdit.clear()
            widgets.mainWindowTextEdit.setReadOnly(True)
            widgets.mainWindowTextEdit.setFontFamily("Courier New")  # 使用等宽字体
            widgets.mainWindowTextEdit.hide()


            # 初始化电池状态查询
            widgets.pushButton_5.clicked.connect(self.bluetooth_tool.send_tbs_cmd)

            # 数据解析和显示已由data_display_mgr内部处理，不需要信号连接


            # 初始化结构体模型列表 到csv文件
            self.struct_list = self.bluetooth_tool.hex_parser.get_struct_name_list()
            ComunManager.get_instance(self.struct_list)

            # 连接按钮信号
            # widgets.pushButton.clicked.connect(self.close)  # 假设 pushButton 是一个关闭按钮
            self.bluetooth_tool.blue_write_log(f"UI文件 {ui_file} 加载成功")

            # ============== 使用DataDisplayManager统一管理显示窗口 ==============
            self.setFixedSize(1150, 600)  # 设置主窗口大小

            # 创建数据显示管理器（嵌入模式）
            self.data_display_mgr = DataDisplayManager(
                parent=None,
                logger=self.logger,
                standalone=False
            )

            # ⭐ 将data_display_mgr传递给bluetooth_tool，使其能使用统一的解析功能
            if hasattr(self, 'bluetooth_tool'):
                self.bluetooth_tool.data_display_mgr = self.data_display_mgr
                self.bluetooth_tool.blue_write_log("✅ 已将data_display_mgr传递给bluetooth_tool")

            # 创建所有显示窗口
            self.data_display_mgr.create_windows(parent_widget=self)

            # 设置窗口位置和大小
            self.data_display_mgr.setup_windows_geometry(
                battery_geom=(150, 10, 580, 580),    # battery_window: x, y, width, height
                bit_geom=(740, 10, 390, 580)  # bit_window: x, y, width, height
            )

            # 显示所有窗口
            self.data_display_mgr.show_windows()

            # 获取内部组件引用（为了兼容性）
            self.battery_window = self.data_display_mgr.battery_window_manager.widget if self.data_display_mgr.battery_window_manager else None
            self.bit_window = self.data_display_mgr.bit_window_manager.widget if self.data_display_mgr.bit_window_manager else None
            self.battery_table_model = self.data_display_mgr.battery_window_manager.table_model if self.data_display_mgr.battery_window_manager else None
            self.command_info_label = None  # 标签已在manager内部管理

            # 连接发送按钮信号（从管理器内部获取按钮）
            if self.data_display_mgr.battery_window_manager:
                self.data_display_mgr.battery_window_manager.send_button.clicked.connect(self.send_modified_values)
                self.data_display_mgr.battery_window_manager.clear_button.clicked.connect(self.clear_modified_values)

            # 保留原有的标签列表（为了兼容性）
            self.key_label_list = []
            self.value_label_list = []

            self.bluetooth_tool.blue_write_log("✅ 数据显示管理器初始化成功（battery_window + bit_window + 数据解析）")

        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"加载UI文件失败: {e}")
            traceback.print_exc()
            # return None

    # ============== 位标志显示相关方法（委托给BitFlagsWidget）==============
    def update_status_bits(self, status_list):
        """更新位标志（供外部调用）- 委托给位标志组件"""
        if hasattr(self, 'bit_window'):
            self.bit_window.update_status_bits(status_list)

    def update_single_status_bit(self, index, name, value):
        """更新单个位标志 - 委托给位标志组件"""
        if hasattr(self, 'bit_window'):
            self.bit_window.update_single_status_bit(index, name, value)

    # visualize_bit_flags 已删除，由 data_display_mgr 内部处理
    def show_bluetooth_tool_on_top(self):
        """显示蓝牙工具窗口并将其置顶"""
        self.bluetooth_tool.show()
        self.bluetooth_tool.raise_()  # 将窗口提升到最前面
        self.bluetooth_tool.activateWindow()  # 激活窗口

    def disconnect_device(self):
        """断开连接"""
        if self.scan_task:
            self.start_scan_task() # 停止监控

        self.bluetooth_tool.on_disconnect_device_clicked()
        
        # 主窗口断开时也取消自动连接勾选
        if self.bluetooth_tool.auto_connect_enabled:
            self.bluetooth_tool.auto_connect_checkbox.setChecked(False)
            self.bluetooth_tool.auto_connect_enabled = False
            self.bluetooth_tool.stop_auto_connect_timer()
            self.bluetooth_tool.save_auto_connect_config()  # 保存配置
            self.bluetooth_tool.blue_write_log("ℹ️ 主窗口断开，已自动取消自动连接")



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

    # get_dict_from_receive_data 已删除，由 data_display_mgr 内部处理
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
                self.bluetooth_tool.blue_write_log("程序关闭")
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
        """获取修改的值并发送到设备（使用DataDisplayManager）"""
        try:
            self.bluetooth_tool.blue_write_log("=== 开始发送修改值流程 ===")

            # ⭐ 使用管理器的统一接口获取修改数据
            modified_data = self.data_display_mgr.get_modified_values() if hasattr(self, 'data_display_mgr') else []

            # 兼容性：如果管理器不可用，尝试直接使用模型
            if not modified_data and hasattr(self, 'battery_table_model'):
                modified_data = self.battery_table_model.get_modified_data()

            if not modified_data:
                self.bluetooth_tool.blue_write_log("没有需要发送的修改值")
                self.bluetooth_tool.blue_write_log("没有需要发送的修改值")
                return []

            self.bluetooth_tool.blue_write_log(f"检测到 {len(modified_data)} 个修改值")

            # 检查当前数据来源
            if not self.current_data_source:
                self.bluetooth_tool.blue_write_log("错误：无法确定当前数据来源")
                self.bluetooth_tool.blue_write_log("错误：无法确定当前数据来源")
                return []

            self.bluetooth_tool.blue_write_log(f"当前数据来源: {self.current_data_source}")

            # 检查是否可以写入
            if not can_command_be_written(self.current_data_source):
                self.bluetooth_tool.blue_write_log(f"错误：命令 {self.current_data_source} 不支持写入")
                self.bluetooth_tool.blue_write_log(f"错误：命令 {self.current_data_source} 不支持写入")
                return []

            # 获取写入命令名称和代码
            write_cmd_name = get_write_command_from_read(self.current_data_source)
            write_cmd_code = get_write_command_code(self.current_data_source)
            if write_cmd_code is None:
                self.bluetooth_tool.blue_write_log(f"错误：无法获取 {self.current_data_source} 的写入命令代码")
                self.bluetooth_tool.blue_write_log(f"错误：无法获取 {self.current_data_source} 的写入命令代码")
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
                self.bluetooth_tool.blue_write_log(f"错误：无法获取 {self.current_data_source} 的格式信息")
                return []

            self.bluetooth_tool.blue_write_log(f"数据格式: {format_string}")
            self.bluetooth_tool.blue_write_log(f"变量数量: {len(variables)}")

            # 创建值数组，初始化为当前值
            values = []
            self.bluetooth_tool.blue_write_log("开始构造数据包:")

            for i, var_name in enumerate(variables):
                current_hex_value = self.battery_table_model._original_data[i][1] if i < len(self.battery_table_model._original_data) else '0x00'

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
                        self.bluetooth_tool.blue_write_log(f"  {var_name}: {current_hex_value} -> {modified_value} (0x{int_value:X})")
                    except ValueError as e:
                        self.bluetooth_tool.blue_write_log(f"  警告：无法解析 {var_name} 的值 '{modified_value}' ({e})，使用当前值")
                        self.bluetooth_tool.blue_write_log(f"  警告：无法解析 {var_name} 的值 '{modified_value}' ({e})，使用当前值")
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
                self.bluetooth_tool.blue_write_log(f"数据打包成功，共 {len(packed_binary_data)} 字节")

                # 使用 send_hex_fill 发送数据
                send_data = self.bluetooth_tool.text_decode.send_hex_fill(write_cmd_code, packed_binary_data)
                self.bluetooth_tool.blue_write_log(f"构造发送数据包: {send_data.hex()}")
                self.bluetooth_tool.blue_write_log(f"发送数据: {send_data.hex()}")

                # 异步发送数据
                async def send_data_async():
                    try:
                        self.bluetooth_tool.blue_write_log("开始发送数据包...")
                        await self.bluetooth_tool.byte_send(send_data)
                        self.bluetooth_tool.display_send_data(send_data)
                        self.bluetooth_tool.blue_write_log("数据发送成功")
                        self.bluetooth_tool.blue_write_log("数据发送成功")

                        # 更新BitWindow显示发送成功
                        self.command_info_label.setText(f"发送成功: {self.current_data_source} → {write_cmd_name}")
                        self.command_info_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")

                        # 发送成功后清空修改值
                        self.bit_table_model.clear_write_values()

                    except Exception as e:
                        self.bluetooth_tool.blue_write_log(f"数据发送失败: {e}")
                        self.bluetooth_tool.blue_write_log(f"数据发送失败: {e}")
                        traceback.print_exc()

                        # 更新BitWindow显示发送失败
                        self.command_info_label.setText(f"发送失败: {self.current_data_source} → {write_cmd_name}")
                        self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")

                # 使用 asyncio 创建任务
                asyncio.create_task(send_data_async())

                return modified_data

            except struct.error as e:
                self.bluetooth_tool.blue_write_log(f"数据打包失败: {e}")
                self.bluetooth_tool.blue_write_log(f"数据打包失败: {e}")

                # 更新BitWindow显示打包失败
                if hasattr(self, 'command_info_label') and self.command_info_label:
                    self.command_info_label.setText(f"打包失败: {self.current_data_source}")
                    self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
                return []

        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"发送修改值失败: {e}")
            self.bluetooth_tool.blue_write_log(f"发送修改值失败: {e}")
            traceback.print_exc()

            # 更新BitWindow显示流程失败
            if hasattr(self, 'command_info_label') and self.command_info_label:
                self.command_info_label.setText(f"流程失败: {self.current_data_source if self.current_data_source else '无'}")
                self.command_info_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            return []

    def clear_modified_values(self):
        """清空所有修改的写入值（使用DataDisplayManager）"""
        try:
            # ⭐ 使用管理器的统一接口清空修改值
            if hasattr(self, 'data_display_mgr'):
                self.data_display_mgr.clear_bit_write_values()
                self.bluetooth_tool.blue_write_log("✅ 已清空所有修改值（通过管理器）")
            elif hasattr(self, 'battery_table_model'):
                # 兼容性：如果管理器不可用，直接使用模型
                self.battery_table_model.clear_write_values()
                self.bluetooth_tool.blue_write_log("已清空所有修改值")
        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"清空修改值失败: {e}")
            traceback.print_exc()

    def set_write_value_by_name(self, param_name, value):
        """根据参数名设置写入值"""
        try:
            row = self.battery_table_model.find_row_by_name(param_name)
            if row >= 0:
                return self.battery_table_model.set_write_value(row, value)
            else:
                self.bluetooth_tool.blue_write_log(f"未找到参数: {param_name}")
                return False
        except Exception as e:
            self.bluetooth_tool.blue_write_log(f"设置写入值失败: {e}")
            return False


# ============== 简化版蓝牙连接窗口 ==============
class SimplifiedBluetoothTool(QWidget):
    """简化版蓝牙连接窗口 - 复用原窗口的核心功能"""
    
    def __init__(self, bluetooth_tool):
        super().__init__()
        
        # 复用原窗口的核心功能（共享连接状态）
        self.bluetooth_tool = bluetooth_tool
        
        # 直接引用原窗口的属性（而不是创建新的）
        self.client = bluetooth_tool.client
        self.serial_port = bluetooth_tool.serial_port
        self.device_name_to_address = bluetooth_tool.device_name_to_address
        
        # 初始化简化UI
        self.initSimplifiedUI()
        
        # 设置窗口属性：无边框、置顶、Window类型（能接收焦点）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window  # 使用Window类型，能够接收焦点事件
        )
        
        # 设置焦点策略，确保窗口能获得焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)  # 显示时激活窗口
        
        # 安装事件过滤器，监听全局鼠标点击
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)
        
    def initSimplifiedUI(self):
        """初始化简化UI"""
        self.setWindowTitle('蓝牙/串口连接')
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # 蓝牙和串口水平布局
        connection_layout = QHBoxLayout()
        
        # ========== 左侧：蓝牙 ==========
        bluetooth_layout = QVBoxLayout()
        bluetooth_title = QLabel('蓝牙连接')
        bluetooth_title.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        bluetooth_layout.addWidget(bluetooth_title)
        
        # 直接使用原窗口的设备列表
        self.device_list = self.bluetooth_tool.device_list
        self.device_list.setMinimumHeight(175)
        bluetooth_layout.addWidget(self.device_list)
        
        # 保存布局引用，用于后续动态添加/移除device_list
        self.simplified_bluetooth_layout = bluetooth_layout
        self.device_list_position = bluetooth_layout.count() - 1
        
        # 使用原窗口的RSSI筛选输入
        rssi_layout = QHBoxLayout()
        rssi_layout.addWidget(QLabel('RSSI >:'))
        self.rssi_threshold_input = self.bluetooth_tool.rssi_threshold_input
        self.rssi_threshold_input.setMaximumWidth(60)
        rssi_layout.addWidget(self.rssi_threshold_input)
        rssi_layout.addStretch()
        bluetooth_layout.addLayout(rssi_layout)
        
        # 使用原窗口的连接/断开按钮（现在是一个按钮）
        self.bt_connect_button = self.bluetooth_tool.bt_connect_button
        bluetooth_layout.addWidget(self.bt_connect_button)
        
        # 使用原窗口的蓝牙状态标签
        self.bluetooth_status_label = self.bluetooth_tool.bluetooth_status_label
        bluetooth_layout.addWidget(self.bluetooth_status_label)
        
        # 自动连接配置（复用原窗口的控件）
        auto_layout = QVBoxLayout()
        auto_title = QLabel('自动连接')
        auto_title.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        auto_layout.addWidget(auto_title)
        
        self.auto_connect_checkbox = self.bluetooth_tool.auto_connect_checkbox
        auto_layout.addWidget(self.auto_connect_checkbox)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('名称:'))
        self.auto_connect_name_input = self.bluetooth_tool.auto_connect_name_input
        self.auto_connect_name_input.setMaximumWidth(120)
        name_layout.addWidget(self.auto_connect_name_input)
        auto_layout.addLayout(name_layout)
        
        mac_layout_simple = QHBoxLayout()
        mac_layout_simple.addWidget(QLabel('MAC:'))
        self.auto_connect_mac_input = self.bluetooth_tool.auto_connect_mac_input
        self.auto_connect_mac_input.setMaximumWidth(120)
        mac_layout_simple.addWidget(self.auto_connect_mac_input)
        auto_layout.addLayout(mac_layout_simple)
        
        # 重试间隔设置
        interval_layout_simple = QHBoxLayout()
        interval_layout_simple.addWidget(QLabel('间隔(秒):'))
        self.auto_connect_interval_spinbox = self.bluetooth_tool.auto_connect_interval_spinbox
        self.auto_connect_interval_spinbox.setMaximumWidth(60)
        interval_layout_simple.addWidget(self.auto_connect_interval_spinbox)
        auto_layout.addLayout(interval_layout_simple)
        
        # 提示标签
        auto_save_hint_simple = QLabel('💡 自动保存')
        auto_save_hint_simple.setStyleSheet("QLabel { color: #666; font-size: 9px; }")
        auto_layout.addWidget(auto_save_hint_simple)
        
        bluetooth_layout.addLayout(auto_layout)
        
        # ========== 右侧：串口 ==========
        serial_layout = QVBoxLayout()
        serial_title = QLabel('串口连接')
        serial_title.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        serial_layout.addWidget(serial_title)
        
        # 使用原窗口的串口参数控件
        param_grid = QGridLayout()
        param_grid.setSpacing(3)
        
        self.port_combo = self.bluetooth_tool.port_combo
        self.baud_combo = self.bluetooth_tool.baud_combo
        self.data_bits_combo = self.bluetooth_tool.data_bits_combo
        self.stop_bits_combo = self.bluetooth_tool.stop_bits_combo
        self.parity_combo = self.bluetooth_tool.parity_combo
        
        param_grid.addWidget(QLabel('串口:'), 0, 0)
        param_grid.addWidget(self.port_combo, 0, 1)
        param_grid.addWidget(QLabel('波特率:'), 1, 0)
        param_grid.addWidget(self.baud_combo, 1, 1)
        param_grid.addWidget(QLabel('数据位:'), 2, 0)
        param_grid.addWidget(self.data_bits_combo, 2, 1)
        param_grid.addWidget(QLabel('停止位:'), 3, 0)
        param_grid.addWidget(self.stop_bits_combo, 3, 1)
        param_grid.addWidget(QLabel('校验位:'), 4, 0)
        param_grid.addWidget(self.parity_combo, 4, 1)
        
        serial_layout.addLayout(param_grid)
        
        # 使用原窗口的串口连接按钮
        self.serial_connect_button = self.bluetooth_tool.serial_connect_button
        serial_layout.addWidget(self.serial_connect_button)
        
        serial_layout.addStretch()
        
        connection_layout.addLayout(bluetooth_layout, 1)
        connection_layout.addLayout(serial_layout, 1)
        main_layout.addLayout(connection_layout)
        
        # ========== 扫描按钮 ==========
        self.scan_button = self.bluetooth_tool.scan_button
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        main_layout.addWidget(self.scan_button)
        
        # ========== 连接测试按钮和状态指示灯 ==========
        test_layout = QHBoxLayout()
        test_layout.setSpacing(5)
        
        # 使用原窗口的注册按钮，改名为"连接测试"
        self.register_button = self.bluetooth_tool.register_button
        self.register_button.setText('连接测试')
        test_layout.addWidget(self.register_button)
        
        # 使用原窗口的状态指示灯
        self.status_indicator = self.bluetooth_tool.status_indicator
        test_layout.addWidget(self.status_indicator)
        
        test_layout.addStretch()
        main_layout.addLayout(test_layout)
        
        # ========== 充放电控制（横排紧凑）==========
        charge_discharge_layout = QHBoxLayout()
        charge_discharge_layout.setSpacing(3)

        # 使用原窗口的充放电按钮
        self.open_charge_button = self.bluetooth_tool.open_charge_button
        self.close_charge_button = self.bluetooth_tool.close_charge_button
        self.open_discharge_button = self.bluetooth_tool.open_discharge_button
        self.close_discharge_button = self.bluetooth_tool.close_discharge_button

        for btn in [self.open_charge_button, self.close_charge_button, 
                    self.open_discharge_button, self.close_discharge_button]:
            btn.setMaximumWidth(90)

        charge_discharge_layout.addWidget(self.open_charge_button)
        charge_discharge_layout.addWidget(self.close_charge_button)
        charge_discharge_layout.addWidget(self.open_discharge_button)
        charge_discharge_layout.addWidget(self.close_discharge_button)

        main_layout.addLayout(charge_discharge_layout)

        # ========== 保电控制（横排紧凑）==========
        store_power_layout = QHBoxLayout()
        store_power_layout.setSpacing(3)

        # 使用原窗口的保电按钮
        self.open_store_power_button = self.bluetooth_tool.open_store_power_button
        self.close_store_power_button = self.bluetooth_tool.close_store_power_button

        for btn in [self.open_store_power_button, self.close_store_power_button]:
            btn.setMaximumWidth(90)

        store_power_layout.addWidget(self.open_store_power_button)
        store_power_layout.addWidget(self.close_store_power_button)

        main_layout.addLayout(store_power_layout)

        # ========== 关机控制 ==========
        shutdown_layout = QHBoxLayout()
        self.shutdown_button = self.bluetooth_tool.shutdown_button
        shutdown_layout.addWidget(self.shutdown_button)
        main_layout.addLayout(shutdown_layout)

        # ========== 加热模式控制 ==========
        heating_layout = QVBoxLayout()
        heating_title = QLabel('加热模式')
        heating_title.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        heating_layout.addWidget(heating_title)

        heating_buttons_layout = QHBoxLayout()
        heating_buttons_layout.setSpacing(3)

        # 使用原窗口的加热模式按钮
        self.self_heating_button = self.bluetooth_tool.self_heating_button
        self.charger_heating_button = self.bluetooth_tool.charger_heating_button

        for btn in [self.self_heating_button, self.charger_heating_button]:
            btn.setMaximumWidth(140)

        heating_buttons_layout.addWidget(self.self_heating_button)
        heating_buttons_layout.addWidget(self.charger_heating_button)

        heating_layout.addLayout(heating_buttons_layout)
        main_layout.addLayout(heating_layout)
        
        self.setLayout(main_layout)
        self.setFixedSize(520, 630)  # 增加高度以容纳自动连接配置和重试间隔
    
    def focusOutEvent(self, event):
        """失去焦点时隐藏（点击窗口外部）"""
        # print(f"[简化窗口] focusOutEvent 被触发")
        # 延迟检查，给下拉框时间展开（可能点击的就是下拉框）
        # print(f"[简化窗口]   延迟150ms检查是否隐藏")
        QTimer.singleShot(150, self._check_and_hide)
        super().focusOutEvent(event)
    
    def _check_and_hide(self):
        """延迟检查并隐藏（用于下拉框情况）"""
        # print(f"[简化窗口] _check_and_hide 被调用")
        from PyQt6.QtWidgets import QComboBox
        from PyQt6.QtGui import QCursor
        
        # 检查鼠标是否回到窗口内
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(cursor_pos):
            # print(f"[简化窗口]   鼠标在窗口内，取消隐藏")
            return
        
        # 检查下拉框是否展开
        for combo in self.findChildren(QComboBox):
            if combo.view().isVisible():
                # print(f"[简化窗口]   下拉框展开中，取消隐藏")
                return
        
        # 下拉框已关闭且鼠标不在窗口内，隐藏窗口
        # print(f"[简化窗口]   可以隐藏，执行隐藏")
        self.hide()
    
    def showEvent(self, event):
        """窗口显示事件"""
        # print(f"[简化窗口] showEvent - 窗口被显示")
        # 把device_list添加到简化窗口的布局中
        if self.device_list.parent() != self:
            # 从当前父级移除
            current_parent = self.device_list.parent()
            if current_parent:
                layout = current_parent.layout()
                if layout:
                    layout.removeWidget(self.device_list)
            # 添加到简化窗口的布局
            self.simplified_bluetooth_layout.insertWidget(self.device_list_position, self.device_list)
        super().showEvent(event)
    
    def hideEvent(self, event):
        """窗口隐藏事件"""
        # print(f"[简化窗口] hideEvent - 窗口被隐藏")
        super().hideEvent(event)
    
    def focusInEvent(self, event):
        """简化窗口获得焦点"""
        # print(f"[简化窗口] focusInEvent - 获得焦点")
        super().focusInEvent(event)
    
    def enterEvent(self, event):
        """鼠标进入窗口"""
        # print(f"[简化窗口] enterEvent - 鼠标进入")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开窗口"""
        # print(f"[简化窗口] leaveEvent - 鼠标离开")
        super().leaveEvent(event)
    
    def eventFilter(self, obj, event):
        """全局事件过滤器：监听鼠标点击"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtWidgets import QComboBox
        
        # 只在窗口可见时处理
        if not self.isVisible():
            return super().eventFilter(obj, event)
        
        # 监听鼠标按下事件
        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = event
            # 获取全局坐标
            global_pos = mouse_event.globalPosition().toPoint()
            # 转换为窗口坐标
            local_pos = self.mapFromGlobal(global_pos)
            
            # 判断点击是否在窗口外
            if not self.rect().contains(local_pos):
                # print(f"[简化窗口] eventFilter - 检测到窗口外点击")
                
                # 检查是否点击在下拉框的弹出列表上
                for combo in self.findChildren(QComboBox):
                    combo_view = combo.view()
                    if combo_view.isVisible():
                        # 获取下拉框弹出列表的几何信息
                        view_geo = combo_view.geometry()
                        view_global_pos = combo_view.mapToGlobal(view_geo.topLeft())
                        view_rect = view_geo
                        view_rect.moveTo(view_global_pos)
                        
                        # 判断点击是否在下拉列表上
                        if view_rect.contains(global_pos):
                            # print(f"[简化窗口]   点击在下拉列表上，不隐藏")
                            return super().eventFilter(obj, event)
                        
                        # 下拉框展开，但点击不在列表上，延迟处理
                        # print(f"[简化窗口]   下拉框展开中，延迟检查")
                        QTimer.singleShot(100, self._check_and_hide)
                        return super().eventFilter(obj, event)
                
                # 没有下拉框展开，直接隐藏
                # print(f"[简化窗口]   没有下拉框，隐藏窗口")
                self.hide()
                return False
        
        return super().eventFilter(obj, event)
    


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

