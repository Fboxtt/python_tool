import sys
import asyncio
import threading
from typing import Dict, Set
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLabel, QScrollArea, QFrame,
                             QGridLayout, QMessageBox, QProgressBar)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QPalette, QColor
import bleak
from bleak import BleakScanner, BleakClient


class BluetoothSignals(QObject):
    """蓝牙操作的信号类"""
    devices_found = pyqtSignal(list)
    device_connected = pyqtSignal(str, str)  # address, name
    device_disconnected = pyqtSignal(str)
    connection_error = pyqtSignal(str, str)  # address, error


class BluetoothManager(QThread):
    """蓝牙管理器线程"""
    
    def __init__(self):
        super().__init__()
        self.signals = BluetoothSignals()
        self.scanning = False
        self.connected_devices: Dict[str, BleakClient] = {}
        self.loop = None
        
    def run(self):
        """运行异步事件循环"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def start_scanning(self):
        """开始扫描蓝牙设备"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._scan_devices(), self.loop)
    
    def stop_scanning(self):
        """停止扫描"""
        self.scanning = False
    
    def connect_device(self, address: str):
        """连接蓝牙设备"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._connect_device(address), self.loop)
    
    def disconnect_device(self, address: str):
        """断开蓝牙设备连接"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._disconnect_device(address), self.loop)
    
    async def _scan_devices(self):
        """异步扫描蓝牙设备"""
        self.scanning = True
        while self.scanning:
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                device_list = []
                for device in devices:
                    if device.name:  # 只显示有名称的设备
                        device_list.append({
                            'address': device.address,
                            'name': device.name,
                            'rssi': device.rssi
                        })
                self.signals.devices_found.emit(device_list)
                await asyncio.sleep(2)  # 每2秒扫描一次
            except Exception as e:
                print(f"扫描错误: {e}")
                await asyncio.sleep(5)
    
    async def _connect_device(self, address: str):
        """异步连接蓝牙设备"""
        try:
            if address in self.connected_devices:
                return
            
            client = BleakClient(address)
            await client.connect()
            self.connected_devices[address] = client
            
            # 获取设备名称
            device_name = "Unknown"
            try:
                devices = await BleakScanner.discover(timeout=2.0)
                for device in devices:
                    if device.address == address:
                        device_name = device.name or "Unknown"
                        break
            except:
                pass
            
            self.signals.device_connected.emit(address, device_name)
            
        except Exception as e:
            self.signals.connection_error.emit(address, str(e))
    
    async def _disconnect_device(self, address: str):
        """异步断开蓝牙设备连接"""
        try:
            if address in self.connected_devices:
                client = self.connected_devices[address]
                await client.disconnect()
                del self.connected_devices[address]
                self.signals.device_disconnected.emit(address)
        except Exception as e:
            print(f"断开连接错误: {e}")


