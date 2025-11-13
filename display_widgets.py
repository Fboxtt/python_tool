"""
显示窗口组件 - 电池参数和位标志的模型、委托和窗口类
独立文件，避免循环导入
"""
import time
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QTableView, QAbstractItemView, QHBoxLayout
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyle


# ==================== 🔄 全局定时器管理器（单例模式）====================

class GlobalRefreshTimerManager:
    """全局刷新定时器管理器（单例模式）
    
    所有需要定时刷新的模型（BatteryTableModel、BitFlagsTableModel）共享同一个定时器，
    实现同步刷新，避免多窗口时定时器不同步导致的性能开销。
    """
    _instance = None
    _timer = None
    _subscribers = set()  # 订阅者集合
    _interval = 1000  # 默认1秒刷新（兼顾渐变颜色和超时检查）
    _debug_mode = False  # 调试模式（生产环境设为False）
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化全局定时器（只会执行一次）"""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._on_timer_tick)
            if self._debug_mode:
                print(f"✅ 全局渐变定时器已创建（间隔: {self._interval}ms）")
    
    def subscribe(self, model):
        """订阅定时器事件
        
        Args:
            model: BatteryTableModel 实例
        """
        self._subscribers.add(model)
        
        # 如果是第一个订阅者，启动定时器
        if len(self._subscribers) == 1 and not self._timer.isActive():
            self._timer.start(self._interval)
            if self._debug_mode:
                print(f"▶️ 全局渐变定时器已启动（订阅者数: {len(self._subscribers)}）")
        else:
            if self._debug_mode:
                print(f"📝 新订阅者已注册（订阅者数: {len(self._subscribers)}）")
    
    def unsubscribe(self, model):
        """取消订阅定时器事件
        
        Args:
            model: BatteryTableModel 实例
        """
        self._subscribers.discard(model)
        
        # 如果没有订阅者了，停止定时器以节省资源
        if len(self._subscribers) == 0 and self._timer.isActive():
            self._timer.stop()
            if self._debug_mode:
                print(f"⏹️ 全局渐变定时器已停止（无订阅者）")
        else:
            if self._debug_mode:
                print(f"📝 订阅者已移除（剩余订阅者数: {len(self._subscribers)}）")
    
    def _on_timer_tick(self):
        """定时器回调：通知所有订阅者刷新"""
        # 通知所有订阅的模型实例（支持不同类型的刷新方法）
        for model in list(self._subscribers):  # 使用list()避免迭代时修改集合
            # BatteryTableModel: 刷新渐变颜色
            if hasattr(model, '_refresh_gradient'):
                model._refresh_gradient()
            # BitFlagsTableModel: 检查超时状态
            elif hasattr(model, '_on_global_timer_tick'):
                model._on_global_timer_tick()
    
    def get_subscriber_count(self):
        """获取当前订阅者数量"""
        return len(self._subscribers)
    
    def is_active(self):
        """定时器是否在运行"""
        return self._timer.isActive() if self._timer else False
    
    def set_debug_mode(self, enabled=True):
        """设置调试模式
        
        Args:
            enabled: 是否启用调试输出
        """
        self._debug_mode = enabled


# 全局单例实例
_global_refresh_timer_manager = GlobalRefreshTimerManager()


class BatteryTableModel(QAbstractTableModel):
    """电池参数表格模型（性能优化版 + 渐变颜色功能）"""
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._original_data = data if data is not None else []
        self._write_values = {}  # 存储写入值的字典，key为原始行索引，value为写入值
        self._columns = 9  # 9列显示：3组参数
        self._max_rows_per_column = 25  # 每列组最大行数
        self._headers = ['参数名1', '当前值1', '写入值1', '参数名2', '当前值2', '写入值2', '参数名3', '当前值3', '写入值3']
        self._organized_data = []  # 重新组织后的数据

        # 性能优化：建立参数名到索引的映射（用于快速查找）
        self._name_to_index = {}

        # 性能优化：缓存显示值，避免重复格式化
        self._display_value_cache = {}

        # 🎨 渐变颜色配置（新增功能）
        self._gradient_enabled = True  # 是否启用渐变效果（默认启用）
        self._gradient_duration = 5.0  # 渐变持续时间（秒）
        self._update_timestamps = {}   # 记录每个参数的最后更新时间 {original_row_index: timestamp}
        
        # 颜色配置
        self._color_fresh = QColor(255, 200, 150)      # 橙色 - 新鲜数据（刚更新）
        self._color_stale = QColor(220, 220, 220)      # 灰色 - 陈旧数据（5秒未更新）
        self._color_modified = QColor(255, 255, 200)   # 浅黄色 - 有待发送的修改
        
        # 🔄 使用全局定时器管理器（多窗口同步刷新，节省性能）
        self._gradient_timer_manager = _global_refresh_timer_manager
        if self._gradient_enabled:
            self._gradient_timer_manager.subscribe(self)

        self._organize_data()
    
    def __del__(self):
        """析构函数：清理时取消订阅全局定时器"""
        try:
            if hasattr(self, '_gradient_timer_manager'):
                self._gradient_timer_manager.unsubscribe(self)
        except:
            pass  # 避免析构时出错

    def _organize_data(self):
        """重新组织数据，超过25行时分成新的列组（性能优化版）"""
        self._organized_data = []
        data_len = len(self._original_data)

        # 性能优化：清空并重建名称索引映射
        self._name_to_index.clear()
        for idx, row_data in enumerate(self._original_data):
            self._name_to_index[row_data[0]] = idx

        if data_len == 0:
            return

        # 计算需要的行数
        max_rows = min(self._max_rows_per_column, data_len)

        # 创建行数据
        for row in range(max_rows):
            row_data = [''] * self._columns

            # 填充第一列组 (columns 0-2)
            if row < data_len:
                row_data[0] = self._original_data[row][0]  # 参数名
                row_data[1] = self._get_cached_display_value(row, self._original_data[row][2])  # 当前值（使用缓存）
                row_data[2] = self._write_values.get(row, "")  # 写入值

            # 填充第二列组 (columns 3-5)
            second_group_idx = row + self._max_rows_per_column
            if second_group_idx < data_len:
                row_data[3] = self._original_data[second_group_idx][0]  # 参数名
                row_data[4] = self._get_cached_display_value(second_group_idx, self._original_data[second_group_idx][2])  # 当前值（使用缓存）
                row_data[5] = self._write_values.get(second_group_idx, "")  # 写入值

            # 填充第三列组 (columns 6-8)
            third_group_idx = row + 2 * self._max_rows_per_column
            if third_group_idx < data_len:
                row_data[6] = self._original_data[third_group_idx][0]  # 参数名
                row_data[7] = self._get_cached_display_value(third_group_idx, self._original_data[third_group_idx][2])  # 当前值（使用缓存）
                row_data[8] = self._write_values.get(third_group_idx, "")  # 写入值

            self._organized_data.append(row_data)

    def _get_cached_display_value(self, row_idx, value):
        """获取缓存的显示值（性能优化）"""
        # 使用(row_idx, value)作为缓存键
        cache_key = (row_idx, str(value))
        if cache_key not in self._display_value_cache:
            self._display_value_cache[cache_key] = self._format_display_value(value)
        return self._display_value_cache[cache_key]

    def _format_display_value(self, value):
        """格式化显示值，处理十六进制显示格式"""
        if isinstance(value, str):
            # 检查是否是十六进制格式 "0xXXXX"
            if value.startswith("0x") or value.startswith("0X"):
                # 已经是十六进制显示，直接返回
                return value
            else:
                # 普通字符串值，直接返回
                return value
        else:
            # 非字符串值，转换为字符串
            return str(value)

    def _get_original_index(self, row, col):
        """根据表格位置获取原始数据索引"""
        if col in [0, 1, 2]:  # 第一列组
            return row
        elif col in [3, 4, 5]:  # 第二列组
            return row + self._max_rows_per_column
        elif col in [6, 7, 8]:  # 第三列组
            return row + 2 * self._max_rows_per_column
        return -1

    # ==================== 🎨 渐变颜色功能（新增）====================

    def enable_gradient_colors(self, enabled=True, duration=5.0):
        """启用/禁用渐变颜色功能
        
        Args:
            enabled: 是否启用渐变效果
            duration: 渐变持续时间（秒）
        """
        was_enabled = self._gradient_enabled
        self._gradient_enabled = enabled
        self._gradient_duration = duration
        
        # 根据状态变化订阅/取消订阅全局定时器
        if enabled and not was_enabled:
            # 从禁用变为启用：订阅全局定时器
            self._gradient_timer_manager.subscribe(self)
        elif not enabled and was_enabled:
            # 从启用变为禁用：取消订阅全局定时器
            self._gradient_timer_manager.unsubscribe(self)
            # 刷新一次以清除颜色
            if self.rowCount() > 0:
                top_left = self.index(0, 0)
                bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.BackgroundRole])

    def _refresh_gradient(self):
        """定时器回调：刷新渐变颜色（性能优化版）"""
        row_count = self.rowCount()
        if not self._gradient_enabled or row_count == 0:
            return
        
        # 批量刷新所有单元格的背景颜色
        # 只刷新"当前值"列（1, 4, 7）以优化性能
        for col in [1, 4, 7]:
            if col < self.columnCount():  # 确保列存在
                top_left = self.index(0, col)
                bottom_right = self.index(row_count - 1, col)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.BackgroundRole])

    def _get_gradient_color(self, original_row_index):
        """计算指定参数的渐变颜色（基于时间线性插值）
        
        Args:
            original_row_index: 原始数据行索引
        
        Returns:
            QColor: 插值后的颜色（白色→橙色）
        """
        if original_row_index not in self._update_timestamps:
            # 没有更新记录，返回陈旧颜色
            return self._color_stale
        
        # 计算距离上次更新的时间
        elapsed = time.time() - self._update_timestamps[original_row_index]
        
        # 计算渐变进度 (0.0 = 刚更新/白色, 1.0 = 已超时/橙色)
        progress = min(elapsed / self._gradient_duration, 1.0)
        
        # RGB线性插值
        r = int(self._color_fresh.red() + 
                (self._color_stale.red() - self._color_fresh.red()) * progress)
        g = int(self._color_fresh.green() + 
                (self._color_stale.green() - self._color_fresh.green()) * progress)
        b = int(self._color_fresh.blue() + 
                (self._color_stale.blue() - self._color_fresh.blue()) * progress)
        
        return QColor(r, g, b)

    # ==================== 数据模型接口 ====================

    def data(self, index, role):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # 显示数据
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if row < len(self._organized_data) and col < self._columns:
                return self._organized_data[row][col]
        
        # 🎨 背景颜色（新增功能）
        elif role == Qt.ItemDataRole.BackgroundRole:
            if not self._gradient_enabled:
                return None  # 渐变功能禁用时不显示背景色
            
            # "当前值"列（1, 4, 7）显示渐变颜色
            if col in [1, 4, 7]:
                original_idx = self._get_original_index(row, col)
                if 0 <= original_idx < len(self._original_data):
                    return self._get_gradient_color(original_idx)
            
            # "写入值"列（2, 5, 8）有值时显示黄色高亮
            elif col in [2, 5, 8]:
                if row < len(self._organized_data):
                    write_value = self._organized_data[row][col]
                    if write_value and str(write_value).strip():
                        return self._color_modified
        
        # 💡 工具提示（新增功能）- 鼠标悬停时显示完整内容
        elif role == Qt.ItemDataRole.ToolTipRole:
            # 所有列都显示工具提示
            if row < len(self._organized_data) and col < self._columns:
                cell_value = self._organized_data[row][col]
                # 只有当单元格内容不为空时才返回工具提示
                if cell_value and str(cell_value).strip():
                    return str(cell_value)
        
        return None

    def setData(self, index, value, role):
        """设置数据，仅允许编辑写入值列"""
        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col = index.column()

            # 只能编辑写入值列 (2, 5, 8)
            if col in [2, 5, 8] and row < len(self._organized_data):
                original_idx = self._get_original_index(row, col)
                if 0 <= original_idx < len(self._original_data):
                    self._write_values[original_idx] = str(value)
                    self._organized_data[row][col] = str(value)
                    # 刷新该单元格的显示和背景色
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])
                    return True
        return False

    def flags(self, index):
        """设置单元格标志，写入值列可编辑"""
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col = index.column()
        if col in [2, 5, 8]:  # 写入值列可编辑
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def rowCount(self, parent=QModelIndex()):
        return len(self._organized_data)

    def columnCount(self, parent=QModelIndex()):
        return self._columns

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section]
            else:
                return str(section + 1)
        return None

    def update_data(self, data):
        """完全更新所有数据（性能优化版 + 记录更新时间）"""
        # 检查数据有效性
        if not data:
            old_row_count = len(self._original_data)
            self._original_data = []
            self._organize_data()
            if old_row_count > 0:
                self.beginResetModel()
                self.endResetModel()
            return
        
        old_row_count = len(self._original_data)
        self._original_data = data

        # 清除缓存
        self._display_value_cache.clear()

        # 🎨 记录更新时间（用于渐变颜色）
        current_time = time.time()
        for idx in range(len(data)):
            self._update_timestamps[idx] = current_time

        self._organize_data()

        # 性能优化：只在行数变化时重置模型
        new_row_count = len(self._organized_data)
        if new_row_count != old_row_count:
            self.beginResetModel()
            self.endResetModel()
        else:
            # 行数未变，使用dataChanged信号（更高效）
            # 🎨 立即刷新背景色（数据更新后立即显示白色）
            if new_row_count > 0:
                top_left = self.index(0, 0)
                bottom_right = self.index(new_row_count - 1, self._columns - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    def update_row(self, row, row_data):
        """更新指定行的数据（性能优化版 + 记录更新时间）"""
        if 0 <= row < len(self._original_data):
            self._original_data[row] = row_data

            # 清除该行相关的缓存
            cache_key = (row, str(self._original_data[row][2]))
            if cache_key in self._display_value_cache:
                del self._display_value_cache[cache_key]

            # 🎨 记录更新时间
            self._update_timestamps[row] = time.time()

            # 性能优化：只更新受影响的单元格
            self._update_affected_cells(row)
            return True
        return False

    def update_cell(self, row, col, value):
        """更新指定单元格的数据（性能优化版 + 记录更新时间）"""
        if 0 <= row < len(self._original_data) and 0 <= col < 2:
            if col == 0:
                # 更新参数名
                self._original_data[row] = (value, self._original_data[row][1], self._original_data[row][2])
            elif col == 1:
                # 更新当前值
                self._original_data[row] = (self._original_data[row][0], self._original_data[row][1], value)
                # 清除缓存
                cache_key = (row, str(value))
                if cache_key in self._display_value_cache:
                    del self._display_value_cache[cache_key]

            # 🎨 记录更新时间
            self._update_timestamps[row] = time.time()

            # 性能优化：只更新受影响的单元格
            self._update_affected_cells(row)
            return True
        return False

    def _update_affected_cells(self, original_row):
        """只更新受影响的单元格（性能优化 + 立即刷新背景色）"""
        # 找出该原始行在组织后的数据中的位置
        if original_row < self._max_rows_per_column:
            # 第一列组
            display_row = original_row
            display_cols = [0, 1, 2]
        elif original_row < 2 * self._max_rows_per_column:
            # 第二列组
            display_row = original_row - self._max_rows_per_column
            display_cols = [3, 4, 5]
        else:
            # 第三列组
            display_row = original_row - 2 * self._max_rows_per_column
            display_cols = [6, 7, 8]

        # 更新组织后的数据
        if display_row < len(self._organized_data):
            if display_cols[0] < self._columns:
                self._organized_data[display_row][display_cols[0]] = self._original_data[original_row][0]
            if display_cols[1] < self._columns:
                self._organized_data[display_row][display_cols[1]] = self._get_cached_display_value(
                    original_row, self._original_data[original_row][2])

            # 🎨 发送变化信号，包括背景色（数据更新后立即显示白色）
            for col in display_cols[:2]:  # 只更新参数名和当前值列
                idx = self.index(display_row, col)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    def update_partial_data(self, updates):
        """批量更新部分数据（性能优化版）
        updates: 字典，格式为 {row_index: new_row_data} 或 {(row, col): new_value}
        """
        changed_rows = set()

        for key, value in updates.items():
            if isinstance(key, int):
                # 更新整行
                if 0 <= key < len(self._original_data):
                    self._original_data[key] = value
                    # 清除缓存
                    cache_key = (key, str(value[2] if len(value) > 2 else ''))
                    if cache_key in self._display_value_cache:
                        del self._display_value_cache[cache_key]
                    changed_rows.add(key)
            elif isinstance(key, tuple) and len(key) == 2:
                # 更新单个单元格
                row, col = key
                if 0 <= row < len(self._original_data) and 0 <= col < 2:
                    if col == 0:
                        self._original_data[row] = (value, self._original_data[row][1], self._original_data[row][2])
                    elif col == 1:
                        self._original_data[row] = (self._original_data[row][0], self._original_data[row][1], value)
                        # 清除缓存
                        cache_key = (row, str(value))
                        if cache_key in self._display_value_cache:
                            del self._display_value_cache[cache_key]
                    changed_rows.add(row)

        # 性能优化：批量更新受影响的单元格
        if changed_rows:
            # 少量更新时逐个更新
            if len(changed_rows) <= 5:
                for row in changed_rows:
                    self._update_affected_cells(row)
            else:
                # 大量更新时重新组织数据并刷新视图
                self._organize_data()
                if len(self._organized_data) > 0:
                    top_left = self.index(0, 0)
                    bottom_right = self.index(len(self._organized_data) - 1, self._columns - 1)
                    self.dataChanged.emit(top_left, bottom_right)

    def find_row_by_name(self, param_name):
        """根据参数名查找行索引（性能优化：O(1)查找）"""
        return self._name_to_index.get(param_name, -1)

    def update_value_by_name(self, param_name, new_value):
        """根据参数名更新数值（性能优化版）"""
        row = self.find_row_by_name(param_name)
        if row >= 0:
            return self.update_cell(row, 1, new_value)
        return False

    def batch_update_values_by_names(self, updates_dict):
        """批量根据参数名更新数值（性能优化：减少视图刷新次数）
        Args:
            updates_dict: {param_name: new_value, ...}
        Returns:
            成功更新的参数名列表
        """
        changed_rows = set()
        success_names = []

        for param_name, new_value in updates_dict.items():
            row = self.find_row_by_name(param_name)
            if row >= 0:
                self._original_data[row] = (self._original_data[row][0], self._original_data[row][1], new_value)
                # 清除缓存
                cache_key = (row, str(new_value))
                if cache_key in self._display_value_cache:
                    del self._display_value_cache[cache_key]
                changed_rows.add(row)
                success_names.append(param_name)

        # 批量更新
        if changed_rows:
            if len(changed_rows) <= 5:
                for row in changed_rows:
                    self._update_affected_cells(row)
            else:
                self._organize_data()
                if len(self._organized_data) > 0:
                    top_left = self.index(0, 0)
                    bottom_right = self.index(len(self._organized_data) - 1, self._columns - 1)
                    self.dataChanged.emit(top_left, bottom_right)

        return success_names

    def get_write_values(self):
        """获取所有写入值"""
        return self._write_values.copy()

    def get_modified_data(self):
        """获取有写入值的数据列表，返回格式：[(row, param_name, current_value, write_value), ...]"""
        modified_data = []
        for row, write_value in self._write_values.items():
            if row < len(self._original_data) and write_value != "":  # 只返回真正有写入值的数据
                param_name = self._original_data[row][0]
                current_value = self._original_data[row][2]
                modified_data.append((row, param_name, current_value, write_value))
        return modified_data

    def clear_write_values(self):
        """清空所有写入值（性能优化版）"""
        if not self._write_values:
            return  # 没有写入值，无需更新

        # 记录需要更新的单元格
        affected_cells = []

        for row in self._write_values.keys():
            # 找出该行在显示中的位置
            if row < self._max_rows_per_column:
                display_row = row
                write_col = 2
            elif row < 2 * self._max_rows_per_column:
                display_row = row - self._max_rows_per_column
                write_col = 5
            else:
                display_row = row - 2 * self._max_rows_per_column
                write_col = 8

            if display_row < len(self._organized_data):
                self._organized_data[display_row][write_col] = ""
                affected_cells.append((display_row, write_col))

        self._write_values.clear()

        # 性能优化：只更新受影响的单元格（包括背景色）
        if affected_cells:
            if len(affected_cells) <= 10:
                for row, col in affected_cells:
                    idx = self.index(row, col)
                    self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])
            else:
                # 大量更新时，批量发送信号
                if len(self._organized_data) > 0:
                    top_left = self.index(0, 0)
                    bottom_right = self.index(len(self._organized_data) - 1, self._columns - 1)
                    self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole])

    def set_write_value(self, row, value):
        """设置指定行的写入值"""
        if 0 <= row < len(self._original_data):
            self._write_values[row] = str(value)
            self._organize_data()
            self.beginResetModel()
            self.endResetModel()
            return True
        return False


# ============== 状态位显示委托（确保背景颜色正确显示）==============
class StatusBitsDelegate(QStyledItemDelegate):
    """自定义委托，确保背景颜色正确渲染"""
    def paint(self, painter, option, index):
        # 检查是否选中
        is_selected = option.state & QStyle.StateFlag.State_Selected

        # 获取背景颜色
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)

        if is_selected:
            # 选中时使用蓝色背景，白色文字
            painter.fillRect(option.rect, QColor(51, 153, 255))
            painter.setPen(QColor(255, 255, 255))
        else:
            # 未选中时使用状态背景颜色，黑色文字
            if bg_color:
                painter.fillRect(option.rect, bg_color)
            painter.setPen(QColor(0, 0, 0))

        # 获取显示文本
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text:
            # 添加内边距
            text_rect = option.rect.adjusted(5, 0, -5, 0)
            # 绘制文本
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(text))


# ============== 位标志显示模型（三色状态：置起绿色、置0红色、5秒未刷新灰色）==============
class BitFlagsTableModel(QAbstractTableModel):
    """位标志表格模型，支持三色状态显示，2列模式（名称 | 状态值）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 所有状态位存储在一个列表中（不分类）
        self._status_bits = []  # 列表形式：[{'name': str, 'value': int, 'last_update': float}, ...]
        self._headers = ['参数名', '状态值']  # 两列显示
        self._timeout_seconds = 5.0  # 超时时间（秒）

        # 性能优化：缓存QColor对象，避免重复创建
        self._color_cache = {
            'green': QColor(144, 238, 144),   # 浅绿色
            'red': QColor(255, 160, 160),     # 浅红色
            'gray': QColor(180, 180, 180),    # 灰色
            'black': QColor(0, 0, 0)          # 黑色文字
        }

        # 性能优化：缓存当前时间，避免每个单元格都调用time.time()
        self._cached_time = time.time()
        self._cache_update_threshold = 0.1  # 缓存更新阈值（秒）
        
        # 🔄 使用全局定时器管理器（与 BatteryTableModel 同步刷新，节省性能）
        self._global_timer_manager = _global_refresh_timer_manager
        self._global_timer_manager.subscribe(self)
    
    def __del__(self):
        """析构函数：清理时取消订阅全局定时器"""
        try:
            if hasattr(self, '_global_timer_manager'):
                self._global_timer_manager.unsubscribe(self)
        except:
            pass  # 避免析构时出错
    
    def _on_global_timer_tick(self):
        """全局定时器回调：检查超时状态（性能优化版）"""
        if self.has_data():
            self.check_timeout()

    def rowCount(self, parent=QModelIndex()):
        # 返回状态位的总数
        return len(self._status_bits)

    def columnCount(self, parent=QModelIndex()):
        return 2  # 两列：名称 | 状态值

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section]
            else:
                return str(section + 1)
        return None

    def _update_cached_time(self):
        """更新缓存的时间（按需更新）"""
        current_time = time.time()
        if current_time - self._cached_time > self._cache_update_threshold:
            self._cached_time = current_time

    def data(self, index, role):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # 检查行索引是否有效
        if row >= len(self._status_bits):
            return None

        bit_info = self._status_bits[row]

        # 性能优化：使用缓存的时间，只在必要时更新
        self._update_cached_time()
        time_diff = self._cached_time - bit_info['last_update']
        is_timeout = time_diff > self._timeout_seconds

        # 显示数据
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # 名称列
                return bit_info['name']
            elif col == 1:  # 状态值列
                return str(bit_info['value'])

        # 背景颜色（仅在状态值列显示）
        elif role == Qt.ItemDataRole.BackgroundRole:
            if col == 1:  # 只在状态值列显示颜色
                if is_timeout:
                    return self._color_cache['gray']
                elif bit_info['value'] == 1:
                    return self._color_cache['red']
                else:
                    return self._color_cache['green']

        # 前景色（文字颜色）- 使用缓存的QColor对象
        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._color_cache['black']

        # 文字对齐
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 💡 工具提示（新增功能）- 鼠标悬停时显示完整内容
        elif role == Qt.ItemDataRole.ToolTipRole:
            # 所有列都显示工具提示
            if col == 0:  # 名称列
                return bit_info['name']
            elif col == 1:  # 状态值列
                return str(bit_info['value'])

        return None

    def batch_update_status_bits(self, status_list):
        """批量更新状态位（2列模式，不分组）
        Args:
            status_list: 列表，每项格式为 {'name': str, 'value': int} 或 (name, value) 元组
        """
        # 检查数据有效性
        if not status_list:
            old_row_count = self.rowCount()
            self._status_bits = []
            if old_row_count > 0:
                self.beginResetModel()
                self.endResetModel()
            return
        
        current_time = time.time()

        # 性能优化：记录旧的行数
        old_row_count = self.rowCount()

        # 清空列表
        self._status_bits = []

        # 添加所有状态位
        for item in status_list:
            if isinstance(item, dict):
                name = item.get('name', '')
                value = item.get('value', 0)
            else:  # 假设是元组
                name, value = item

            bit_data = {
                'name': name,
                'value': value,
                'last_update': current_time
            }
            self._status_bits.append(bit_data)

        # 性能优化：只在行数变化时使用resetModel，否则使用dataChanged
        new_row_count = self.rowCount()
        if new_row_count != old_row_count:
            # 行数变化，需要重置模型
            self.beginResetModel()
            self.endResetModel()
        else:
            # 行数未变，只通知数据变化（更高效）
            if new_row_count > 0:
                top_left = self.index(0, 0)
                bottom_right = self.index(new_row_count - 1, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)

        # 更新时间缓存
        self._cached_time = current_time

    def check_timeout(self):
        """检查所有状态位是否超时，返回是否有变化（性能优化版）"""
        current_time = time.time()
        self._cached_time = current_time  # 更新时间缓存

        # 性能优化：记录需要更新的行
        changed_rows = []

        # 检查所有状态位
        for row_idx, bit_info in enumerate(self._status_bits):
            time_diff = current_time - bit_info['last_update']
            # 检查是否刚好跨越超时阈值（前后1秒的窗口）
            if self._timeout_seconds - 1 < time_diff < self._timeout_seconds + 1:
                changed_rows.append(row_idx)

        # 性能优化：只更新变化的行
        if changed_rows:
            # 如果变化的行少于10个，逐个发送信号（更精确）
            if len(changed_rows) <= 10:
                for row in changed_rows:
                    # 只更新状态值列（第1列）
                    idx = self.index(row, 1)
                    self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.BackgroundRole])
            else:
                # 变化较多时，刷新整个视图（避免信号风暴）
                if self._status_bits:
                    top_left = self.index(0, 0)
                    bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
                    self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.BackgroundRole])
            return True

        return False

    def set_timeout_seconds(self, seconds):
        """设置超时时间"""
        self._timeout_seconds = float(seconds)

    def clear_all(self):
        """清空所有状态位"""
        self.beginResetModel()
        self._status_bits = []
        self.endResetModel()

    def has_data(self):
        """检查是否有数据（用于优化定时器）"""
        return len(self._status_bits) > 0


