"""
集成示例 - 展示如何在主程序中使用MultiWindowManager
"""
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt
import sys

# 假设这些模块已经导入
# from newblue3_17 import BluetoothTool
# from log_controller import LogManager
from multi_window_manager import MultiWindowManager


class EnhancedMainWindow(QMainWindow):
    """增强版主窗口 - 集成MultiWindowManager"""
    
    def __init__(self, bluetooth_tool, logger):
        super().__init__()
        self.bluetooth_tool = bluetooth_tool
        self.logger = logger
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('增强版蓝牙调试工具')
        
        # 设置自适应大小
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        
        # ========== 顶部控制区域 ==========
        control_layout = QHBoxLayout()
        
        # 连接按钮
        self.connect_btn = QPushButton('打开连接窗口')
        self.connect_btn.clicked.connect(self.show_bluetooth_tool)
        control_layout.addWidget(self.connect_btn)
        
        # 断开按钮
        self.disconnect_btn = QPushButton('断开连接')
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        control_layout.addWidget(self.disconnect_btn)
        
        # 监控按钮
        self.monitor_btn = QPushButton('开始监控')
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        control_layout.addWidget(self.monitor_btn)
        
        control_layout.addStretch()
        
        # 队列状态显示
        self.queue_status_label = QLabel('发送队列: 0')
        control_layout.addWidget(self.queue_status_label)
        
        main_layout.addLayout(control_layout)
        
        # ========== 多窗口管理器区域 ==========
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
        
        main_layout.addWidget(self.multi_window_manager, 1)  # 占据大部分空间
        
        central_widget.setLayout(main_layout)
        
        # 设置定时器更新队列状态
        from PyQt6.QtCore import QTimer
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.update_queue_status)
        self.queue_timer.start(1000)  # 每秒更新
        
    def setup_data_windows(self):
        """配置数据窗口"""
        # 可配置的窗口（3列：名称、读取值、写入值）
        self.multi_window_manager.add_window_config(
            window_id='write_protect_params',
            title='写保护参数配置',
            column_mode=3,
            default_visible=True
        )
        
        self.multi_window_manager.add_window_config(
            window_id='battery_params',
            title='电池参数配置',
            column_mode=3,
            default_visible=True
        )
        
        # 只读窗口（2列：名称、当前值）
        self.multi_window_manager.add_window_config(
            window_id='sbs_data',
            title='SBS数据',
            column_mode=2,
            default_visible=True
        )
        
        self.multi_window_manager.add_window_config(
            window_id='tbs_data',
            title='TBS数据',
            column_mode=2,
            default_visible=False
        )
        
        self.multi_window_manager.add_window_config(
            window_id='bms_status',
            title='BMS状态',
            column_mode=2,
            default_visible=False
        )
        
        self.multi_window_manager.add_window_config(
            window_id='cell_voltages',
            title='单体电压',
            column_mode=2,
            default_visible=True
        )
        
        self.multi_window_manager.add_window_config(
            window_id='temperatures',
            title='温度数据',
            column_mode=2,
            default_visible=True
        )
        
    def show_bluetooth_tool(self):
        """显示蓝牙工具窗口"""
        if hasattr(self, 'bluetooth_tool') and self.bluetooth_tool:
            self.bluetooth_tool.show()
            self.bluetooth_tool.raise_()
            self.bluetooth_tool.activateWindow()
            
    def disconnect_device(self):
        """断开设备连接"""
        if hasattr(self, 'bluetooth_tool') and self.bluetooth_tool:
            self.bluetooth_tool.on_disconnect_device_clicked()
            
    def toggle_monitoring(self):
        """切换监控状态"""
        # 这里实现监控逻辑
        if self.monitor_btn.text() == '开始监控':
            self.monitor_btn.setText('停止监控')
            # 启动监控任务
            self.start_monitoring()
        else:
            self.monitor_btn.setText('开始监控')
            # 停止监控任务
            self.stop_monitoring()
            
    def start_monitoring(self):
        """启动监控"""
        import asyncio
        if not hasattr(self, 'monitor_task') or self.monitor_task is None:
            self.monitor_task = asyncio.create_task(self.monitoring_loop())
            
    def stop_monitoring(self):
        """停止监控"""
        if hasattr(self, 'monitor_task') and self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None
            
    async def monitoring_loop(self):
        """监控循环"""
        import asyncio
        while True:
            try:
                # 轮询发送查询命令
                # 例如：查询SBS数据
                await self.queue_send_command(0x13)  # SBS命令
                await asyncio.sleep(1)
                
                # 查询TBS数据
                await self.queue_send_command(0x15)  # TBS命令
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.write_log(f"监控循环错误: {str(e)}")
                await asyncio.sleep(1)
                
    async def queue_send_command(self, cmd_code):
        """通过队列发送命令"""
        if hasattr(self.bluetooth_tool, 'text_decode'):
            data = self.bluetooth_tool.text_decode.send_hex_fill(cmd_code)
            await self.multi_window_manager.queue_send(data, priority=False)
            
    def on_window_read(self, window_id):
        """处理窗口读取请求"""
        self.logger.write_log(f"收到读取请求: {window_id}")
        
        # 根据window_id发送对应的读取命令
        cmd_map = {
            'write_protect_params': 0x52,  # 假设的命令码
            'battery_params': 0x13,
            'sbs_data': 0x13,
            'tbs_data': 0x15,
        }
        
        if window_id in cmd_map:
            import asyncio
            asyncio.create_task(self.queue_send_command(cmd_map[window_id]))
            
    def on_window_write(self, window_id, modified_data):
        """处理窗口写入请求"""
        self.logger.write_log(f"收到写入请求: {window_id}, 修改项: {len(modified_data)}")
        
        # 根据window_id和modified_data构造写入命令
        # 这里需要根据实际的协议实现
        
        # 示例：将修改打包成写入命令并通过队列发送
        import asyncio
        asyncio.create_task(self.process_write_request(window_id, modified_data))
        
    async def process_write_request(self, window_id, modified_data):
        """处理写入请求"""
        try:
            # 1. 构造写入数据包
            # 这里需要根据实际的数据格式实现
            
            # 2. 通过队列发送（优先发送写入命令）
            # write_data = self.build_write_packet(window_id, modified_data)
            # await self.multi_window_manager.queue_send(write_data, priority=True)
            
            # 3. 清空写入值
            self.multi_window_manager.clear_window_write_values(window_id)
            
            self.logger.write_log(f"写入命令已加入队列: {window_id}")
            
        except Exception as e:
            self.logger.write_log(f"处理写入请求失败: {str(e)}")
            
    def update_queue_status(self):
        """更新队列状态显示"""
        queue_len = self.multi_window_manager.get_queue_length()
        self.queue_status_label.setText(f'发送队列: {queue_len}')
        
    def update_window_data_from_parsed_result(self, struct_name, dict_data):
        """根据解析结果更新窗口数据
        
        Args:
            struct_name: 结构体名称（例如：'PC_GET_SBS'）
            dict_data: 解析后的字典数据
        """
        # 将dict_data转换为窗口需要的格式
        formatted_data = []
        for category, items in dict_data.items():
            for item in items:
                if len(item) >= 3:
                    name, unit, value = item[0], item[1], item[2]
                    formatted_data.append((name, value, value))
                    
        # 根据struct_name更新对应的窗口
        window_mapping = {
            'PC_GET_SBS': 'sbs_data',
            'PC_GET_TBS': 'tbs_data',
            'PC_GET_BMS': 'bms_status',
            'PC_GET_WRITE_PROTECT': 'write_protect_params',
        }
        
        window_id = window_mapping.get(struct_name)
        if window_id and formatted_data:
            self.multi_window_manager.update_window_data(window_id, formatted_data)
            self.logger.write_log(f"更新窗口数据: {window_id}, {len(formatted_data)}项")


