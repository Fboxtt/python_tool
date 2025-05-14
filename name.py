import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton,
                            QTextEdit, QGroupBox, QSpinBox, QDateEdit)
from PyQt6.QtCore import QDate

class FirmwareNamingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMS固件命名工具 v1.0")
        self.setFixedSize(800, 600)
        
        self.initUI()
        self.update_format_description()
    
    def initUI(self):
        # 主窗口布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # 1. 基本信息组
        info_group = QGroupBox("基本信息")
        info_layout = QHBoxLayout()
        
        # 电压选择
        voltage_layout = QVBoxLayout()
        voltage_layout.addWidget(QLabel("电压(V)"))
        self.voltage_combo = QComboBox()
        self.voltage_combo.addItems(["12", "24", "36", "48"])
        voltage_layout.addWidget(self.voltage_combo)
        
        # 容量选择
        capacity_layout = QVBoxLayout()
        capacity_layout.addWidget(QLabel("容量(Ah)"))
        self.capacity_combo = QComboBox()
        self.capacity_combo.addItems(["100", "120", "140", "160", "200", "240"])
        capacity_layout.addWidget(self.capacity_combo)
        
        # 电芯型号
        cell_layout = QVBoxLayout()
        cell_layout.addWidget(QLabel("电芯型号"))
        self.cell_combo = QComboBox()
        self.cell_combo.addItems(["G_N_H10", "L_F_H20", "P_C_H50", "A_K_H100"])
        cell_layout.addWidget(self.cell_combo)
        
        # 产品线
        product_line_layout = QVBoxLayout()
        product_line_layout.addWidget(QLabel("产品线"))
        self.product_line_combo = QComboBox()
        self.product_line_combo.addItems(["T", "ST", "GC"])
        product_line_layout.addWidget(self.product_line_combo)
        
        info_layout.addLayout(voltage_layout)
        info_layout.addLayout(capacity_layout)
        info_layout.addLayout(cell_layout)
        info_layout.addLayout(product_line_layout)
        info_group.setLayout(info_layout)
        
        # 2. 功能特征组 (多选)
        feature_group = QGroupBox("功能特征 (可多选)")
        feature_layout = QHBoxLayout()
        
        self.hts_check = QCheckBox("HTS (智能加热)")
        self.ht_check = QCheckBox("HT (充电加热)")
        self.pwr_check = QCheckBox("PWR (启动功能)")
        self.com_check = QCheckBox("COM (通信功能)")
        
        feature_layout.addWidget(self.hts_check)
        feature_layout.addWidget(self.ht_check)
        feature_layout.addWidget(self.pwr_check)
        feature_layout.addWidget(self.com_check)
        feature_group.setLayout(feature_layout)
        
        # 3. 版本信息组
        version_group = QGroupBox("版本信息")
        version_layout = QHBoxLayout()
        
        # 主版本
        main_ver_layout = QVBoxLayout()
        main_ver_layout.addWidget(QLabel("主版本"))
        self.main_ver_spin = QSpinBox()
        self.main_ver_spin.setRange(0, 99)
        self.main_ver_spin.setValue(1)
        main_ver_layout.addWidget(self.main_ver_spin)
        
        # 次版本
        rev_ver_layout = QVBoxLayout()
        rev_ver_layout.addWidget(QLabel("次版本"))
        self.rev_ver_spin = QSpinBox()
        self.rev_ver_spin.setRange(0, 99)
        rev_ver_layout.addWidget(self.rev_ver_spin)
        
        # 修订号
        fix_ver_layout = QVBoxLayout()
        fix_ver_layout.addWidget(QLabel("修订号"))
        self.fix_ver_spin = QSpinBox()
        self.fix_ver_spin.setRange(0, 99)
        fix_ver_layout.addWidget(self.fix_ver_spin)
        
        # 发布日期
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("发布日期"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        date_layout.addWidget(self.date_edit)
        
        version_layout.addLayout(main_ver_layout)
        version_layout.addLayout(rev_ver_layout)
        version_layout.addLayout(fix_ver_layout)
        version_layout.addLayout(date_layout)
        version_group.setLayout(version_layout)
        
        # 4. 生成按钮
        generate_btn = QPushButton("生成文件名")
        generate_btn.clicked.connect(self.generate_names)
        
        # 5. 结果显示
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        
        # 6. 格式说明
        self.format_text = QTextEdit()
        self.format_text.setReadOnly(True)
        
        # 添加到主布局
        main_layout.addWidget(info_group)
        main_layout.addWidget(feature_group)
        main_layout.addWidget(version_group)
        main_layout.addWidget(generate_btn)
        main_layout.addWidget(QLabel("生成结果:"))
        main_layout.addWidget(self.result_text)
        main_layout.addWidget(QLabel("命名格式说明:"))
        main_layout.addWidget(self.format_text)
    
    def get_selected_features(self):
        """获取选中的功能特征并按优先级排序"""
        features = []
        if self.hts_check.isChecked():
            features.append("HTS")
        if self.ht_check.isChecked():
            features.append("HT")
        if self.pwr_check.isChecked():
            features.append("PWR")
        if self.com_check.isChecked():
            features.append("COM")
        
        # 按优先级排序
        priority_order = ["HTS", "HT", "PWR", "COM"]
        return sorted(features, key=lambda x: priority_order.index(x))
    
    def generate_names(self):
        """生成各种固件文件名"""
        # 获取基本参数
        voltage = self.voltage_combo.currentText()
        capacity = self.capacity_combo.currentText()
        cell_model = self.cell_combo.currentText()
        product_line = self.product_line_combo.currentText()
        
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FirmwareNamingTool()
    window.show()
    sys.exit(app.exec())