import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
                            QTextEdit, QGroupBox, QSpinBox, QDateEdit, QMessageBox, QDialog, QTabWidget, QRadioButton, QButtonGroup)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont

CONFIG_FILE = "bms_config.json"

class ConfigManager:
    def __init__(self):
        self.config_path = Path(CONFIG_FILE)
        self.default_config = {
            "bms_voltages": ["12", "24", "36", "48"],
            "bms_capacities": ["50", "100", "140", "165", "200", "300"],
            "voltages": ["12", "24", "36", "48"],
            "capacities": ["50", "100", "140", "165", "200", "300"],
            "cell_models": ["略", "G_N_H10", "L_F_H20", "P_C_H50", "A_K_H100"],
            "use_cases": ["T", "S", "GC"],
            "features": ["HTS", "HT", "PWR", "COM", "HTIN", "OTA", "LINK", "PARA", "MON"],
            "chip_platforms": ["C", "D"],
            "product_numbers": ["01", "02", "03", "04", "05"]
        }
        
        self.config_explanations = {
            "bms_voltages": "BMS保护板额定电压值（单位：V）",
            "bms_capacities": "BMS保护板额定容量值（单位：Ah）",
            "voltages": "软件特性电压值（单位：V）",
            "capacities": "软件特性容量值（单位：Ah）",
            "cell_models": "支持的电芯型号",
            "use_cases": "使用场景（T: 普通场景，S: 启动电池，GC: 高尔夫）",
            "features": "功能特征（HTS: 智能加热，HT: 加热，PWR: 保电，COM: 通信，HTIN: 薄款电池，OTA: 无线升级，LINK: 互联，PARA: 并机，MON: 屏幕监控）",
            "chip_platforms": "芯片平台（C: 中微，D: 国民）",
            "product_numbers": "产品序号（01/02等代表该平台的第几款产品）"
        }
        
    def load_config(self):
        try:
            if not self.config_path.exists():
                self.save_config(self.default_config)
                return self.default_config
            with open(self.config_path, 'r') as f:
                loaded_config = json.load(f)
                
            # 检查并补充缺失的配置项
            updated = False
            for key, value in self.default_config.items():
                if key not in loaded_config:
                    loaded_config[key] = value
                    updated = True
            
            # 更新使用场景：ST改为S
            if "ST" in loaded_config.get("use_cases", []):
                loaded_config["use_cases"] = [case if case != "ST" else "S" for case in loaded_config["use_cases"]]
                updated = True
                print("更新使用场景: ST -> S")
            
            # 更新功能特征：THIN改为HTIN
            if "THIN" in loaded_config.get("features", []):
                loaded_config["features"] = [feature if feature != "THIN" else "HTIN" for feature in loaded_config["features"]]
                updated = True
                print("更新功能特征: THIN -> HTIN")
            
            # 如果有更新，保存配置文件
            if updated:
                self.save_config(loaded_config)
                
            return loaded_config
        except Exception as e:
            QMessageBox.critical(None, "配置错误", f"无法加载配置文件: {str(e)}")
            return self.default_config

    def save_config(self, config):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            QMessageBox.critical(None, "配置错误", f"无法保存配置文件: {str(e)}")
            return False

class FirmwareNamingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager().load_config()
        self.init_ui()
        self.update_format_description()

    def init_ui(self):
        self.setWindowTitle("BMS固件命名工具 v2.0 (PyQt6)")
        self.setFixedSize(1400, 800)  # 增加窗口宽度以适应左右布局
        
        # 设置QGroupBox样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QGroupBox:hover {
                border-color: #45a049;
            }
        """)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 配置管理按钮
        config_btn = QPushButton("管理配置")
        config_btn.clicked.connect(self.show_config_dialog)
        main_layout.addWidget(config_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # 创建水平布局，左边是输入控件，右边是结果显示
        content_layout = QHBoxLayout()
        
        # 左侧输入区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # BMS特性组
        self.init_bms_info_group(left_layout)
        
        # 软件特性组
        self.init_software_info_group(left_layout)
        
        # 芯片平台和产品序号组
        self.init_chip_product_group(left_layout)
        
        # 功能特征组
        self.init_feature_group(left_layout)
        
        # 版本信息组
        self.init_version_group(left_layout)
        
        # 生成按钮
        generate_btn = QPushButton("生成文件名")
        generate_btn.clicked.connect(self.generate_names)
        left_layout.addWidget(generate_btn)
        
        # 添加弹性空间，让输入控件紧凑排列
        left_layout.addStretch()
        
        # 右侧结果显示区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 结果显示
        right_layout.addWidget(QLabel("📊 生成结果:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(300)
        # 设置等宽字体
        font = QFont("Consolas", 10)  # Windows上的等宽字体
        if not font.exactMatch():
            font = QFont("Courier New", 10)  # 备用等宽字体
        if not font.exactMatch():
            font = QFont("monospace", 10)  # Linux/Mac上的等宽字体
        self.result_text.setFont(font)
        right_layout.addWidget(self.result_text)

        # 格式说明
        right_layout.addWidget(QLabel("📖 命名格式说明:"))
        self.format_text = QTextEdit()
        self.format_text.setReadOnly(True)
        self.format_text.setMinimumHeight(200)
        right_layout.addWidget(self.format_text)
        
        # 设置左右两侧的比例 (输入区域:结果区域 = 1:1)
        content_layout.addWidget(left_widget, 1)
        content_layout.addWidget(right_widget, 1)
        
        main_layout.addLayout(content_layout)

    def init_bms_info_group(self, parent_layout):
        group = QGroupBox("BMS特性")
        layout = QVBoxLayout()

        # BMS特性启用checkbox
        self.bms_enable_checkbox = QCheckBox("BMS的电压容量和软件容量不同")
        self.bms_enable_checkbox.stateChanged.connect(self.on_bms_enable_changed)
        layout.addWidget(self.bms_enable_checkbox)

        # BMS电压和容量选择容器
        self.bms_controls_container = QWidget()
        bms_controls_layout = QHBoxLayout(self.bms_controls_container)
        
        # BMS电压选择
        self.bms_voltage_container = self.create_combo("BMS电压(V)", self.config["bms_voltages"])
        # BMS容量选择
        self.bms_capacity_container = self.create_combo("BMS容量(Ah)", self.config["bms_capacities"])

        bms_controls_layout.addWidget(self.bms_voltage_container)
        bms_controls_layout.addWidget(self.bms_capacity_container)
        bms_controls_layout.addStretch()  # 添加弹性空间
        
        layout.addWidget(self.bms_controls_container)
        
        # 默认隐藏BMS控件
        self.bms_controls_container.setVisible(False)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def init_software_info_group(self, parent_layout):
        group = QGroupBox("软件特性")
        layout = QHBoxLayout()

        # 使用场景
        self.use_case_container = self.create_combo("使用场景", self.config["use_cases"])
        # 电压选择
        self.voltage_container = self.create_combo("电压(V)", self.config["voltages"])
        # 容量选择
        self.capacity_container = self.create_combo("容量(Ah)", self.config["capacities"])
        # 电芯型号
        self.cell_container = self.create_combo("电芯型号", self.config["cell_models"])

        layout.addWidget(self.use_case_container)
        layout.addWidget(self.voltage_container)
        layout.addWidget(self.capacity_container)
        layout.addWidget(self.cell_container)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_combo(self, label, items):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel(label))
        combo = QComboBox()
        combo.addItems(items)
        layout.addWidget(combo)
        return container

    def init_chip_product_group(self, parent_layout):
        group = QGroupBox("芯片平台和产品序号")
        layout = QHBoxLayout()

        # 芯片平台选择（互斥）
        chip_container = QWidget()
        chip_layout = QVBoxLayout(chip_container)
        chip_layout.addWidget(QLabel("芯片平台"))
        
        self.chip_button_group = QButtonGroup()
        chip_radio_layout = QHBoxLayout()
        
        self.chip_radios = {}
        for platform in self.config["chip_platforms"]:
            radio = QRadioButton(platform)
            self.chip_radios[platform] = radio
            self.chip_button_group.addButton(radio)
            chip_radio_layout.addWidget(radio)
        
        # 默认选择第一个
        if self.config["chip_platforms"]:
            self.chip_radios[self.config["chip_platforms"][0]].setChecked(True)
        
        chip_layout.addLayout(chip_radio_layout)

        # 产品序号选择
        self.product_container = self.create_combo("产品序号", self.config["product_numbers"])

        layout.addWidget(chip_container)
        layout.addWidget(self.product_container)
        layout.addStretch()  # 添加弹性空间
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def init_feature_group(self, parent_layout):
        self.group = QGroupBox("功能特征（最多6个，HTS和HT互斥）")
        layout = QHBoxLayout()
        
        # 设置更紧密的间距
        layout.setSpacing(5)  # 设置控件之间的间距为5像素
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边距
        
        self.feature_checks = []
        for feature in self.config["features"]:
            cb = QCheckBox(feature)
            cb.stateChanged.connect(self.on_feature_changed)
            layout.addWidget(cb)
            self.feature_checks.append(cb)
        
        # 添加弹簧以使复选框靠左排列
        layout.addStretch()
        
        self.group.setLayout(layout)
        parent_layout.addWidget(self.group)

    def init_version_group(self, parent_layout):
        group = QGroupBox("版本信息")
        layout = QHBoxLayout()

        # 主版本
        self.main_ver_spin = QSpinBox()
        self.main_ver_spin.setRange(0, 99)
        self.main_ver_spin.setValue(1)
        
        # 次版本
        self.rev_ver_spin = QSpinBox()
        self.rev_ver_spin.setRange(0, 99)
        
        # 修订号
        self.fix_ver_spin = QSpinBox()
        self.fix_ver_spin.setRange(0, 99)
        
        # 日期
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)

        layout.addLayout(self.create_version_item("主版本", self.main_ver_spin))
        layout.addLayout(self.create_version_item("次版本", self.rev_ver_spin))
        layout.addLayout(self.create_version_item("修订号", self.fix_ver_spin))
        layout.addLayout(self.create_version_item("发布日期", self.date_edit))
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_version_item(self, label, widget):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)
        return layout

    def show_config_dialog(self):
        dialog = ConfigDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_updated_config()
            self.refresh_ui()

    def refresh_ui(self):
        # 更新BMS特性下拉框
        self.bms_voltage_container.findChild(QComboBox).clear()
        self.bms_voltage_container.findChild(QComboBox).addItems(self.config["bms_voltages"])
        self.bms_capacity_container.findChild(QComboBox).clear()
        self.bms_capacity_container.findChild(QComboBox).addItems(self.config["bms_capacities"])
        # 重置BMS特性checkbox状态
        self.bms_enable_checkbox.setChecked(False)
        self.bms_controls_container.setVisible(False)
        
        # 更新软件特性下拉框
        self.voltage_container.findChild(QComboBox).clear()
        self.voltage_container.findChild(QComboBox).addItems(self.config["voltages"])
        self.capacity_container.findChild(QComboBox).clear()
        self.capacity_container.findChild(QComboBox).addItems(self.config["capacities"])
        self.cell_container.findChild(QComboBox).clear()
        self.cell_container.findChild(QComboBox).addItems(self.config["cell_models"])
        self.use_case_container.findChild(QComboBox).clear()
        self.use_case_container.findChild(QComboBox).addItems(self.config["use_cases"])
        
        # 更新产品序号下拉框
        self.product_container.findChild(QComboBox).clear()
        self.product_container.findChild(QComboBox).addItems(self.config["product_numbers"])
        
        # 更新芯片平台单选按钮
        for radio in self.chip_radios.values():
            radio.deleteLater()
        self.chip_radios.clear()
        
        # 重新创建芯片平台单选按钮
        for platform in self.config["chip_platforms"]:
            radio = QRadioButton(platform)
            self.chip_radios[platform] = radio
            self.chip_button_group.addButton(radio)
        
        # 默认选择第一个
        if self.config["chip_platforms"]:
            self.chip_radios[self.config["chip_platforms"][0]].setChecked(True)
        
        # 更新功能特征复选框
        for cb in self.feature_checks:
            cb.deleteLater()
        self.feature_checks.clear()
        
        # 查找 QGroupBox内的QCheckBox，并更新
        feature_group = self.group
        layout = feature_group.layout()
        
        # 移除所有现有的控件（除了弹簧）
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 重新添加复选框
        for feature in self.config["features"]:
            cb = QCheckBox(feature)
            layout.addWidget(cb)
            self.feature_checks.append(cb)
        
        # 重新添加弹簧以使复选框靠左排列
        layout.addStretch()

    def on_bms_enable_changed(self):
        """BMS特性启用状态变化时的处理"""
        is_enabled = self.bms_enable_checkbox.isChecked()
        self.bms_controls_container.setVisible(is_enabled)

    def on_feature_changed(self):
        """功能特征变化时的处理"""
        selected_features = []
        for cb in self.feature_checks:
            if cb.isChecked():
                selected_features.append(cb.text())
        
        # 检查HTS和HT互斥
        if "HTS" in selected_features and "HT" in selected_features:
            # 找到最后被选中的，保留它，取消另一个
            sender = self.sender()
            if sender.text() == "HTS":
                # 取消HT
                for cb in self.feature_checks:
                    if cb.text() == "HT":
                        cb.setChecked(False)
                        break
            elif sender.text() == "HT":
                # 取消HTS
                for cb in self.feature_checks:
                    if cb.text() == "HTS":
                        cb.setChecked(False)
                        break
        
        # 检查功能特征数量限制（最多6个）
        selected_count = sum(1 for cb in self.feature_checks if cb.isChecked())
        if selected_count > 6:
            # 取消最后选中的
            sender = self.sender()
            sender.setChecked(False)
            QMessageBox.warning(self, "功能特征限制", "功能特征最多只能选择6个！")

    def get_selected_features(self):
        """获取选中的功能特征并按优先级排序"""
        features = []
        for feature in self.feature_checks:
            if feature.isChecked():
                features.append(feature.text())

        # 按优先级排序，如果功能特征不在优先级列表中，则放在最后
        priority_order = ["HTS", "HT", "PWR", "COM", "HTIN", "OTA", "LINK", "PARA", "MON"]
        def get_priority(feature):
            try:
                return priority_order.index(feature)
            except ValueError:
                # 如果不在优先级列表中，返回一个大的数值，使其排在最后
                return len(priority_order)
        
        return sorted(features, key=get_priority)
    
    def generate_names(self):
        """生成各种固件文件名"""
        # 获取BMS特性启用状态
        bms_enabled = self.bms_enable_checkbox.isChecked()
        
        # 获取BMS特性参数（始终获取，但只在启用时使用）
        bms_voltage = self.bms_voltage_container.findChild(QComboBox).currentText()
        bms_capacity = self.bms_capacity_container.findChild(QComboBox).currentText()
        
        # 获取软件特性参数
        voltage = self.voltage_container.findChild(QComboBox).currentText()
        capacity = self.capacity_container.findChild(QComboBox).currentText()
        cell_model = self.cell_container.findChild(QComboBox).currentText()
        use_case = self.use_case_container.findChild(QComboBox).currentText()
        
        # 获取芯片平台
        chip_platform = ""
        for platform, radio in self.chip_radios.items():
            if radio.isChecked():
                chip_platform = platform
                break
        
        # 获取产品序号
        product_number = self.product_container.findChild(QComboBox).currentText()
        
        # 获取功能特征
        features = self.get_selected_features()
        feature_str = "-".join(features) if features else ""
        
        # 获取版本信息
        main_ver = self.main_ver_spin.value()
        rev_ver = self.rev_ver_spin.value()
        fix_ver = self.fix_ver_spin.value()
        version_str = f"V{main_ver}_{rev_ver}_{fix_ver}"
        
        # 获取日期
        date = self.date_edit.date().toString("yyyyMMdd")
        
        # 生成BMS特性标识（始终包含BMS，但电压容量根据checkbox决定）
        bms_spec = f"BMS{bms_voltage}{bms_capacity}" if bms_enabled else "BMS"
        
        # 生成软件特性标识
        software_spec = f"{use_case}{voltage}{capacity}"
        
        # 生成唯一码
        unique_code = f"{chip_platform}{product_number}"
        
        # 生成软件版本定义 (ver_FW)
        if feature_str:
            fw_version = f"{software_spec}-{feature_str}-{unique_code}_V{main_ver}_{rev_ver}"
        else:
            fw_version = f"{software_spec}-{unique_code}_V{main_ver}_{rev_ver}"
        
        # 判断是否包含电芯型号
        include_cell_model = cell_model != "略"
        
        # 生成各种文件名 - 按照新规范
        # BOOT命名: IAP-【芯片平台】_V【主版本】_【次版本】_【修订号】_【日期】.bin
        iap_name = f"IAP-{chip_platform}_{version_str}_{date}.bin"
        
        # 始终包含BMS特性标识
        if include_cell_model:
            if feature_str:
                # 升级固件: APP-【BMS特性】-【使用场景】【电压】【容量】-【功能特征】-【电芯型号】-OTA-【芯片平台】【产品序号】_V【主版本】_【次版本】_【修订号】_【日期】.hex
                app_name = f"APP-{bms_spec}-{software_spec}-{feature_str}-{cell_model}-OTA-{unique_code}_{version_str}_{date}.hex"
                # 完整固件: IAP+APP-【BMS特性】-【使用场景】【电压】【容量】-【功能特征】-【电芯型号】-【芯片平台】【产品序号】_V【主版本】_【次版本】_【修订号】_【日期】.hex
                full_name = f"IAP+APP-{bms_spec}-{software_spec}-{feature_str}-{cell_model}-{unique_code}_{version_str}_{date}.hex"
            else:
                app_name = f"APP-{bms_spec}-{software_spec}-{cell_model}-OTA-{unique_code}_{version_str}_{date}.hex"
                full_name = f"IAP+APP-{bms_spec}-{software_spec}-{cell_model}-{unique_code}_{version_str}_{date}.hex"
        else:
            if feature_str:
                app_name = f"APP-{bms_spec}-{software_spec}-{feature_str}-OTA-{unique_code}_{version_str}_{date}.hex"
                full_name = f"IAP+APP-{bms_spec}-{software_spec}-{feature_str}-{unique_code}_{version_str}_{date}.hex"
            else:
                app_name = f"APP-{bms_spec}-{software_spec}-OTA-{unique_code}_{version_str}_{date}.hex"
                full_name = f"IAP+APP-{bms_spec}-{software_spec}-{unique_code}_{version_str}_{date}.hex"
        
        # 显示结果
        result = ""
        # 版本定义部分
        result += "📋 版本定义:\n"
        result += "─" * 50 + "\n"
        result += f"   软件版本 (ver_FW): {fw_version}\n\n"
        
        # 文件名生成部分
        result += "📁 生成的文件名:\n"
        result += "─" * 50 + "\n"
        result += f"   🔧 Boot命名:    {iap_name}\n"
        result += f"   📦 升级固件:    {app_name}\n"
        result += f"   🔄 完整固件:    {full_name}\n\n"
        
        # 配置信息部分
        result += "⚙️ 当前配置:\n"
        result += "─" * 50 + "\n"
        if bms_enabled:
            result += f"   BMS特性: {bms_voltage}V {bms_capacity}Ah → 文件名显示: BMS{bms_voltage}{bms_capacity}\n"
        else:
            result += f"   BMS特性: {bms_voltage}V {bms_capacity}Ah → 文件名显示: BMS\n"
        result += f"   软件特性: {use_case} {voltage}V {capacity}Ah\n"
        result += f"   电芯型号: {cell_model if cell_model != '略' else '无'}\n"
        result += f"   芯片平台: {chip_platform}    产品序号: {product_number}\n"
        result += f"   功能特征: {feature_str if feature_str else '无'}\n"
        result += f"   版本信息: V{main_ver}.{rev_ver}.{fix_ver}    发布日期: {date}\n"
        result += "=" * 80
        
        self.result_text.setPlainText(result)
    
    def update_format_description(self):
        """更新格式说明"""
        description = """=== BMS固件命名规范说明 ===

