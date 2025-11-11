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
        self.setWindowTitle('增强版BMS调试工具 - 多窗口管理')
        
        # 设置自适应大小
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        
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
        panel.setStyleSheet("""
            QWidget {
                background-color: #ecf0f1;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        
        layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel('🔧 BMS调试工具控制面板')
        title_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; background: none; }")
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
        panel.setStyleSheet("""
            QWidget {
                background-color: #34495e;
                border-radius: 5px;
                padding: 5px;
            }
            QLabel {
                color: #ecf0f1;
                font-size: 11px;
                background: none;
                padding: 3px 10px;
            }
        """)
        
        layout = QHBoxLayout()
        
        # 连接状态
        self.conn_status_label = QLabel('📡 连接状态: 未连接')
        layout.addWidget(self.conn_status_label)
        
        layout.addStretch()
        
        # 发送队列状态
        self.queue_status_label = QLabel('📤 发送队列: 0')
        layout.addWidget(self.queue_status_label)
        
        # 数据接收计数
        self.rx_count_label = QLabel('📥 接收: 0')
        layout.addWidget(self.rx_count_label)
        
        # 数据发送计数
        self.tx_count_label = QLabel('📤 发送: 0')
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
            self.multi_window_manager.add_window_config(
                window_id=config['window_id'],
                title=config['title'],
                column_mode=config['column_mode'],
                default_visible=config['default_visible'],
                expected_row_count=config['expected_row_count']
            )
        
        self.logger.write_log(f"✅ 已自动配置 {len(window_configs)} 个数据窗口")
        
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
        
        if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
            is_connected = True
            self.conn_status_label.setText('📡 连接状态: 蓝牙已连接')
        elif self.bluetooth_tool.serial_port and self.bluetooth_tool.serial_port.is_open:
            is_connected = True
            self.conn_status_label.setText('📡 连接状态: 串口已连接')
        else:
            self.conn_status_label.setText('📡 连接状态: 未连接')
            
        # 更新按钮状态
        self.disconnect_btn.setEnabled(is_connected)
        self.monitor_btn.setEnabled(is_connected)
        
    def disconnect_device(self):
        """断开设备连接"""
        if self.scan_task:
            self.toggle_monitoring()  # 停止监控
            
        self.bluetooth_tool.on_disconnect_device_clicked()
        
        QTimer.singleShot(200, self.check_connection_status)
        
    def toggle_monitoring(self):
        """切换监控状态"""
        if self.monitor_btn.text() == '▶️ 开始监控':
            self.monitor_btn.setText('⏸️ 停止监控')
            self.monitor_btn.setStyleSheet("QPushButton { background-color: #e74c3c; }")
            self.scan_task = asyncio.create_task(self.monitoring_loop())
            self.logger.write_log("开始监控")
        else:
            self.monitor_btn.setText('▶️ 开始监控')
            self.monitor_btn.setStyleSheet("")
            if self.scan_task:
                self.scan_task.cancel()
                self.scan_task = None
            self.logger.write_log("停止监控")
            
    async def monitoring_loop(self):
        """监控循环 - 定期查询数据"""
        try:
            while True:
                # 查询SBS数据
                await self.queue_send_command(0x13, "PC_GET_SBS")
                await asyncio.sleep(1)
                
                # 查询TBS数据
                # await self.queue_send_command(0x15, "PC_GET_TBS")
                # await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            self.logger.write_log("监控循环已停止")
        except Exception as e:
            self.logger.write_log(f"监控循环错误: {str(e)}")
            traceback.print_exc()
            
    async def queue_send_command(self, cmd_code, struct_name=None):
        """通过队列发送命令
        
        Args:
            cmd_code: 命令码
            struct_name: 结构体名称（用于记录）
        """
        try:
            data = self.bluetooth_tool.text_decode.send_hex_fill(cmd_code)
            await self.multi_window_manager.queue_send(data, priority=False)
            
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
        """处理窗口读取请求"""
        self.logger.write_log(f"收到读取请求: {window_id}")
        
        # 根据window_id获取对应的命令码（直接从STRUCT_COMMANDS获取）
        from struct_model import STRUCT_COMMANDS
        cmd_code = STRUCT_COMMANDS.get(window_id)
        
        if cmd_code:
            asyncio.create_task(self.queue_send_command(cmd_code, window_id))
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
            
            # 准备要写入的值列表（有写入值用写入值，否则用当前值）
            write_values = []
            for row_idx, row_data in enumerate(original_data):
                if row_idx in modifications:
                    value_str = modifications[row_idx]
                else:
                    value_str = row_data[2] if len(row_data) > 2 else row_data[1]
                
                # 转换为整数
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
                self.logger.write_log(f"写入命令已构造: {len(full_command)} 字节")
            except Exception as e:
                self.logger.write_log(f"命令构造失败: {str(e)}")
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
                # 使用data_display_mgr解析数据
                if hasattr(self.bluetooth_tool, 'data_display_mgr') and self.bluetooth_tool.data_display_mgr:
                    success, result = self.bluetooth_tool.data_display_mgr.parse_and_update_displays(data_buffer)
                    
                    if success:
                        struct_name = result['struct_name']
                        dict_data = result['data']
                        
                        # 更新多窗口管理器
                        self.update_window_data_from_parsed_result(struct_name, dict_data)
                        
                        # 记录CSV
                        from log_controller import ComunManager
                        header = f"RX->,{self.bluetooth_tool.commu_type},{self.bluetooth_tool.device_name},{struct_name}"
                        csv_data = ",".join([item[2] for items in dict_data.values() for item in items if len(item) >= 3])
                        ComunManager.get_instance().write_csv(f"{header},{csv_data}")
                else:
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

