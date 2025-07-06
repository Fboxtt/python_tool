import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
                            QTextEdit, QGroupBox, QSpinBox, QDateEdit, QMessageBox, QDialog, QTabWidget, QRadioButton, QButtonGroup)
from PyQt6.QtCore import QDate, Qt

CONFIG_FILE = "bms_config.json"

class ConfigManager:
    def __init__(self):
        self.config_path = Path(CONFIG_FILE)
        self.default_config = {
            "voltages": ["12", "24", "36", "48"],
            "capacities": ["100", "120", "140", "160", "200", "240"],
            "cell_models": ["略", "G_N_H10", "L_F_H20", "P_C_H50", "A_K_H100"],
            "use_cases": ["T", "ST", "GC"],
            "features": ["HTS", "HT", "PWR", "COM", "THIN"],
            "chip_platforms": ["C", "D"],
            "product_numbers": ["01", "02", "03", "04", "05"]
        }
        
        self.config_explanations = {
            "voltages": "支持的电压值（单位：V）",
            "capacities": "支持的容量值（单位：Ah）",
            "cell_models": "支持的电芯型号",
            "use_cases": "支持的使用场景（T: 通用，ST: 高温，GC: 工业）",
            "features": "支持的功能特征（HTS: 高温保护，HT: 高功率，PWR: 电源管理，COM: 通信，THIN: 薄型设计）",
            "chip_platforms": "芯片平台（C/D代表不同芯片）",
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
        self.setFixedSize(1000, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 配置管理按钮
        config_btn = QPushButton("管理配置")
        config_btn.clicked.connect(self.show_config_dialog)
        main_layout.addWidget(config_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # 基本信息组
        self.init_basic_info_group(main_layout)
        
        # 芯片平台和产品序号组
        self.init_chip_product_group(main_layout)
        
        # 功能特征组
        self.init_feature_group(main_layout)
        
        # 版本信息组
        self.init_version_group(main_layout)
        
        # 生成按钮
        generate_btn = QPushButton("生成文件名")
        generate_btn.clicked.connect(self.generate_names)
        main_layout.addWidget(generate_btn)

        # 结果显示
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        main_layout.addWidget(QLabel("生成结果:"))
        main_layout.addWidget(self.result_text)

        # 格式说明
        self.format_text = QTextEdit()
        self.format_text.setReadOnly(True)
        main_layout.addWidget(QLabel("命名格式说明:"))
        main_layout.addWidget(self.format_text)

    def init_basic_info_group(self, parent_layout):
        group = QGroupBox("基本信息")
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
        self.group = QGroupBox("func_feature")
        layout = QHBoxLayout()
        
        self.feature_checks = []
        for feature in self.config["features"]:
            cb = QCheckBox(feature)
            layout.addWidget(cb)
            self.feature_checks.append(cb)
        
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
        # 更新基本信息下拉框
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
        for feature in self.config["features"]:
            cb = QCheckBox(feature)
            layout.addWidget(cb)
            self.feature_checks.append(cb)

    def get_selected_features(self):
        """获取选中的功能特征并按优先级排序"""
        features = []
        for feature in self.feature_checks:
            if feature.isChecked():
                features.append(feature.text())

        # 按优先级排序
        priority_order = ["HTS", "HT", "PWR", "COM", "THIN"]
        return sorted(features, key=lambda x: priority_order.index(x))
    
    def generate_names(self):
        """生成各种固件文件名"""
        # 获取基本参数
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
        
        # 生成基础产品标识：T12100 
        base_product = f"{use_case}{voltage}{capacity}"
        
        # 构建完整的产品标识，包含功能特征
        if feature_str:
            # 有功能特征：T12100-HTS_HT
            full_product = f"{base_product}-{feature_str}"
        else:
            # 无功能特征：T12100
            full_product = base_product
        
        # 生成硬件版本和固件版本
        if feature_str:
            hw_version = f"{full_product}-{chip_platform}{product_number}_V{main_ver}_{rev_ver}"
            fw_version = f"{full_product}-{chip_platform}{product_number}_V{main_ver}_{rev_ver}"
        else:
            hw_version = f"{full_product}-{chip_platform}{product_number}_V{main_ver}_{rev_ver}"
            fw_version = f"{full_product}-{chip_platform}{product_number}_V{main_ver}_{rev_ver}"
        
        # 判断是否包含电芯型号
        include_cell_model = cell_model != "略"
        
        # 生成各种文件名 - 新格式（芯片平台、版本字符串和日期之间用下划线连接）
        if include_cell_model:
            if feature_str:
                # 有功能特征+有电芯型号：FULL_BMS-T12100-HTS-HT-G_N_H10-C02_V1_0_0_20250704.hex
                no_ota_name     = f"    FULL_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                app_name        = f"     APP_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                iap_name        = f"     IAP_BMS-{full_product}-{chip_platform}_{version_str}_{date}.bin"
                iap_full_name   = f"FULL_OTA_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.bin"
            else:
                # 无功能特征+有电芯型号：FULL_BMS-T12100-G_N_H10-D01_V1_0_0_20250704.hex
                no_ota_name     = f"    FULL_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                app_name        = f"     APP_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                iap_name        = f"     IAP_BMS-{full_product}-{chip_platform}_{version_str}_{date}.bin"
                iap_full_name   = f"FULL_OTA_BMS-{full_product}-{cell_model}-{chip_platform}{product_number}_{version_str}_{date}.bin"
        else:
            if feature_str:
                # 有功能特征+无电芯型号：FULL_BMS-T12100-HTS-HT-C02_V1_0_0_20250704.hex
                no_ota_name     = f"    FULL_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                app_name        = f"     APP_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                iap_name        = f"     IAP_BMS-{full_product}-{chip_platform}_{version_str}_{date}.bin"
                iap_full_name   = f"FULL_OTA_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.bin"
            else:
                # 无功能特征+无电芯型号：FULL_BMS-T12100-D01_V1_0_0_20250704.hex
                no_ota_name     = f"    FULL_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                app_name        = f"     APP_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.hex"
                iap_name        = f"     IAP_BMS-{full_product}-{chip_platform}_{version_str}_{date}.bin"
                iap_full_name   = f"FULL_OTA_BMS-{full_product}-{chip_platform}{product_number}_{version_str}_{date}.bin"
        
        # 显示结果
        result = f"硬件版本定义 (ver_HW): {hw_version}\n"
        result += f"固件版本定义 (ver_FW): {fw_version}\n\n"
        result += "生成的文件名:\n"
        result += f" boot命名: {iap_name}\n"
        result += f" 升级包:   {app_name}\n"
        result += f" 完整包:   {iap_full_name}\n\n"
        result += f" 无OTA固件:{no_ota_name}"
        
        self.result_text.setPlainText(result)
    
    def update_format_description(self):
        """更新格式说明"""
        description = """=== BMS固件命名规范说明 ===

1. 硬件版本定义 (ver_HW):
   [使用场景][电压V][容量Ah]-[功能特征]-[芯片平台][产品序号]_V[主版本]_[次版本]
   示例: "T12100-HTS-HT-D01_V1_5"
   无功能特征时: "T12100-D01_V1_5"

2. 固件版本定义 (ver_FW):
   [使用场景][电压][容量]-[功能特征]-[芯片平台][产品序号]_V[主版本]_[次版本]
   示例: "T12100-HTS-HT-D01_V1_7"
   无功能特征时: "T12100-D01_V1_7"

3. 无OTA固件 (FULL):
   有电芯型号: FULL_BMS-[使用场景][电压][容量]-[功能特征]-[电芯型号]-[芯片平台][产品序号]_V[主版本]_[次版本]_[修订号]_[日期].hex
   示例: "FULL_BMS-T12100-HTS-HT-G_N_H10-C02_V1_0_0_20250704.hex"
   无电芯型号: FULL_BMS-[使用场景][电压][容量]-[功能特征]-[芯片平台][产品序号]_V[主版本]_[次版本]_[修订号]_[日期].hex
   示例: "FULL_BMS-T12100-HTS-HT-C02_V1_0_0_20250704.hex"
   无功能特征时: "FULL_BMS-T12100-G_N_H10-D01_V1_0_0_20250704.hex"

4. 升级包 (APP):
   格式与无OTA固件相同，前缀为APP_BMS
   示例: "APP_BMS-T12100-HTS-HT-G_N_H10-C02_V1_0_0_20250704.hex"

5. Boot命名 (IAP):
   IAP_BMS-[使用场景][电压][容量]-[功能特征]-[芯片平台]_V[主版本]_[次版本]_[修订号]_[日期].bin
   示例: "IAP_BMS-T12100-HTS-HT-D01_V1_0_0_20250704.bin"

6. 完整包 (FULL_OTA):
   有电芯型号: FULL_OTA_BMS-[使用场景][电压][容量]-[功能特征]-[电芯型号]-[芯片平台][产品序号]_V[主版本]_[次版本]_[修订号]_[日期].bin
   示例: "FULL_OTA_BMS-T12100-HTS-HT-G_N_H10-C02_V1_0_0_20250704.bin"
   无电芯型号: FULL_OTA_BMS-[使用场景][电压][容量]-[功能特征]-[芯片平台][产品序号]_V[主版本]_[次版本]_[修订号]_[日期].bin
   示例: "FULL_OTA_BMS-T12100-HTS-HT-C02_V1_0_0_20250704.bin"

重要说明:
- 电芯型号: 选择"略"时不包含在文件名中
- 芯片平台: C/D (互斥选择)
- 产品序号: 01/02/03... (该平台的第几款产品)
- 功能特征优先级: HTS > HT > PWR > COM > THIN
- 功能特征分隔符: - (连字符)
- 版本号格式: V[主版本]_[次版本]_[修订号] (用下划线连接)
- 硬件/固件版本: V[主版本]_[次版本] (用下划线连接)
- FULL_OTA_BMS: 固件类型标识符，和后面内容用 - 连接
- 芯片平台、版本字符串和日期: 用 _ 连接
- 其他地方: 用 - 连接
- 日期格式: YYYYMMDD (如20250704)"""
        
        self.format_text.setPlainText(description)
    # 以下 generate_names 和 update_format_description 方法与之前版本相同
    # 由于篇幅限制，此处省略，保持原有逻辑不变

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
        
        # 电压配置
        self.voltages_edit = self.create_list_editor("电压选项", self.current_config["voltages"])
        # 容量配置
        self.capacities_edit = self.create_list_editor("容量选项", self.current_config["capacities"])
        # 电芯型号
        self.cell_models_edit = self.create_list_editor("电芯型号", self.current_config["cell_models"])
        # 使用场景
        self.use_cases_edit = self.create_list_editor("使用场景", self.current_config["use_cases"])
        # 功能特征
        self.features_edit = self.create_list_editor("功能特征", self.current_config["features"])
        # 芯片平台
        self.chip_platforms_edit = self.create_list_editor("芯片平台", self.current_config["chip_platforms"])
        # 产品序号
        self.product_numbers_edit = self.create_list_editor("产品序号", self.current_config["product_numbers"])
        
        self.tabs.addTab(self.voltages_edit, "电压")
        self.tabs.addTab(self.capacities_edit, "容量")
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