"""
多窗口管理器 - 支持多个batterywindow窗口的显示和管理
支持checkbox控制窗口显示/隐藏，自适应布局
"""
import asyncio
import time
from collections import deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QLabel, QPushButton, QScrollArea,
    QGroupBox, QTableView, QAbstractItemView, QSizePolicy, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QAbstractTableModel
from PyQt6.QtGui import QFont, QColor, QPainter
from display_widgets import BatteryTableModel, get_adaptive_colors, BitFlagsTableModel, _global_refresh_timer_manager


# ============== 圆形通讯状态指示器（优化版）==============
class CommStatusIndicator(QLabel):
    """圆形通讯状态指示器（性能优化版）
    
    - 灰色：默认/空闲
    - 绿色闪烁：通讯成功
    - 红色闪烁：通讯超时
    
    优化点：
    1. 缓存QColor对象，避免重复创建
    2. 单例QTimer，避免每次闪烁创建定时器
    3. 防抖机制，避免频繁更新UI
    """
    
    def __init__(self, size=20, parent=None):
        super().__init__(parent)
        self.size = size
        self.setFixedSize(size, size)
        
        # 缓存颜色对象（避免重复创建，提升性能）
        self._color_idle = QColor(128, 128, 128)    # 灰色
        self._color_success = QColor(0, 255, 0)     # 绿色
        self._color_error = QColor(255, 0, 0)       # 红色
        self.current_color = self._color_idle
        
        # 单例定时器（复用，避免每次创建）
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._restore_color)
        
        # 防抖：避免过于频繁的闪烁
        self._last_flash_time = 0
        self._min_flash_interval = 0.05  # 最小闪烁间隔50ms
        
    def paintEvent(self, event):
        """绘制圆形指示器（优化版）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.current_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, self.size - 4, self.size - 4)
        
    def flash_success(self):
        """闪烁绿色（带防抖）"""
        current_time = time.time()
        if current_time - self._last_flash_time < self._min_flash_interval:
            return  # 防抖：忽略过于频繁的闪烁
        
        self._last_flash_time = current_time
        self.current_color = self._color_success
        self.update()
        self.flash_timer.start(300)  # 300ms后恢复
        
    def flash_error(self):
        """闪烁红色（带防抖）"""
        current_time = time.time()
        if current_time - self._last_flash_time < self._min_flash_interval:
            return  # 防抖：忽略过于频繁的闪烁
        
        self._last_flash_time = current_time
        self.current_color = self._color_error
        self.update()
        self.flash_timer.start(300)  # 300ms后恢复
        
    def _restore_color(self):
        """恢复为灰色"""
        self.current_color = self._color_idle
        self.update()
        
    def set_idle(self):
        """设置为空闲状态（灰色）"""
        self.flash_timer.stop()
        self.current_color = self._color_idle
        self.update()


# ============== 蓝牙队列发送管理器（性能优化版）==============
class BluetoothQueueSender(QObject):
    """蓝牙队列发送管理器（性能优化版）
    
    确保数据按顺序发送，避免数据冲突
    支持响应等待机制，确保BMS端有足够时间处理每个指令
    
    优化点：
    1. 减少冗余日志输出（可配置）
    2. 缓存命令码提取结果
    3. 统计响应时间和成功率
    4. 优化asyncio事件处理
    """
    
    # 通讯状态信号
    comm_status_changed = pyqtSignal(str)  # 'success' 或 'timeout'
    
    def __init__(self, bluetooth_tool, logger=None, verbose=False):
        """
        Args:
            bluetooth_tool: BluetoothTool实例
            logger: 日志记录器
            verbose: 是否输出详细日志（默认False，减少日志噪音）
        """
        super().__init__()
        self.bluetooth_tool = bluetooth_tool
        self.logger = logger
        self.verbose = verbose  # 详细日志开关
        self.send_queue = deque()  # 发送队列
        self.is_sending = False  # 是否正在发送
        self.send_lock = asyncio.Lock()  # 发送锁
        
        # 响应等待机制
        self.response_timeout = 0.5  # BMS响应超时时间（秒）
        self.waiting_for_response = False  # 是否正在等待响应
        self.response_received = asyncio.Event()  # 响应接收事件
        self.last_send_time = 0  # 上次发送时间
        
        # 队列去重：记录队列中已有的命令码（set查找O(1)，性能高）
        self.queued_commands = set()
        
        # 性能统计（可选）
        self.stats = {
            'total_sent': 0,
            'total_success': 0,
            'total_timeout': 0,
            'avg_response_time': 0.0
        }
        self._response_times = deque(maxlen=100)  # 保留最近100次响应时间
        
        # 连接receive_ok_signal信号
        if hasattr(bluetooth_tool, 'receive_ok_signal'):
            bluetooth_tool.receive_ok_signal.connect(self._on_response_received)
        
    def _on_response_received(self, cmd_code, data):
        """收到响应的回调（优化版）"""
        # 无论是否在等待，都设置事件（避免时序问题）
        self.response_received.set()
        # 只在verbose模式输出详细日志（减少日志噪音）
        if self.verbose and hasattr(self.bluetooth_tool, 'blue_write_log'):
            self.bluetooth_tool.blue_write_log(f"✅ 收到BMS响应，命令码: 0x{cmd_code:02X}")
        
    @staticmethod
    def _extract_cmd_code(data_bytes):
        """快速提取命令码（内联优化）"""
        return data_bytes[4] if len(data_bytes) > 4 else None
    
    @staticmethod
    def _is_write_command(cmd_code):
        """判断命令码是否为写入命令
        
        写入命令需要更长的超时时间（0.7秒），因为响应时间比读取命令长
        """
        if cmd_code is None:
            return False
        # 写入命令列表（根据WRITE_READ_COMMAND_MAPPING定义）
        write_commands = {
            0x08,  # PC_SET_KB
            0x09,  # PC_SET_BMS
            0x11,  # PC_SET_SERIALNUM
            0x26,  # PC_SET_OCP_DELAYTIME
            0x40,  # PC_SET_LIFE_PARA
            0x42,  # PC_SET_CELL_CAP_PARA
            0x66,  # PC_SET_MOSHTDATA
        }
        return cmd_code in write_commands
    
    async def add_to_queue(self, data_bytes, priority=False):
        """添加数据到发送队列（优化版，带去重）
        
        Args:
            data_bytes: 要发送的字节数据
            priority: 是否优先发送（手动点击的读取指令设置为True）
        """
        # 提取命令码（数据包格式：[0x00][长度H][长度L][单板类型][命令码][0x55][0xAA][数据][校验]）
        cmd_code = self._extract_cmd_code(data_bytes)
        
        # 去重检查：如果队列中已有相同命令，跳过
        if cmd_code is not None and cmd_code in self.queued_commands:
            if self.verbose and hasattr(self.bluetooth_tool, 'blue_write_log'):
                self.bluetooth_tool.blue_write_log(f"⚠️ 队列已有指令0x{cmd_code:02X}，跳过重复添加")
            return
        
        # 添加到队列
        if priority:
            self.send_queue.appendleft(data_bytes)  # 优先级高的插入队首
        else:
            self.send_queue.append(data_bytes)  # 普通的添加到队尾
        
        # 记录命令码到去重集合
        if cmd_code is not None:
            self.queued_commands.add(cmd_code)
        
        # 只在verbose模式或重要操作时输出日志
        if self.verbose and hasattr(self.bluetooth_tool, 'blue_write_log'):
            priority_flag = "🔴 优先" if priority else "➕"
            self.bluetooth_tool.blue_write_log(f"{priority_flag} 添加到队列(0x{cmd_code:02X if cmd_code else 0:02X})，队列长度: {len(self.send_queue)}")
            
        # 如果没有正在发送，启动发送任务
        if not self.is_sending:
            asyncio.create_task(self._process_queue())
            
    async def _process_queue(self):
        """处理发送队列（性能优化版，支持响应等待）"""
        async with self.send_lock:
            self.is_sending = True
            try:
                while self.send_queue:
                    # 检查连接状态
                    try:
                        is_connected = (self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected) or (self.bluetooth_tool.serial_port and self.bluetooth_tool.serial_port.is_open)
                    except:
                        is_connected = False
                    if not is_connected:
                        if hasattr(self.bluetooth_tool, 'blue_write_log'):
                            self.bluetooth_tool.blue_write_log("❌ 检测到未连接，停止队列处理")
                        self.clear_queue()
                        break
                    data_bytes = self.send_queue.popleft()
                    send_start_time = time.time()
                    # 发送前从去重集合移除该命令
                    cmd_code = self._extract_cmd_code(data_bytes)
                    if cmd_code is not None:
                        self.queued_commands.discard(cmd_code)
                    try:
                        # 确保与上次发送间隔
                        current_time = time.time()
                        elapsed = current_time - self.last_send_time
                        if elapsed < self.response_timeout:
                            await asyncio.sleep(self.response_timeout - elapsed)
                        # 重置响应事件
                        self.response_received.clear()
                        self.waiting_for_response = True
                        # 判断是否为写入命令
                        is_write_command = self._is_write_command(cmd_code)
                        timeout_duration = 0.7 if is_write_command else 0.5
                        # 发送数据
                        await self.bluetooth_tool.byte_send(data_bytes)
                        self.bluetooth_tool.display_send_data(data_bytes)
                        self.last_send_time = time.time()
                        self.stats['total_sent'] += 1
                        # 等待BMS响应或超时
                        try:
                            await asyncio.wait_for(self.response_received.wait(), timeout=timeout_duration)
                            response_time = time.time() - send_start_time
                            self._response_times.append(response_time)
                            self.stats['total_success'] += 1
                            self.stats['avg_response_time'] = sum(self._response_times) / len(self._response_times)
                            self.comm_status_changed.emit('success')
                        except asyncio.TimeoutError:
                            self.stats['total_timeout'] += 1
                            if hasattr(self.bluetooth_tool, 'blue_write_log'):
                                self.bluetooth_tool.blue_write_log(f"⏰ BMS响应超时({timeout_duration}秒)")
                            self.comm_status_changed.emit('timeout')
                        self.waiting_for_response = False
                        # 确保最小间隔
                        elapsed_after_wait = time.time() - self.last_send_time
                        if elapsed_after_wait < self.response_timeout:
                            await asyncio.sleep(self.response_timeout - elapsed_after_wait)
                    except Exception as e:
                        self.waiting_for_response = False
                        if hasattr(self.bluetooth_tool, 'blue_write_log'):
                            self.bluetooth_tool.blue_write_log(f"❌ 队列发送失败: {str(e)}")
                        if "未连接" in str(e) or "已断开" in str(e):
                            self.clear_queue()
                            break
                        await asyncio.sleep(0.5)
            finally:
                self.is_sending = False
                
    def clear_queue(self):
        """清空发送队列"""
        self.send_queue.clear()
        self.queued_commands.clear()  # 同时清空去重集合
        if hasattr(self.bluetooth_tool, 'blue_write_log'):
            self.bluetooth_tool.blue_write_log("🗑️ 已清空发送队列")
            
    def get_queue_length(self):
        """获取队列长度"""
        return len(self.send_queue)
    
    def set_response_timeout(self, timeout):
        """设置响应超时时间
        
        Args:
            timeout: 超时时间（秒）
        """
        self.response_timeout = timeout
        if hasattr(self.bluetooth_tool, 'blue_write_log'):
            self.bluetooth_tool.blue_write_log(f"⚙️ 设置响应超时时间: {timeout}秒")
    
    def get_stats(self):
        """获取性能统计信息"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_sent': 0,
            'total_success': 0,
            'total_timeout': 0,
            'avg_response_time': 0.0
        }
        self._response_times.clear()
        if hasattr(self.bluetooth_tool, 'blue_write_log'):
            self.bluetooth_tool.blue_write_log("📊 统计信息已重置")


