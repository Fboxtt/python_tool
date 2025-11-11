"""
多窗口管理器 - 支持多个batterywindow窗口的显示和管理
支持checkbox控制窗口显示/隐藏，自适应布局
"""
import asyncio
from collections import deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QLabel, QPushButton, QScrollArea,
    QGroupBox, QTableView, QAbstractItemView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from display_widgets import BatteryTableModel


# ============== 蓝牙队列发送管理器 ==============
class BluetoothQueueSender:
    """蓝牙队列发送管理器
    
    确保数据按顺序发送，避免数据冲突
    """
    
    def __init__(self, bluetooth_tool, logger=None):
        """
        Args:
            bluetooth_tool: BluetoothTool实例
            logger: 日志记录器
        """
        self.bluetooth_tool = bluetooth_tool
        self.logger = logger
        self.send_queue = deque()  # 发送队列
        self.is_sending = False  # 是否正在发送
        self.send_lock = asyncio.Lock()  # 发送锁
        
    async def add_to_queue(self, data_bytes, priority=False):
        """添加数据到发送队列
        
        Args:
            data_bytes: 要发送的字节数据
            priority: 是否优先发送
        """
        if priority:
            self.send_queue.appendleft(data_bytes)  # 优先级高的插入队首
        else:
            self.send_queue.append(data_bytes)  # 普通的添加到队尾
            
        if self.logger:
            self.logger.write_log(f"添加数据到发送队列，队列长度: {len(self.send_queue)}")
            
        # 如果没有正在发送，启动发送任务
        if not self.is_sending:
            asyncio.create_task(self._process_queue())
            
    async def _process_queue(self):
        """处理发送队列"""
        async with self.send_lock:
            self.is_sending = True
            
            try:
                while self.send_queue:
                    data_bytes = self.send_queue.popleft()
                    
                    try:
                        # 发送数据
                        await self.bluetooth_tool.byte_send(data_bytes)
                        self.bluetooth_tool.display_send_data(data_bytes)
                        
                        if self.logger:
                            self.logger.write_log(f"队列发送成功，剩余队列长度: {len(self.send_queue)}")
                        
                        # 发送间隔，避免设备处理不过来
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        if self.logger:
                            self.logger.write_log(f"队列发送失败: {str(e)}")
                        # 发送失败，可以选择重试或跳过
                        break
                        
            finally:
                self.is_sending = False
                
    def clear_queue(self):
        """清空发送队列"""
        self.send_queue.clear()
        if self.logger:
            self.logger.write_log("已清空发送队列")
            
    def get_queue_length(self):
        """获取队列长度"""
        return len(self.send_queue)