class BluetoothDeviceCard(QFrame):
    """蓝牙设备卡片组件"""
    
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal(str)
    
    def __init__(self, address: str, name: str, rssi: int = None):
        super().__init__()
        self.address = address
        self.name = name
        self.rssi = rssi
        self.is_connected = False
        self.setup_ui()
    
    def setup_ui(self):
        """设置卡片UI"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #cccccc;
                border-radius: 10px;
                background-color: #f9f9f9;
                margin: 5px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #4CAF50;
                background-color: #f0f8ff;
            }
        """)
        
        layout = QVBoxLayout()
        
        # 设备名称标签
        self.name_label = QLabel(self.name)
        self.name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: #333333; margin-bottom: 5px;")
        
        # 设备地址标签
        self.address_label = QLabel(f"地址: {self.address}")
        self.address_label.setFont(QFont("Arial", 9))
        self.address_label.setStyleSheet("color: #666666;")
        
        # 信号强度标签
        if self.rssi:
            self.rssi_label = QLabel(f"信号强度: {self.rssi} dBm")
            self.rssi_label.setFont(QFont("Arial", 9))
            self.rssi_label.setStyleSheet("color: #666666;")
        
        # 连接状态标签
        self.status_label = QLabel("未连接")
        self.status_label.setFont(QFont("Arial", 10))
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        
        # 连接按钮
        self.connect_button = QPushButton("连接")
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.connect_button.clicked.connect(self.on_connect_clicked)
        
        # 添加组件到布局
        layout.addWidget(self.name_label)
        layout.addWidget(self.address_label)
        if self.rssi:
            layout.addWidget(self.rssi_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.connect_button)
        
        self.setLayout(layout)
    
    def on_connect_clicked(self):
        """处理连接按钮点击"""
        if self.is_connected:
            self.disconnect_requested.emit(self.address)
        else:
            self.connect_requested.emit(self.address)
    
    def set_connected(self, connected: bool):
        """设置连接状态"""
        self.is_connected = connected
        if connected:
            self.status_label.setText("已连接")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.connect_button.setText("断开")
            self.connect_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c1170a;
                }
            """)
            # 已连接的设备卡片样式
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #4CAF50;
                    border-radius: 10px;
                    background-color: #e8f5e8;
                    margin: 5px;
                    padding: 10px;
                }
            """)
        else:
            self.status_label.setText("未连接")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.connect_button.setText("连接")
            self.connect_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            # 未连接的设备卡片样式
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #cccccc;
                    border-radius: 10px;
                    background-color: #f9f9f9;
                    margin: 5px;
                    padding: 10px;
                }
                QFrame:hover {
                    border-color: #4CAF50;
                    background-color: #f0f8ff;
                }
            """)


class MultiBTWindow(QMainWindow):
    """多蓝牙连接主窗口"""
    
    def __init__(self):
        super().__init__()
        self.bluetooth_manager = BluetoothManager()
        self.device_cards: Dict[str, BluetoothDeviceCard] = {}
        self.connected_devices: Set[str] = set()
        self.scanned_devices: Set[str] = set()
        
        self.setup_ui()
        self.setup_bluetooth()
        
        # 启动蓝牙管理器线程
        self.bluetooth_manager.start()
        
        # 定时器用于清理未扫描到的设备
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_devices)
        self.cleanup_timer.start(10000)  # 每10秒清理一次
    
    def setup_ui(self):
        """设置主窗口UI"""
        self.setWindowTitle("多蓝牙设备连接管理器")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
        """)
        
        # 中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 标题
        title_label = QLabel("蓝牙设备管理")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333333; margin: 20px; text-align: center;")
        main_layout.addWidget(title_label)
        
        # 控制按钮区域
        control_layout = QHBoxLayout()
        
        self.scan_button = QPushButton("开始扫描")
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.scan_button.clicked.connect(self.toggle_scanning)
        
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #666666; font-size: 12px; margin-left: 20px;")
        
        control_layout.addWidget(self.scan_button)
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()
        
        main_layout.addLayout(control_layout)
        
        # 设备卡片滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # 设备卡片容器
        self.cards_widget = QWidget()
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(10)
        self.cards_widget.setLayout(self.cards_layout)
        
        self.scroll_area.setWidget(self.cards_widget)
        main_layout.addWidget(self.scroll_area)
    
    def setup_bluetooth(self):
        """设置蓝牙信号连接"""
        self.bluetooth_manager.signals.devices_found.connect(self.on_devices_found)
        self.bluetooth_manager.signals.device_connected.connect(self.on_device_connected)
        self.bluetooth_manager.signals.device_disconnected.connect(self.on_device_disconnected)
        self.bluetooth_manager.signals.connection_error.connect(self.on_connection_error)
    
    def toggle_scanning(self):
        """切换扫描状态"""
        if self.scan_button.text() == "开始扫描":
            self.bluetooth_manager.start_scanning()
            self.scan_button.setText("停止扫描")
            self.scan_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c1170a;
                }
            """)
            self.status_label.setText("正在扫描...")
        else:
            self.bluetooth_manager.stop_scanning()
            self.scan_button.setText("开始扫描")
            self.scan_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #1565C0;
                }
            """)
            self.status_label.setText("已停止扫描")
    
    @pyqtSlot(list)
    def on_devices_found(self, devices):
        """处理发现的蓝牙设备"""
        current_scanned = set()
        
        for device in devices:
            address = device['address']
            name = device['name']
            rssi = device.get('rssi')
            
            current_scanned.add(address)
            
            # 如果是新设备，创建卡片
            if address not in self.device_cards:
                self.add_device_card(address, name, rssi)
        
        # 更新扫描到的设备集合
        self.scanned_devices = current_scanned
        
        # 更新状态
        self.status_label.setText(f"发现 {len(devices)} 个设备")
    
    def add_device_card(self, address: str, name: str, rssi: int = None):
        """添加设备卡片"""
        card = BluetoothDeviceCard(address, name, rssi)
        card.connect_requested.connect(self.connect_device)
        card.disconnect_requested.connect(self.disconnect_device)
        
        # 如果设备已连接，更新状态
        if address in self.connected_devices:
            card.set_connected(True)
        
        self.device_cards[address] = card
        
        # 计算网格位置
        row = len(self.device_cards) // 3
        col = len(self.device_cards) % 3
        self.cards_layout.addWidget(card, row, col)
    
    def remove_device_card(self, address: str):
        """移除设备卡片"""
        if address in self.device_cards:
            card = self.device_cards[address]
            self.cards_layout.removeWidget(card)
            card.deleteLater()
            del self.device_cards[address]
            
            # 重新排列剩余的卡片
            self.rearrange_cards()
    
    def rearrange_cards(self):
        """重新排列卡片"""
        # 清除当前布局
        for i in reversed(range(self.cards_layout.count())):
            self.cards_layout.itemAt(i).widget().setParent(None)
        
        # 重新添加卡片
        for i, card in enumerate(self.device_cards.values()):
            row = i // 3
            col = i % 3
            self.cards_layout.addWidget(card, row, col)
    
    def cleanup_devices(self):
        """清理未扫描到的设备"""
        devices_to_remove = []
        
        for address in self.device_cards:
            # 保留已连接的设备，即使没有扫描到
            if address not in self.scanned_devices and address not in self.connected_devices:
                devices_to_remove.append(address)
        
        for address in devices_to_remove:
            self.remove_device_card(address)
    
    @pyqtSlot(str)
    def connect_device(self, address: str):
        """连接蓝牙设备"""
        self.bluetooth_manager.connect_device(address)
        if address in self.device_cards:
            self.status_label.setText(f"正在连接 {self.device_cards[address].name}...")
    
    @pyqtSlot(str)
    def disconnect_device(self, address: str):
        """断开蓝牙设备连接"""
        self.bluetooth_manager.disconnect_device(address)
        if address in self.device_cards:
            self.status_label.setText(f"正在断开 {self.device_cards[address].name}...")
    
    @pyqtSlot(str, str)
    def on_device_connected(self, address: str, name: str):
        """处理设备连接成功"""
        self.connected_devices.add(address)
        if address in self.device_cards:
            self.device_cards[address].set_connected(True)
        self.status_label.setText(f"已连接到 {name}")
    
    @pyqtSlot(str)
    def on_device_disconnected(self, address: str):
        """处理设备断开连接"""
        if address in self.connected_devices:
            self.connected_devices.remove(address)
        if address in self.device_cards:
            self.device_cards[address].set_connected(False)
            name = self.device_cards[address].name
            self.status_label.setText(f"已断开 {name}")
    
    @pyqtSlot(str, str)
    def on_connection_error(self, address: str, error: str):
        """处理连接错误"""
        if address in self.device_cards:
            name = self.device_cards[address].name
            QMessageBox.warning(self, "连接错误", f"连接 {name} 失败:\n{error}")
            self.status_label.setText(f"连接 {name} 失败")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.bluetooth_manager.stop_scanning()
        if self.bluetooth_manager.loop:
            self.bluetooth_manager.loop.call_soon_threadsafe(self.bluetooth_manager.loop.stop)
        self.bluetooth_manager.quit()
        self.bluetooth_manager.wait()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    window = MultiBTWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
