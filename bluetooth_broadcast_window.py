import sys
import asyncio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QComboBox, QLineEdit, QTextEdit, QGroupBox, QSpinBox,
    QCheckBox, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from qasync import QEventLoop, asyncSlot
import struct
from datetime import datetime


class BluetoothBroadcastWindow(QWidget):
    """蓝牙广播控制窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("蓝牙广播信号控制器")
        self.setGeometry(100, 100, 800, 600)
        
        # 广播相关变量
        self.is_broadcasting = False
        self.broadcast_timer = QTimer()
        self.broadcast_timer.timeout.connect(self.broadcast_signal)
        
        # 初始化UI
        self.initUI()
        
    def initUI(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel("🔵 蓝牙广播信号控制器")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 信号类型选择组
        signal_group = QGroupBox("广播信号类型")
        signal_layout = QFormLayout()
        
        # 信号类型下拉框
        self.signal_type_combo = QComboBox()
        self.signal_type_combo.addItems([
            "自定义数据包",
            "电池状态信息",
            "设备识别信号",
            "温度传感器数据",
            "电压电流数据",
            "警报信号",
            "心跳信号",
            "测试信号"
        ])
        self.signal_type_combo.currentIndexChanged.connect(self.on_signal_type_changed)
        signal_layout.addRow("信号类型:", self.signal_type_combo)
        
        signal_group.setLayout(signal_layout)
        main_layout.addWidget(signal_group)
        
        # 广播参数设置组
        param_group = QGroupBox("广播参数设置")
        param_layout = QFormLayout()
        
        # 广播间隔
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix(" ms")
        param_layout.addRow("广播间隔:", self.interval_spin)
        
        # 设备名称
        self.device_name_input = QLineEdit()
        self.device_name_input.setText("BMS_Broadcast")
        self.device_name_input.setPlaceholderText("输入设备广播名称")
        param_layout.addRow("设备名称:", self.device_name_input)
        
        # 信号强度（模拟）
        self.power_spin = QSpinBox()
        self.power_spin.setRange(-40, 4)
        self.power_spin.setValue(0)
        self.power_spin.setSuffix(" dBm")
        param_layout.addRow("发射功率:", self.power_spin)
        
        param_group.setLayout(param_layout)
        main_layout.addWidget(param_group)
        
        # 数据配置组
        data_group = QGroupBox("广播数据配置")
        data_layout = QVBoxLayout()
        
        # 数据输入框
        data_input_layout = QHBoxLayout()
        self.data_input = QLineEdit()
        self.data_input.setPlaceholderText("输入十六进制数据，如: AA BB CC DD")
        data_input_layout.addWidget(QLabel("数据内容:"))
        data_input_layout.addWidget(self.data_input)
        data_layout.addLayout(data_input_layout)
        
        # 自动递增选项
        self.auto_increment_check = QCheckBox("数据自动递增")
        self.auto_increment_check.setToolTip("每次广播时数据末尾字节自动+1")
        data_layout.addWidget(self.auto_increment_check)
        
        # 预设数据按钮组
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("快速预设:"))
        
        btn_preset1 = QPushButton("电池信息")
        btn_preset1.clicked.connect(lambda: self.load_preset("battery"))
        preset_layout.addWidget(btn_preset1)
        
        btn_preset2 = QPushButton("设备ID")
        btn_preset2.clicked.connect(lambda: self.load_preset("device_id"))
        preset_layout.addWidget(btn_preset2)
        
        btn_preset3 = QPushButton("测试数据")
        btn_preset3.clicked.connect(lambda: self.load_preset("test"))
        preset_layout.addWidget(btn_preset3)
        
        preset_layout.addStretch()
        data_layout.addLayout(preset_layout)
        
        data_group.setLayout(data_layout)
        main_layout.addWidget(data_group)
        
        # 控制按钮组
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ 开始广播")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 10px;")
        self.start_btn.clicked.connect(self.start_broadcast)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ 停止广播")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-size: 14px; padding: 10px;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_broadcast)
        control_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(control_layout)
        
        # 状态显示组
        status_group = QGroupBox("广播状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("状态: 未开始")
        self.status_label.setStyleSheet("font-size: 12px; padding: 5px;")
        status_layout.addWidget(self.status_label)
        
        self.broadcast_count_label = QLabel("已广播次数: 0")
        status_layout.addWidget(self.broadcast_count_label)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # 日志显示
        log_group = QGroupBox("广播日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        # 清除日志按钮
        clear_btn = QPushButton("清除日志")
        clear_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_btn)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # 设置主布局
        self.setLayout(main_layout)
        
        # 广播计数器
        self.broadcast_count = 0
        
    def on_signal_type_changed(self, index):
        """信号类型改变时的处理"""
        signal_types = {
            0: "自定义数据包",
            1: "电池状态信息",
            2: "设备识别信号",
            3: "温度传感器数据",
            4: "电压电流数据",
            5: "警报信号",
            6: "心跳信号",
            7: "测试信号"
        }
        self.write_log(f"选择信号类型: {signal_types.get(index, '未知')}")
        
        # 根据信号类型自动填充数据
        if index == 1:  # 电池状态信息
            self.data_input.setText("AA 01 64 00 1F 40")  # 示例：SOC=100%, 温度=31°C, 电压=64V
        elif index == 2:  # 设备识别信号
            self.data_input.setText("DE V1 00 01 23 45")  # 示例：设备ID
        elif index == 3:  # 温度传感器数据
            self.data_input.setText("54 4D 50 19")  # 示例：温度25°C
        elif index == 4:  # 电压电流数据
            self.data_input.setText("33 00 0A 00")  # 示例：51V, 10A
        elif index == 5:  # 警报信号
            self.data_input.setText("FF FF 01 00")  # 示例：警报标志
        elif index == 6:  # 心跳信号
            self.data_input.setText("48 42 00 00")  # HB = HeartBeat
        elif index == 7:  # 测试信号
            self.data_input.setText("00 11 22 33 44 55 AA BB CC DD EE FF")
        else:  # 自定义
            self.data_input.setText("")
    
    def load_preset(self, preset_type):
        """加载预设数据"""
        if preset_type == "battery":
            self.signal_type_combo.setCurrentIndex(1)
            self.data_input.setText("AA 01 64 00 1F 40 12 34")
            self.write_log("加载预设: 电池信息数据")
        elif preset_type == "device_id":
            self.signal_type_combo.setCurrentIndex(2)
            self.data_input.setText("DE 56 49 44 31 32 33 34")
            self.write_log("加载预设: 设备ID数据")
        elif preset_type == "test":
            self.signal_type_combo.setCurrentIndex(7)
            self.data_input.setText("01 02 03 04 05 06 07 08 09 0A 0B 0C")
            self.write_log("加载预设: 测试数据")
    
    def start_broadcast(self):
        """开始广播"""
        if self.is_broadcasting:
            self.write_log("⚠️ 广播已在运行中")
            return
        
        # 验证数据
        data_str = self.data_input.text().strip()
        if not data_str:
            self.write_log("❌ 错误: 请输入广播数据")
            return
        
        # 开始广播
        self.is_broadcasting = True
        self.broadcast_count = 0
        
        # 获取间隔时间
        interval_ms = self.interval_spin.value()
        self.broadcast_timer.start(interval_ms)
        
        # 更新UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("状态: 正在广播 🟢")
        self.status_label.setStyleSheet("font-size: 12px; padding: 5px; color: green;")
        
        self.write_log(f"✅ 开始广播 - 间隔: {interval_ms}ms")
        self.write_log(f"📡 设备名称: {self.device_name_input.text()}")
        self.write_log(f"📊 信号类型: {self.signal_type_combo.currentText()}")
    
    def stop_broadcast(self):
        """停止广播"""
        if not self.is_broadcasting:
            return
        
        self.is_broadcasting = False
        self.broadcast_timer.stop()
        
        # 更新UI
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("状态: 已停止 ⚪")
        self.status_label.setStyleSheet("font-size: 12px; padding: 5px; color: gray;")
        
        self.write_log(f"⏹ 停止广播 - 总共广播 {self.broadcast_count} 次")
    
    def broadcast_signal(self):
        """执行广播操作（定时器回调）"""
        # 获取数据
        data_str = self.data_input.text().strip()
        
        try:
            # 解析十六进制数据
            data_bytes = bytes.fromhex(data_str.replace(" ", ""))
            
            # 如果启用自动递增
            if self.auto_increment_check.isChecked() and len(data_bytes) > 0:
                data_list = list(data_bytes)
                data_list[-1] = (data_list[-1] + 1) % 256
                data_bytes = bytes(data_list)
                # 更新显示
                self.data_input.setText(" ".join(f"{b:02X}" for b in data_bytes))
            
            # 这里执行实际的蓝牙广播操作
            # 注意：Windows下的bleak库主要用于连接BLE设备，不是用于广播
            # 真正的BLE广播需要使用其他库或平台特定的API
            # 这里我们模拟广播过程
            self.simulate_broadcast(data_bytes)
            
            self.broadcast_count += 1
            self.broadcast_count_label.setText(f"已广播次数: {self.broadcast_count}")
            
        except ValueError as e:
            self.write_log(f"❌ 数据格式错误: {e}")
            self.stop_broadcast()
    
    def simulate_broadcast(self, data_bytes):
        """模拟蓝牙广播（实际项目中需要替换为真实的广播API）"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        hex_str = " ".join(f"{b:02X}" for b in data_bytes)
        
        # 模拟广播
        device_name = self.device_name_input.text()
        power = self.power_spin.value()
        
        self.write_log(
            f"[{timestamp}] 📡 广播数据 | "
            f"设备: {device_name} | "
            f"功率: {power}dBm | "
            f"数据: {hex_str}"
        )
        
        # 在实际应用中，这里应该调用蓝牙广播API
        # 例如在Linux下可以使用bluez的D-Bus接口
        # 在Windows下可以使用Windows.Devices.Bluetooth.Advertisement
        # 注意：Python的bleak库主要用于扫描和连接，不支持广播功能
        # 需要使用平台特定的库，如：
        # - Windows: bleak + Windows.Devices.Bluetooth.Advertisement (需要pythonnet)
        # - Linux: python-dbus + bluez
        # - 或使用专门的广播库
    
    def write_log(self, message):
        """写入日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.is_broadcasting:
            self.stop_broadcast()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 使用qasync事件循环（如果需要异步操作）
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = BluetoothBroadcastWindow()
    window.show()
    
    with loop:
        loop.run_forever()


if __name__ == '__main__':
    main()

