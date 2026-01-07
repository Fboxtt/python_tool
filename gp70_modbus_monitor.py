#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GP70 Modbus协议上位机监控软件
支持通过串口读取电池管理系统数据
"""

import sys
import struct
import json
import csv
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGroupBox, QLabel, QComboBox, 
                             QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
                             QSpinBox, QCheckBox, QSplitter, QTabWidget, QFileDialog,
                             QMessageBox)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont
import serial
import serial.tools.list_ports


class ModbusRTU:
    """Modbus RTU协议处理类"""
    
    @staticmethod
    def crc16(data):
        """计算Modbus CRC16校验"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    @staticmethod
    def build_read_request(slave_addr, start_addr, num_regs):
        """构建功能码0x03读请求"""
        data = bytearray([
            slave_addr,
            0x03,  # 功能码
            (start_addr >> 8) & 0xFF,
            start_addr & 0xFF,
            (num_regs >> 8) & 0xFF,
            num_regs & 0xFF
        ])
        crc = ModbusRTU.crc16(data)
        data.append(crc & 0xFF)
        data.append((crc >> 8) & 0xFF)
        return bytes(data)
    
    @staticmethod
    def parse_response(data):
        """解析功能码0x03响应"""
        if len(data) < 5:
            return None, "数据长度不足"
        
        slave_addr = data[0]
        func_code = data[1]
        
        if func_code & 0x80:  # 错误响应
            error_code = data[2]
            return None, f"Modbus错误码: {error_code}"
        
        byte_count = data[2]
        if len(data) < byte_count + 5:
            return None, "数据不完整"
        
        # 验证CRC
        crc_received = data[-2] | (data[-1] << 8)
        crc_calculated = ModbusRTU.crc16(data[:-2])
        if crc_received != crc_calculated:
            return None, f"CRC校验失败 (接收: {crc_received:04X}, 计算: {crc_calculated:04X})"
        
        # 提取寄存器数据（大端序）
        registers = []
        for i in range(3, 3 + byte_count, 2):
            reg_value = (data[i] << 8) | data[i + 1]
            registers.append(reg_value)
        
        return registers, "成功"


