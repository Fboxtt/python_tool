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


class BatteryTableModel(QAbstractTableModel):
    """电池参数表格模型（性能优化版）"""
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

        self._organize_data()

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

    def data(self, index, role):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if row < len(self._organized_data) and col < self._columns:
                return self._organized_data[row][col]
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
                    self.dataChanged.emit(index, index)
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
        """完全更新所有数据（性能优化版）"""
        old_row_count = len(self._original_data)
        self._original_data = data

        # 清除缓存
        self._display_value_cache.clear()

        self._organize_data()

        # 性能优化：只在行数变化时重置模型
        new_row_count = len(self._organized_data)
        if new_row_count != old_row_count:
            self.beginResetModel()
            self.endResetModel()
        else:
            # 行数未变，使用dataChanged信号（更高效）
            if new_row_count > 0:
                top_left = self.index(0, 0)
                bottom_right = self.index(new_row_count - 1, self._columns - 1)
                self.dataChanged.emit(top_left, bottom_right)

    def update_row(self, row, row_data):
        """更新指定行的数据（性能优化版）"""
        if 0 <= row < len(self._original_data):
            self._original_data[row] = row_data

            # 清除该行相关的缓存
            cache_key = (row, str(self._original_data[row][2]))
            if cache_key in self._display_value_cache:
                del self._display_value_cache[cache_key]

            # 性能优化：只更新受影响的单元格
            self._update_affected_cells(row)
            return True
        return False

    def update_cell(self, row, col, value):
        """更新指定单元格的数据（性能优化版）"""
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

            # 性能优化：只更新受影响的单元格
            self._update_affected_cells(row)
            return True
        return False

    def _update_affected_cells(self, original_row):
        """只更新受影响的单元格（性能优化）"""
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

            # 只发送受影响单元格的变化信号
            for col in display_cols[:2]:  # 只更新参数名和当前值列
                idx = self.index(display_row, col)
                self.dataChanged.emit(idx, idx)

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

        # 性能优化：只更新受影响的单元格
        if affected_cells:
            if len(affected_cells) <= 10:
                for row, col in affected_cells:
                    idx = self.index(row, col)
                    self.dataChanged.emit(idx, idx)
            else:
                # 大量更新时，批量发送信号
                if len(self._organized_data) > 0:
                    top_left = self.index(0, 0)
                    bottom_right = self.index(len(self._organized_data) - 1, self._columns - 1)
                    self.dataChanged.emit(top_left, bottom_right)

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
    """位标志表格模型，支持三色状态显示，每种状态位单独一列（性能优化版）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 状态位按类型分组存储
        self._status_bits = {
            'alarm': [],    # 告警状态（告_）
            'protect': [],  # 保护状态（护_）
            'fault': [],    # 失效状态（错_）
            'info': []      # 其他信息（另_）
        }
        self._headers = ['告警', '保护', '失效', '其他']  # 四列显示
        self._timeout_seconds = 5.0  # 超时时间（秒）

        # 列到类型的映射
        self._col_to_type = ['alarm', 'protect', 'fault', 'info']

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

    def rowCount(self, parent=QModelIndex()):
        # 返回所有列中最长的那列的行数
        if not any(self._status_bits.values()):
            return 0
        return max(len(bits) for bits in self._status_bits.values())

    def columnCount(self, parent=QModelIndex()):
        return 4  # 四列

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section]
            else:
                return str(section + 1)
        return None

    def _get_status_list_for_column(self, col):
        """根据列号获取对应的状态位列表"""
        if 0 <= col < len(self._col_to_type):
            return self._status_bits[self._col_to_type[col]]
        return []

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

        # 获取该列对应的状态位列表
        status_list = self._get_status_list_for_column(col)

        # 检查行索引是否有效
        if row >= len(status_list):
            return None

        bit_info = status_list[row]

        # 性能优化：使用缓存的时间，只在必要时更新
        self._update_cached_time()
        time_diff = self._cached_time - bit_info['last_update']
        is_timeout = time_diff > self._timeout_seconds

        # 显示数据：名称（状态由背景颜色表示）
        if role == Qt.ItemDataRole.DisplayRole:
            return bit_info['name']

        # 背景颜色（0=绿色，1=红色）- 使用缓存的QColor对象
        elif role == Qt.ItemDataRole.BackgroundRole:
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

        return None

    def batch_update_status_bits(self, status_list):
        """批量更新状态位，根据前缀自动分组到对应列（性能优化版）
        Args:
            status_list: 列表，每项格式为 {'name': str, 'value': int} 或 (name, value) 元组
        """
        current_time = time.time()

        # 性能优化：记录旧的行数
        old_row_count = self.rowCount()

        # 清空所有列表
        for key in self._status_bits:
            self._status_bits[key] = []

        # 根据前缀分组
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

            # 根据前缀分组到对应的列表
            if name.startswith('告_'):
                self._status_bits['alarm'].append(bit_data)
            elif name.startswith('护_'):
                self._status_bits['protect'].append(bit_data)
            elif name.startswith('错_'):
                self._status_bits['fault'].append(bit_data)
            elif name.startswith('另_'):
                self._status_bits['info'].append(bit_data)
            else:
                # 未知类型，默认放到其他信息列
                self._status_bits['info'].append(bit_data)

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

        # 性能优化：记录需要更新的单元格
        changed_cells = []

        # 检查所有列的所有状态位
        for col_idx, col_type in enumerate(self._col_to_type):
            status_list = self._status_bits[col_type]
            for row_idx, bit_info in enumerate(status_list):
                time_diff = current_time - bit_info['last_update']
                # 检查是否刚好跨越超时阈值（前后1秒的窗口）
                if self._timeout_seconds - 1 < time_diff < self._timeout_seconds + 1:
                    changed_cells.append((row_idx, col_idx))

        # 性能优化：只更新变化的单元格
        if changed_cells:
            # 如果变化的单元格少于10个，逐个发送信号（更精确）
            if len(changed_cells) <= 10:
                for row, col in changed_cells:
                    idx = self.index(row, col)
                    self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.BackgroundRole])
            else:
                # 变化较多时，刷新整个视图（避免信号风暴）
                if any(self._status_bits.values()):
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
        for key in self._status_bits:
            self._status_bits[key] = []
        self.endResetModel()

    def has_data(self):
        """检查是否有数据（用于优化定时器）"""
        return any(len(bits) > 0 for bits in self._status_bits.values())


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

        # 设置列宽（四列，适应390宽度窗口）
        self.table_view.setColumnWidth(0, 70)
        self.table_view.setColumnWidth(1, 70)
        self.table_view.setColumnWidth(2, 70)
        self.table_view.setColumnWidth(3, 70)

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

        # 创建定时器，每2秒检查一次超时状态（性能优化）
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_timeout)
        self.check_timer.start(2000)

    def check_timeout(self):
        """定时器回调：检查位标志是否超时（性能优化版）"""
        try:
            if self.table_model.has_data():
                self.table_model.check_timeout()
        except Exception as e:
            if self.logger:
                self.logger.write_log(f"检查位标志超时失败: {e}")

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