# ============== 单个数据显示窗口 ==============
class DataDisplayWindow(QWidget):
    """单个数据显示窗口
    
    支持2列和3列两种模式：
    - 2列模式：名称 | 当前值
    - 3列模式：名称 | 读取值 | 写入值（可编辑）
    """
    
    def __init__(self, window_id, title, column_mode=2, parent=None):
        """
        Args:
            window_id: 窗口ID
            title: 窗口标题
            column_mode: 列数模式（2或3）
            parent: 父窗口
        """
        super().__init__(parent)
        self.window_id = window_id
        self.title = title
        self.column_mode = column_mode
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("QLabel { color: blue; font-weight: bold; font-size: 10px; }")
        layout.addWidget(title_label)
        
        # 创建表格视图
        self.table_view = QTableView()
        
        # 根据列模式创建不同的数据模型
        if self.column_mode == 2:
            self.table_model = TwoColumnTableModel()
            self.table_view.setColumnWidth(0, 120)  # 名称列
            self.table_view.setColumnWidth(1, 100)  # 当前值列
        else:  # 3列模式
            self.table_model = BatteryTableModel()
            # 只显示第一组列（3列）
            for col in range(3, 9):
                self.table_view.setColumnHidden(col, True)
            self.table_view.setColumnWidth(0, 100)  # 名称列
            self.table_view.setColumnWidth(1, 80)   # 读取值列
            self.table_view.setColumnWidth(2, 80)   # 写入值列
            
        self.table_view.setModel(self.table_model)
        
        # 设置表格属性
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setVisible(False)
        
        # 自适应字体大小
        table_font = self.table_view.font()
        table_font.setPointSize(8)
        self.table_view.setFont(table_font)
        
        # 设置行高
        self.table_view.verticalHeader().setDefaultSectionSize(20)
        self.table_view.verticalHeader().setMinimumSectionSize(18)
        
        # 设置表头字体
        header_font = self.table_view.horizontalHeader().font()
        header_font.setPointSize(8)
        self.table_view.horizontalHeader().setFont(header_font)
        
        # 设置大小策略为可扩展
        self.table_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.table_view)
        
        # 添加按钮（所有窗口都有读取按钮）
        button_layout = QHBoxLayout()
        self.read_button = QPushButton('🔄 读取')
        self.read_button.setMaximumWidth(70)
        button_layout.addWidget(self.read_button)
        
        # 3列模式额外添加写入按钮
        if self.column_mode == 3:
            self.write_button = QPushButton('✏️ 写入')
            self.write_button.setMaximumWidth(70)
            button_layout.addWidget(self.write_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 设置窗口边框
        self.setStyleSheet("""
            DataDisplayWindow {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white;
            }
        """)
        
    def update_data(self, data):
        """更新数据
        
        Args:
            data: 数据列表，格式根据列模式不同：
                2列: [(name, value), ...]
                3列: [(name, hex_value, dec_value), ...]
        """
        if self.table_model:
            self.table_model.update_data(data)
            
    def get_modified_data(self):
        """获取修改的数据（仅3列模式）"""
        if self.column_mode == 3 and hasattr(self.table_model, 'get_modified_data'):
            return self.table_model.get_modified_data()
        return []
        
    def clear_write_values(self):
        """清空写入值（仅3列模式）"""
        if self.column_mode == 3 and hasattr(self.table_model, 'clear_write_values'):
            self.table_model.clear_write_values()
            
    def adjust_size_to_content(self):
        """根据内容自适应调整大小"""
        # 计算所需高度
        row_count = self.table_model.rowCount()
        row_height = self.table_view.verticalHeader().defaultSectionSize()
        header_height = self.table_view.horizontalHeader().height()
        
        # 标题和按钮的高度（现在所有窗口都有按钮）
        extra_height = 60
        
        # 计算总高度
        total_height = header_height + row_count * row_height + extra_height
        
        # 计算所需宽度
        if self.column_mode == 2:
            total_width = 240
        else:
            total_width = 280
            
        # 设置最小和首选大小
        self.setMinimumSize(total_width, min(total_height, 600))
        self.setMaximumHeight(600)


# ============== 2列表格模型 ==============
class TwoColumnTableModel(BatteryTableModel):
    """2列表格模型（名称 | 当前值）"""
    
    def __init__(self, data=None, parent=None):
        super().__init__(data, parent)
        self._columns = 2
        self._headers = ['参数名', '当前值']
        
    def _organize_data(self):
        """重新组织数据为2列"""
        self._organized_data = []
        
        for row_data in self._original_data:
            if len(row_data) >= 3:
                self._organized_data.append([
                    row_data[0],  # 名称
                    self._get_cached_display_value(self._original_data.index(row_data), row_data[2])  # 当前值
                ])
                
    def flags(self, index):
        """2列模式下所有单元格都不可编辑"""
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


# ============== 多窗口管理器主窗口 ==============
class MultiWindowManager(QWidget):
    """多窗口管理器主窗口
    
    左侧：checkbox列表，控制窗口显示
    右侧：多个数据显示窗口的网格布局
    """
    
    # 定义信号
    window_read_requested = pyqtSignal(str)  # 请求读取数据，参数为window_id
    window_write_requested = pyqtSignal(str, list)  # 请求写入数据，参数为window_id和修改数据列表
    
    def __init__(self, bluetooth_tool, logger=None, parent=None):
        """
        Args:
            bluetooth_tool: BluetoothTool实例
            logger: 日志记录器
            parent: 父窗口
        """
        super().__init__(parent)
        self.bluetooth_tool = bluetooth_tool
        self.logger = logger
        
        # 窗口配置列表
        self.window_configs = []
        
        # 窗口实例字典 {window_id: DataDisplayWindow}
        self.windows = {}
        
        # checkbox字典 {window_id: QCheckBox}
        self.checkboxes = {}
        
        # 初始化蓝牙队列发送器
        self.queue_sender = BluetoothQueueSender(bluetooth_tool, logger)
        
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # ========== 左侧：checkbox区域 ==========
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_label = QLabel('数据窗口控制')
        title_label.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; }")
        left_layout.addWidget(title_label)
        
        # checkbox滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumWidth(200)
        
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout()
        self.checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.checkbox_container.setLayout(self.checkbox_layout)
        scroll_area.setWidget(self.checkbox_container)
        
        left_layout.addWidget(scroll_area)
        
        # 控制按钮
        button_layout = QVBoxLayout()
        
        self.select_all_btn = QPushButton('全选')
        self.select_all_btn.clicked.connect(self.select_all_windows)
        button_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton('全不选')
        self.deselect_all_btn.clicked.connect(self.deselect_all_windows)
        button_layout.addWidget(self.deselect_all_btn)
        
        left_layout.addLayout(button_layout)
        left_layout.addStretch()
        
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(220)
        
        # ========== 右侧：窗口显示区域 ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # 窗口显示区域标题
        display_title = QLabel('数据显示窗口')
        display_title.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; }")
        right_layout.addWidget(display_title)
        
        # 滚动区域
        display_scroll = QScrollArea()
        display_scroll.setWidgetResizable(True)
        
        self.window_container = QWidget()
        self.window_layout = QGridLayout()
        self.window_layout.setSpacing(10)
        self.window_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.window_container.setLayout(self.window_layout)
        display_scroll.setWidget(self.window_container)
        
        right_layout.addWidget(display_scroll)
        right_panel.setLayout(right_layout)
        
        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)  # 右侧占据更多空间
        
        self.setLayout(main_layout)
        
        # 设置窗口大小策略
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
    def add_window_config(self, window_id, title, column_mode=2, default_visible=False):
        """添加窗口配置
        
        Args:
            window_id: 窗口ID（唯一标识）
            title: 窗口标题
            column_mode: 列数模式（2或3）
            default_visible: 默认是否可见
        """
        config = {
            'id': window_id,
            'title': title,
            'column_mode': column_mode,
            'visible': default_visible
        }
        self.window_configs.append(config)
        
        # 创建checkbox
        checkbox = QCheckBox(title)
        checkbox.setChecked(default_visible)
        checkbox.stateChanged.connect(lambda state, wid=window_id: self.on_checkbox_changed(wid, state))
        self.checkbox_layout.addWidget(checkbox)
        self.checkboxes[window_id] = checkbox
        
        # 如果默认可见，创建窗口
        if default_visible:
            self.create_window(window_id, title, column_mode)
            
    def create_window(self, window_id, title, column_mode):
        """创建数据显示窗口"""
        if window_id in self.windows:
            return  # 窗口已存在
            
        window = DataDisplayWindow(window_id, title, column_mode, parent=self.window_container)
        
        # 连接读取按钮信号（所有窗口都有）
        window.read_button.clicked.connect(lambda checked=False, wid=window_id: self.on_read_clicked(wid))
        
        # 3列模式额外连接写入按钮
        if column_mode == 3:
            window.write_button.clicked.connect(lambda checked=False, wid=window_id: self.on_write_clicked(wid))
            
        self.windows[window_id] = window
        
        # 添加到网格布局
        self.rearrange_windows()
        
        if self.logger:
            self.logger.write_log(f"创建数据窗口: {title} ({column_mode}列)")
            
    def remove_window(self, window_id):
        """移除数据显示窗口"""
        if window_id in self.windows:
            window = self.windows[window_id]
            self.window_layout.removeWidget(window)
            window.deleteLater()
            del self.windows[window_id]
            
            # 重新排列窗口
            self.rearrange_windows()
            
            if self.logger:
                self.logger.write_log(f"移除数据窗口: {window_id}")
                
    def rearrange_windows(self):
        """重新排列窗口布局（自适应网格）"""
        # 清空布局
        while self.window_layout.count():
            child = self.window_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                
        # 计算网格布局
        visible_windows = list(self.windows.values())
        if not visible_windows:
            return
            
        # 动态计算列数（根据窗口总数）
        num_windows = len(visible_windows)
        if num_windows <= 2:
            cols = 1
        elif num_windows <= 4:
            cols = 2
        else:
            cols = 3
            
        # 添加到网格
        for idx, window in enumerate(visible_windows):
            row = idx // cols
            col = idx % cols
            self.window_layout.addWidget(window, row, col)
            
            # 调整窗口大小
            window.adjust_size_to_content()
            
    def on_checkbox_changed(self, window_id, state):
        """checkbox状态改变处理"""
        is_checked = state == Qt.CheckState.Checked.value
        
        if is_checked:
            # 创建窗口
            config = next((c for c in self.window_configs if c['id'] == window_id), None)
            if config:
                self.create_window(window_id, config['title'], config['column_mode'])
        else:
            # 移除窗口
            self.remove_window(window_id)
            
    def select_all_windows(self):
        """全选所有窗口"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
            
    def deselect_all_windows(self):
        """全不选所有窗口"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
            
    def on_read_clicked(self, window_id):
        """读取按钮点击"""
        self.window_read_requested.emit(window_id)
        if self.logger:
            self.logger.write_log(f"请求读取数据: {window_id}")
            
    def on_write_clicked(self, window_id):
        """写入按钮点击"""
        if window_id in self.windows:
            window = self.windows[window_id]
            modified_data = window.get_modified_data()
            
            if modified_data:
                self.window_write_requested.emit(window_id, modified_data)
                if self.logger:
                    self.logger.write_log(f"请求写入数据: {window_id}, 修改项数: {len(modified_data)}")
            else:
                if self.logger:
                    self.logger.write_log(f"没有修改的数据: {window_id}")
                    
    def update_window_data(self, window_id, data):
        """更新指定窗口的数据"""
        if window_id in self.windows:
            self.windows[window_id].update_data(data)
        else:
            if self.logger:
                self.logger.write_log(f"窗口未显示: {window_id}（请先勾选对应的checkbox）")
            
    def get_window_modified_data(self, window_id):
        """获取指定窗口的修改数据"""
        if window_id in self.windows:
            return self.windows[window_id].get_modified_data()
        return []
        
    def clear_window_write_values(self, window_id):
        """清空指定窗口的写入值"""
        if window_id in self.windows:
            self.windows[window_id].clear_write_values()
            
    # ========== 蓝牙队列发送接口 ==========
    
    async def queue_send(self, data_bytes, priority=False):
        """通过队列发送数据
        
        Args:
            data_bytes: 要发送的字节数据
            priority: 是否优先发送
        """
        await self.queue_sender.add_to_queue(data_bytes, priority)
        
    def clear_send_queue(self):
        """清空发送队列"""
        self.queue_sender.clear_queue()
        
    def get_queue_length(self):
        """获取队列长度"""
        return self.queue_sender.get_queue_length()

