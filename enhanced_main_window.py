"""
增强版主窗口 - 集成MultiWindowManager到load_ui_dynamically
替代原有的battery_window和bit_window
"""
import sys
import asyncio
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# 导入必要的模块
from newblue3_17 import BluetoothTool, load_ui_dynamically
from log_controller import LogManager, ComunManager
from multi_window_manager import MultiWindowManager
from struct_model import HexParserApp, STRUCT_COMMANDS

# 尝试导入版本信息
try:
    import build_version_info
    VERSION_INFO_AVAILABLE = True
except ImportError:
    VERSION_INFO_AVAILABLE = False
    build_version_info = None


class EnhancedMainWindow(QMainWindow):
    """增强版主窗口 - 使用MultiWindowManager替代原有的显示方案"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化日志
        self.logger = LogManager.get_instance()
        self.logger.write_log("增强版主窗口初始化")
        
        # 初始化当前数据来源
        self.current_data_source = None
        
        # 初始化蓝牙工具
        self.bluetooth_tool = BluetoothTool()
        
        # 初始化结构体解析器
        self.hex_parser = HexParserApp()
        struct_list = self.hex_parser.get_struct_name_list()
        ComunManager.get_instance(struct_list)
        
        # 初始化数据显示管理器（用于数据解析）
        from data_display_manager import DataDisplayManager
        self.data_display_mgr = DataDisplayManager(
            parent=None,
            logger=self.logger,
            standalone=False
        )
        
        # 将data_display_mgr传递给bluetooth_tool（用于数据解析）
        self.bluetooth_tool.data_display_mgr = self.data_display_mgr
        
        # 断开定时器的旧连接，重新连接到自定义处理方法
        try:
            self.bluetooth_tool.data_timer.timeout.disconnect()
        except:
            pass
        self.bluetooth_tool.data_timer.timeout.connect(self.custom_process_complete_data)
        
        # 监控任务
        self.scan_task = None
        
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        # 构建窗口标题，包含版本信息
        base_title = '增强版BMS调试工具 - 多窗口管理'
        if VERSION_INFO_AVAILABLE:
            try:
                version_str = build_version_info.get_version_string()
                self.setWindowTitle(f'{base_title} | {version_str}')
                
                # 打印详细信息到日志
                detailed_info = build_version_info.get_detailed_info()
                self.logger.write_log("="*60)
                self.logger.write_log("版本信息:")
                self.logger.write_log(f"  打包日期: {detailed_info['build_date']}")
                self.logger.write_log(f"  Git分支: {detailed_info['git_branch']}")
                self.logger.write_log(f"  Commit: {detailed_info['git_commit_hash']}")
                self.logger.write_log(f"  提交信息: {detailed_info['git_commit_message']}")
                self.logger.write_log(f"  提交作者: {detailed_info['git_commit_author']}")
                self.logger.write_log(f"  提交时间: {detailed_info['git_commit_date']}")
                self.logger.write_log("="*60)
            except Exception as e:
                self.logger.write_log(f"读取版本信息出错: {e}")
                self.setWindowTitle(base_title)
        else:
            self.setWindowTitle(base_title)
        
        # 获取屏幕大小，设置窗口为屏幕的2/3
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        window_width = int(screen_width * 2 / 3)
        window_height = int(screen_height * 2 / 3)
        
        # 设置最小尺寸和默认尺寸
        self.setMinimumSize(int(window_width * 0.8), int(window_height * 0.8))
        self.resize(window_width, window_height)
        
        # 居中显示
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.move(x, y)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # ========== 顶部控制面板 ==========
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # ========== 多窗口管理器 ==========
        self.multi_window_manager = MultiWindowManager(
            bluetooth_tool=self.bluetooth_tool,
            logger=self.logger,
            parent=central_widget
        )
        
        # 配置数据窗口
        self.setup_data_windows()
        
        # 连接信号
        self.multi_window_manager.window_read_requested.connect(self.on_window_read)
        self.multi_window_manager.window_write_requested.connect(self.on_window_write)
        
        main_layout.addWidget(self.multi_window_manager, 1)  # 占据主要空间
        
        # ========== 底部状态栏 ==========
        status_panel = self.create_status_panel()
        main_layout.addWidget(status_panel)
        
        central_widget.setLayout(main_layout)
        
        # 设置定时器
        self.setup_timers()
        
    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title_label = QLabel('🔧 BMS调试工具控制面板')
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(14)
        title_label.setFont(font)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 连接控制
        self.connect_btn = QPushButton('📱 打开连接窗口')
        self.connect_btn.clicked.connect(self.show_bluetooth_tool)
        layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton('🔌 断开连接')
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn)
        
        # 监控控制
        self.monitor_btn = QPushButton('▶️ 开始监控')
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        self.monitor_btn.setEnabled(False)
        layout.addWidget(self.monitor_btn)
        
        # 版本查询
        self.version_btn = QPushButton('📋 查询版本')
        self.version_btn.clicked.connect(self.query_version)
        layout.addWidget(self.version_btn)
        
        # 清空队列
        self.clear_queue_btn = QPushButton('🗑️ 清空队列')
        self.clear_queue_btn.clicked.connect(self.clear_send_queue)
        layout.addWidget(self.clear_queue_btn)
        
        panel.setLayout(layout)
        panel.setMaximumHeight(60)
        
        return panel
        
    def create_status_panel(self):
        """创建状态面板"""
        panel = QWidget()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 连接状态
        self.conn_status_label = QLabel('📡 连接状态: 未连接')
        font = self.conn_status_label.font()
        font.setPointSize(11)
        self.conn_status_label.setFont(font)
        self.conn_status_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.conn_status_label)
        
        layout.addStretch()
        
        # 发送队列状态
        self.queue_status_label = QLabel('📤 发送队列: 0')
        self.queue_status_label.setFont(font)
        self.queue_status_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.queue_status_label)
        
        # 数据接收计数
        self.rx_count_label = QLabel('📥 接收: 0')
        self.rx_count_label.setFont(font)
        self.rx_count_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.rx_count_label)
        
        # 数据发送计数
        self.tx_count_label = QLabel('📤 发送: 0')
        self.tx_count_label.setFont(font)
        self.tx_count_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.tx_count_label)
        
        panel.setLayout(layout)
        panel.setMaximumHeight(40)
        
        return panel
        
    def setup_data_windows(self):
        """自动配置数据窗口（从 struct_model 获取）"""
        from struct_model import get_all_display_windows
        
        # 获取所有窗口配置
        window_configs = get_all_display_windows()
        
        # 自动添加所有窗口
        for config in window_configs:
            window_type = config.get('window_type', 'data')  # 获取窗口类型，默认为数据窗口
            self.multi_window_manager.add_window_config(
                window_id=config['window_id'],
                title=config['title'],
                column_mode=config['column_mode'],
                default_visible=config['default_visible'],
                expected_row_count=config['expected_row_count'],
                window_type=window_type
            )
        
        self.logger.write_log(f"✅ 已自动配置 {len(window_configs)} 个显示窗口")
        
    def setup_timers(self):
        """设置定时器"""
        # 队列状态更新定时器
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.update_status_display)
        self.queue_timer.start(500)  # 每0.5秒更新
        
    def show_bluetooth_tool(self):
        """显示蓝牙工具窗口"""
        self.bluetooth_tool.show()
        self.bluetooth_tool.raise_()
        self.bluetooth_tool.activateWindow()
        
        # 检查连接状态
        QTimer.singleShot(100, self.check_connection_status)
        
    def check_connection_status(self):
        """检查连接状态"""
        is_connected = False
        try:
            if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
                is_connected = True
                self.conn_status_label.setText('📡 连接状态: 蓝牙已连接')
            elif self.bluetooth_tool.is_serial_connected:
                is_connected = True
                self.conn_status_label.setText('📡 连接状态: 串口已连接')
            else:
                self.conn_status_label.setText('📡 连接状态: 未连接')
        except:
            self.conn_status_label.setText('📡 连接状态: 未连接')
        self.disconnect_btn.setEnabled(is_connected)
        self.monitor_btn.setEnabled(is_connected)
        
    def disconnect_device(self):
        """断开设备连接"""
        if self.scan_task:
            self.toggle_monitoring()
        # 判断连接类型并断开
        try:
            if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
                asyncio.create_task(self.bluetooth_tool.disconnect_device())
            elif self.bluetooth_tool.is_serial_connected:
                asyncio.create_task(self.bluetooth_tool.disconnect_serial())
        except:
            pass
        QTimer.singleShot(200, self.check_connection_status)
        
    def toggle_monitoring(self):
        """切换监控状态"""
        if self.monitor_btn.text() == '▶️ 开始监控':
            self.monitor_btn.setText('⏸️ 停止监控')
            self.scan_task = asyncio.create_task(self.monitoring_loop())
            self.logger.write_log("开始监控")
        else:
            self.monitor_btn.setText('▶️ 开始监控')
            if self.scan_task:
                self.scan_task.cancel()
                self.scan_task = None
            self.logger.write_log("停止监控")
            
    async def monitoring_loop(self):
        """监控循环 - 定期查询数据"""
        try:
            while True:
                # 获取监控间隔时间
                interval = self.bluetooth_tool.monitor_interval_spinbox.value()
                
                # 查询SBS数据
                await self.queue_send_command(0x13, "PC_GET_SBS")
                await asyncio.sleep(interval)
                
                # 查询TBS数据
                # await self.queue_send_command(0x15, "PC_GET_TBS")
                # await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            self.logger.write_log("监控循环已停止")
        except Exception as e:
            self.logger.write_log(f"监控循环错误: {str(e)}")
            traceback.print_exc()
            
    async def queue_send_command(self, cmd_code, struct_name=None, priority=False):
        """通过队列发送命令
        
        Args:
            cmd_code: 命令码
            struct_name: 结构体名称（用于记录）
            priority: 是否优先发送（手动点击的指令设为True）
        """
        try:
            data = self.bluetooth_tool.text_decode.send_hex_fill(cmd_code)
            await self.multi_window_manager.queue_send(data, priority=priority)
            
            if struct_name:
                self.current_data_source = struct_name
                
        except Exception as e:
            self.logger.write_log(f"发送命令失败: {str(e)}")
            
    def query_version(self):
        """查询版本"""
        asyncio.create_task(self.queue_send_command(0x71, "VERSION"))
        
    def clear_send_queue(self):
        """清空发送队列"""
        self.multi_window_manager.clear_send_queue()
        self.logger.write_log("已清空发送队列")
        
    def update_status_display(self):
        """更新状态显示"""
        # 更新队列状态
        queue_len = self.multi_window_manager.get_queue_length()
        self.queue_status_label.setText(f'📤 发送队列: {queue_len}')
        
        # 检查连接状态
        self.check_connection_status()
        
    def on_window_read(self, window_id):
        """处理窗口读取请求（手动点击，优先发送）"""
        self.logger.write_log(f"🖱️ 收到手动读取请求: {window_id}")
        
        # 根据window_id获取对应的命令码（直接从STRUCT_COMMANDS获取）
        from struct_model import STRUCT_COMMANDS
        cmd_code = STRUCT_COMMANDS.get(window_id)
        
        if cmd_code:
            # 手动点击的读取指令，使用优先发送
            asyncio.create_task(self.queue_send_command(cmd_code, window_id, priority=True))
        else:
            self.logger.write_log(f"未找到窗口 {window_id} 对应的读取命令")
            
    def on_window_write(self, window_id, modified_data):
        """处理窗口写入请求"""
        self.logger.write_log(f"收到写入请求: {window_id}, 修改项数: {len(modified_data)}")
        asyncio.create_task(self.process_write_request(window_id, modified_data))
        
    async def process_write_request(self, window_id, modified_data):
        """处理写入请求"""
        try:
            # 获取写入命令码
            from struct_model import get_write_command_code, STRUCT_FORMATS
            import struct
            
            cmd_code = get_write_command_code(window_id)
            if not cmd_code:
                self.logger.write_log(f"窗口 {window_id} 不支持写入")
                return
            
            # 获取当前窗口的所有数据
            window = self.multi_window_manager.windows.get(window_id)
            if not window or not window.table_model:
                self.logger.write_log(f"无法获取窗口数据")
                return
            
            original_data = window.table_model._original_data
            
            # 构建修改映射 {row: write_value}
            modifications = {}
            for row, param_name, current_value, write_value in modified_data:
                modifications[row] = write_value
            
            # 准备要写入的值列表
            write_values = []
            import re
            fmt = STRUCT_FORMATS.get(window_id, '')
            
            # 检查格式中是否包含字符串类型
            has_string_field = 's' in fmt
            
            for row_idx, row_data in enumerate(original_data):
                if row_idx in modifications:
                    value_str = modifications[row_idx]
                else:
                    value_str = row_data[2] if len(row_data) > 2 else row_data[1]
                
                # 如果格式包含字符串类型，且当前值是str或bytes，强制作为字符串处理
                if has_string_field and isinstance(value_str, (str, bytes)):
                    # 转换为bytes
                    if isinstance(value_str, bytes):
                        value_bytes = value_str
                    else:
                        # 对于字符串格式，即使是纯数字也当字符串处理
                        value_bytes = value_str.encode('utf-8', errors='ignore')
                    
                    # 提取目标长度并补全/截断
                    match = re.search(r'(\d+)s', fmt)
                    if match:
                        target_len = int(match.group(1))
                        if len(value_bytes) < target_len:
                            value_bytes += b'\xFF' * (target_len - len(value_bytes))
                        elif len(value_bytes) > target_len:
                            value_bytes = value_bytes[:target_len]
                    write_values.append(value_bytes)
                else:
                    # 数值类型字段
                    try:
                        if isinstance(value_str, str) and value_str.startswith('0x'):
                            value = int(value_str, 16)
                        else:
                            value = int(value_str)
                        write_values.append(value)
                    except (ValueError, TypeError):
                        self.logger.write_log(f"行{row_idx}值转换失败: {value_str}")
                        write_values.append(0)
            
            # 根据结构体格式打包
            if window_id not in STRUCT_FORMATS:
                self.logger.write_log(f"未找到结构体格式: {window_id}")
                return
            
            fmt = STRUCT_FORMATS[window_id]
            
            try:
                packed_data = struct.pack(fmt, *write_values)
            except struct.error as e:
                self.logger.write_log(f"数据打包失败: {str(e)}")
                return
            
            # 构造完整命令
            try:
                full_command = self.bluetooth_tool.text_decode.send_hex_fill(cmd_code, packed_data)
            except Exception as e:
                self.logger.write_log(f"命令构造失败: {str(e)}")
                traceback.print_exc()
                return
            
            # 通过队列发送
            await self.multi_window_manager.queue_send(full_command, priority=True)
            self.logger.write_log(f"✅ 写入命令已发送: {window_id}")
            
            # 不清空写入值，保留用户输入
            # self.multi_window_manager.clear_window_write_values(window_id)
            
        except Exception as e:
            self.logger.write_log(f"处理写入请求失败: {str(e)}")
            traceback.print_exc()
            
    def custom_process_complete_data(self):
        """自定义数据处理方法（替代bluetooth_tool的原始方法）"""
        try:
            # 获取接收到的数据
            if not hasattr(self.bluetooth_tool, 'received_data_buffer'):
                return
                
            data_buffer = bytes(self.bluetooth_tool.received_data_buffer)
            
            if len(data_buffer) == 0:
                return
            
            # 检查是否是密码响应（原始方法的逻辑）
            if self.bluetooth_tool.check_new_password_response(data_buffer):
                self.bluetooth_tool.handle_new_password_response(data_buffer)
            else:
                # 提取响应命令码（用于发射信号）
                response_cmd_code = None
                if len(data_buffer) >= 5:
                    response_cmd_code = data_buffer[4] & 0x7F  # 去掉0x80标志，获取原始命令码
                
                # 使用data_display_mgr解析数据
                if hasattr(self.bluetooth_tool, 'data_display_mgr') and self.bluetooth_tool.data_display_mgr:
                    success, result = self.bluetooth_tool.data_display_mgr.parse_and_update_displays(data_buffer)
                    
                    if success:
                        struct_name = result['struct_name']
                        dict_data = result['data']
                        
                        # 更新多窗口管理器
                        self.update_window_data_from_parsed_result(struct_name, dict_data)
                        
                        # 更新位标志窗口（如果有SBS数据）
                        if struct_name == 'PC_GET_SBS':
                            self.update_bit_flags_window(dict_data)
                        
                        # 记录CSV
                        from log_controller import ComunManager
                        header = f"RX->,{self.bluetooth_tool.commu_type},{self.bluetooth_tool.device_name},{struct_name}"
                        csv_data = ",".join([item[2] for items in dict_data.values() for item in items if len(item) >= 3])
                        ComunManager.get_instance().write_csv(f"{header},{csv_data}")
                        
                        # 🔥 发射信号通知队列管理器：数据接收成功
                        from struct_model import STRUCT_COMMANDS
                        cmd_code = STRUCT_COMMANDS.get(struct_name, 0)
                        self.bluetooth_tool.receive_ok_signal.emit(cmd_code, data_buffer)
                    else:
                        # 解析失败，但仍然发射信号（用于写入命令的简单确认响应）
                        if response_cmd_code is not None:
                            self.bluetooth_tool.receive_ok_signal.emit(response_cmd_code, data_buffer)
                else:
                    # data_display_mgr未初始化，仍然发射信号
                    if response_cmd_code is not None:
                        self.bluetooth_tool.receive_ok_signal.emit(response_cmd_code, data_buffer)
                    self.logger.write_log("错误：data_display_mgr未初始化")
            
            # 显示接收到的数据（原始逻辑）
            self.bluetooth_tool.display_received_data(data_buffer)
            
            # 清空缓冲区
            self.bluetooth_tool.received_data_buffer.clear()
                        
        except Exception as e:
            self.logger.write_log(f"custom_process_complete_data错误: {str(e)}")
            traceback.print_exc()
    
    def update_window_data_from_parsed_result(self, struct_name, dict_data):
        """根据解析结果更新窗口数据
        
        Args:
            struct_name: 结构体名称
            dict_data: 解析后的字典数据
        """
        try:
            # 格式化数据为 (name, read_value, write_value) 三元组
            formatted_data = []
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        name, unit, value = item[0], item[1], item[2]
                        formatted_data.append((name, value, value))
            
            # 更新对应的窗口
            if formatted_data:
                self.multi_window_manager.update_window_data(struct_name, formatted_data)
                
        except Exception as e:
            self.logger.write_log(f"更新窗口数据失败: {str(e)}")
            traceback.print_exc()
    
    def update_bit_flags_window(self, dict_data):
        """更新状态位窗口（告警-保护、其他状态信息、电池状态）
        
        Args:
            dict_data: SBS解析后的字典数据
        """
        try:
            from struct_model import (
                get_alarm_protect_display_data,
                get_other_status_display_data,
                get_battery_status_display_data
            )
            
            # 将dict_data转换为flat_dict（需要转换为整数）
            flat_dict = {}
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        name, unit, value_str = item[0], item[1], item[2]
                        # 尝试将字符串转换为整数（对于状态位字段）
                        try:
                            # 如果是十六进制字符串
                            if isinstance(value_str, str) and value_str.startswith('0x'):
                                flat_dict[name] = int(value_str, 16)
                            else:
                                flat_dict[name] = int(value_str)
                        except (ValueError, TypeError):
                            # 如果转换失败，保持原值
                            flat_dict[name] = value_str
            
            # 更新告警-保护信息窗口
            alarm_protect_data = get_alarm_protect_display_data(flat_dict)
            if alarm_protect_data and 'ALARM_PROTECT' in self.multi_window_manager.windows:
                self.multi_window_manager.update_window_data('ALARM_PROTECT', alarm_protect_data)
            
            # 更新其他状态信息窗口
            other_status_data = get_other_status_display_data(flat_dict)
            if other_status_data and 'OTHER_STATUS' in self.multi_window_manager.windows:
                self.multi_window_manager.update_window_data('OTHER_STATUS', other_status_data)
            
            # 更新电池状态窗口
            battery_status_data = get_battery_status_display_data(flat_dict)
            if battery_status_data and 'BATTERY_STATUS' in self.multi_window_manager.windows:
                self.multi_window_manager.update_window_data('BATTERY_STATUS', battery_status_data)
                
        except Exception as e:
            self.logger.write_log(f"更新状态位窗口失败: {str(e)}")
            traceback.print_exc()
            
    def closeEvent(self, event):
        """重写关闭事件"""
        # 停止监控
        if self.scan_task:
            self.scan_task.cancel()
            
        # 关闭日志
        self.logger.close_log()
        
        # 断开连接
        if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
            asyncio.create_task(self.bluetooth_tool.disconnect_device())
            
        event.accept()


# ==================== 程序入口 ====================

def main():
    """主函数"""
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # 使用Fusion样式，跟随系统颜色
        # 设置事件循环
        from qasync import QEventLoop
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # 创建主窗口
        window = EnhancedMainWindow()
        window.show()
        
        # 运行事件循环
        with loop:
            loop.run_forever()
            
    except Exception as e:
        print(f"程序错误: {str(e)}")
        traceback.print_exc()
        

if __name__ == "__main__":
    main()

