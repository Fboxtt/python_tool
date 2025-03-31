import sys
import asyncio
import traceback
import time
from datetime import datetime

from PyQt6.QtCore import QTimer  # 导入 QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QLabel, QMessageBox, QTextEdit, QLineEdit, QHBoxLayout,
    QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt
from bleak import BleakScanner, BleakClient
from qasync import QEventLoop, asyncSlot
from hex_model import HexFileModel
from program_controller import DownloadController
from program_controller import TextDecode
from program_controller import ReceveDataStatus,BmsCmdType,ComStatus,DownloadErr


class BluetoothTool(QWidget):
    task_flag = 0
    pass
    def __init__(self):
        super().__init__()
        self.client = None  # 当前连接的蓝牙设备
        self.initUI()
        self.hex_model = HexFileModel()
        self.text_decode = TextDecode()
        self.download_data = DownloadController(self.client,self.hex_model)
        # asyncio.create_task(self.scan_devices())
        QTimer.singleShot(0, self.on_scan_devices_clicked)
    def initUI(self):
        self.setWindowTitle('蓝牙查询与连接工具')

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
        self.hex_send_checkbox = QCheckBox('16进制发送')
        self.hex_send_checkbox.setChecked(True)
        self.send_button = QPushButton('发送数据')
        self.send_button.clicked.connect(self.on_send_data_clicked)
        self.send_button.setEnabled(False)  # 初始状态下发送按钮不可用
        self.send_layout.addWidget(self.send_input)
        self.send_layout.addWidget(self.hex_send_checkbox)
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

        # 烧录控制部分
        self.program_layout = QHBoxLayout()
        self.program_button = QPushButton('开始烧录')
        self.program_button.clicked.connect(self.on_program_clicked)
        self.program_layout.addWidget(self.program_button)
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

        self.setLayout(layout)

    def on_hex_display_changed(self, state):
        """当16进制显示选项改变时，重新显示接收到的数据"""
        if hasattr(self, 'received_data_buffer'):
            self.receive_output.clear()
            for data in self.received_data_buffer:
                self.display_received_data(data)

    def display_received_data(self, data):
        """显示接收到的数据，根据16进制显示选项决定显示格式"""
        if self.hex_display_checkbox.isChecked():
            # 16进制显示
            hex_data = ' '.join([f'{b:02X}' for b in data])
            self.receive_output.append(f"接收: {hex_data}")
        else:
            # 文本显示
            try:
                text_data = data.decode('utf-8')
                self.receive_output.append(f"接收: {text_data}")
            except UnicodeDecodeError:
                # 如果无法解码为文本，则显示16进制
                hex_data = ' '.join([f'{b:02X}' for b in data])
                self.receive_output.append(f"接收(HEX): {hex_data}")

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
    
    async def send_data(self, data:str):
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
                    self.receive_output.append(f"发送: {hex_data}")
                else:
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
    async def byte_send(self,data:bytes):
        if(len(data) == 0):
            return
        if(self.client and self.client.is_connected):
            self.text_decode.legality = ReceveDataStatus.ERR_NOTHING
            """异步方法，发送字节数据"""
            await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)


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
        if not hasattr(self, 'received_data_buffer'):
            self.received_data_buffer = []
        self.received_data_buffer.append(data)
        self.text_decode.split_data(data)
        self.display_received_data(data)

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
        if not self.hex_model.is_file_loaded:
            QMessageBox.warning(self, '警告', '请先选择HEX文件')
            # return
        
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, '警告', '请先连接设备')
            return
        
        # 创建烧录任务
        asyncio.create_task(self.start_programming())

    async def start_programming(self):
        """异步方法，执行烧录过程"""
        try:
            # 禁用烧录按钮，避免重复点击
            self.program_button.setEnabled(False)
            self.program_button.setText('烧录中...')
            err_count = 0  
            while err_count < 4:
                data = self.download_data.get_download_data(BmsCmdType.DOWNLOAD_BUFFER)
                await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                self.receive_output.append("75发送")
                await asyncio.sleep(0.5)
                if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                    await asyncio.sleep(1.5)
                if(self.text_decode.no80_cmd == BmsCmdType.DOWNLOAD_BUFFER  and self.text_decode.cmd_ack == 0x00):
                    err_count -= 1
                    break
                else:
                    err_count += 1
            await asyncio.sleep(1)

            shake_count = 0
            while shake_count < 3:
                err_count = 0
                while err_count < 3:
                    data = bytearray([0x00,0x00,0x04,0x01,0x76,0x55,0xaa,0x7a])
                    await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                    self.receive_output.append("76发送")
                    await asyncio.sleep(0.5)
                    if(self.text_decode.is_download_cmd):
                        break
                    err_count += 1
                else:
                    if err_count == 3:
                        print(f"握手命令发送失败")
                        # raise Exception("握手命令发送失败")
                shake_count += 1
            else:
                print(f"握手命令发送成功")
            self.text_decode.legality = ReceveDataStatus.ERR_NOTHING



            err_count = 0  
            while err_count < 1:
                data = self.download_data.get_download_data(BmsCmdType.DOWNLOAD_BUFFER)
                await self.client.write_gatt_char("0000ffe1-0000-1000-8000-00805f9b34fb", data)
                # self.receive_output.append("75发送")
                await asyncio.sleep(0.5)
                if self.text_decode.legality == ReceveDataStatus.ERR_NOTHING:
                    await asyncio.sleep(1.5)
                if(self.text_decode.no80_cmd == BmsCmdType.DOWNLOAD_BUFFER  and self.text_decode.cmd_ack == 0x00):
                    break
                else:
                    err_count += 1
            else:
                print(f"擦除命令发送失败")
                
            # while 
            

            # 发送下载命令并等待响应
            if not self.hex_model.is_file_loaded:
                raise Exception("HEX文件未加载")
            else:
                pass
            # TODO: 在这里添加后续的烧录步骤
            # 例如：发送数据块、校验等
            
            self.receive_output.append("烧录完成")
            QMessageBox.information(self, '成功', '烧录完成')
            
        except Exception as e:
            traceback.print_exc()
            self.receive_output.append(f"烧录失败: {str(e)}")
            QMessageBox.critical(self, '错误', f'烧录失败: {str(e)}')
        
        finally:
            # 恢复按钮状态
            self.program_button.setEnabled(True)
            self.program_button.setText('开始烧录')


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 使用 qasync 创建事件循环
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tool = BluetoothTool()
    tool.show()

    with loop:
        loop.run_forever()