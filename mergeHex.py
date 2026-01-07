import sys
import traceback
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QMessageBox
)
from intelhex import IntelHex
from datetime import datetime


class HexMergerApp(QWidget):
    packDataSize = 372
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('HEX 文件合并工具 (PyQt6)')
        self.setGeometry(100, 100, 400, 300)  # 调整窗口大小以容纳更多内容

        layout = QVBoxLayout()

        # 选择 HEX 文件的标签和按钮
        self.label = QLabel('选择要合并的 HEX 文件', self)
        layout.addWidget(self.label)

        self.select_button = QPushButton('选择 HEX 文件', self)
        self.select_button.clicked.connect(self.select_hex_files)
        layout.addWidget(self.select_button)

        # 显示选中 HEX 文件的字节数量
        self.selected_hex_size_label = QLabel('选中 HEX 文件的字节数量：0', self)
        layout.addWidget(self.selected_hex_size_label)

        # 显示较大 HEX 文件的校验和（十六进制）
        self.checksum_label = QLabel('较大 HEX 文件的校验和：无', self)
        layout.addWidget(self.checksum_label)

        # 合并按钮
        self.merge_button = QPushButton('合并 HEX 文件', self)
        self.merge_button.clicked.connect(self.merge_hex_files)
        layout.addWidget(self.merge_button)
        
        # 添加导出BIN文件按钮
        self.export_bin_button = QPushButton('导出为BIN文件', self)
        self.export_bin_button.clicked.connect(self.export_bin_file)
        layout.addWidget(self.export_bin_button)

        # 添加修改并保存按钮
        self.modify_button = QPushButton('修改并保存较大HEX文件', self)
        self.modify_button.clicked.connect(self.modify_and_save_large_hex)
        layout.addWidget(self.modify_button)

        # 显示合并后的 HEX 文件的字节数量
        self.merged_hex_size_label = QLabel('合并后的 HEX 文件的字节数量：0', self)
        layout.addWidget(self.merged_hex_size_label)

        self.setLayout(layout)

    def select_hex_files(self):
        options = QFileDialog.Option.ReadOnly
        self.hex_files, _ = QFileDialog.getOpenFileNames(
            self, "选择 HEX 文件", "", "HEX Files (*.hex);;All Files (*)", options=options
        )
        if self.hex_files:
            self.label.setText(f"已选择 {len(self.hex_files)} 个 HEX 文件")
            # 计算选中 HEX 文件的总字节数量
            total_size = 0
            litst_file_size = 0
            self.largest_file_size = 0
            largest_file_checksum = 0

            for hex_file in self.hex_files:
                try:
                    ih = IntelHex(hex_file)
                    file_size = len(ih)

                    # 找到较大的 HEX 文件并计算校验和
                    if file_size > self.largest_file_size:
                        self.largest_file_size = file_size
                        self.largest_file_name = hex_file
                        largest_file_checksum = self.calculate_checksum(ih)
                    else:
                        litst_file_size = file_size
                except Exception as e:
                    QMessageBox.critical(self, '错误', f'无法读取文件 {hex_file}: {str(e)}')
                    return

            self.selected_hex_size_label.setText(f"文件1字节数量：{litst_file_size} 文件2字节数量：{self.largest_file_size}")
            # 将校验和转换为十六进制显示
            self.checksum_label.setText(self.checksum_label.text() + f"较大 HEX 文件的校验和：0x{largest_file_checksum:08X}")
    def merge_hex_files(self):
        if not self.hex_files:
            QMessageBox.warning(self, '警告', '请先选择 HEX 文件')
            return

        self.merged_hex = IntelHex()

        # i = 0
        # ih0 = IntelHex(self.hex_files[0])
        # ih1 = IntelHex(self.hex_files[1])
        # try:
        #     if len(ih0) > len(ih1):
        #         ih1.merge(ih0, overlap='replace')
        #     else:
        #         ih0.merge(ih1, overlap='replace')
        # except Exception as e:
        #     QMessageBox.critical(self, '错误', f'无法读取文件 {hex_files}: {str(e)}')
        #     return
        small_size = 0x4000
        for hex_file in self.hex_files:
            try:
                ih = IntelHex(hex_file)
                small_size = len(ih) if (small_size > len(ih)) else small_size
                self.merged_hex.merge(ih, overlap='replace')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法读取文件 {hex_file}: {str(e)}')
                return
        # FF_size = 0x4000 - small_size
        print(f"small_size = {small_size:02x}")
        for i in range(small_size + 0x8000000, 0x4000 + 0x8000000) :
            self.merged_hex[i] = 0xff
            if(i < 0x8003d00) :
                print(f"i = {i:02x}",end=',')
        # print(f"test ih = {merged_hex[0x3A00]} type = {type(merged_hex)}")
        try:
            #包数量地址 4个字节
            # merged_hex[0x2E04] = (self.packetNum >> 0) & 0xff
            # merged_hex[0x2E05] = (self.packetNum >> 8) & 0xff
            # merged_hex[0x2E06] = (self.packetNum >> 16) & 0xff
            # merged_hex[0x2E07] = (self.packetNum >> 24) & 0xff

            # #校验和地址 4个字节但是两个低地址字节有值，2个无值
            # merged_hex[0x2E08] = self.checkSum & 0xff
            # merged_hex[0x2E09] = (self.checkSum >> 8) & 0xff
            # merged_hex[0x2E0A] = 0x00
            # merged_hex[0x2E0B] = 0x00

            # #按照规则补全HEX
            # for i in range(0x3000 + self.largest_file_size, 0x3000 + self.largest_file_size + self.compementHexNum):
            #     merged_hex[i] = 0xff
                pass
        except Exception as e:
            QMessageBox.critical(self, '错误', f'写入校验和值和数量值失败 {str(e)}')
            return
        print(self.merged_hex.start_addr)
        self.merged_hex.start_addr = {'EIP': 0}
        print(self.merged_hex.start_addr)
        # 计算合并后的 HEX 文件的字节数量
        merged_size = len(self.merged_hex)
        self.merged_hex_size_label.setText(f"合并后的 HEX 文件的字节数量：{merged_size}")

        # 生成文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        # default_filename = f"mergeFile_{current_time}.hex"
        default_filename = "IAP+" + self.largest_file_name.split('/')[-1]
        print(f"default_filename = {default_filename}")
        options = QFileDialog.Option.ReadOnly
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存合并后的 HEX 文件", default_filename, "HEX Files (*.hex);;All Files (*)", options=options
        )
        if save_path:
            try:
                self.merged_hex.write_hex_file(save_path)
                
                # 添加bin文件保存功能
                # bin_save_path = save_path.replace('.hex', '.bin')
                self.merged_hex.write_hex_file(save_path)
                
                QMessageBox.information(self, '成功', f'合并后的 HEX 文件已保存到 {save_path}\n')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法保存文件: {str(e)}')
                traceback.print_exc()

    def calculate_checksum(self, ih):
        """计算 HEX 文件的校验和（所有字节的值相加）"""
        checksum = 0
        self.compementHexNum = 0
        hexSum = 0
        for i in range(0x3000, 0x3000 + len(ih)):
            hexSum += 1
            checksum += ih[i]

        self.packetNum = len(ih) // self.packDataSize if len(ih) // self.packDataSize == 0 else  len(ih) // self.packDataSize + 1
        if len(ih) % self.packDataSize != 0:
            for i in range(0, self.packDataSize - (len(ih) % self.packDataSize)):
                self.compementHexNum += 1
                hexSum += 1
                checksum += 0xff
        self.checkSum = checksum
        print(f"self.compementHexNum = {self.compementHexNum}  hexSum = {hexSum} checksum = 0x{checksum:08X}")
        print(f"上传到服务器校验和的值是16位，并且是小端序 = {(checksum % 256 ):02X} {(checksum // 256 % 256):02X}")
        self.checksum_label.setText(f"compementHexNum = {self.compementHexNum}  hexSum = {hexSum} checksum = 0x{checksum:08X} \n\
上传到服务器校验和的值是16位，并且是小端序 = {(checksum % 256 ):02X} {(checksum // 256 % 256):02X}\n")
        return checksum

    def export_bin_file(self):
        """导出为BIN文件"""
        if not hasattr(self, 'hex_files') or not self.hex_files:
            QMessageBox.warning(self, '警告', '请先选择并合并HEX文件')
            return
            
        try:
            # 如果已经合并过文件，使用已合并的IntelHex对象
            if hasattr(self, 'merged_hex'):
                ih = self.merged_hex
            else:
                # 否则重新合并
                ih = IntelHex()
                for hex_file in self.hex_files:
                    ih.merge(IntelHex(hex_file), overlap='replace')
                
            # 保存BIN文件
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = "merged_" + current_time + ".bin"
            
            options = QFileDialog.Option.ReadOnly
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存BIN文件", default_filename, "BIN Files (*.bin);;All Files (*)", options=options
            )
            
            if save_path:
                ih.tobinfile(save_path)
                QMessageBox.information(self, '成功', f'BIN文件已保存到 {save_path}')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法导出BIN文件: {str(e)}')
            traceback.print_exc()

    def modify_and_save_large_hex(self):
        """修改并保存较大的HEX文件"""
        if not hasattr(self, 'hex_files') or not self.hex_files:
            QMessageBox.warning(self, '警告', '请先选择HEX文件')
            return
            
        try:
            # 找到较大的HEX文件
            if not hasattr(self, 'largest_file_name'):
                QMessageBox.warning(self, '警告', '请先选择HEX文件')
                return
                
            # 读取较大的HEX文件
            ih = IntelHex(self.largest_file_name)
            
            # 在这里添加您需要的修改逻辑
            # 示例：修改地址0x3000到0x300F的数据
            # for i in range(0x3000, 0x3010):
            #     ih[i] = 0xFF  # 将所有字节设置为0xFF
            a = ih[0x00030d2]
            
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存修改后的HEX文件", "", 
                "HEX Files (*.hex);;All Files (*)"
            )
            for i in range(0, 100):
                if(a + i + 1> 0xff):
                    print(f'a = {a}, 版本号大小超出了限制')
                    break
                a = a + 1
                ih[0x00030d2] =  a
                # 保存修改后的文件

                end_path = save_path.replace('.hex', f"major{ih[0x00030d0]}minor{ih[0x00030d2]}.hex")
                if end_path:
                    ih.write_hex_file(end_path)
                    # QMessageBox.information(self, '成功', f'修改后的HEX文件已保存到 {save_path}')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法修改并保存HEX文件: {str(e)}')
            traceback.print_exc()


if __name__ == '__main__':
    # test = IntelHex()
    # print(f"test = {test[0]} type = {type(test[0])}")

    app = QApplication(sys.argv)
    ex = HexMergerApp()
    ex.show()
    sys.exit(app.exec())