class GP70DataParser:
    """GP70协议数据解析器"""
    
    # 寄存器定义映射
    REGISTER_MAP = [
        # Part 1: 单机运行数据 (地址0-65)
        (0, "电池组总压", "10mV", "uint16", 1),  # 寄存器值就是10mV单位，不需转换
        (1, "电流", "0.1A", "int16", 1),  # 寄存器值就是0.1A单位
        (2, "SOC剩余电量", "%", "uint16", 1),
        (3, "SOH健康度", "%", "uint16", 1),
        (4, "剩余容量", "0.1Ah", "uint16", 1),  # 寄存器值就是0.1Ah单位
        (5, "满充容量", "0.1Ah", "uint16", 1),
        (6, "循环次数", "次", "uint16", 1),
        (7, "保护状态(高16位)", "Bit 16-31", "uint16", 1),
        (8, "保护状态(低16位)", "Bit 0-15", "uint16", 1),
        (9, "故障状态(高16位)", "Bit 16-31", "uint16", 1),
        (10, "故障状态(低16位)", "Bit 0-15", "uint16", 1),
        (11, "均衡状态(高16位)", "电芯17-32", "uint16", 1),
        (12, "均衡状态(低16位)", "电芯1-16", "uint16", 1),
        (13, "MOS温度", "0.1°C", "int16", 1),  # 寄存器值就是0.1°C单位
        (14, "环境温度", "0.1°C", "int16", 1),
        (15, "充电电压限制", "10mV", "uint16", 1),
        (16, "充电电流限制", "0.1A", "uint16", 1),
        (17, "放电电流限制", "0.1A", "uint16", 1),
    ]
    
    # 单体电压 (18-49)
    for i in range(32):
        REGISTER_MAP.append((18 + i, f"单体电压{i+1}", "mV", "uint16", 1))
    
    # 温度传感器 (50-65)
    for i in range(16):
        REGISTER_MAP.append((50 + i, f"温度传感器{i+1}", "0.1°C", "int16", 1))
    
    # 保留区域1 (66-69)
    for i in range(4):
        REGISTER_MAP.append((66 + i, f"保留{i+1}", "", "uint16", 1))
    
    # Part 2: 电池组管理数据 (70-87)
    REGISTER_MAP.extend([
        (70, "电池组总电压", "10mV", "uint16", 1),  # 寄存器值就是10mV单位
        (71, "电池组总电流", "0.1A", "int16", 1),   # 寄存器值就是0.1A单位
        (72, "系统SOC", "%", "uint16", 1),
        (73, "系统总容量", "0.1Ah", "uint16", 1),
        (74, "集群保护状态(高16位)", "Bit 16-31", "uint16", 1),
        (75, "集群保护状态(低16位)", "Bit 0-15", "uint16", 1),
        (76, "集群故障状态(高16位)", "Bit 16-31", "uint16", 1),
        (77, "集群故障状态(低16位)", "Bit 0-15", "uint16", 1),
        (78, "保护状态电池数量", "个", "uint16", 1),
        (79, "故障电池数量", "个", "uint16", 1),
        (80, "通信失败电池数量", "个", "uint16", 1),
        (81, "电池总数量", "个", "uint16", 1),
        (82, "单模块容量", "0.1Ah", "uint16", 1),
        (83, "系统SOH", "%", "uint16", 1),
        (84, "充电MOS断开电池数量", "个", "uint16", 1),
        (85, "放电MOS断开电池数量", "个", "uint16", 1),
        (86, "最高单体电压", "10mV", "uint16", 1),  # 寄存器值就是10mV单位
        (87, "最低单体电压", "10mV", "uint16", 1),
    ])
    
    # 保留区域2 (88-100)
    for i in range(13):
        REGISTER_MAP.append((88 + i, f"保留区域2-{i+1}", "", "uint16", 1))
    
    @staticmethod
    def parse_registers(registers, start_addr=0):
        """解析寄存器数据"""
        parsed_data = []
        for i, reg_value in enumerate(registers):
            addr = start_addr + i
            # 查找对应的寄存器定义
            reg_info = None
            for item in GP70DataParser.REGISTER_MAP:
                if item[0] == addr:
                    reg_info = item
                    break
            
            if reg_info:
                _, name, unit, data_type, divisor = reg_info
                
                # 根据数据类型解析
                if data_type == "int16":
                    # 有符号16位整数
                    if reg_value & 0x8000:
                        value = reg_value - 0x10000
                    else:
                        value = reg_value
                else:
                    value = reg_value
                
                # 应用除数
                if divisor > 1:
                    display_value = value / divisor
                else:
                    display_value = value
                
                parsed_data.append({
                    'addr': addr,
                    'name': name,
                    'raw': reg_value,
                    'value': display_value,
                    'unit': unit,
                    'type': data_type
                })
            else:
                parsed_data.append({
                    'addr': addr,
                    'name': f"寄存器{addr}",
                    'raw': reg_value,
                    'value': reg_value,
                    'unit': "",
                    'type': "uint16"
                })
        
        return parsed_data


