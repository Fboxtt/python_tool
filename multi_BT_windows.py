import sys
import asyncio
import threading
import json
import os
from typing import Dict, Set
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLabel, QScrollArea, QFrame,
                             QGridLayout, QMessageBox, QProgressBar)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread, pyqtSlot, QEvent
from PyQt6.QtGui import QFont, QPalette, QColor, QKeySequence, QShortcut
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
    
    def send_data(self, address: str, characteristic_uuid: str, data: bytes):
        """发送数据到指定蓝牙设备"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._send_data(address, characteristic_uuid, data), self.loop
            )
    
    def read_data(self, address: str, characteristic_uuid: str):
        """从指定蓝牙设备读取数据"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._read_data(address, characteristic_uuid), self.loop
            )
    
    def get_connected_client(self, address: str):
        """获取已连接的蓝牙客户端对象"""
        return self.connected_devices.get(address)
    
    async def _scan_devices(self):
        """异步扫描蓝牙设备"""
        self.scanning = True
        while self.scanning:
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                device_list = []
                for device in devices:
                    if device.name:  # 只显示有名称的设备
                        # 只显示以D、L、R开头的蓝牙设备
                        if device.name.upper().startswith(('D', 'L', 'R')):
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
    
    async def _send_data(self, address: str, characteristic_uuid: str, data: bytes):
        """异步发送数据到蓝牙设备"""
        try:
            if address in self.connected_devices:
                client = self.connected_devices[address]
                await client.write_gatt_char(characteristic_uuid, data)
                print(f"数据发送成功到 {address}: {data.hex()}")
            else:
                print(f"设备 {address} 未连接，无法发送数据")
        except Exception as e:
            print(f"发送数据错误: {e}")
    
    async def _read_data(self, address: str, characteristic_uuid: str):
        """异步从蓝牙设备读取数据"""
        try:
            if address in self.connected_devices:
                client = self.connected_devices[address]
                data = await client.read_gatt_char(characteristic_uuid)
                print(f"从 {address} 读取数据: {data.hex()}")
                return data
            else:
                print(f"设备 {address} 未连接，无法读取数据")
                return None
        except Exception as e:
            print(f"读取数据错误: {e}")
            return None


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
        self.setFixedSize(300, 210)  # 固定卡片大小，进一步增加尺寸以适应大字体
        self.setStyleSheet("""
            BluetoothDeviceCard {
                border: 2px solid #cccccc;
                border-radius: 8px;
                background-color: #f9f9f9;
                margin: 3px;
                padding: 8px;
            }
            BluetoothDeviceCard:hover {
                border-color: #4CAF50;
                background-color: #f0f8ff;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        
        # 主布局 - 垂直布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # 顶部区域 - 设备名称和状态
        top_layout = QHBoxLayout()
        top_layout.setSpacing(5)
        
        # 设备名称标签（截断长名称）
        display_name = self.name if len(self.name) <= 18 else self.name[:15] + "..."
        self.name_label = QLabel(display_name)
        self.name_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: #000000; background-color: transparent; border: none;")
        self.name_label.setToolTip(self.name)  # 完整名称作为工具提示
        
        # 连接状态标签
        self.status_label = QLabel("●")
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("color: #ff0000; font-weight: bold; background-color: transparent; border: none;")
        self.status_label.setFixedWidth(20)
        self.status_label.setToolTip("连接状态")
        
        top_layout.addWidget(self.name_label)
        top_layout.addStretch()
        top_layout.addWidget(self.status_label)
        
        # 信息区域 - 地址和信号强度
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        
        # 信号强度显示（优先显示）
        if self.rssi:
            rssi_text = f"信号: {self.rssi}dBm"
            # 根据信号强度设置颜色
            if self.rssi > -50:
                rssi_color = "#4CAF50"  # 强信号-绿色
            elif self.rssi > -70:
                rssi_color = "#FF9800"  # 中等信号-橙色
            else:
                rssi_color = "#f44336"  # 弱信号-红色
                
            self.rssi_label = QLabel(rssi_text)
            self.rssi_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            self.rssi_label.setStyleSheet(f"color: {rssi_color}; font-weight: bold; background-color: transparent; border: none;")
            info_layout.addWidget(self.rssi_label)
        
        # 设备地址标签（显示简化地址）
        short_address = self.address[-8:] if len(self.address) > 8 else self.address
        self.address_label = QLabel(f"地址: {short_address}")
        self.address_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.address_label.setStyleSheet("color: #000000; font-weight: bold; background-color: transparent; border: none;")
        self.address_label.setToolTip(f"完整地址: {self.address}")
        info_layout.addWidget(self.address_label)
        
        # 预留扩展区域
        self.extension_layout = QHBoxLayout()
        self.extension_layout.setSpacing(5)
        
        # 预留空间标签（可用于显示额外信息）
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.info_label.setStyleSheet("color: #333333; background-color: transparent; border: none;")
        self.info_label.setFixedHeight(20)
        self.extension_layout.addWidget(self.info_label)
        
        # 连接按钮 - 更紧凑的设计
        self.connect_button = QPushButton("连接")
        self.connect_button.setFixedHeight(36)
        self.connect_button.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
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
        
        # 组装布局
        main_layout.addLayout(top_layout)
        main_layout.addLayout(info_layout)
        main_layout.addLayout(self.extension_layout)
        main_layout.addStretch()  # 推送按钮到底部
        main_layout.addWidget(self.connect_button)
        
        self.setLayout(main_layout)
    
    def on_connect_clicked(self):
        """处理连接按钮点击"""
        if self.is_connected:
            self.disconnect_requested.emit(self.address)
        else:
            self.connect_requested.emit(self.address)
    
    def set_extension_info(self, info_text: str, color: str = "#333333"):
        """设置扩展区域信息"""
        self.info_label.setText(info_text)
        self.info_label.setStyleSheet(f"color: {color}; font-weight: bold; background-color: transparent; border: none;")
    
    def add_extension_widget(self, widget):
        """添加扩展组件到预留区域"""
        self.extension_layout.addWidget(widget)
    
    def clear_extension_area(self):
        """清空扩展区域"""
        # 清除所有扩展组件
        for i in reversed(range(self.extension_layout.count())):
            item = self.extension_layout.itemAt(i)
            if item.widget() != self.info_label:  # 保留info_label
                widget = item.widget()
                self.extension_layout.removeWidget(widget)
                widget.deleteLater()
        
        # 重置info_label
        self.info_label.setText("")
        self.info_label.setStyleSheet("color: #333333; background-color: transparent; border: none;")
    
    def set_connected(self, connected: bool):
        """设置连接状态"""
        self.is_connected = connected
        if connected:
            # 更新状态指示器为绿色圆点
            self.status_label.setText("●")
            self.status_label.setStyleSheet("color: #00AA00; font-weight: bold; background-color: transparent; border: none;")
            self.status_label.setToolTip("已连接")
            
            # 更新扩展区域显示连接信息
            self.info_label.setText("已连接")
            self.info_label.setStyleSheet("color: #00AA00; font-weight: bold; background-color: transparent; border: none;")
            
            # 更新连接按钮
            self.connect_button.setText("断开")
            self.connect_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
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
                BluetoothDeviceCard {
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    background-color: #e8f5e8;
                    margin: 3px;
                    padding: 8px;
                }
                QLabel {
                    background-color: transparent;
                    border: none;
                    color: #000000;
                }
            """)
        else:
            # 更新状态指示器为红色圆点
            self.status_label.setText("●")
            self.status_label.setStyleSheet("color: #ff0000; font-weight: bold; background-color: transparent; border: none;")
            self.status_label.setToolTip("未连接")
            
            # 清空扩展区域信息
            self.info_label.setText("")
            self.info_label.setStyleSheet("color: #333333; background-color: transparent; border: none;")
            
            # 更新连接按钮
            self.connect_button.setText("连接")
            self.connect_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
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
                BluetoothDeviceCard {
                    border: 2px solid #cccccc;
                    border-radius: 8px;
                    background-color: #f9f9f9;
                    margin: 3px;
                    padding: 8px;
                }
                BluetoothDeviceCard:hover {
                    border-color: #4CAF50;
                    background-color: #f0f8ff;
                }
                QLabel {
                    background-color: transparent;
                    border: none;
                    color: #000000;
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
        
        # 配置文件路径
        self.config_file = "bluetooth_config.json"
        self.auto_connect_devices = {}  # 存储需要自动连接的设备信息
        
        # 窗口模式配置
        self.is_fullscreen = False
        self.window_mode_cols = 4  # 窗口模式：4列
        self.window_mode_rows = 2  # 窗口模式：2行
        self.fullscreen_mode_cols = 6  # 全屏模式：6列
        self.fullscreen_mode_rows = 4  # 全屏模式：4行
        
        # 加载配置文件
        self.load_config()
        
        self.setup_ui()
        self.setup_bluetooth()
        
        # 启动蓝牙管理器线程
        self.bluetooth_manager.start()
        
        # 启动时自动开始扫描
        QTimer.singleShot(1000, self.auto_start_scanning)  # 延迟1秒后开始扫描
        
        # 定时器用于清理未扫描到的设备
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_devices)
        self.cleanup_timer.start(10000)  # 每10秒清理一次
    
    def setup_ui(self):
        """设置主窗口UI"""
        self.setWindowTitle("多蓝牙设备连接管理器")
        
        # 计算窗口模式大小 (4×2卡片)
        card_width, card_height = 300, 210
        spacing = 10
        margin = 40
        title_height = 80
        control_height = 60
        
        window_width = self.window_mode_cols * card_width + (self.window_mode_cols - 1) * spacing + margin
        window_height = self.window_mode_rows * card_height + (self.window_mode_rows - 1) * spacing + title_height + control_height + margin
        
        # 初始设置窗口大小，但不固定，以便全屏按钮可用
        self.setGeometry(100, 100, window_width, window_height)
        self.setMinimumSize(window_width, window_height)  # 设置最小尺寸
        self.setMaximumSize(window_width, window_height)  # 设置最大尺寸，保持窗口模式下的固定大小
        
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
        
        self.status_label = QLabel("准备就绪 - 窗口模式 (4×2)")
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
        self.cards_layout.setHorizontalSpacing(10)
        self.cards_layout.setVerticalSpacing(15)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        self.cards_widget.setLayout(self.cards_layout)
        
        self.scroll_area.setWidget(self.cards_widget)
        main_layout.addWidget(self.scroll_area)
        
        # 添加键盘快捷键
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """设置键盘快捷键"""
        # F11 切换全屏
        fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        
        # Ctrl+F 切换全屏
        fullscreen_shortcut2 = QShortcut(QKeySequence("Ctrl+F"), self)
        fullscreen_shortcut2.activated.connect(self.toggle_fullscreen)
        
        # Ctrl+S 开始/停止扫描
        scan_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        scan_shortcut.activated.connect(self.toggle_scanning)
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.auto_connect_devices = config.get('auto_connect_devices', {})
                    print(f"已加载配置文件，找到 {len(self.auto_connect_devices)} 个自动连接设备")
            else:
                # 创建空配置文件
                self.auto_connect_devices = {}
                self.save_config()
                print("创建新的配置文件")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self.auto_connect_devices = {}
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                'auto_connect_devices': self.auto_connect_devices
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"配置文件已保存，包含 {len(self.auto_connect_devices)} 个设备")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def auto_start_scanning(self):
        """自动开始扫描"""
        if self.scan_button.text() == "开始扫描":
            self.toggle_scanning()
            print("自动开始扫描蓝牙设备")
    
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
    
    def toggle_fullscreen(self):
        """切换全屏/窗口模式"""
        if self.isFullScreen():
            # 切换到窗口模式 (4×2)
            self.showNormal()
        else:
            # 切换到全屏模式 (6×4)
            self.showFullScreen()
    
    def changeEvent(self, event):
        """处理窗口状态变化事件"""
        if event.type() == QEvent.Type.WindowStateChange:
            # 检查是否进入或退出全屏
            if self.isFullScreen() and not self.is_fullscreen:
                # 进入全屏模式
                self.is_fullscreen = True
                # 移除尺寸限制以允许全屏
                self.setMaximumSize(16777215, 16777215)  # Qt的最大尺寸值
                self.status_label.setText("全屏模式 (6×4)")
                self.rearrange_cards()
                
            elif not self.isFullScreen() and self.is_fullscreen:
                # 退出全屏模式
                self.is_fullscreen = False
                
                # 恢复窗口模式大小
                card_width, card_height = 300, 210
                spacing = 10
                margin = 40
                title_height = 80
                control_height = 60
                
                window_width = self.window_mode_cols * card_width + (self.window_mode_cols - 1) * spacing + margin
                window_height = self.window_mode_rows * card_height + (self.window_mode_rows - 1) * spacing + title_height + control_height + margin
                
                # 恢复窗口大小和最小尺寸限制
                self.resize(window_width, window_height)
                self.setMinimumSize(window_width, window_height)
                self.setMaximumSize(window_width, window_height)  # 限制最大尺寸以保持固定效果
                self.status_label.setText("窗口模式 (4×2)")
                self.rearrange_cards()
        
        super().changeEvent(event)
    
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
            
            # 检查是否需要自动连接
            if (address in self.auto_connect_devices and 
                address not in self.connected_devices):
                # 双重验证：地址匹配 AND 名称匹配（防止重名设备问题）
                stored_device = self.auto_connect_devices[address]
                if (stored_device['address'] == address and 
                    stored_device['name'] == name):
                    # 确保设备卡片存在且未连接
                    if address in self.device_cards and not self.device_cards[address].is_connected:
                        print(f"自动连接设备: {name} ({address}) - 地址和名称验证通过")
                        self.connect_device(address)
                    elif address not in self.device_cards:
                        print(f"自动连接设备: {name} ({address}) - 地址和名称验证通过")
                        self.connect_device(address)
                else:
                    print(f"设备验证失败: 存储的名称为 '{stored_device['name']}', 当前扫描到的名称为 '{name}'")
        
        # 更新扫描到的设备集合
        self.scanned_devices = current_scanned
        
        # 更新状态
        self.status_label.setText(f"发现 {len(devices)} 个设备")
    
    def add_device_card(self, address: str, name: str, rssi: int = None):
        """添加设备卡片"""
        card = BluetoothDeviceCard(address, name, rssi)
        card.connect_requested.connect(self.connect_device)
        card.disconnect_requested.connect(lambda addr: self.disconnect_device(addr, manual_disconnect=True))
        
        # 如果设备已连接，更新状态
        if address in self.connected_devices:
            card.set_connected(True)
        
        self.device_cards[address] = card
        
        # 根据当前模式计算网格位置
        current_cols = self.fullscreen_mode_cols if self.is_fullscreen else self.window_mode_cols
        card_count = len(self.device_cards) - 1
        row = card_count // current_cols
        col = card_count % current_cols
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
        
        # 根据当前模式重新添加卡片
        current_cols = self.fullscreen_mode_cols if self.is_fullscreen else self.window_mode_cols
        for i, card in enumerate(self.device_cards.values()):
            row = i // current_cols
            col = i % current_cols
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
    def disconnect_device(self, address: str, manual_disconnect: bool = True):
        """断开蓝牙设备连接"""
        self.bluetooth_manager.disconnect_device(address)
        if address in self.device_cards:
            self.status_label.setText(f"正在断开 {self.device_cards[address].name}...")
            
            # 如果是手动断开，从自动连接列表中移除
            if manual_disconnect and address in self.auto_connect_devices:
                device_name = self.auto_connect_devices[address].get('name', 'Unknown')
                del self.auto_connect_devices[address]
                self.save_config()
                print(f"设备 {device_name} ({address}) 已从自动连接列表中移除")
    
    @pyqtSlot(str, str)
    def on_device_connected(self, address: str, name: str):
        """处理设备连接成功"""
        self.connected_devices.add(address)
        
        # 获取正确的设备名称（优先使用设备卡片中的名称）
        actual_name = name
        if address in self.device_cards:
            self.device_cards[address].set_connected(True)
            # 使用设备卡片中的名称，因为它是从扫描时获取的正确名称
            actual_name = self.device_cards[address].name
        
        # 将连接成功的设备保存到配置文件
        self.auto_connect_devices[address] = {
            'name': actual_name,
            'address': address
        }
        self.save_config()
        print(f"设备 {actual_name} ({address}) 已添加到自动连接列表")
        
        self.status_label.setText(f"已连接到 {actual_name}")
    
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
    
    def send_bluetooth_data(self, address: str, characteristic_uuid: str, data: bytes):
        """发送数据到指定蓝牙设备"""
        self.bluetooth_manager.send_data(address, characteristic_uuid, data)
    
    def read_bluetooth_data(self, address: str, characteristic_uuid: str):
        """从指定蓝牙设备读取数据"""
        self.bluetooth_manager.read_data(address, characteristic_uuid)
    
    def get_bluetooth_client(self, address: str):
        """获取指定设备的BleakClient对象"""
        return self.bluetooth_manager.get_connected_client(address)
    
    def get_connected_devices_list(self):
        """获取所有已连接设备的地址列表"""
        return list(self.connected_devices)
    
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
