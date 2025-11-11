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
    
    def __init__(self, window_id, title, column_mode=2, expected_row_count=10, parent=None):
        """
        Args:
            window_id: 窗口ID
            title: 窗口标题
            column_mode: 列数模式（2或3）
            expected_row_count: 预期的数据行数
            parent: 父窗口
        """
        super().__init__(parent)
        self.window_id = window_id
        self.title = title
        self.column_mode = column_mode
        self.expected_row_count = expected_row_count
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        # 标题（压缩字体以节省空间）
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            QLabel { 
                color: #2c3e50; 
                font-weight: bold; 
                font-size: 10px;
                padding: 2px;
                background-color: #ecf0f1;
                border-radius: 3px;
            }
        """)
        layout.addWidget(title_label)
        
        # 创建表格视图
        self.table_view = QTableView()
        
        # 根据列模式创建不同的数据模型
        if self.column_mode == 2:
            self.table_model = TwoColumnTableModel()
            self.table_view.setModel(self.table_model)
            self.table_view.setColumnWidth(0, 97)   # 名称列
            self.table_view.setColumnWidth(1, 60)   # 当前值列
        else:  # 3列模式
            self.table_model = ThreeColumnTableModel()
            self.table_view.setModel(self.table_model)
            self.table_view.setColumnWidth(0, 103)  # 名称列
            self.table_view.setColumnWidth(1, 60)   # 读取值列
            self.table_view.setColumnWidth(2, 60)   # 写入值列
        
        # 设置表格属性
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setVisible(False)
        
        # 固定列宽，防止自动调整
        from PyQt6.QtWidgets import QHeaderView
        for col in range(self.table_model.columnCount()):
            self.table_view.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # 自适应字体大小（压缩以节省空间）
        table_font = self.table_view.font()
        table_font.setPointSize(8)
        self.table_view.setFont(table_font)
        
        # 设置行高（压缩以节省空间）
        self.table_view.verticalHeader().setDefaultSectionSize(20)
        self.table_view.verticalHeader().setMinimumSectionSize(18)
        
        # 设置表头字体（压缩以节省空间）
        header_font = self.table_view.horizontalHeader().font()
        header_font.setPointSize(8)
        header_font.setBold(True)
        self.table_view.horizontalHeader().setFont(header_font)
        
        # 设置大小策略为可扩展
        self.table_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.table_view)
        
        # 添加按钮（所有窗口都有读取按钮）
        button_layout = QHBoxLayout()
        button_layout.setSpacing(3)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.read_button = QPushButton('🔄 读取')
        self.read_button.setMinimumWidth(60)
        self.read_button.setMaximumWidth(60)
        self.read_button.setMinimumHeight(24)
        self.read_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        button_layout.addWidget(self.read_button)
        
        # 3列模式额外添加写入按钮
        if self.column_mode == 3:
            self.write_button = QPushButton('✏️ 写入')
            self.write_button.setMinimumWidth(60)
            self.write_button.setMaximumWidth(60)
            self.write_button.setMinimumHeight(24)
            self.write_button.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
                QPushButton:pressed {
                    background-color: #1e8449;
                }
            """)
            button_layout.addWidget(self.write_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 设置窗口边框和样式（压缩边框）
        self.setStyleSheet("""
            DataDisplayWindow {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
                padding: 2px;
            }
            QTableView {
                border: 1px solid #dce0e3;
                gridline-color: #ecf0f1;
            }
            QTableView::item:selected {
                background-color: #3498db;
                color: white;
            }
            QTableView::item:hover {
                background-color: #ecf0f1;
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
            
    def print_column_widths(self):
        """打印表格每一列的实际宽度"""
        print(f"\n{'='*50}")
        print(f"窗口: {self.title} ({self.column_mode}列模式)")
        print(f"{'-'*50}")
        for col in range(self.table_model.columnCount()):
            header = self.table_model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            width = self.table_view.columnWidth(col)
            print(f"  列{col} [{header}]: {width}px")
        print(f"{'='*50}\n")
    
    def adjust_size_to_content(self, max_container_height=None):
        """根据内容自适应调整大小
        
        Args:
            max_container_height: 容器的最大高度限制
        """
        # 获取实际行数，如果没有数据则使用预期行数
        row_count = self.table_model.rowCount()
        if row_count == 0:
            row_count = self.expected_row_count
        
        row_height = self.table_view.verticalHeader().defaultSectionSize()
        
        # 获取表头高度，如果为0则使用默认值30
        header_height = self.table_view.horizontalHeader().height()
        if header_height == 0:
            header_height = 30  # 使用合理的默认值
        
        # 标题和按钮的高度（现在所有窗口都有按钮）
        extra_height = 50  # 标题(18) + 按钮(24) + 边距(8)
        
        # 计算总高度
        total_height = header_height + row_count * row_height + extra_height
        
        # 设置最小高度（至少显示3行）
        min_height = header_height + 3 * row_height + extra_height
        total_height = max(total_height, min_height)
        
        # 限制最大高度为容器高度的90%（如果有容器高度限制）
        # 超出部分会显示滚动条
        if max_container_height and max_container_height > 0:
            max_window_height = int(max_container_height * 0.9)
            total_height = min(total_height, max_window_height)
        
        # 计算所需宽度（列宽总和 + 10px，避免横向滚动条）
        if self.column_mode == 2:
            total_width = 97 + 60 + 10  # 2列：名称97 + 当前值60 + 10 = 167
        else:
            total_width = 103 + 60 + 60 + 10  # 3列：名称103 + 读取60 + 写入60 + 10 = 233
            
        # 设置固定大小
        self.setMinimumHeight(total_height)
        self.setMaximumHeight(total_height)
        self.setMinimumWidth(total_width)
        self.setMaximumWidth(total_width)
        
        # 返回实际高度供布局算法使用
        return total_height


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


# ============== 3列表格模型 ==============
class ThreeColumnTableModel(BatteryTableModel):
    """3列表格模型（名称 | 读取值 | 写入值）"""
    
    def __init__(self, data=None, parent=None):
        super().__init__(data, parent)
        self._columns = 3
        self._headers = ['参数名', '读取值', '写入值']
        
    def _organize_data(self):
        """重新组织数据为3列"""
        self._organized_data = []
        
        for row_data in self._original_data:
            if len(row_data) >= 3:
                self._organized_data.append([
                    row_data[0],  # 名称
                    self._get_cached_display_value(self._original_data.index(row_data), row_data[2]),  # 读取值（当前值）
                    ""  # 写入值（初始为空）
                ])
    
    def flags(self, index):
        """3列模式：名称和读取值不可编辑，写入值可编辑"""
        if index.column() == 2:  # 写入值列可编辑
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    
    def get_modified_data(self):
        """获取修改的数据（写入值不为空的行）"""
        modified = []
        for row_idx, row_data in enumerate(self._organized_data):
            if len(row_data) >= 3 and row_data[2]:  # 写入值不为空
                # 返回: (行号, 参数名, 读取值, 写入值)
                param_name = self._original_data[row_idx][0] if row_idx < len(self._original_data) else ""
                modified.append((row_idx, param_name, row_data[1], row_data[2]))
        return modified
    
    def clear_write_values(self):
        """清空所有写入值"""
        for row_data in self._organized_data:
            if len(row_data) >= 3:
                row_data[2] = ""
        self.layoutChanged.emit()


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
        main_layout.setContentsMargins(2, 2, 2, 2)
        
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
        right_layout.setContentsMargins(2, 2, 2, 2)
        
        # 窗口显示区域标题
        display_title = QLabel('数据显示窗口')
        display_title.setStyleSheet("QLabel { font-weight: bold; font-size: 12px; }")
        right_layout.addWidget(display_title)
        
        # 滚动区域
        self.display_scroll = QScrollArea()
        self.display_scroll.setWidgetResizable(True)
        
        self.window_container = QWidget()
        # 不使用布局，使用绝对定位手动放置窗口
        self.display_scroll.setWidget(self.window_container)
        
        right_layout.addWidget(self.display_scroll)
        right_panel.setLayout(right_layout)
        
        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)  # 右侧占据更多空间
        
        self.setLayout(main_layout)
        
        # 设置窗口大小策略
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 延迟重排定时器（避免频繁重排）
        self.rearrange_timer = QTimer()
        self.rearrange_timer.setSingleShot(True)
        self.rearrange_timer.timeout.connect(self.rearrange_windows)
        
    def resizeEvent(self, event):
        """窗口大小改变时重新排列"""
        super().resizeEvent(event)
        # 延迟500ms后重新排列，避免频繁触发
        if hasattr(self, 'rearrange_timer'):
            self.rearrange_timer.start(500)
        
    def add_window_config(self, window_id, title, column_mode=2, default_visible=False, expected_row_count=10):
        """添加窗口配置
        
        Args:
            window_id: 窗口ID（唯一标识）
            title: 窗口标题
            column_mode: 列数模式（2或3）
            default_visible: 默认是否可见
            expected_row_count: 预期的数据行数
        """
        config = {
            'id': window_id,
            'title': title,
            'column_mode': column_mode,
            'visible': default_visible,
            'expected_row_count': expected_row_count
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
            self.create_window(window_id, title, column_mode, expected_row_count)
            
    def create_window(self, window_id, title, column_mode, expected_row_count=10):
        """创建数据显示窗口"""
        if window_id in self.windows:
            return  # 窗口已存在
            
        window = DataDisplayWindow(window_id, title, column_mode, expected_row_count, parent=self.window_container)
        
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
            window.hide()
            window.deleteLater()
            del self.windows[window_id]
            
            # 重新排列窗口
            self.rearrange_windows()
            
            if self.logger:
                self.logger.write_log(f"移除数据窗口: {window_id}")
                
    def rearrange_windows(self):
        """重新排列窗口（手动计算坐标，实现真正的紧密拼接）
        
        规则：
        1. 使用绝对定位，不依赖布局管理器
        2. 按高度降序排列窗口
        3. 动态选择当前最矮的列放置窗口（贪心策略）
        """
        # 获取可见窗口
        visible_windows = []
        for config in self.window_configs:
            window_id = config['id']
            if window_id in self.windows:
                visible_windows.append(self.windows[window_id])
        
        if not visible_windows:
            return
        
        # 获取容器可用高度和宽度
        container_height = 800  # 默认高度
        container_width = 1200  # 默认宽度
        if hasattr(self, 'display_scroll') and self.display_scroll:
            viewport_height = self.display_scroll.viewport().height()
            viewport_width = self.display_scroll.viewport().width()
            if viewport_height > 0:
                container_height = viewport_height - 20
            if viewport_width > 0:
                container_width = viewport_width - 20
        
        # 计算每个窗口的实际高度和宽度
        window_info = []
        for window in visible_windows:
            height = window.adjust_size_to_content(container_height)
            width = window.minimumWidth()
            window_info.append((window, height, width))
        
        # 按高度降序排列
        window_info.sort(key=lambda x: x[1], reverse=True)
        
        # 窗口间距
        spacing = 2
        
        # 使用动态规划进行列分配
        columns = []  # 每列是一个窗口列表: [(window, height, width), ...]
        
        # 第1步：把高度超过容器高度的窗口单独放一列
        remaining_windows = []
        for window, win_height, win_width in window_info:
            if win_height > container_height:
                columns.append([(window, win_height, win_width)])
                if self.bluetooth_tool:
                    self.bluetooth_tool.blue_write_log(f"超高窗口 {window.title}({win_height}px) 单独占列{len(columns)}")
            else:
                remaining_windows.append((window, win_height, win_width))
        
        # 第2步：对剩余窗口进行动态规划拼接
        while remaining_windows:
            # 选出最高的窗口作为新列的起始
            remaining_windows.sort(key=lambda x: x[1], reverse=True)
            new_column = [remaining_windows.pop(0)]
            current_height = new_column[0][1] + spacing
            
            # 动态规划：在剩余窗口中找能放入当前列的最大窗口
            i = 0
            while i < len(remaining_windows):
                window, win_height, win_width = remaining_windows[i]
                if current_height + win_height <= container_height:
                    # 能放入，添加到当前列
                    new_column.append(remaining_windows.pop(i))
                    current_height += win_height + spacing
                else:
                    i += 1
            
            columns.append(new_column)
        
        # 第3步：根据列数计算布局
        num_columns = len(columns)
        
        # 为每个窗口分配位置（每列根据实际宽度紧密排列）
        if self.bluetooth_tool:
            self.bluetooth_tool.blue_write_log("=" * 60)
            self.bluetooth_tool.blue_write_log(f"动态规划布局（共{num_columns}列）：")
        
        column_heights = []
        column_windows = []
        column_widths = []  # 记录每列的实际宽度
        
        for col_idx, column in enumerate(columns):
            # 计算当前列的起始x坐标（累加前面所有列的宽度）
            x_base = spacing
            for prev_width in column_widths:
                x_base += prev_width + spacing
            
            y_current = 0
            col_window_names = []
            max_col_width = 0  # 当前列的最大窗口宽度
            
            for window, win_height, win_width in column:
                x = x_base
                y = y_current
                w = win_width
                h = win_height
                max_col_width = max(max_col_width, w)
                
                # 设置窗口位置和大小
                window.setParent(self.window_container)
                window.setGeometry(x, y, w, h)
                window.show()
                
                # 打印窗口列宽信息
                window.print_column_widths()
                
                # 打印窗口位置信息
                if self.bluetooth_tool:
                    self.bluetooth_tool.blue_write_log(
                        f"  {window.title}: 位置({x}, {y}), 大小({w}×{h}), 列{col_idx+1}"
                    )
                
                y_current += h + spacing
                col_window_names.append(window.title)
            
            column_heights.append(y_current)
            column_windows.append(col_window_names)
            column_widths.append(max_col_width)  # 记录当前列的宽度
        
        # 设置容器的最小尺寸（以便滚动）
        max_height = max(column_heights)
        self.window_container.setMinimumSize(container_width, max_height + spacing)
        
        # 输出布局总结信息
        if self.bluetooth_tool:
            self.bluetooth_tool.blue_write_log("=" * 60)
            self.bluetooth_tool.blue_write_log("布局总结：")
            for col_idx, windows in enumerate(column_windows):
                if windows:
                    self.bluetooth_tool.blue_write_log(
                        f"  列{col_idx+1}: 高度={column_heights[col_idx]}px, 窗口数={len(windows)}个"
                    )
            remaining = container_height - max_height
            self.bluetooth_tool.blue_write_log(
                f"📐 容器总高度={max_height}px, 可视高度={container_height}px, 剩余空间={remaining}px"
            )
            self.bluetooth_tool.blue_write_log("=" * 60)
            
    def on_checkbox_changed(self, window_id, state):
        """checkbox状态改变处理"""
        is_checked = state == Qt.CheckState.Checked.value
        
        if is_checked:
            # 创建窗口
            config = next((c for c in self.window_configs if c['id'] == window_id), None)
            if config:
                expected_row_count = config.get('expected_row_count', 10)
                self.create_window(window_id, config['title'], config['column_mode'], expected_row_count)
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