class SerialThread(QThread):
    """串口通信线程"""
    data_received = pyqtSignal(bytes, str)  # 接收到的数据和时间戳
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.running = False
        self.request_queue = []
    
    def set_serial(self, port, baudrate, timeout=1.0):
        """配置串口"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout
            )
            return True
        except Exception as e:
            self.error_occurred.emit(f"串口打开失败: {str(e)}")
            return False
    
    def send_request(self, data):
        """发送请求"""
        self.request_queue.append(data)
    
    def run(self):
        """线程运行"""
        self.running = True
        while self.running:
            if self.serial_port and self.serial_port.is_open:
                # 发送请求
                if self.request_queue:
                    request = self.request_queue.pop(0)
                    try:
                        self.serial_port.write(request)
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        
                        # 等待响应
                        response = self.serial_port.read(256)
                        if response:
                            self.data_received.emit(response, timestamp)
                    except Exception as e:
                        self.error_occurred.emit(f"通信错误: {str(e)}")
            
            self.msleep(10)
    
    def stop(self):
        """停止线程"""
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()


class GP70MonitorApp(QMainWindow):
    """GP70监控主窗口"""
    
    def __init__(self):
        super().__init__()
        self.serial_thread = SerialThread()
        self.serial_thread.data_received.connect(self.on_data_received)
        self.serial_thread.error_occurred.connect(self.on_error)
        
        self.auto_read_timer = QTimer()
        self.auto_read_timer.timeout.connect(self.read_all_data)
        
        self.current_data = []  # 存储当前数据用于导出
        
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("GP70 Modbus协议监控上位机")
        # 最大化窗口
        self.showMaximized()
        
        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)  # 减小边距
        main_layout.setSpacing(3)  # 减小间距
        
        # 串口配置和控制区域合并为一行
        top_group = QGroupBox("配置与控制")
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(5, 5, 5, 5)
        top_layout.setSpacing(5)
        
        # 串口选择
        top_layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMaximumWidth(150)
        self.refresh_ports()
        top_layout.addWidget(self.port_combo)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setMaximumWidth(50)
        refresh_btn.clicked.connect(self.refresh_ports)
        top_layout.addWidget(refresh_btn)
        
        # 波特率选择
        top_layout.addWidget(QLabel("波特率:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.setMaximumWidth(80)
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("9600")
        top_layout.addWidget(self.baudrate_combo)
        
        # 从机地址
        top_layout.addWidget(QLabel("地址:"))
        self.slave_addr_spin = QSpinBox()
        self.slave_addr_spin.setMaximumWidth(50)
        self.slave_addr_spin.setRange(1, 247)
        self.slave_addr_spin.setValue(1)
        top_layout.addWidget(self.slave_addr_spin)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setMaximumWidth(60)
        self.connect_btn.clicked.connect(self.toggle_connection)
        top_layout.addWidget(self.connect_btn)
        
        # 分隔符
        top_layout.addWidget(QLabel("|"))
        
        # 起始地址
        top_layout.addWidget(QLabel("起始:"))
        self.start_addr_spin = QSpinBox()
        self.start_addr_spin.setMaximumWidth(50)
        self.start_addr_spin.setRange(0, 100)
        self.start_addr_spin.setValue(0)
        top_layout.addWidget(self.start_addr_spin)
        
        # 寄存器数量
        top_layout.addWidget(QLabel("数量:"))
        self.num_regs_spin = QSpinBox()
        self.num_regs_spin.setMaximumWidth(50)
        self.num_regs_spin.setRange(1, 101)
        self.num_regs_spin.setValue(88)
        top_layout.addWidget(self.num_regs_spin)
        
        # 读取按钮
        self.read_btn = QPushButton("读取")
        self.read_btn.setMaximumWidth(50)
        self.read_btn.clicked.connect(self.read_once)
        self.read_btn.setEnabled(False)
        top_layout.addWidget(self.read_btn)
        
        # 读取全部按钮
        self.read_all_btn = QPushButton("全部")
        self.read_all_btn.setMaximumWidth(50)
        self.read_all_btn.clicked.connect(self.read_all_data)
        self.read_all_btn.setEnabled(False)
        top_layout.addWidget(self.read_all_btn)
        
        # 分隔符
        top_layout.addWidget(QLabel("|"))
        
        # 自动读取
        self.auto_read_check = QCheckBox("自动")
        self.auto_read_check.stateChanged.connect(self.toggle_auto_read)
        top_layout.addWidget(self.auto_read_check)
        
        # 刷新间隔
        top_layout.addWidget(QLabel("间隔:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setMaximumWidth(60)
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix("ms")
        top_layout.addWidget(self.interval_spin)
        
        # 分隔符
        top_layout.addWidget(QLabel("|"))
        
        # 导出数据按钮
        export_csv_btn = QPushButton("CSV")
        export_csv_btn.setMaximumWidth(50)
        export_csv_btn.clicked.connect(self.export_to_csv)
        top_layout.addWidget(export_csv_btn)
        
        export_json_btn = QPushButton("JSON")
        export_json_btn.setMaximumWidth(50)
        export_json_btn.clicked.connect(self.export_to_json)
        top_layout.addWidget(export_json_btn)
        
        # 清空日志按钮
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setMaximumWidth(70)
        clear_log_btn.clicked.connect(self.clear_logs)
        top_layout.addWidget(clear_log_btn)
        
        top_layout.addStretch()
        top_group.setLayout(top_layout)
        main_layout.addWidget(top_group)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 数据显示表格
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(6)
        self.data_table.setHorizontalHeaderLabels(["地址", "变量名", "原始值(HEX)", "解析值", "单位", "类型"])
        
        # 优化表格显示
        header = self.data_table.horizontalHeader()
        header.setStretchLastSection(False)
        # 设置列宽
        self.data_table.setColumnWidth(0, 50)   # 地址
        self.data_table.setColumnWidth(2, 100)  # 原始值
        self.data_table.setColumnWidth(3, 100)  # 解析值
        self.data_table.setColumnWidth(4, 80)   # 单位
        self.data_table.setColumnWidth(5, 70)   # 类型
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)  # 变量名自适应
        
        # 设置表格字体更小以显示更多内容
        table_font = QFont()
        table_font.setPointSize(9)
        self.data_table.setFont(table_font)
        
        # 减小行高
        self.data_table.verticalHeader().setDefaultSectionSize(20)
        self.data_table.verticalHeader().setVisible(False)  # 隐藏行号
        
        splitter.addWidget(self.data_table)
        
        # 日志显示 - 更紧凑
        log_tabs = QTabWidget()
        log_tabs.setMaximumHeight(180)  # 限制日志区域高度
        
        # 通信日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 8))
        log_tabs.addTab(self.log_text, "日志")
        
        # 发送数据
        self.send_log = QTextEdit()
        self.send_log.setReadOnly(True)
        self.send_log.setFont(QFont("Courier New", 8))
        log_tabs.addTab(self.send_log, "发送")
        
        # 接收数据
        self.recv_log = QTextEdit()
        self.recv_log.setReadOnly(True)
        self.recv_log.setFont(QFont("Courier New", 8))
        log_tabs.addTab(self.recv_log, "接收")
        
        splitter.addWidget(log_tabs)
        splitter.setStretchFactor(0, 8)  # 数据表格占更多空间
        splitter.setStretchFactor(1, 1)  # 日志占少量空间
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self.statusBar().showMessage("未连接")
    
    def refresh_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")
    
    def toggle_connection(self):
        """切换连接状态"""
        if self.connect_btn.text() == "连接":
            # 获取串口名称
            port_text = self.port_combo.currentText()
            if not port_text:
                self.append_log("错误: 请选择串口")
                return
            
            port = port_text.split(" - ")[0]
            baudrate = int(self.baudrate_combo.currentText())
            
            if self.serial_thread.set_serial(port, baudrate):
                self.serial_thread.start()
                self.connect_btn.setText("断开")
                self.read_btn.setEnabled(True)
                self.read_all_btn.setEnabled(True)
                self.statusBar().showMessage(f"已连接: {port} @ {baudrate}bps")
                self.append_log(f"串口已连接: {port} @ {baudrate}bps")
            else:
                self.statusBar().showMessage("连接失败")
        else:
            self.serial_thread.stop()
            self.serial_thread.wait()
            self.connect_btn.setText("连接")
            self.read_btn.setEnabled(False)
            self.read_all_btn.setEnabled(False)
            self.auto_read_check.setChecked(False)
            self.statusBar().showMessage("未连接")
            self.append_log("串口已断开")
    
    def read_once(self):
        """读取一次数据"""
        slave_addr = self.slave_addr_spin.value()
        start_addr = self.start_addr_spin.value()
        num_regs = self.num_regs_spin.value()
        
        request = ModbusRTU.build_read_request(slave_addr, start_addr, num_regs)
        self.serial_thread.send_request(request)
        
        # 记录发送数据
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        hex_str = ' '.join([f"{b:02X}" for b in request])
        self.append_send_log(f"[{timestamp}] 发送 ({len(request)}字节): {hex_str}")
        self.append_log(f"发送读取请求: 地址{start_addr}, 数量{num_regs}")
    
    def read_all_data(self):
        """读取全部数据(0-100)"""
        slave_addr = self.slave_addr_spin.value()
        # 读取地址0-87 (88个寄存器，包含主要数据)
        request = ModbusRTU.build_read_request(slave_addr, 0, 88)
        self.serial_thread.send_request(request)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        hex_str = ' '.join([f"{b:02X}" for b in request])
        self.append_send_log(f"[{timestamp}] 发送 ({len(request)}字节): {hex_str}")
        self.append_log(f"发送读取全部数据请求")
    
    def toggle_auto_read(self, state):
        """切换自动读取"""
        if state == Qt.CheckState.Checked.value:
            interval = self.interval_spin.value()
            self.auto_read_timer.start(interval)
            self.append_log(f"启动自动读取, 间隔{interval}ms")
        else:
            self.auto_read_timer.stop()
            self.append_log("停止自动读取")
    
    def on_data_received(self, data, timestamp):
        """处理接收到的数据"""
        hex_str = ' '.join([f"{b:02X}" for b in data])
        self.append_recv_log(f"[{timestamp}] 接收 ({len(data)}字节): {hex_str}")
        
        # 解析响应
        registers, msg = ModbusRTU.parse_response(data)
        if registers:
            self.append_log(f"接收响应成功: {len(registers)}个寄存器")
            # 解析并显示数据
            start_addr = self.start_addr_spin.value()
            if self.auto_read_check.isChecked():
                start_addr = 0  # 自动读取时从0开始
            parsed_data = GP70DataParser.parse_registers(registers, start_addr)
            self.update_data_table(parsed_data)
        else:
            self.append_log(f"解析失败: {msg}")
    
    def on_error(self, error_msg):
        """处理错误"""
        self.append_log(f"错误: {error_msg}")
        self.statusBar().showMessage(f"错误: {error_msg}")
    
    def update_data_table(self, parsed_data):
        """更新数据表格"""
        self.current_data = parsed_data  # 保存数据用于导出
        self.data_table.setRowCount(len(parsed_data))
        
        for i, item in enumerate(parsed_data):
            # 地址
            self.data_table.setItem(i, 0, QTableWidgetItem(str(item['addr'])))
            # 变量名
            self.data_table.setItem(i, 1, QTableWidgetItem(item['name']))
            # 原始值
            self.data_table.setItem(i, 2, QTableWidgetItem(f"0x{item['raw']:04X}"))
            # 解析值
            if isinstance(item['value'], float):
                value_str = f"{item['value']:.2f}"
            else:
                value_str = str(item['value'])
            self.data_table.setItem(i, 3, QTableWidgetItem(value_str))
            # 单位
            self.data_table.setItem(i, 4, QTableWidgetItem(item['unit']))
            # 类型
            self.data_table.setItem(i, 5, QTableWidgetItem(item['type']))
    
    def append_log(self, text):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {text}")
    
    def append_send_log(self, text):
        """添加发送日志"""
        self.send_log.append(text)
    
    def append_recv_log(self, text):
        """添加接收日志"""
        self.recv_log.append(text)
    
    def export_to_csv(self):
        """导出数据为CSV格式"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可导出，请先读取数据")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"GP70_Data_{timestamp}.csv"
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出CSV文件",
            default_filename,
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    writer.writerow(['地址', '变量名', '原始值(HEX)', '解析值', '单位', '类型', '读取时间'])
                    # 写入数据
                    read_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for item in self.current_data:
                        value_str = f"{item['value']:.2f}" if isinstance(item['value'], float) else str(item['value'])
                        writer.writerow([
                            item['addr'],
                            item['name'],
                            f"0x{item['raw']:04X}",
                            value_str,
                            item['unit'],
                            item['type'],
                            read_time
                        ])
                
                QMessageBox.information(self, "成功", f"数据已导出到:\n{filename}")
                self.append_log(f"数据已导出到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")
                self.append_log(f"导出CSV失败: {str(e)}")
    
    def export_to_json(self):
        """导出数据为JSON格式"""
        if not self.current_data:
            QMessageBox.warning(self, "警告", "没有数据可导出，请先读取数据")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"GP70_Data_{timestamp}.json"
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出JSON文件",
            default_filename,
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if filename:
            try:
                export_data = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'device_info': {
                        'protocol': 'GP70 Modbus RTU',
                        'slave_address': self.slave_addr_spin.value(),
                        'port': self.port_combo.currentText().split(' - ')[0] if self.port_combo.currentText() else 'N/A',
                        'baudrate': int(self.baudrate_combo.currentText())
                    },
                    'data': []
                }
                
                for item in self.current_data:
                    export_data['data'].append({
                        'address': item['addr'],
                        'name': item['name'],
                        'raw_value': f"0x{item['raw']:04X}",
                        'parsed_value': item['value'],
                        'unit': item['unit'],
                        'data_type': item['type']
                    })
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", f"数据已导出到:\n{filename}")
                self.append_log(f"数据已导出到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")
                self.append_log(f"导出JSON失败: {str(e)}")
    
    def clear_logs(self):
        """清空所有日志"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要清空所有日志吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.log_text.clear()
            self.send_log.clear()
            self.recv_log.clear()
            self.append_log("日志已清空")
    
    def closeEvent(self, event):
        """关闭窗口"""
        if self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = GP70MonitorApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