# ============== 位标志紧凑模型（4列显示：名称|值|名称|值） ==============
class BitFlagsCompactModel(BatteryTableModel):
    """位标志紧凑模型，4列显示，带超时渐变色"""
    
    def __init__(self, data=None, parent=None):
        super().__init__(data, parent)
        self._columns = 4
        self._headers = ['参数名', '值', '参数名', '值']
        # 指定哪些列需要渐变色（第1、3列：值列）
        self._gradient_columns = [1, 3]
        # 启用渐变功能
        self._gradient_enabled = True
        # 渐变持续时间（与其他窗口保持统一：5秒）
        self._gradient_duration = 5.0
        # 位标志的新鲜色和陈旧色（自适应系统主题）
        colors = get_adaptive_colors()
        self._color_green_fresh = colors['green_fresh']  # 鲜艳绿色（0值，刚更新）
        self._color_green_stale = colors['green_stale']  # 淡绿色（0值，陈旧）
        self._color_red_fresh = colors['red_fresh']      # 鲜艳红色（1值，刚更新）
        self._color_red_stale = colors['red_stale']      # 淡红色（1值，陈旧）
        
    def _get_gradient_color_for_bit(self, original_idx, value):
        """计算位标志的渐变颜色（与其他窗口保持统一的渐变算法）
        
        Args:
            original_idx: 原始数据索引
            value: 位标志值（0或1）
        
        Returns:
            QColor: 插值后的颜色
        """
        if original_idx not in self._update_timestamps:
            # 没有更新记录，返回陈旧颜色
            return self._color_green_stale if value == 0 else self._color_red_stale
        
        # 计算距离上次更新的时间
        elapsed = time.time() - self._update_timestamps[original_idx]
        
        # 计算渐变进度 (0.0 = 刚更新, 1.0 = 已超时)
        progress = min(elapsed / self._gradient_duration, 1.0)
        
        # 根据值选择颜色对
        if value == 0:
            color_fresh = self._color_green_fresh
            color_stale = self._color_green_stale
        else:
            color_fresh = self._color_red_fresh
            color_stale = self._color_red_stale
        
        # RGB线性插值（与其他窗口统一的算法）
        r = int(color_fresh.red() + 
                (color_stale.red() - color_fresh.red()) * progress)
        g = int(color_fresh.green() + 
                (color_stale.green() - color_fresh.green()) * progress)
        b = int(color_fresh.blue() + 
                (color_stale.blue() - color_fresh.blue()) * progress)
        
        return QColor(r, g, b)
        
    def _organize_data(self):
        """将位标志数据重新组织为4列显示（2个名称-值对一行）"""
        self._organized_data = []
        
        # 将数据按2个一组排列
        for i in range(0, len(self._original_data), 2):
            row = []
            
            # 第1对：名称和值
            if i < len(self._original_data):
                item = self._original_data[i]
                if isinstance(item, dict):
                    row.append(item.get('name', ''))
                    row.append(str(item.get('value', '')))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    row.append(item[0])  # 名称
                    row.append(str(item[1]))  # 值
                else:
                    row.extend(['', ''])
            else:
                row.extend(['', ''])
            
            # 第2对：名称和值
            if i + 1 < len(self._original_data):
                item = self._original_data[i + 1]
                if isinstance(item, dict):
                    row.append(item.get('name', ''))
                    row.append(str(item.get('value', '')))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    row.append(item[0])  # 名称
                    row.append(str(item[1]))  # 值
                else:
                    row.extend(['', ''])
            else:
                row.extend(['', ''])
            
            self._organized_data.append(row)
    
    def data(self, index, role):
        """重写data方法，实现位标志的渐变色（与其他窗口保持统一）"""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row >= len(self._organized_data):
            return None
        
        # 显示数据
        if role == Qt.ItemDataRole.DisplayRole:
            return self._organized_data[row][col]
        
        # 背景颜色（使用与其他窗口统一的渐变算法）
        elif role == Qt.ItemDataRole.BackgroundRole:
            if col in self._gradient_columns:  # 第1、3列：值列
                # 计算原始数据索引
                if col == 1:
                    original_idx = row * 2
                else:  # col == 3
                    original_idx = row * 2 + 1
                
                # 获取值
                if original_idx < len(self._original_data):
                    value_str = self._organized_data[row][col]
                    if value_str:
                        try:
                            value = int(value_str)
                            # 使用统一的渐变色算法
                            return self._get_gradient_color_for_bit(original_idx, value)
                        except (ValueError, TypeError):
                            pass
        
        # 文字对齐
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 💡 工具提示（新增功能）- 鼠标悬停时显示完整内容
        elif role == Qt.ItemDataRole.ToolTipRole:
            # 所有列都显示工具提示
            if row < len(self._organized_data) and col < self._columns:
                cell_value = self._organized_data[row][col]
                # 只有当单元格内容不为空时才返回工具提示
                if cell_value and str(cell_value).strip():
                    return str(cell_value)
        
        return None
    
    def update_single_bit(self, name, value):
        """增量更新单个位标志（用于提高效率）
        
        Args:
            name: 位标志名称
            value: 位标志值（0或1）
        """
        current_time = time.time()
        
        # 查找该位标志在原始数据中的索引
        for idx, item in enumerate(self._original_data):
            item_name = item.get('name') if isinstance(item, dict) else item[0]
            if item_name == name:
                # 更新值
                if isinstance(item, dict):
                    item['value'] = value
                else:
                    self._original_data[idx] = (name, value)
                
                # 更新时间戳
                self._update_timestamps[idx] = current_time
                
                # 计算该位标志在组织后的数据中的位置
                table_row = idx // 2
                table_col = 1 if idx % 2 == 0 else 3
                
                # 更新组织后的数据
                if table_row < len(self._organized_data):
                    self._organized_data[table_row][table_col] = str(value)
                    
                    # 发射dataChanged信号，只刷新该单元格
                    cell_index = self.index(table_row, table_col)
                    self.dataChanged.emit(cell_index, cell_index, 
                                        [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])
                return
        
        # 如果没找到，说明是新的位标志，添加到末尾
        self._original_data.append({'name': name, 'value': value})
        self._update_timestamps[len(self._original_data) - 1] = current_time
        self._organize_data()
        self.beginResetModel()
        self.endResetModel()
    
    def flags(self, index):
        """所有单元格都不可编辑"""
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