【固件类型】-【BMS特性】-【软件特性】-【软件版本】
注：BMS特性始终包含，可通过checkbox控制显示具体电压容量还是只显示"BMS"标识

一、版本定义:
软件版本 (ver_FW): 【使用场景】【电压】【容量】-【功能特征】-【芯片平台】【产品序号】_V【主版本】_【次版本】
示例: "T12100-HTS-HT-D01_V1_7"
无功能特征时: "T12100-D01_V1_7"

二、固件类型:
1. Boot命名 (IAP):
   IAP-【芯片平台】_V【主版本】_【次版本】_【修订号】_【日期】.bin
   示例: "IAP-D_V1_0_0_20250704.bin"

2. 升级固件 (APP):
   APP-【BMS特性】-【使用场景】【电压】【容量】-【功能特征】-OTA-【芯片平台】【产品序号】_V【主版本】_【次版本】_【修订号】_【日期】.hex
   示例: "APP-BMS12100-T12200-HTS-OTA-C02_V1_0_0_20250704.hex"
   BMS特性checkbox未勾选时: "APP-BMS-T12100-HTS-HT-G_N_H10-OTA-C02_V1_0_0_20250704.hex"

3. 完整固件 (IAP+APP):
   IAP+APP-【BMS特性】-【使用场景】【电压】【容量】-【功能特征】-【芯片平台】【产品序号】_V【主版本】_【次版本】_【修订号】_【日期】.hex
   示例: "IAP+APP-BMS12100-T12200-HTS-HT-C02_V1_0_0_20250704.hex"
   无功能特征时: "IAP+APP-BMS-T12100-G_N_H10-D01_V1_0_0_20250704.hex"

