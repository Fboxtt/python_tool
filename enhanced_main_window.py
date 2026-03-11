"""
增强版主窗口 - 集成MultiWindowManager到load_ui_dynamically
替代原有的battery_window和bit_window
"""
import sys
import os
import asyncio
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QCursor, QIcon, QPixmap

# 导入必要的模块
from newblue3_17 import BluetoothTool, SimplifiedBluetoothTool, load_ui_dynamically
from log_controller import LogManager, ComunManager
from multi_window_manager import MultiWindowManager
from struct_model import (
    HexParserApp,
    STRUCT_COMMANDS,
    get_alarm_protect_display_data,
    get_other_status_display_data,
    get_battery_status_display_data,
    get_voltage_params_display_data,
    detect_special_command
)
from language_manager import t, set_language, get_current_language

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
        self.logger.write_log(t('ui.log_init'))
        
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
        
        # 连接/断开信号
        self.bluetooth_tool.device_connected.connect(self.check_connection_status)
        self.bluetooth_tool.device_disconnected.connect(self._on_device_disconnected)
        
        self.init_ui()
        # 注册增强窗口引用到bluetooth_tool，供OTA暂停/恢复监控使用
        self.bluetooth_tool._enhanced_window_ref = self
        self._ota_paused_monitoring = False
        
    def init_ui(self):
        """初始化UI"""
        # 获取APP模式
        app_mode = os.environ.get('APP_MODE', 'factoryApp')
        
        # 构建窗口标题，根据模式使用不同格式
        if app_mode == 'userApp':
            # 用户版：使用简化标题
            if VERSION_INFO_AVAILABLE:
                try:
                    version = build_version_info.VERSION
                    window_title = t('ui.user_app_title') + f' v{version}'
                    company_info = t('ui.company_info', version)
                    self.setWindowTitle(window_title)
                    
                    # 打印公司信息到日志
                    self.logger.write_log("="*60)
                    self.logger.write_log(company_info)
                    self.logger.write_log(t('ui.version_number', version))
                    self.logger.write_log("="*60)
                except Exception as e:
                    self.logger.write_log(t('ui.version_read_error', e))
                    self.setWindowTitle(t('ui.user_app_title'))
            else:
                self.setWindowTitle(t('ui.user_app_title'))
        else:
            # 工厂版/开发版/firstuse：使用完整标题
            base_title = t('ui.window_title')
            if VERSION_INFO_AVAILABLE:
                try:
                    version_str = build_version_info.get_version_string()
                    self.setWindowTitle(f'{base_title} | {version_str}')
                    
                    # 打印详细信息到日志
                    detailed_info = build_version_info.get_detailed_info()
                    self.logger.write_log("="*60)
                    self.logger.write_log(t('ui.version_info_title'))
                    self.logger.write_log(f"  {t('ui.build_date')}: {detailed_info['build_date']}")
                    self.logger.write_log(f"  {t('ui.git_branch')}: {detailed_info['git_branch']}")
                    self.logger.write_log(f"  {t('ui.git_commit')}: {detailed_info['git_commit_hash']}")
                    self.logger.write_log(f"  {t('ui.commit_message')}: {detailed_info['git_commit_message']}")
                    self.logger.write_log(f"  {t('ui.commit_author')}: {detailed_info['git_commit_author']}")
                    self.logger.write_log(f"  {t('ui.commit_time')}: {detailed_info['git_commit_date']}")
                    self.logger.write_log("="*60)
                except Exception as e:
                    self.logger.write_log(t('ui.version_read_error', e))
                    self.setWindowTitle(base_title)
            else:
                self.setWindowTitle(base_title)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), 'Ampere-Time-logo.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
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
        
        # 标题（图标+文字）
        icon_path = os.path.join(os.path.dirname(__file__), 'Ampere-Time-logo.ico')
        if os.path.exists(icon_path):
            icon_label = QLabel()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(scaled_pixmap)
            layout.addWidget(icon_label)
        title_label = QLabel(t('ui.control_panel'))
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(14)
        title_label.setFont(font)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 获取APP模式
        app_mode = os.environ.get('APP_MODE', 'factoryApp')
        
        # 工厂模式checkbox
        self.factory_mode_checkbox = QCheckBox(t('ui.factory_mode'))
        if app_mode == 'userApp':
            # 用户版：不可切换，强制不勾选（用户模式）
            self.factory_mode_checkbox.setChecked(False)
            self.factory_mode_checkbox.setEnabled(False)
        else:
            # 工厂版/firstuse：可切换，默认勾选（工厂模式）
            self.factory_mode_checkbox.setChecked(True)
            self.factory_mode_checkbox.setEnabled(True)
        self.factory_mode_checkbox.stateChanged.connect(self.on_factory_mode_changed)
        layout.addWidget(self.factory_mode_checkbox)
        
        # 窗口模式切换checkbox
        self.use_simplified_window = QCheckBox(t('ui.simplified_window'))
        if app_mode == 'userApp':
            # 用户版：默认简化窗口，不可切换
            self.use_simplified_window.setChecked(True)
            self.use_simplified_window.setEnabled(False)
        else:
            # 工厂版/firstuse：可切换，默认原窗口
            self.use_simplified_window.setChecked(False)
            self.use_simplified_window.setEnabled(True)
        layout.addWidget(self.use_simplified_window)
        
        # 32电芯配置checkbox
        self.cell_32_checkbox = QCheckBox(t('ui.cell_32_config'))
        self.cell_32_checkbox.setToolTip(t('ui.cell_32_tooltip'))
        self.cell_32_checkbox.stateChanged.connect(self.on_cell_config_changed)

        # 英文用户版：禁用32-cell配置选项
        if app_mode == 'userApp':
            self.cell_32_checkbox.setChecked(False)
            self.cell_32_checkbox.setEnabled(False)

        layout.addWidget(self.cell_32_checkbox)
        
        # 连接控制
        self.connect_btn = QPushButton(t('ui.open_connection'))
        self.connect_btn.clicked.connect(self.show_bluetooth_tool)
        layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton(t('ui.disconnect'))
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn)
        
        # 监控控制
        self.monitor_btn = QPushButton(t('ui.start_monitor'))
        self.monitor_btn.clicked.connect(self.toggle_monitoring)
        self.monitor_btn.setEnabled(False)
        layout.addWidget(self.monitor_btn)
        
        # 版本查询
        self.version_btn = QPushButton(t('ui.query_version'))
        self.version_btn.clicked.connect(self.query_version)
        layout.addWidget(self.version_btn)
        
        # 清空队列
        self.clear_queue_btn = QPushButton(t('ui.clear_queue'))
        self.clear_queue_btn.clicked.connect(self.clear_send_queue)
        layout.addWidget(self.clear_queue_btn)
        
        # 语言选择下拉框
        self.language_combo = QComboBox()
        self.language_combo.addItem('language: 中文', 'zh_CN')
        self.language_combo.addItem('language: English', 'en_US')
        
        # 设置当前语言
        current_lang = get_current_language()
        if current_lang == 'zh_CN':
            self.language_combo.setCurrentIndex(0)
        else:
            self.language_combo.setCurrentIndex(1)
        
        self.language_combo.setToolTip('选择界面语言 / Select Language')
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        layout.addWidget(self.language_combo)
        
        panel.setLayout(layout)
        panel.setMaximumHeight(60)
        
        return panel
        
    def create_status_panel(self):
        """创建状态面板"""
        panel = QWidget()
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 连接状态
        self.conn_status_label = QLabel(t('ui.status_disconnected'))
        font = self.conn_status_label.font()
        font.setPointSize(11)
        self.conn_status_label.setFont(font)
        self.conn_status_label.setStyleSheet('color: #999;')  # 初始灰色
        self.conn_status_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.conn_status_label)
        
        layout.addStretch()
        
        # 发送队列状态
        self.queue_status_label = QLabel(f"{t('ui.send_queue')}: 0")
        self.queue_status_label.setFont(font)
        self.queue_status_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.queue_status_label)
        
        # 数据接收计数
        self.rx_count_label = QLabel(f"{t('ui.receive')}: 0")
        self.rx_count_label.setFont(font)
        self.rx_count_label.setContentsMargins(3, 0, 10, 0)
        layout.addWidget(self.rx_count_label)
        
        # 数据发送计数
        self.tx_count_label = QLabel(f"{t('ui.send')}: 0")
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
        
        self.logger.write_log(t('ui.log_windows_configured', len(window_configs)))
        
        # 初始化写入功能状态（根据工厂模式checkbox的初始状态）
        QTimer.singleShot(100, lambda: self.multi_window_manager.set_write_enabled(
            self.factory_mode_checkbox.isChecked()
        ))
        
    def setup_timers(self):
        """设置定时器"""
        # 队列状态更新定时器
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.update_status_display)
        self.queue_timer.start(500)  # 每0.5秒更新
        
    def _activate_simplified_window(self):
        """延迟激活简化窗口，确保获得焦点"""
        if hasattr(self, 'simplified_bluetooth_tool') and self.simplified_bluetooth_tool.isVisible():
            # print(f"[主窗口] 强制激活简化窗口")
            self.simplified_bluetooth_tool.activateWindow()
            self.simplified_bluetooth_tool.setFocus()
    
    def _adjust_window_position(self, window, target_pos):
        """调整窗口位置，确保不超出屏幕边界
        
        Args:
            window: 要调整的窗口
            target_pos: 目标位置（QPoint）
        
        Returns:
            QPoint: 调整后的位置
        """
        # 获取窗口大小
        window_size = window.size()
        window_width = window_size.width()
        window_height = window_size.height()
        
        # 获取屏幕几何信息
        screen = QApplication.screenAt(target_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        
        screen_geometry = screen.availableGeometry()
        screen_right = screen_geometry.x() + screen_geometry.width()
        screen_bottom = screen_geometry.y() + screen_geometry.height()
        
        # 调整X坐标，确保窗口右边不超出屏幕
        x = target_pos.x()
        if x + window_width > screen_right:
            x = screen_right - window_width
        if x < screen_geometry.x():
            x = screen_geometry.x()
        
        # 调整Y坐标，确保窗口底部不超出屏幕
        y = target_pos.y()
        if y + window_height > screen_bottom:
            y = screen_bottom - window_height
        if y < screen_geometry.y():
            y = screen_geometry.y()
        
        from PyQt6.QtCore import QPoint
        return QPoint(x, y)
    
    def show_bluetooth_tool(self):
        """显示/隐藏蓝牙工具窗口（切换功能）"""
        cursor_pos = QCursor.pos()
        
        if self.use_simplified_window.isChecked():
            # 简化窗口：切换显示/隐藏
            if not hasattr(self, 'simplified_bluetooth_tool'):
                # print(f"[主窗口] 创建简化窗口")
                self.simplified_bluetooth_tool = SimplifiedBluetoothTool(self.bluetooth_tool)
            
            # 确保原窗口隐藏
            if self.bluetooth_tool.isVisible():
                self.bluetooth_tool.hide()
            
            is_visible = self.simplified_bluetooth_tool.isVisible()
            # print(f"[主窗口] show_bluetooth_tool: 简化窗口可见性={is_visible}")
            
            if is_visible:
                # print(f"[主窗口] 隐藏简化窗口")
                self.simplified_bluetooth_tool.hide()
            else:
                # print(f"[主窗口] 显示简化窗口在: {cursor_pos}")
                # 调整位置，确保不超出屏幕
                adjusted_pos = self._adjust_window_position(self.simplified_bluetooth_tool, cursor_pos)
                self.simplified_bluetooth_tool.move(adjusted_pos)
                self.simplified_bluetooth_tool.show()
                self.simplified_bluetooth_tool.raise_()
                # 强制设置焦点
                QTimer.singleShot(10, self._activate_simplified_window)
        else:
            # 原窗口：切换显示/隐藏
            # 确保简化窗口隐藏
            if hasattr(self, 'simplified_bluetooth_tool') and self.simplified_bluetooth_tool.isVisible():
                self.simplified_bluetooth_tool.hide()
            
            is_visible = self.bluetooth_tool.isVisible()
            # print(f"[主窗口] show_bluetooth_tool: 原窗口可见性={is_visible}")
            
            if is_visible:
                # print(f"[主窗口] 隐藏原窗口")
                self.bluetooth_tool.hide()
            else:
                # print(f"[主窗口] 显示原窗口在: {cursor_pos}")
                # 恢复device_list到原窗口
                self.bluetooth_tool.restore_device_list()
                # 调整位置，确保不超出屏幕
                adjusted_pos = self._adjust_window_position(self.bluetooth_tool, cursor_pos)
                self.bluetooth_tool.move(adjusted_pos)
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
                # 显示蓝牙设备信息
                device_name = getattr(self.bluetooth_tool, 'device_name', t('ui.unknown_device'))
                device_address = getattr(self.bluetooth_tool, 'device_address', '')
                if device_address:
                    self.conn_status_label.setText(t('ui.bt_connected_with_addr', device_name, device_address))
                else:
                    self.conn_status_label.setText(t('ui.bt_connected_no_addr', device_name))
            elif self.bluetooth_tool.is_serial_connected:
                is_connected = True
                # 显示串口信息
                port_name = self.bluetooth_tool.port_combo.currentText() if hasattr(self.bluetooth_tool, 'port_combo') else t('ui.unknown_port')
                self.conn_status_label.setText(t('ui.serial_connected', port_name))
        except:
            pass
        if not is_connected:
            self.conn_status_label.setText(t('ui.status_disconnected'))
            self.conn_status_label.setStyleSheet('color: #999;')  # 灰色
            if self.scan_task:
                self.monitor_btn.setText(t('ui.start_monitor'))
                self.scan_task.cancel()
                self.scan_task = None
        else:
            self.conn_status_label.setStyleSheet('color: #28a745;')  # 连接时绿色
        self.disconnect_btn.setEnabled(is_connected)
        self.monitor_btn.setEnabled(is_connected)
        
    def _on_device_disconnected(self):
        """设备断开时立即清理（由 device_disconnected 信号触发）"""
        if self.scan_task:
            self.scan_task.cancel()
            self.scan_task = None
            self.monitor_btn.setText('▶️ 开始监控')
        self.multi_window_manager.clear_send_queue()
        self.bluetooth_tool.blue_write_log("🧹 监控已停止，发送队列已清空")
        self.check_connection_status()  # 立即更新按钮状态
    def disconnect_device(self):
        """断开设备连接"""
        # 直接停止监控，不调用 toggle_monitoring 避免状态判断出错
        if self.scan_task:
            self.scan_task.cancel()
            self.scan_task = None
            self.monitor_btn.setText('▶️ 开始监控')
        try:
            if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
                asyncio.create_task(self.bluetooth_tool.disconnect_device())
            elif self.bluetooth_tool.is_serial_connected:
                asyncio.create_task(self.bluetooth_tool.disconnect_serial())
        except:
            pass
        self.check_connection_status()  # 立即更新按钮状态，无需延迟
        
    def toggle_monitoring(self):
        """切换监控状态"""
        # 防止快速重复点击重入
        if getattr(self, '_monitoring_toggling', False):
            return
        self._monitoring_toggling = True
        try:
            # 以 scan_task 是否存在为唯一状态判断，不依赖 button text
            if self.scan_task is None:
                try:
                    is_connected = (self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected) or self.bluetooth_tool.is_serial_connected
                except:
                    is_connected = False
                if not is_connected:
                    self.bluetooth_tool.blue_write_log("⚠️ 未连接设备，无法开始监控")
                    return
                self.monitor_btn.setText(t('ui.stop_monitor'))
                self.scan_task = asyncio.create_task(self.monitoring_loop())
                self.logger.write_log(t('ui.log_monitoring_start'))
            else:
                self.monitor_btn.setText(t('ui.start_monitor'))
                self.scan_task.cancel()
                self.scan_task = None
                self.logger.write_log(t('ui.log_monitoring_stop'))
        finally:
            self._monitoring_toggling = False

    def pause_monitoring_for_ota(self):
        """OTA开始时暂停监控，并禁用监控按钮"""
        if self.scan_task:
            self._ota_paused_monitoring = True
            self.scan_task.cancel()
            self.scan_task = None
            self.monitor_btn.setText('▶️ 开始监控')
            self.bluetooth_tool.blue_write_log("⏸️ OTA开始，监控已暂停")
        else:
            self._ota_paused_monitoring = False
        self.monitor_btn.setEnabled(False)

    def resume_monitoring_after_ota(self):
        """OTA结束后恢复监控按钮，并在之前有监控时自动重启"""
        self.monitor_btn.setEnabled(True)
        if getattr(self, '_ota_paused_monitoring', False):
            self._ota_paused_monitoring = False
            self.bluetooth_tool.blue_write_log("▶️ OTA结束，自动恢复监控")
            self.toggle_monitoring()

    async def monitoring_loop(self):
        """监控循环 - 定期查询数据"""
        current_task = asyncio.current_task()
        try:
            while True:
                # 检查连接状态
                try:
                    is_connected = (self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected) or self.bluetooth_tool.is_serial_connected
                except:
                    is_connected = False
                if not is_connected:
                    break
                # 获取监控间隔时间
                interval = self.bluetooth_tool.monitor_interval_spinbox.value()
                # 查询SBS数据
                await self.queue_send_command(0x13, "PC_GET_SBS")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.write_log(t('ui.log_monitoring_error', str(e)))
        finally:
            # 只有当自己仍是当前 scan_task 时才更新 UI，防止覆盖快速重启创建的新 task
            if self.scan_task is current_task:
                self.monitor_btn.setText(t('ui.start_monitor'))
                self.scan_task = None
            
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
            self.logger.write_log(t('ui.log_send_command_failed', str(e)))
            
    def on_factory_mode_changed(self, state):
        """工厂模式checkbox状态改变"""
        is_factory_mode = (state == Qt.CheckState.Checked.value)
        is_user_mode = not is_factory_mode  # 用户模式 = 非工厂模式

        mode_name = t('ui.mode_factory') if is_factory_mode else t('ui.mode_user')
        self.logger.write_log(t('ui.log_mode_switched', mode_name))

        # 更新所有数据窗口的写入功能状态
        self.multi_window_manager.set_write_enabled(is_factory_mode)

        # 更新32-cell配置checkbox状态
        if is_user_mode:
            # 用户模式：禁用32-cell配置
            self.cell_32_checkbox.setChecked(False)
            self.cell_32_checkbox.setEnabled(False)
        else:
            # 工厂模式：启用32-cell配置
            self.cell_32_checkbox.setEnabled(True)

        # 更新数据窗口选择限制
        self.multi_window_manager.set_user_mode_restrictions(is_user_mode)
        
    def on_cell_config_changed(self, state):
        """32电芯配置checkbox状态改变"""
        is_32_cell = (state == Qt.CheckState.Checked.value)
        config_name = t('ui.config_32cell_name') if is_32_cell else t('ui.config_16cell_name')
        self.logger.write_log(t('ui.log_cell_config_switch', config_name))
        
        # 同步到bluetooth_tool的配置
        if hasattr(self, 'bluetooth_tool') and self.bluetooth_tool:
            # 阻止触发bluetooth_tool的信号，避免循环
            self.bluetooth_tool.cell_32_checkbox.blockSignals(True)
            self.bluetooth_tool.cell_32_checkbox.setChecked(is_32_cell)
            self.bluetooth_tool.cell_32_checkbox.blockSignals(False)
            
            # 调用bluetooth_tool的配置切换逻辑
            self.bluetooth_tool.on_cell_config_changed(state)
    
    def sync_cell_config_from_bluetooth_tool(self):
        """从bluetooth_tool同步32电芯配置到主界面"""
        if hasattr(self, 'bluetooth_tool') and self.bluetooth_tool:
            try:
                # 获取bluetooth_tool的配置状态
                is_32_cell = self.bluetooth_tool.cell_32_checkbox.isChecked()
                
                # 阻止触发主界面的信号，避免循环
                self.cell_32_checkbox.blockSignals(True)
                self.cell_32_checkbox.setChecked(is_32_cell)
                self.cell_32_checkbox.blockSignals(False)
                
                config_name = t('ui.config_32cell_name') if is_32_cell else t('ui.config_16cell_name')
                self.logger.write_log(t('ui.log_cell_config_loaded', config_name))
            except Exception as e:
                self.logger.write_log(t('ui.log_cell_config_sync_failed', str(e)))
        
    def query_version(self):
        """查询版本"""
        asyncio.create_task(self.queue_send_command(0x71, "VERSION"))
        
    def clear_send_queue(self):
        """清空发送队列"""
        self.multi_window_manager.clear_send_queue()
        self.logger.write_log(t('ui.log_queue_cleared'))
    
    def on_language_changed(self, index):
        """语言下拉框选择改变 - 切换语言后重启窗口"""
        if index < 0:
            return
        new_language = self.language_combo.itemData(index)
        current_language = get_current_language()
        if new_language == current_language:
            return
        set_language(new_language)
        QTimer.singleShot(100, self._restart_window)
    def _restart_window(self):
        """重启窗口以应用新语言"""
        new_window = EnhancedMainWindow()
        new_window.show()
        # 挂到 QApplication 防止被垃圾回收
        QApplication.instance()._keep_window = new_window
        self._is_restarting = True
        self.close()
    
    def update_status_display(self):
        """更新状态显示"""
        # 更新队列状态
        queue_len = self.multi_window_manager.get_queue_length()
        self.queue_status_label.setText(f"{t('ui.send_queue')}: {queue_len}")
        
        # 检查连接状态
        self.check_connection_status()
        
    def on_window_read(self, window_id):
        """处理窗口读取请求（手动点击，优先发送）"""
        self.logger.write_log(t('ui.log_read_request', window_id))
        
        # 根据window_id获取对应的命令码（直接从STRUCT_COMMANDS获取）
        from struct_model import STRUCT_COMMANDS
        cmd_code = STRUCT_COMMANDS.get(window_id)
        
        if cmd_code:
            # 手动点击的读取指令，使用优先发送
            asyncio.create_task(self.queue_send_command(cmd_code, window_id, priority=True))
        else:
            self.logger.write_log(t('ui.log_read_command_not_found', window_id))
            
    def on_window_write(self, window_id, modified_data):
        """处理窗口写入请求"""
        self.logger.write_log(t('ui.log_write_request', window_id, len(modified_data)))
        asyncio.create_task(self.process_write_request(window_id, modified_data))
        
    async def process_write_request(self, window_id, modified_data):
        """处理写入请求"""
        try:
            # 获取写入命令码
            from struct_model import get_write_command_code, STRUCT_FORMATS, STRUCT_VARIABLES, WRITE_VALIDATORS
            import struct
            
            cmd_code = get_write_command_code(window_id)
            if not cmd_code:
                self.logger.write_log(t('ui.log_write_not_supported', window_id))
                return
            
            # 获取当前窗口的所有数据
            window = self.multi_window_manager.windows.get(window_id)
            if not window or not window.table_model:
                self.logger.write_log(t('ui.log_cannot_get_window_data'))
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
                        self.logger.write_log(t('ui.log_value_convert_failed', row_idx, value_str))
                        write_values.append(0)
            
            # 写入前校验（如有校验函数）
            validator = WRITE_VALIDATORS.get(window_id)
            if validator:
                var_names = STRUCT_VARIABLES.get(window_id, [])
                ok, err_msg = validator(write_values, var_names)
                if not ok:
                    self.bluetooth_tool.blue_write_log(f"❌ 写入校验失败: {err_msg}")
                    return
            
            # 根据结构体格式打包
            if window_id not in STRUCT_FORMATS:
                self.logger.write_log(t('ui.log_struct_format_not_found', window_id))
                return
            
            fmt = STRUCT_FORMATS[window_id]
            
            try:
                packed_data = struct.pack(fmt, *write_values)
            except struct.error as e:
                self.logger.write_log(t('ui.log_pack_failed', str(e)))
                return
            
            # 构造完整命令
            try:
                full_command = self.bluetooth_tool.text_decode.send_hex_fill(cmd_code, packed_data)
            except Exception as e:
                self.logger.write_log(t('ui.log_command_construct_failed', str(e)))
                traceback.print_exc()
                return
            
            # 通过队列发送
            await self.multi_window_manager.queue_send(full_command, priority=True)
            self.logger.write_log(t('ui.log_write_command_sent', window_id))
            
            # 不清空写入值，保留用户输入
            # self.multi_window_manager.clear_window_write_values(window_id)
            
        except Exception as e:
            self.bluetooth_tool.blue_write_log(t('ui.log_write_request_failed', str(e)))
            traceback.print_exc()
            
    def custom_process_complete_data(self):
        """自定义数据处理方法（替代bluetooth_tool的原始方法）"""
        try:
            if not hasattr(self.bluetooth_tool, 'received_data_buffer'):
                return
            data_buffer = bytes(self.bluetooth_tool.received_data_buffer)
            if not data_buffer:
                return
            self.bluetooth_tool.display_received_data(data_buffer)
            # 检测特殊指令
            special_cmd = detect_special_command(data_buffer)
            if special_cmd:
                self.bluetooth_tool.blue_write_log(special_cmd['message'])
                if special_cmd['clear_buffer']:
                    self.bluetooth_tool.received_data_buffer.clear()
                if special_cmd['stop_processing']:
                    return
            # 检查密码响应
            if self.bluetooth_tool.check_new_password_response(data_buffer):
                self.bluetooth_tool.handle_new_password_response(data_buffer)
                self.bluetooth_tool.received_data_buffer.clear()
                return

            # 检查是否是OTA指令
            if self.bluetooth_tool.is_ota_command(data_buffer):
                # 特殊处理：71指令（PC_GET_INF）需要同时满足OTA验证和窗口显示
                cmd_code = data_buffer[4] & 0x7F if len(data_buffer) >= 5 else 0
                if cmd_code == 0x71:  # PC_GET_INF
                    # 先调用split_data，设置no80_cmd和cmd_ack供OTA控制器判断
                    self.bluetooth_tool.text_decode.split_data(bytearray(data_buffer))
                    # 保存data_hex供OTA前置检查（版本/唯一ID比较）使用
                    self.bluetooth_tool.last_inf_data_hex = bytearray(self.bluetooth_tool.text_decode.data_hex)
                    # 继续下面的普通数据处理，同时更新显示窗口
                    pass
                else:
                    # 其他OTA指令正常处理
                    self.bluetooth_tool.text_decode.split_data(bytearray(data_buffer))
                    self.bluetooth_tool.received_data_buffer.clear()
                    return

            # 特殊处理：PRINT 指令（0x14/0x94）- 不校验，直接转ASCII
            if self.bluetooth_tool.process_print_command(data_buffer):
                pass  # 已在 process_print_command 中处理完毕

            # 提取响应命令码（用于发射信号）
            response_cmd_code = None
            if len(data_buffer) >= 5:
                response_cmd_code = data_buffer[4] & 0x7F  # 去掉0x80标志，获取原始命令码

            # 普通数据指令：使用data_display_mgr解析
            if hasattr(self.bluetooth_tool, 'data_display_mgr') and self.bluetooth_tool.data_display_mgr:
                success, result = self.bluetooth_tool.data_display_mgr.parse_and_update_displays(data_buffer)

                if success:
                    struct_name = result['struct_name']
                    dict_data = result['data']

                    # ⭐ 特殊处理：PC_A_PRINT 和 MCU_A_PRINT - 打印 ASCII 字符串到终端
                    if struct_name in ['PC_A_PRINT', 'MCU_A_PRINT']:
                        # 提取 ASCII 字符串（第一个字段）
                        ascii_string = ""
                        for items in dict_data.values():
                            if items and len(items) > 0 and len(items[0]) >= 3:
                                ascii_string = items[0][2]  # 第一个字段的值
                                break

                        # 额外打印一行彩色的 ASCII 字符串（便于阅读）
                        if ascii_string:
                            self.bluetooth_tool.blue_write_log(
                                f"[ASCII] {ascii_string}",
                                color='#00CED1'  # 深青色 (DarkTurquoise)
                            )

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

                    # 🔥 发射信号通知队列管理器和其他监听者：数据接收成功
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
                self.bluetooth_tool.blue_write_log("错误：data_display_mgr未初始化")
            
            # 显示接收到的数据（原始逻辑）
            # self.bluetooth_tool.display_received_data(data_buffer)
            
            # 清空缓冲区
            self.bluetooth_tool.received_data_buffer.clear()
                        
        except Exception as e:
            self.bluetooth_tool.received_data_buffer.clear()
            self.bluetooth_tool.blue_write_log(t('ui.log_custom_process_error', str(e)))
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
            self.logger.write_log(t('ui.log_update_window_data_failed', str(e)))
            traceback.print_exc()
    
    def update_bit_flags_window(self, dict_data):
        """更新状态位窗口（告警-保护、其他状态信息、电池状态）
        
        Args:
            dict_data: SBS解析后的字典数据，格式为 {category: [(name, unit, value), ...]}
        """
        try:
            # 将dict_data转换为flat_dict（需要转换为整数）
            flat_dict = {}
            
            # 将dict_data转换为sbs_data_dict格式（键名为翻译后的名称）
            # dict_data格式: {category: [(name, unit, value), ...]}
            # 需要转换为: {key_name: integer_value}
            sbs_data_dict = {}
            
            # 获取当前语言下的键名（这些是STRUCT_VARIABLES中使用的键名）
            alarm_key = t('var_templates.alarm_status')
            protect_key = t('var_templates.protect_status')
            fault_key = t('var_templates.fault_status')
            other_info_key = t('var_templates.other_info')
            balance_key = t('var_templates.balance_status')
            battery_key = t('var_templates.battery_status_label')
            
            # 遍历dict_data，找到对应的状态位字段并转换为整数
            # 变量名就是翻译后的名称，直接精确匹配
            all_names = []
            for category, items in dict_data.items():
                for item in items:
                    if len(item) >= 3:
                        name, unit, value_str = item[0], item[1], item[2]
                        all_names.append(name)
                        
                        # 精确匹配变量名（name就是翻译后的名称）
                        if name == alarm_key:
                            try:
                                sbs_data_dict[alarm_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
                        elif name == protect_key:
                            try:
                                sbs_data_dict[protect_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
                        elif name == fault_key:
                            try:
                                sbs_data_dict[fault_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
                        elif name == other_info_key:
                            try:
                                sbs_data_dict[other_info_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
                        elif name == balance_key:
                            try:
                                sbs_data_dict[balance_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
                        elif name == battery_key:
                            try:
                                sbs_data_dict[battery_key] = int(value_str, 16) if isinstance(value_str, str) and value_str.startswith('0x') else int(value_str)
                            except (ValueError, TypeError):
                                pass
            
            # 更新告警-保护信息窗口
            if sbs_data_dict:
                # 更新告警-保护信息窗口
                alarm_protect_data = get_alarm_protect_display_data(sbs_data_dict)
                if alarm_protect_data and 'ALARM_PROTECT' in self.multi_window_manager.windows:
                    self.multi_window_manager.update_window_data('ALARM_PROTECT', alarm_protect_data)
                elif not alarm_protect_data:
                    self.bluetooth_tool.blue_write_log("警告: ALARM_PROTECT 数据为空")
                elif 'ALARM_PROTECT' not in self.multi_window_manager.windows:
                    self.bluetooth_tool.blue_write_log("警告: ALARM_PROTECT 窗口未创建")
                
                # 更新其他状态信息窗口
                other_status_data = get_other_status_display_data(sbs_data_dict)
                if other_status_data and 'OTHER_STATUS' in self.multi_window_manager.windows:
                    self.multi_window_manager.update_window_data('OTHER_STATUS', other_status_data)
                elif not other_status_data:
                    self.bluetooth_tool.blue_write_log("警告: OTHER_STATUS 数据为空")
                elif 'OTHER_STATUS' not in self.multi_window_manager.windows:
                    self.bluetooth_tool.blue_write_log("警告: OTHER_STATUS 窗口未创建")
                
                # 更新电池状态窗口
                battery_status_data = get_battery_status_display_data(sbs_data_dict)
                if battery_status_data and 'BATTERY_STATUS' in self.multi_window_manager.windows:
                    self.multi_window_manager.update_window_data('BATTERY_STATUS', battery_status_data)
                elif not battery_status_data:
                    self.bluetooth_tool.blue_write_log("警告: BATTERY_STATUS 数据为空")
                elif 'BATTERY_STATUS' not in self.multi_window_manager.windows:
                    self.bluetooth_tool.blue_write_log("警告: BATTERY_STATUS 窗口未创建")
                
            # 更新电压参数窗口
            voltage_params_data = get_voltage_params_display_data(flat_dict)
            if voltage_params_data and 'VOLTAGE_PARAMS' in self.multi_window_manager.windows:
                self.multi_window_manager.update_window_data('VOLTAGE_PARAMS', voltage_params_data)
                
        except Exception as e:
            self.logger.write_log(t('ui.log_update_bit_flags_failed', str(e)))
            traceback.print_exc()
            
    def focusInEvent(self, event):
        """主窗口获得焦点时，隐藏简化窗口"""
        # print(f"[主窗口] focusInEvent - 主窗口获得焦点")
        if hasattr(self, 'simplified_bluetooth_tool'):
            is_visible = self.simplified_bluetooth_tool.isVisible()
            # print(f"[主窗口]   简化窗口可见性: {is_visible}")
            if is_visible:
                # print(f"[主窗口]   隐藏简化窗口")
                self.simplified_bluetooth_tool.hide()
        super().focusInEvent(event)
    
    def closeEvent(self, event):
        """重写关闭事件"""
        # 停止监控
        if self.scan_task:
            self.scan_task.cancel()
            
        # 关闭日志（重启时不关闭，避免新窗口写日志失败）
        if not getattr(self, '_is_restarting', False):
            self.logger.close_log()
        
        # 断开连接
        if self.bluetooth_tool.client and self.bluetooth_tool.client.is_connected:
            asyncio.create_task(self.bluetooth_tool.disconnect_device())
        
        # 关闭蓝牙工具窗口（newblue.py窗口）
        try:
            # 关闭简化窗口
            if hasattr(self, 'simplified_bluetooth_tool'):
                self.simplified_bluetooth_tool.close()
            
            # 关闭原始蓝牙工具窗口
            if hasattr(self, 'bluetooth_tool'):
                self.bluetooth_tool.close()
        except Exception as e:
            self.logger.write_log(t('ui.log_close_bt_window_error', str(e)))
            
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
        print(t('ui.program_error', str(e)))
        traceback.print_exc()
        

if __name__ == "__main__":
    main()