# ============== 位标志显示窗口 ==============
class BitFlagsDisplayWindow(QWidget):
    """位标志显示窗口（使用与DataDisplayWindow相同的架构）"""
    
    def __init__(self, window_id, title, expected_row_count=50, parent=None):
        super().__init__(parent)
        self.window_id = window_id
        self.title = title
        self.expected_row_count = expected_row_count
        self.init_ui()
        
        # 启动定时器，定期刷新颜色（每500ms刷新一次，用于超时变灰）
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_colors)
        self.refresh_timer.start(500)  # 500ms刷新一次
    
    def _refresh_colors(self):
        """定时刷新颜色（用于超时变灰）"""
        if hasattr(self.table_model, '_gradient_columns'):
            row_count = self.table_model.rowCount()
            if row_count > 0:
                # 刷新所有值列的背景色
                for col in self.table_model._gradient_columns:
                    top_left = self.table_model.index(0, col)
                    bottom_right = self.table_model.index(row_count - 1, col)
                    self.table_model.dataChanged.emit(top_left, bottom_right, 
                                                     [Qt.ItemDataRole.BackgroundRole])
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        # 标题
        title_label = QLabel(self.title)
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(10)
        title_label.setFont(font)
        title_label.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(title_label)
        
        # 创建表格视图（使用2列模型，但分4列显示）
        self.table_view = QTableView()
        self.table_model = BitFlagsCompactModel()  # 使用新的紧凑模型
        self.table_view.setModel(self.table_model)
        
        # 设置4列的列宽（名称 | 值 | 名称 | 值）
        # 名称列减少2/5：90 - 36 = 54
        self.table_view.setColumnWidth(0, 54)   # 第1列名称
        self.table_view.setColumnWidth(1, 30)   # 第1列值
        self.table_view.setColumnWidth(2, 54)   # 第2列名称
        self.table_view.setColumnWidth(3, 30)   # 第2列值
        
        # 固定列宽
        for col in range(4):
            self.table_view.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # 设置表格属性
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setVisible(False)
        
        # 设置字体
        table_font = self.table_view.font()
        table_font.setPointSize(8)
        self.table_view.setFont(table_font)
        
        # 设置行高（15像素，确保下划线字符能正确显示）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        # 强制固定行高
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        # 设置表头字体
        header_font = self.table_view.horizontalHeader().font()
        header_font.setPointSize(8)
        header_font.setBold(True)
        self.table_view.horizontalHeader().setFont(header_font)
        
        self.table_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.table_view)
        
        self.setLayout(layout)
        
        # 强制设置行高（确保生效）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
    def update_data(self, status_list):
        """更新位标志数据"""
        if self.table_model:
            self.table_model.update_data(status_list)
            
    def adjust_size_to_content(self, max_container_height=None):
        """根据内容自适应调整大小"""
        # 在计算前再次强制设置行高（防止被重置）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        # 获取实际行数（4列显示，行数为数据总数/2向上取整）
        data_count = len(self.table_model._original_data) if hasattr(self.table_model, '_original_data') else 0
        if data_count == 0:
            row_count = (self.expected_row_count + 1) // 2  # 向上取整
        else:
            row_count = (data_count + 1) // 2  # 向上取整
        
        row_height = self.table_view.verticalHeader().defaultSectionSize()
        header_height = self.table_view.horizontalHeader().height()
        if header_height == 0:
            header_height = 30
        
        extra_height = 40  # 标题 + 边距
        
        # 计算总高度（预留两行位置用于滚动条等）
        total_height = header_height + row_count * row_height + extra_height + 2 * row_height
        
        # 设置最小高度（至少显示3行）
        min_height = header_height + 3 * row_height + extra_height + 2 * row_height
        total_height = max(total_height, min_height)
        
        # 限制最大高度（99%，除了读取写入按钮）
        if max_container_height and max_container_height > 0:
            max_window_height = int(max_container_height * 0.99)
            total_height = min(total_height, max_window_height)
        
        # 计算所需宽度（4列：54+30+54+30+边距+15px用于滚动条 = 193）
        total_width = 54 + 30 + 54 + 30 + 25
        
        # 设置固定大小
        self.setMinimumHeight(total_height)
        self.setMaximumHeight(total_height)
        self.setMinimumWidth(total_width)
        self.setMaximumWidth(total_width)
        
        return total_height
    
    def print_column_widths(self):
        """打印窗口信息（位标志窗口）- 用于调试"""
        pass  # 调试日志已移除


