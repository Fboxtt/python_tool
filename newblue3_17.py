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
    QCheckBox, QFileDialog, QComboBox, QGridLayout, QMainWindow, QSplashScreen, QSizePolicy
)
from PyQt6.QtCore import Qt
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
from struct_model import HexParserApp

from ui_main import Ui_Form
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
        self.baud_combo.addItems(['9600', '18000','18600', '19200', '38400', '57600', '115200'])
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
                except ValueError as e:
                    QMessageBox.warning(self, '警告', '无效的16进制数据')
                    return
            else:
                # 文本发送
                data_bytes = input_data.encode()

            await self.byte_send(data_bytes)
            # 显示发送的数据
            if self.hex_send_checkbox.isChecked():
                hex_data = ' '.join([f'{b:02X}' for b in data_bytes])
                self.blue_write_log(f"发送: {hex_data}")
                self.display_send_data(data_bytes)
            else:
                self.blue_write_log(f"发送: {input_data}")
                self.display_send_data(input_data)
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
            # 文本显示
            try:
                print(type(data),'|||',data)
                reve_data = data.decode('utf-8')
            except UnicodeDecodeError:
                # 如果无法解码为文本，则显示16进制
                reve_data = ' '.join([f'{b:02X}' for b in data])  
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
                try:
                    send_data = input_data.decode('utf-8')
                except UnicodeDecodeError:
                    # 如果无法解码为文本，则显示16进制
                    send_data = ' '.join([f'{b:02X}' for b in input_data])
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
            # 设置扫描时间为3秒
            devices = await BleakScanner.discover(timeout=2.0)  # 单位是秒
        except Exception as e:
            # QMessageBox.critical(self, '扫描失败', str(e))
            self.blue_write_log(f"扫描失败 {str(e)}")
            traceback.print_exc()
            return
        
        self.device_list.clear()
        for device in devices:
            # 只显示有名字且信号强度符合要求的设备
            if device.name and device.rssi > rssi_threshold:
                self.device_list.addItem(f"{device.name} - {device.address} (RSSI: {device.rssi})")
        
        self.label.setText('发现的蓝牙设备:')

    async def connect_device(self):
        """异步方法，连接蓝牙设备"""
        selected_device = self.device_list.currentItem()
        if selected_device:
            device_address = selected_device.text().split(' - ')[1].split(' (')[0]  # 提取设备地址
            try:
                self.client = BleakClient(device_address)
                await self.client.connect()
                self.commu_type = "bluetooth"
                # 创建消息框实例
                connectMessage = QMessageBox(QMessageBox.Icon.Information, '连接成功', f'已连接到 {device_address}')
                # 设置定时器自动关闭 (3000毫秒后)
                QTimer.singleShot(300, connectMessage.close)
                # 显示消息框
                connectMessage.exec()
                # 启用断开按钮和发送按钮
                self.disconnect_button.setEnabled(True)
                self.send_button.setEnabled(True)
                # 开始监听数据
                if self.client and self.client.is_connected:
                    self.device_name = selected_device.text().split(' - ')[0]
                    await self.client.start_notify("0000ffe1-0000-1000-8000-00805f9b34fb", self.on_data_received)
                QTimer.singleShot(1000, self.send_find_version_cmd)
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
    
        # 处理数据
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

widgets = None

# 修正后的函数 - 注意这是一个函数，不是类
class load_ui_dynamically(QMainWindow):
    scan_task = None
    def __init__(self, ui_file):
        super().__init__()
        try:
            # 初始化日志管理器
            self.logger = LogManager.get_instance()

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
            self.bit_window = QWidget(self)
            self.test_pushButton = QPushButton('test_hide')
            # self.test_pushButton.setGeometry(10, 10, 100, 100)
            self.bit_layout = QGridLayout()
            self.bit_layout.setVerticalSpacing(1)
            self.bit_layout.setHorizontalSpacing(10)
            self.bit_layout.addWidget(self.test_pushButton,0,0)
            self.bit_window.setLayout(self.bit_layout)
            self.key_label_list = []
            self.value_label_list = []
            self.test_pushButton.clicked.connect(self.test_open_close_bitwidows)
            self.bit_window.setWindowTitle('烧录标志位')
            self.bit_window.setGeometry(620, 10, 300, 600)
            self.bit_window.show()
        except Exception as e:
            self.logger.write_log(f"加载UI文件失败: {e}")
            traceback.print_exc()
            # return None
    def test_open_close_bitwidows(self):
        # 实际使用需要删掉
        if self.test_pushButton.text() == "test_hide":
            self.bit_window.hide()
            self.test_pushButton.setText('test_show')
        else:
            self.bit_window.show()
            self.test_pushButton.setText('test_hide')
    def visualize_bit_flags(self,data: list):
        row = 0
        clomn = 0
        try:
            for i,unit in enumerate(data):
                print(f'i = {i} len(list) = {len(self.key_label_list)} tuple = {len(unit)}',end = '')
                # print(f"len(value_label_list) = {len(self.value_label_list)}")
                print(f'row = {row} clomn = {clomn}')
                if i >= len(self.key_label_list):
                    self.key_label_list.append(QLabel(f'{unit[0]}'))
                    self.value_label_list.append(QLabel(f'{unit[2]}'))
                    self.bit_layout.addWidget(self.key_label_list[i],row,clomn)
                    self.bit_layout.addWidget(self.value_label_list[i],row,clomn+1)
                else:
                    self.key_label_list[i].setText(f'{unit[0]}')
                    self.value_label_list[i].setText(f'{unit[2]}')
                row+=1
                if row >= 30:
                    row = 0
                    clomn+=2
        except Exception as e:
            self.logger.write_log(f"bit windows写入失败: {e}")
            traceback.print_exc()
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
        self.bluetooth_tool.blue_write_log(f"{header},{dict_data}")
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

