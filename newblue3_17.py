import sys
import asyncio
import traceback
import time
from datetime import datetime

from PyQt6.QtCore import QTimer  # 导入 QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QMessageBox, QTextEdit, QLineEdit, QHBoxLayout
)
from PyQt6.QtCore import Qt
from bleak import BleakScanner, BleakClient
from qasync import QEventLoop, asyncSlot




class BluetoothTool(QWidget):
    task_flag = 0
    pass
    def __init__(self):
        super().__init__()
        self.client = None  # 当前连接的蓝牙设备
        self.initUI()
        
        # asyncio.create_task(self.scan_devices())
        QTimer.singleShot(0, self.on_scan_devices_clicked)
    def initUI(self):
        self.setWindowTitle('蓝牙查询与连接工具')

        layout = QVBoxLayout()

        # 设备扫描部分
        self.label = QLabel('发现的蓝牙设备:')
        layout.addWidget(self.label)

        self.device_list = QListWidget()
        layout.addWidget(self.device_list)

        # 信号强度筛选部分
        self.rssi_threshold_layout = QHBoxLayout()
        self.rssi_threshold_label = QLabel('信号强度筛选 (RSSI >):')
        self.rssi_threshold_input = QLineEdit()
        self.rssi_threshold_input.setText("-80")
        self.rssi_threshold_input.setPlaceholderText('例如: -70')
        self.rssi_threshold_layout.addWidget(self.rssi_threshold_label)
        self.rssi_threshold_layout.addWidget(self.rssi_threshold_input)
        layout.addLayout(self.rssi_threshold_layout)

        self.scan_button = QPushButton('扫描设备')
        self.scan_button.clicked.connect(self.on_scan_devices_clicked)
        layout.addWidget(self.scan_button)

        # 设备连接和断开部分
        self.connect_layout = QHBoxLayout()
        self.connect_button = QPushButton('连接设备')
        self.connect_button.clicked.connect(self.on_connect_device_clicked)
        self.disconnect_button = QPushButton('断开设备')
        self.disconnect_button.clicked.connect(self.on_disconnect_device_clicked)
        self.disconnect_button.setEnabled(False)  # 初始状态下断开按钮不可用
        self.connect_layout.addWidget(self.connect_button)
        self.connect_layout.addWidget(self.disconnect_button)
        layout.addLayout(self.connect_layout)

        # 数据发送部分
        self.send_layout = QHBoxLayout()
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText('输入要发送的数据')
        self.send_button = QPushButton('发送数据')
        self.send_button.clicked.connect(self.on_send_data_clicked)
        self.send_button.setEnabled(False)  # 初始状态下发送按钮不可用
        self.send_layout.addWidget(self.send_input)
        self.send_layout.addWidget(self.send_button)
        layout.addLayout(self.send_layout)

        # 测试数据发送部分

        self.test_layout = QHBoxLayout()
        self.test_send_button = QPushButton('连续发送')
        self.test128 = QLineEdit('0')
        self.test512 = QLineEdit('460')
        self.test_layout.addWidget(self.test128)
        self.test_layout.addWidget(self.test512)
        self.test_layout.addWidget(self.test_send_button)
        self.test_send_button.clicked.connect(self.on_test_send_buttoned)
        layout.addLayout(self.test_layout)

        # 数据接收部分
        self.receive_label = QLabel('接收到的数据:')
        layout.addWidget(self.receive_label)

        self.receive_output = QTextEdit()
        self.receive_output.setReadOnly(True)
        layout.addWidget(self.receive_output)

        self.setLayout(layout)

    def closeEvent(self, event):
        """重写关闭事件，退出时断开蓝牙连接"""
        if self.client and self.client.is_connected:
            asyncio.create_task(self.disconnect_device())
        event.accept()

    def on_scan_devices_clicked(self):
        """同步方法，用于触发异步扫描"""
        asyncio.create_task(self.scan_devices())

    def on_connect_device_clicked(self):
        """同步方法，用于触发异步连接"""
        asyncio.create_task(self.connect_device())

    def on_disconnect_device_clicked(self):
        """同步方法，用于触发异步断开连接"""
        asyncio.create_task(self.disconnect_device())

    def on_send_data_clicked(self):
        """同步方法，用于触发异步发送数据"""
        data = self.send_input.text()
        if data:
            asyncio.create_task(self.send_data(data))
        else:
            QMessageBox.warning(self, '警告', '请输入要发送的数据')
    def on_test_send_buttoned(self):
        """同步方法,用于测试"""
        # data = self.send_input.text()
        # if data:
        
        if self.task_flag == 1:
            self.task.cancel()
            self.task_flag = 0
            return
        self.task_flag = 1
        self.task = asyncio.create_task(self.test_send_data())
        # else:
        #     QMessageBox.warning(self, '警告', '请输入要发送的数据')

    async def scan_devices(self):
        """异步方法，扫描蓝牙设备"""
        self.device_list.clear()
        self.label.setText('正在扫描设备...')

        # 获取用户输入的信号强度阈值
        try:
            rssi_threshold = int(self.rssi_threshold_input.text())
        except ValueError:
            rssi_threshold = -100  # 默认值，显示所有设备

        devices = await BleakScanner.discover()
        self.device_list.clear()
        for device in devices:
            if device.rssi > rssi_threshold:  # 筛选信号强度大于阈值的设备
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
                QMessageBox.information(self, '连接成功', f'已连接到 {device_address}')
                # 启用断开按钮和发送按钮
                self.disconnect_button.setEnabled(True)
                self.send_button.setEnabled(True)
                # 开始监听数据
                asyncio.create_task(self.receive_data())
            except Exception as e:
                QMessageBox.critical(self, '连接失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '请先选择一个设备')

    async def disconnect_device(self):
        """异步方法，断开蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                QMessageBox.information(self, '断开成功', '设备已断开')
                # 禁用断开按钮和发送按钮
                self.disconnect_button.setEnabled(False)
                self.send_button.setEnabled(False)
                self.client = None
            except Exception as e:
                QMessageBox.critical(self, '断开失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '未连接到设备')

    async def send_data(self, data):
        """异步方法，发送数据到蓝牙设备"""
        if self.client and self.client.is_connected:
            try:
                # 假设设备的写特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data.encode())
                self.receive_output.append(f"发送: {data}")
            except Exception as e:
                QMessageBox.critical(self, '发送失败', str(e))
        else:
            QMessageBox.warning(self, '警告', '未连接到设备')

    async def test_send_data(self):
        """异步方法，发送测试数据"""
        data = bytes(128)
        time128 = int(self.test128.text()) / 1000
        time512 = int(self.test512.text()) / 1000
        self.send_count = 0
        # print(data,f"size(data) = {len(data)}")
        while 1:
            time128 = int(self.test128.text()) / 1000
            time512 = int(self.test512.text()) / 1000
            if self.client and self.client.is_connected:
                try:
                    # 假设设备的写特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    time.sleep(time128)
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    time.sleep(time128)
                    # await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    # time.sleep(time128)
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    time.sleep(time512)
                    self.send_count += 1
                    if self.send_count > 10:                        
                        cursor = self.receive_output.textCursor()  # 获取 QTextCursor
                        cursor.movePosition(cursor.MoveOperation.Start)  # 移动到文档开头
                        cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)  # 选中首行
                        cursor.removeSelectedText()  # 删除选中文本
                        cursor.deleteChar()  # 删除换行符
                    current_time = datetime.now().strftime("%d %H:%M:%S")[:18]  # 格式化并限制长度到毫秒
                    self.receive_output.append(f"成功发送次数 = {self.send_count} 发送时间 = {current_time}")
                    # self.receive_output.append(f"发送: {data}")
                except Exception as e:
                    traceback.print_exc()
                    self.receive_output.append(f"蓝牙发送失败 {str(e)}")
                    QMessageBox.critical(self, '发送失败', str(e))
                    break
            else:
                # QMessageBox.warning(self, '警告', '未连接到设备')
                break

    async def receive_data(self):
        """异步方法，接收蓝牙设备发送的数据"""
        if self.client and self.client.is_connected:
            try:
                # 假设设备的通知特征 UUID 是 "0000ffe1-0000-1000-8000-00805f9b34fb"
                await self.client.start_notify("0000ffe1-0000-1000-8000-00805f9b34fb", self.on_data_received)
            except Exception as e:
                QMessageBox.critical(self, '接收失败', str(e))

    def on_data_received(self, sender, data):
        """回调函数，处理接收到的数据"""
        self.receive_output.append(f"接收: {data.decode()}")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 使用 qasync 创建事件循环
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tool = BluetoothTool()
    tool.show()

    with loop:
        loop.run_forever()