# ============== 单个数据显示窗口 ==============
class DataDisplayWindow(QWidget):
    """单个数据显示窗口
    
    支持2列、3列、4列和6列模式：
    - 2列模式：名称 | 当前值
    - 3列模式：名称 | 读取值 | 写入值（可编辑）
    - 4列模式：告警名称 | 告警值 | 保护名称 | 保护值
    - 6列模式：错误名称 | 错误值 | 信息名称 | 信息值 | 均衡名称 | 均衡值
    """
    
    def __init__(self, window_id, title, column_mode=2, expected_row_count=10, window_type='data', parent=None):
        """
        Args:
            window_id: 窗口ID
            title: 窗口标题
            column_mode: 列数模式（2、3、4或6）
            expected_row_count: 预期的数据行数
            window_type: 窗口类型
            parent: 父窗口
        """
        super().__init__(parent)
        self.window_id = window_id
        self.title = title
        self.column_mode = column_mode
        self.expected_row_count = expected_row_count
        self.window_type = window_type
        self._determine_column_widths()
        self.init_ui()
    
    def _determine_column_widths(self):
        """根据窗口ID和类型确定列宽"""
        if self.window_id in ['PC_GET_VER', 'PC_GET_SERIALNUM']:
            if self.column_mode == 2:
                self.col_widths = [48, 210]
            else:
                self.col_widths = [48, 210, 210]
        elif self.window_type == 'alarm_protect':
            # 告警-保护窗口：4列（告警名称, 告警值, 保护名称, 保护值）
            self.col_widths = [59, 15, 75, 15]  # 值列宽度从30减半到15
        elif self.window_type == 'other_status':
            # 其他状态信息窗口：6列（错误名称, 错误值, 信息名称, 信息值, 均衡名称, 均衡值）
            self.col_widths = [75, 15, 63, 15, 44, 15]  # 值列宽度从30减半到15
        else:
            if self.column_mode == 2:
                self.col_widths = [97, 60]
            else:
                self.col_widths = [103, 60, 60]
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        # 标题（压缩字体以节省空间）
        title_label = QLabel(self.title)
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(10)
        title_label.setFont(font)
        title_label.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(title_label)
        
        # 创建表格视图
        self.table_view = QTableView()
        
        # 根据列模式和窗口类型创建不同的数据模型
        if self.window_type == 'alarm_protect':
            self.table_model = BitFlagsTableModel(num_columns=4, headers=['告警', '值', '保护', '值'], value_columns=[1, 3])
            self.table_view.setModel(self.table_model)
            for col, width in enumerate(self.col_widths):
                self.table_view.setColumnWidth(col, width)
        elif self.window_type == 'other_status':
            self.table_model = BitFlagsTableModel(num_columns=6, headers=['错误', '值', '信息', '值', '均衡', '值'], value_columns=[1, 3, 5])
            self.table_view.setModel(self.table_model)
            for col, width in enumerate(self.col_widths):
                self.table_view.setColumnWidth(col, width)
        elif self.window_type == 'battery_status':
            self.table_model = BitFlagsTableModel(num_columns=2, headers=['参数名', '状态值'], value_columns=[])
            self.table_view.setModel(self.table_model)
            for col, width in enumerate(self.col_widths):
                self.table_view.setColumnWidth(col, width)
        elif self.column_mode == 2:
            self.table_model = TwoColumnTableModel()
            self.table_view.setModel(self.table_model)
            self.table_view.setColumnWidth(0, self.col_widths[0])   # 名称列
            self.table_view.setColumnWidth(1, self.col_widths[1])   # 当前值列
        else:  # 3列模式
            self.table_model = ThreeColumnTableModel()
            self.table_view.setModel(self.table_model)
            self.table_view.setColumnWidth(0, self.col_widths[0])  # 名称列
            self.table_view.setColumnWidth(1, self.col_widths[1])  # 读取值列
            self.table_view.setColumnWidth(2, self.col_widths[2])  # 写入值列
        
        # 设置表格属性
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setVisible(False)
        
        # 固定列宽，防止自动调整
        for col in range(self.table_model.columnCount()):
            self.table_view.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # 自适应字体大小（压缩以节省空间）
        table_font = self.table_view.font()
        table_font.setPointSize(8)
        self.table_view.setFont(table_font)
        
        # 设置行高（15像素，确保下划线字符能正确显示）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        # 强制固定行高
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        # 设置表头字体（压缩以节省空间）
        header_font = self.table_view.horizontalHeader().font()
        header_font.setPointSize(8)
        header_font.setBold(True)
        self.table_view.horizontalHeader().setFont(header_font)
        
        # 设置大小策略为可扩展
        self.table_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.table_view)
        
        # 只有需要读取按钮的窗口才添加按钮
        if self.window_type not in ['alarm_protect', 'other_status', 'battery_status']:
            # 添加按钮（所有数据窗口都有读取按钮）
            button_layout = QHBoxLayout()
            button_layout.setSpacing(3)
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            self.read_button = QPushButton('🔄 读取')
            self.read_button.setMinimumWidth(60)
            self.read_button.setMaximumWidth(60)
            self.read_button.setMinimumHeight(24)
            font = self.read_button.font()
            font.setBold(True)
            font.setPointSize(9)
            self.read_button.setFont(font)
            button_layout.addWidget(self.read_button)
            
            # 3列模式额外添加写入按钮
            if self.column_mode == 3:
                self.write_button = QPushButton('✏️ 写入')
                self.write_button.setMinimumWidth(60)
                self.write_button.setMaximumWidth(60)
                self.write_button.setMinimumHeight(24)
                font = self.write_button.font()
                font.setBold(True)
                font.setPointSize(9)
                self.write_button.setFont(font)
                button_layout.addWidget(self.write_button)
            
            button_layout.addStretch()
            layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 强制设置行高（确保生效）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
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
    
    def set_write_enabled(self, enabled):
        """设置写入功能启用状态
        
        Args:
            enabled: True=启用, False=禁用
        """
        # 更新写入按钮状态
        if hasattr(self, 'write_button'):
            self.write_button.setEnabled(enabled)
        
        # 更新表格模型的写入列编辑状态
        if hasattr(self.table_model, 'set_write_enabled'):
            self.table_model.set_write_enabled(enabled)
            # 强制刷新视图
            self.table_view.viewport().update()
            
    def print_column_widths(self):
        """打印表格每一列的实际宽度 - 用于调试"""
        pass  # 调试日志已移除
    
    def adjust_size_to_content(self, max_container_height=None):
        """根据内容自适应调整大小
        
        Args:
            max_container_height: 容器的最大高度限制
        """
        # 在计算前再次强制设置行高（防止被重置）
        self.table_view.verticalHeader().setDefaultSectionSize(15)
        self.table_view.verticalHeader().setMinimumSectionSize(15)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
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
        
        # 计算总高度（预留两行位置用于滚动条等）
        total_height = header_height + row_count * row_height + extra_height + 2 * row_height
        
        # 设置最小高度（至少显示3行）
        min_height = header_height + 3 * row_height + extra_height + 2 * row_height
        total_height = max(total_height, min_height)
        
        # 限制最大高度为容器高度的99%（如果有容器高度限制）
        # 超出部分会显示滚动条
        if max_container_height and max_container_height > 0:
            max_window_height = int(max_container_height * 0.99)
            total_height = min(total_height, max_window_height)
        
        # 计算所需宽度（列宽总和 + 25px，预留15px用于滚动条）
        total_width = sum(self.col_widths) + 25
            
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
        self._write_enabled = True  # 默认启用写入
        
    def _organize_data(self):
        """重新组织数据为3列（保留现有的写入值）"""
        # 保存旧的写入值（通过参数名匹配）
        old_write_values = {row[0]: row[2] for row in self._organized_data if len(row) >= 3 and row[2]}
        
        self._organized_data = []
        for row_data in self._original_data:
            if len(row_data) >= 3:
                self._organized_data.append([
                    row_data[0],  # 名称
                    self._get_cached_display_value(self._original_data.index(row_data), row_data[2]),  # 读取值
                    old_write_values.get(row_data[0], "")  # 写入值（保留或为空）
                ])
    
    def flags(self, index):
        """3列模式：名称和读取值不可编辑，写入值根据_write_enabled决定是否可编辑"""
        if index.column() == 2 and self._write_enabled:  # 写入值列，且写入功能已启用
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
    
    def set_write_enabled(self, enabled):
        """设置写入功能启用状态"""
        self._write_enabled = enabled


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
        
        # 写入功能启用状态（默认启用）
        self._write_enabled = True
        
        # 初始化蓝牙队列发送器
        self.queue_sender = BluetoothQueueSender(bluetooth_tool, logger)
        
        self.init_ui()
        
        # 连接通讯状态信号到指示器
        self.queue_sender.comm_status_changed.connect(self._on_comm_status_changed)
        
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
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(12)
        title_label.setFont(font)
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
        
        self.read_all_btn = QPushButton('📖 读取所有')
        self.read_all_btn.clicked.connect(self.read_all_checked_windows)
        font = self.read_all_btn.font()
        font.setBold(True)
        self.read_all_btn.setFont(font)
        button_layout.addWidget(self.read_all_btn)
        
        # 通讯状态指示器
        status_layout = QHBoxLayout()
        status_label = QLabel('通讯状态:')
        font = status_label.font()
        font.setPointSize(10)
        status_label.setFont(font)
        self.comm_indicator = CommStatusIndicator(size=16)
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.comm_indicator)
        status_layout.addStretch()
        button_layout.addLayout(status_layout)
        
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
        font = display_title.font()
        font.setBold(True)
        font.setPointSize(12)
        display_title.setFont(font)
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
        
    def add_window_config(self, window_id, title, column_mode=2, default_visible=False, expected_row_count=10, window_type='data'):
        """添加窗口配置
        
        Args:
            window_id: 窗口ID（唯一标识）
            title: 窗口标题
            column_mode: 列数模式（2或3）
            default_visible: 默认是否可见
            expected_row_count: 预期的数据行数
            window_type: 窗口类型（'data'数据窗口 或 'bitflags'位标志窗口）
        """
        config = {
            'id': window_id,
            'title': title,
            'column_mode': column_mode,
            'visible': default_visible,
            'expected_row_count': expected_row_count,
            'window_type': window_type
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
            self.create_window(window_id, title, column_mode, expected_row_count, window_type)
            
    def create_window(self, window_id, title, column_mode, expected_row_count=10, window_type='data'):
        """创建显示窗口（数据窗口或位标志窗口）"""
        if window_id in self.windows:
            return  # 窗口已存在
        
        # 根据窗口类型创建不同的窗口
        if window_type == 'bitflags':
            window = BitFlagsDisplayWindow(window_id, title, expected_row_count, parent=self.window_container)
        else:
            window = DataDisplayWindow(window_id, title, column_mode, expected_row_count, window_type, parent=self.window_container)
            
            # 只有普通数据窗口才连接读取/写入按钮
            if hasattr(window, 'read_button'):
                window.read_button.clicked.connect(lambda checked=False, wid=window_id: self.on_read_clicked(wid))
            
            # 3列模式额外连接写入按钮
            if column_mode == 3 and hasattr(window, 'write_button'):
                window.write_button.clicked.connect(lambda checked=False, wid=window_id: self.on_write_clicked(wid))
            
        self.windows[window_id] = window
        
        # 应用当前的写入启用状态
        if hasattr(window, 'set_write_enabled'):
            window.set_write_enabled(self._write_enabled)
        
        # 添加到布局
        self.rearrange_windows()
        
        if self.logger:
            if window_type == 'bitflags':
                window_type_name = "位标志窗口"
            elif window_type in ['alarm_protect', 'other_status', 'battery_status']:
                window_type_name = f"{window_type}窗口"
            else:
                window_type_name = f"数据窗口({column_mode}列)"
            self.logger.write_log(f"创建{window_type_name}: {title}")
            
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
            else:
                remaining_windows.append((window, win_height, win_width))
        
        # 第2步：对剩余窗口进行动态规划拼接（持续填充直到真的放不下）
        while remaining_windows:
            # 选出最高的窗口作为新列的起始
            remaining_windows.sort(key=lambda x: x[1], reverse=True)
            new_column = [remaining_windows.pop(0)]
            current_height = new_column[0][1] + spacing
            
            # 持续循环：每次找剩余窗口中最大的能放入的窗口
            while True:
                # 找到能放入的最大窗口
                best_idx = -1
                best_height = 0
                
                for i, (window, win_height, win_width) in enumerate(remaining_windows):
                    if current_height + win_height <= container_height:
                        if win_height > best_height:
                            best_idx = i
                            best_height = win_height
                
                # 如果找到了能放入的窗口，添加到当前列
                if best_idx >= 0:
                    new_column.append(remaining_windows.pop(best_idx))
                    current_height += best_height + spacing
                else:
                    # 没有能放入的窗口了，结束当前列
                    break
            
            columns.append(new_column)
        
        # 第3步：根据列数计算布局
        num_columns = len(columns)
        
        # 为每个窗口分配位置（每列根据实际宽度紧密排列）
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
                
                # 记录窗口信息（简化日志）
                pass
                
                y_current += h + spacing
                col_window_names.append(window.title)
            
            column_heights.append(y_current)
            column_windows.append(col_window_names)
            column_widths.append(max_col_width)  # 记录当前列的宽度
        
        # 计算所有列的总宽度（用于设置容器最小宽度，确保横向滚动条）
        total_width = spacing  # 左边距
        for col_width in column_widths:
            total_width += col_width + spacing
        
        # 设置容器的最小尺寸（以便滚动）
        max_height = max(column_heights)
        self.window_container.setMinimumSize(total_width, max_height + spacing)
        
        # 输出简化的布局总结信息
        if self.bluetooth_tool:
            total_used_height = sum(column_heights)
            avg_utilization = (total_used_height / (num_columns * container_height) * 100) if num_columns > 0 else 0
            # self.bluetooth_tool.blue_write_log(
            #     f"📊 布局完成: {num_columns}列, {len(visible_windows)}窗口, "
            #     f"容器({total_width}×{max_height}px), 利用率{avg_utilization:.1f}%"
            # )
            
    def on_checkbox_changed(self, window_id, state):
        """checkbox状态改变处理"""
        is_checked = state == Qt.CheckState.Checked.value
        
        if is_checked:
            # 创建窗口
            config = next((c for c in self.window_configs if c['id'] == window_id), None)
            if config:
                expected_row_count = config.get('expected_row_count', 10)
                window_type = config.get('window_type', 'data')
                self.create_window(window_id, config['title'], config['column_mode'], expected_row_count, window_type)
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
            
    def read_all_checked_windows(self):
        """读取所有已勾选的窗口数据"""
        checked_windows = []
        
        # 收集所有已勾选的窗口ID
        for window_id, checkbox in self.checkboxes.items():
            if checkbox.isChecked() and window_id in self.windows:
                checked_windows.append(window_id)
        
        if not checked_windows:
            if self.logger:
                self.logger.write_log("⚠️ 没有勾选的窗口")
            return
        
        if self.logger:
            self.logger.write_log(f"📖 开始读取 {len(checked_windows)} 个窗口的数据")
        
        # 依次触发每个窗口的读取请求
        for window_id in checked_windows:
            self.window_read_requested.emit(window_id)
            
    def _on_comm_status_changed(self, status):
        """通讯状态改变回调（优化版）"""
        if status == 'success':
            self.comm_indicator.flash_success()
            # 成功时只闪灯，不输出日志
        elif status == 'timeout':
            self.comm_indicator.flash_error()
            # 超时输出到蓝牙日志（重要信息）
            
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
    
    def update_bit_flags_incremental(self, window_id, status_bits):
        """增量更新位标志窗口（只更新变化的位）
        
        Args:
            window_id: 窗口ID
            status_bits: 位标志列表 [{'name': str, 'value': int}, ...]
        """
        if window_id in self.windows:
            window = self.windows[window_id]
            if isinstance(window, BitFlagsDisplayWindow):
                # 逐个更新位标志
                for bit in status_bits:
                    if isinstance(bit, dict):
                        name = bit.get('name', '')
                        value = bit.get('value', 0)
                        window.table_model.update_single_bit(name, value)
            
    def get_window_modified_data(self, window_id):
        """获取指定窗口的修改数据"""
        if window_id in self.windows:
            return self.windows[window_id].get_modified_data()
        return []
    
    def set_write_enabled(self, enabled):
        """设置所有窗口的写入功能启用状态
        
        Args:
            enabled: True=启用写入功能, False=禁用写入功能
        """
        # 保存状态，用于后续创建新窗口时应用
        self._write_enabled = enabled
        
        # 更新所有已存在的窗口
        for window_id, window in self.windows.items():
            if hasattr(window, 'set_write_enabled'):
                window.set_write_enabled(enabled)
        
        if self.logger:
            self.logger.write_log(f"{'启用' if enabled else '禁用'}所有窗口写入功能")
        
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