# ============== 位标志显示窗口组件（封装UI和逻辑）==============
class BitFlagsWidget(QWidget):
    """位标志显示窗口，包含UI和业务逻辑的完整封装"""

    def __init__(self, parent=None, logger=None):
        super().__init__(parent)
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        """初始化UI组件"""
        # 创建标题标签
        self.title_label = QLabel('位标志监控（绿=0正常 红=1告警 灰=未刷新）')
        self.title_label.setStyleSheet("QLabel { color: blue; font-weight: bold; font-size: 8px; }")

        # 创建按钮布局
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton('刷新')
        self.clear_button = QPushButton('清空')
        self.test_button = QPushButton('测试')

        # 设置按钮字体大小
        button_font = QFont()
        button_font.setPointSize(7)
        self.refresh_button.setFont(button_font)
        self.clear_button.setFont(button_font)
        self.test_button.setFont(button_font)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.test_button)
        button_layout.addStretch()

        # 创建QTableView和位标志模型
        self.table_view = QTableView()
        self.table_model = BitFlagsTableModel()
        self.table_view.setModel(self.table_model)

        # 设置表格属性
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setVisible(False)

        # 设置较小的字体以适应窄列
        table_font = self.table_view.font()
        table_font.setPointSize(8)
        self.table_view.setFont(table_font)

        # 设置表头字体
        header_font = self.table_view.horizontalHeader().font()
        header_font.setPointSize(7)
        self.table_view.horizontalHeader().setFont(header_font)

        # 设置列宽度（2列模式：名称 | 状态值）
        self.table_view.setColumnWidth(0, 120)  # 名称列
        self.table_view.setColumnWidth(1, 50)   # 状态值列

        # 设置行高
        self.table_view.verticalHeader().setDefaultSectionSize(18)
        self.table_view.verticalHeader().setMinimumSectionSize(16)

        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.table_view)
        self.setLayout(main_layout)

        # 连接按钮信号
        self.clear_button.clicked.connect(self.clear_status_bits)
        self.test_button.clicked.connect(self.test_status_bits)

        # ⚠️ 注意：超时检查已通过全局定时器管理器实现，无需创建独立定时器
        # 这样可以与 BatteryTableModel 同步刷新，节省性能

    def clear_status_bits(self):
        """清空所有位标志"""
        try:
            self.table_model.clear_all()
            if self.logger:
                self.logger.write_log("已清空所有位标志")
        except Exception as e:
            if self.logger:
                self.logger.write_log(f"清空位标志失败: {e}")

    def test_status_bits(self):
        """测试按钮：生成测试数据"""
        try:
            # 生成分类测试数据
            test_data = []

            # 告警状态 14个
            for i in range(14):
                test_data.append({
                    'name': f'告_测试{i:02d}',
                    'value': random.randint(0, 1)
                })

            # 保护状态 21个
            for i in range(21):
                test_data.append({
                    'name': f'护_测试{i:02d}',
                    'value': random.randint(0, 1)
                })

            # 失效状态 12个
            for i in range(12):
                test_data.append({
                    'name': f'错_测试{i:02d}',
                    'value': random.randint(0, 1)
                })

            # 信息状态 21个
            for i in range(21):
                test_data.append({
                    'name': f'另_测试{i:02d}',
                    'value': random.randint(0, 1)
                })

            self.update_status_bits(test_data)
            if self.logger:
                self.logger.write_log(f"生成测试位标志数据: {len(test_data)} 个")
        except Exception as e:
            if self.logger:
                self.logger.write_log(f"生成测试数据失败: {e}")

    def update_status_bits(self, status_list):
        """更新位标志
        Args:
            status_list: 列表，每项格式为 {'name': str, 'value': int}
        """
        try:
            self.table_model.batch_update_status_bits(status_list)
        except Exception as e:
            if self.logger:
                self.logger.write_log(f"更新位标志失败: {e}")

    def update_single_status_bit(self, index, name, value):
        """更新单个位标志（已废弃，建议使用 update_status_bits）"""
        print(f"警告：update_single_status_bit 方法已废弃，请使用 update_status_bits")
        self.update_status_bits([{'name': name, 'value': value}])

    def set_timeout_seconds(self, seconds):
        """设置超时时间"""
        self.table_model.set_timeout_seconds(seconds)

    def get_status_bit(self, col, row):
        """获取指定位置的状态位信息"""
        return self.table_model.get_status_bit(col, row)