三、参数说明:
1. 使用场景: T(普通场景), S(启动电池), GC(高尔夫)
2. BMS特性: 电压(12/24/36/48V), 容量(50/100/140/165/200/300Ah)
3. 软件特性: 电压(12/24/36/48V), 容量(50/100/140/165/200/300Ah)
4. 功能特征: HTS(智能加热), HT(加热), PWR(保电), COM(通信), HTIN(薄款电池), OTA(无线升级), LINK(互联), PARA(并机), MON(屏幕监控)
5. 芯片平台: C(中微), D(国民)
6. 产品序号: 01/02/03/04/05...

四、重要规则:
- 智能加热HTS和充电加热HT互斥，不能同时存在
- 功能特征最多6个，超过要去掉不重要的
- 电芯型号选择"略"时不包含在文件名中
- BMS特性可通过checkbox控制显示方式：
  ✓ 未勾选：固件名只显示"BMS"标识
  ✓ 勾选：固件名显示具体的BMS电压容量值（如"BMS12100"）
- BMS特性始终在文件名中显示，电压容量选择框始终可见
- 固件类型内用+连接，表示是一个整体
- 软件特性内用-连接，表示各种功能
- 软件版本内用_连接，表示是一个整体
- 三者之间用-连接
- 日期格式: YYYYMMDD (如20250704)"""
        
        self.format_text.setPlainText(description)

class ConfigDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理配置")
        self.setFixedSize(600, 400)
        
        self.original_config = config
        self.current_config = json.loads(json.dumps(config))  # Deep copy
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 配置项编辑区域
        self.tabs = QTabWidget()
        
        # BMS特性配置
        self.bms_voltages_edit = self.create_list_editor("BMS电压选项", self.current_config["bms_voltages"])
        self.bms_capacities_edit = self.create_list_editor("BMS容量选项", self.current_config["bms_capacities"])
        # 软件特性配置
        self.voltages_edit = self.create_list_editor("软件电压选项", self.current_config["voltages"])
        self.capacities_edit = self.create_list_editor("软件容量选项", self.current_config["capacities"])
        # 其他配置
        self.cell_models_edit = self.create_list_editor("电芯型号", self.current_config["cell_models"])
        self.use_cases_edit = self.create_list_editor("使用场景", self.current_config["use_cases"])
        self.features_edit = self.create_list_editor("功能特征", self.current_config["features"])
        self.chip_platforms_edit = self.create_list_editor("芯片平台", self.current_config["chip_platforms"])
        self.product_numbers_edit = self.create_list_editor("产品序号", self.current_config["product_numbers"])
        
        self.tabs.addTab(self.bms_voltages_edit, "BMS电压")
        self.tabs.addTab(self.bms_capacities_edit, "BMS容量")
        self.tabs.addTab(self.voltages_edit, "软件电压")
        self.tabs.addTab(self.capacities_edit, "软件容量")
        self.tabs.addTab(self.cell_models_edit, "电芯型号")
        self.tabs.addTab(self.use_cases_edit, "使用场景")
        self.tabs.addTab(self.features_edit, "功能特征")
        self.tabs.addTab(self.chip_platforms_edit, "芯片平台")
        self.tabs.addTab(self.product_numbers_edit, "产品序号")
        
        # 按钮组
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addWidget(self.tabs)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def create_list_editor(self, title, items):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        text_edit = QTextEdit()
        text_edit.setPlainText("\n".join(items))
        
        layout.addWidget(QLabel(f"{title} (每行一个选项)"))
        layout.addWidget(text_edit)
        
        return widget
    
    def get_updated_config(self):
        return {
            "bms_voltages": self.bms_voltages_edit.findChild(QTextEdit).toPlainText().split(),
            "bms_capacities": self.bms_capacities_edit.findChild(QTextEdit).toPlainText().split(),
            "voltages": self.voltages_edit.findChild(QTextEdit).toPlainText().split(),
            "capacities": self.capacities_edit.findChild(QTextEdit).toPlainText().split(),
            "cell_models": self.cell_models_edit.findChild(QTextEdit).toPlainText().split(),
            "use_cases": self.use_cases_edit.findChild(QTextEdit).toPlainText().split(),
            "features": self.features_edit.findChild(QTextEdit).toPlainText().split(),
            "chip_platforms": self.chip_platforms_edit.findChild(QTextEdit).toPlainText().split(),
            "product_numbers": self.product_numbers_edit.findChild(QTextEdit).toPlainText().split()
        }
    
    def save_config(self):
        new_config = self.get_updated_config()
        if ConfigManager().save_config(new_config):
            self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FirmwareNamingTool()
    window.show()
    sys.exit(app.exec())