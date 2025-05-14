import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
                            QTextEdit, QGroupBox, QSpinBox, QDateEdit, QMessageBox, QDialog, QTabWidget)
from PyQt6.QtCore import QDate, Qt

CONFIG_FILE = "bms_config.json"

class ConfigManager:
    def __init__(self):
        self.config_path = Path(CONFIG_FILE)
        self.default_config = {
            "voltages": ["12", "24", "36", "48"],
            "capacities": ["100", "120", "140", "160", "200", "240"],
            "cell_models": ["G_N_H10", "L_F_H20", "P_C_H50", "A_K_H100"],
            "product_lines": ["T", "ST", "GC"],
            "features": ["HTS", "HT", "PWR", "COM"]
        }
        
    def load_config(self):
        try:
            if not self.config_path.exists():
                self.save_config(self.default_config)
                return self.default_config
            with open(self.config_path, 'r') as f:
                return json.load(f)
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

        # 电压选择
        self.voltage_container = self.create_combo("电压(V)", self.config["voltages"])
        # 容量选择
        self.capacity_container = self.create_combo("容量(Ah)", self.config["capacities"])
        # 电芯型号
        self.cell_container = self.create_combo("电芯型号", self.config["cell_models"])
        # 产品线
        self.product_line_container = self.create_combo("产品线", self.config["product_lines"])

        layout.addWidget(self.voltage_container)
        layout.addWidget(self.capacity_container)
        layout.addWidget(self.cell_container)
        layout.addWidget(self.product_line_container)
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
        self.product_line_container.findChild(QComboBox).clear()
        self.product_line_container.findChild(QComboBox).addItems(self.config["product_lines"])
        
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
        for i, feature in enumerate(self.config["features"]):
            if self.feature_checks[i].isChecked():
                features.append(feature)

        # 按优先级排序
        priority_order = ["HTS", "HT", "PWR", "COM"]
        return sorted(features, key=lambda x: priority_order.index(x))
    
    def generate_names(self):
        """生成各种固件文件名"""
        # 获取基本参数
        voltage = self.voltage_container.findChild(QComboBox).currentText()
        capacity = self.capacity_container.findChild(QComboBox).currentText()
        cell_model = self.cell_container.findChild(QComboBox).currentText()
        product_line = self.product_line_container.findChild(QComboBox).currentText()
        
        # 获取功能特征
        features = self.get_selected_features()
        feature_str = "-".join(features) if features else "BASE"
        
        # 获取版本信息
        main_ver = self.main_ver_spin.value()
        rev_ver = self.rev_ver_spin.value()
        fix_ver = self.fix_ver_spin.value()
        version_str = f"V{main_ver}-{rev_ver}-{fix_ver}"
        
        # 获取日期
        date = self.date_edit.date().toString("yyyyMMdd")
        
        # 生成硬件版本
        hw_version = f"{voltage}{capacity}-{feature_str}-V{main_ver}.{rev_ver}"
        
        # 生成固件版本
        fw_version = f"{product_line}{voltage}{capacity}-{feature_str}-V{main_ver}.{rev_ver}.{fix_ver}"
        
        # 生成各种文件名
        app_name = f"APP_APT-BMS-{voltage}{capacity}-{cell_model}_{feature_str}_{version_str}_{date}.hex"
        iap_name = f"IAP_APP-BMS-{voltage}{capacity}_{feature_str}_{version_str}_{date}.bin"
        iap_full_name = f"IAP_APP-BMS-{voltage}{capacity}_{feature_str}_FULL_{version_str}_{date}.bin"
        
        # 显示结果
        result = f"硬件版本定义 (ver_HW): {hw_version}\n"
        result += f"固件版本定义 (ver_FW): {fw_version}\n\n"
        result += "生成的文件名:\n"
        result += f"1. 主应用固件: {app_name}\n"
        result += f"2. 增量升级包: {iap_name}\n"
        result += f"3. 完整升级包: {iap_full_name}"
        
        self.result_text.setPlainText(result)
    
    def update_format_description(self):
        """更新格式说明"""
        description = """=== BMS固件命名规范说明 ===

1. 硬件版本定义 (ver_HW):
   [电压V][容量Ah]-[功能特征]-V[主版本].[次版本]
   示例: "12200-HTS-HT-V1.5"

2. 固件版本定义 (ver_FW):
   [产品线][电压][容量]-[功能特征]-V[主版本].[次版本].[修订号]
   示例: "T12200-HTS-HT-V1.7.0"

3. 主应用固件 (APP):
   APP_APT-BMS-[电压][容量]-[电芯型号]_[功能特征]_V[主版本]-[次版本]-[修订号]_[日期].hex
   示例: "APP_APT-BMS-12200-G_N_H10_HTS-HT_V1-7-0_20240624.hex"

4. 增量升级包 (IAP):
   IAP_APP-BMS-[电压][容量]_[功能特征]_V[主版本]-[次版本]-[修订号]_[日期].bin
   示例: "IAP_APP-BMS-12200_HTS-HT_V1-7-0_20240624.bin"

5. 完整升级包 (IAP_APP):
   IAP_APP-BMS-[电压][容量]_[功能特征]_FULL_V[主版本]-[次版本]-[修订号]_[日期].bin
   示例: "IAP_APP-BMS-12200_HTS-HT_FULL_V1-7-0_20240624.bin"

功能特征优先级: HTS > HT > PWR > COM
日期格式: YYYYMMDD (如20240624)"""
        
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
        # 产品线
        self.product_lines_edit = self.create_list_editor("产品线", self.current_config["product_lines"])
        # 功能特征
        self.features_edit = self.create_list_editor("功能特征", self.current_config["features"])
        
        self.tabs.addTab(self.voltages_edit, "电压")
        self.tabs.addTab(self.capacities_edit, "容量")
        self.tabs.addTab(self.cell_models_edit, "电芯型号")
        self.tabs.addTab(self.product_lines_edit, "产品线")
        self.tabs.addTab(self.features_edit, "功能特征")
        
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
            "product_lines": self.product_lines_edit.findChild(QTextEdit).toPlainText().split(),
            "features": self.features_edit.findChild(QTextEdit).toPlainText().split()
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