# ==================== 集成到现有的load_ui_dynamically类 ====================

def integrate_into_existing_main_window(existing_window_class):
    """
    将MultiWindowManager集成到现有的load_ui_dynamically类
    
    使用步骤：
    1. 在__init__中创建MultiWindowManager
    2. 替换原有的battery_window和bit_window布局
    3. 在process_complete_data中更新窗口数据
    """
    
    # 在__init__中添加：
    """
    # 创建多窗口管理器
    self.multi_window_manager = MultiWindowManager(
        bluetooth_tool=self.bluetooth_tool,
        logger=self.logger,
        parent=self
    )
    
    # 配置窗口
    self.setup_multi_windows()
    
    # 设置位置（替换原有的battery_window和bit_window）
    self.multi_window_manager.setGeometry(150, 10, 980, 580)
    self.multi_window_manager.show()
    
    # 连接信号
    self.multi_window_manager.window_read_requested.connect(self.on_multi_window_read)
    self.multi_window_manager.window_write_requested.connect(self.on_multi_window_write)
    """
    
    # 添加setup_multi_windows方法：
    """
    def setup_multi_windows(self):
        '''配置多窗口'''
        # 写保护参数（3列）
        self.multi_window_manager.add_window_config(
            'write_protect', '写保护参数', 3, True
        )
        
        # SBS数据（2列）
        self.multi_window_manager.add_window_config(
            'sbs_data', 'SBS数据', 2, True
        )
        
        # 单体电压（2列）
        self.multi_window_manager.add_window_config(
            'cell_voltages', '单体电压', 2, True
        )
    """
    
    # 在process_complete_data中使用：
    """
    def process_complete_data(self):
        '''处理完整数据包'''
        # ... 原有的解析逻辑 ...
        
        success, result = self.data_display_mgr.parse_and_update_displays(
            self.received_data_buffer
        )
        
        if success:
            struct_name = result['struct_name']
            dict_data = result['data']
            
            # 格式化数据
            formatted_data = []
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        formatted_data.append((item[0], item[2], item[2]))
            
            # 更新对应的窗口
            window_map = {
                'PC_GET_SBS': 'sbs_data',
                'PC_GET_WRITE_PROTECT': 'write_protect'
            }
            
            window_id = window_map.get(struct_name)
            if window_id:
                self.multi_window_manager.update_window_data(window_id, formatted_data)
    """
    
    pass


if __name__ == "__main__":
    print("这是一个集成示例文件")
    print("请参考代码注释，将MultiWindowManager集成到您的主程序中")
    print("\n主要步骤：")
    print("1. 导入MultiWindowManager")
    print("2. 在主窗口中创建MultiWindowManager实例")
    print("3. 配置需要的数据窗口")
    print("4. 连接读取/写入信号")
    print("5. 在数据接收处理函数中更新窗口数据")
    print("6. 使用queue_send方法发送数据")

