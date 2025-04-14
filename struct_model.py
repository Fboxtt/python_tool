import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
import struct
from intelhex import IntelHex

# ---------------------------- 结构体定义 ----------------------------
# 注意：所有格式字符串均已展开为具体字符，确保顺序严格匹配
STRUCT_FORMATS = {
    # 地址 0x500202 - TBMS 结构体 (共 1536 字节)
    "TBMS": "<"
        # ULONG x12
        "LLLLLLLLLLLL"  # ulCHG_SwitchV(4) ~ ulBatt_OVP_Resume(4)
        # USHORT x8
        "HHHH"
        # ULONG x4    这里减了4个UL
        "LLLL"
        # USHORT x8
        "HHHH"
        # LONG x6
        "llllll"
        # SHORT x24
        "hhhhhhhhhhhhhhhh"
        # SHORT x2
        "hh",

    # 地址 0x5002C2 - TKB 结构体
    "TKB": "<"
        # USHORT x2
        "HH"
        # USHORT x16 (CELL_COUNT=16)
        "HHHHHHHHHHHHHHHH"
        # 混合类型 x16 (USHORT/SHORT交替)
        "HhHhHhHhHhHh"
        # USHORT x16 (TEMP_DEF=16)
        "HHHHH",

    # 地址 0x500322 - TDelayTimePara
    "TDelayTimePara": "<HHHH",  # USHORT x4

    # 地址 0x500332 - TCAP
    "TCAP": "<LL",             # ULONG x2

    # 地址 0x500342 - TMOSHTDATA
    "TMOSHTDATA": "<HHHH",     # USHORT x4

    # 地址 0x500362 - 未命名结构体 (char[20])
    # "UNNAMED_362": "<20B",     # 字节数组

    # 地址 0x500402 - TLIFE
    "TLIFE": "<HHLLL"           # USHORT + ULONG x3
}

STRUCT_ADDRESSES = {
    "TBMS": 0x500202,
    "TKB": 0x5002C2,
    "TDelayTimePara": 0x500322,
    "TCAP": 0x500332,
    "TMOSHTDATA": 0x500342,
    # "UNNAMED_362": 0x500362,
    "TLIFE": 0x500402
}


STRUCT_VARIABLES = {
    "TBMS": [
        # ULONG x12
        "ulCHG_SwitchV", "ulSwitch_PB_DiffV", 
        "ulCHG_Bls_StartV", "ulCHG_Bls_StopV",
        "ulPack_OVA_Threshold", "ulPack_OVA_Resume",
        "ulPack_OVP_Threshold", "ulPack_OVP_Resume",
        "ulBatt_OVA_Threshold", "ulBatt_OVA_Resume",
        "ulBatt_OVP_Threshold", "ulBatt_OVP_Resume", #---------------------
        
        # USHORT x8
        "usCell_OVA_Threshold", "usCell_OVA_Resume",
        "usCell_OVP_Threshold", "usCell_OVP_Resume",


        
        # ULONG x8
        "ulBatt_UVA_Threshold", "ulBatt_UVA_Resume",
        "ulBatt_UVP_Threshold", "ulBatt_UVP_Resume",


        "usCell_UVA_Threshold", "usCell_UVA_Resume",  # 注意：原始定义中这部分应为ULONG，根据实际需求调整
        "usCell_UVP_Threshold", "usCell_UVP_Resume",#-----------------------
        

        
        # LONG x6
        "lCHG_OCA_Threshold", "lCHG_OCA_Resume", "lCHG_OCP_Threshold",
        "lDIS_OCA_Threshold", "lDIS_OCA_Resume", "lDIS_OCP_Threshold",
        
        # SHORT x24
        "sCHG_OTA_Threshold", "sCHG_OTA_Resume", "sCHG_OTP_Threshold", "sCHG_OTP_Resume",
        "sDIS_OTA_Threshold", "sDIS_OTA_Resume", "sDIS_OTP_Threshold", "sDIS_OTP_Resume",
        "sCHG_UTA_Threshold", "sCHG_UTA_Resume", "sCHG_UTP_Threshold", "sCHG_UTP_Resume",
        "sDIS_UTA_Threshold", "sDIS_UTA_Resume", "sDIS_UTP_Threshold", "sDIS_UTP_Resume",
        "sHEATER_START_T", "sHEATER_STOP_T",
    ],
    
    "TKB": [
        "usPackVK", "usBattVK",
        # usCellVK[16]
        *[f"usCellVK[{i}]" for i in range(16)],
        # 电流相关参数
        "usChgCurrK", "sChgCurrB",
        "usDisCurrK", "sDisCurrB",
        "usChgCurrSK", "sChgCurrSB",
        "usDisCurrSK", "sDisCurrSB",
        "usChgCurrSSK", "sChgCurrSSB",
        "usDisCurrSSK", "sDisCurrSSB",
        # usTempK[16]
        *[f"usTempK[{i}]" for i in range(5)]
    ],
    
    "TDelayTimePara": [
        "ChgDelayCount_1C", "ChgDelayCount_2C",
        "DisDelayCount_1C", "DisDelayCount_2C"
    ],
    
    "TCAP": [
        "ulModuleDesignCap", "ulModuleFactoryCap"
    ],
    
    "TMOSHTDATA": [
        "sAlarm", "sAlarmRe", "sProtect", "sProtectRe"
    ],
    
    # "UNNAMED_362": [
    #     f"char_{i}" for i in range(20)  # 20字节无名数组
    # ],
    
    "TLIFE": [
        "usSOC_Percent", "reserved", "ulSOH_Percent",
        "ulRemainPointmAs", "lSingleDis_Ah"
    ]
}


STRUCT_COMMANDS = {
    "NONE": 0x00,
    "PC_LOGIN": 0x01,
    "PC_LOGOUT": 0x02,
    "PC_GET_OLDSBS": 0x03,
    "PC_GET_SBS": 0x13,
    "PC_GET_ADC": 0x04,
    "PC_GET_IO": 0x05,
    "PC_GET_OLDVER": 0x06,
    "PC_GET_VER": 0x16,
    "PC_GET_KB": 0x07,
    "PC_SET_KB": 0x08,
    "PC_SET_BMS": 0x09,
    "PC_GET_BMS": 0x15,
    "PC_OPEN_CHG": 0x0A,
    "PC_CLOSE_CHG": 0x0B,
    "PC_OPEN_DIS": 0x0C,
    "PC_CLOSE_DIS": 0x0D,
    "PC_GET_SERIALNUM": 0x10,
    "PC_SET_SERIALNUM": 0x11,
    "PC_A_PRINT": 0x14,
    "PC_SET_HEATERMODE": 0x17,
    "PC_SET_FORCEDDISMODE": 0x18,
    "PC_SET_PWSFUNCTION": 0x19,
    "PC_SET_SYSTIME": 0x20,
    "PC_GET_SYSTIME": 0x29,
    "PC_Buzzer_ON": 0x23,
    "PC_Buzzer_OFF": 0x24,
    "PC_GET_OCP_DELAYTIME": 0x25,
    "PC_SET_OCP_DELAYTIME": 0x26,
    "PC_OPEN_CHGLIMIT": 0x27,
    "PC_CLOSE_CHGLIMIT": 0x28,
    "PC_GET_CLUSTER_SBS": 0x30,
    "PC_SET_LIFE_PARA": 0x40,
    "PC_GET_LIFE_PARA": 0x41,
    "PC_SET_CELL_CAP_PARA": 0x42,
    "PC_GET_CELL_CAP_PARA": 0x43,
    "PC_GET_RUN_DATA": 0x44,
    "PC_CLEAR_RUN_DATA": 0x45,
    "PC_SET_WAIT_TIMEOUT": 0x46,
    "PC_FACTORY_CLEAER": 0x47,
    "PC_GET_CLUSTER_STATUS": 0x49,
    "PC_GET_DEBUG_DATA": 0x4C,
    "PC_GET_CLUSTER_MINRCD": 0x50,
    "PC_CLEAR_CLUSTER_MINRCD": 0x51,
    "PC_GET_SELF_MINRCD": 0x54,
    "PC_CLEAR_SELF_MINRCD": 0x55,
    "PC_GET_SELF_DAYRCD": 0x56,
    "PC_CLEAR_SELF_DAYRCD": 0x57,
    "PC_GET_SELF_ALMRCD": 0x58,
    "PC_CLEAR_SELF_ALMRCD": 0x59,
    "PC_SET_SHUTDOWN": 0x60,
    "PC_GET_FUSESTATE": 0x61,
    "PC_SET_FUSESTATE": 0x62,
    "PC_SET_BALANCE": 0x63,
    "PC_SET_SLEEP": 0x64,
    "PC_GET_MOSHTDATA": 0x65,
    "PC_SET_MOSHTDATA": 0x66,
    "MCU_A_PRINT": 0x94,
}

STRUCT_GET_CMD = {
    "TBMS": bytes([COMMANDS["PC_GET_BMS"]]),
    "TKB": bytes([COMMANDS["PC_GET_KB"]]),
    "TDelayTimePara": bytes([COMMANDS["PC_GET_OCP_DELAYTIME"]]),
    "TCAP": bytes([COMMANDS["PC_GET_CELL_CAP_PARA"]]),
    "TMOSHTDATA": bytes([COMMANDS["PC_GET_MOSHTDATA"]]),
    "TLIFE": bytes([COMMANDS["PC_GET_LIFE_PARA"]])
}

STRUCT_GET_CMD_NAME = {
    "TBMS": "PC_GET_BMS",
    "TKB": "PC_GET_KB",
    "TDelayTimePara": "PC_GET_OCP_DELAYTIME",
    "TCAP": "PC_GET_CELL_CAP_PARA",
    "TMOSHTDATA": "PC_GET_MOSHTDATA",
    "TLIFE": "PC_GET_LIFE_PARA",
}

STRUCT_SET_CMD = {
    "TBMS": bytes([COMMANDS["PC_SET_BMS"]]),
    "TKB": bytes([COMMANDS["PC_SET_KB"]]),
    "TDelayTimePara": bytes([COMMANDS["PC_SET_OCP_DELAYTIME"]]),
    "TCAP": bytes([COMMANDS["PC_SET_CELL_CAP_PARA"]]),
    "TMOSHTDATA": bytes([COMMANDS["PC_SET_MOSHTDATA"]]),
    "TLIFE": bytes([COMMANDS["PC_SET_LIFE_PARA"]])
}

STRUCT_SET_CMD_NAME = {
    "TBMS": "PC_SET_BMS",
    "TKB": "PC_SET_KB",
    "TDelayTimePara": "PC_SET_OCP_DELAYTIME",
    "TCAP": "PC_SET_CELL_CAP_PARA",
    "TMOSHTDATA": "PC_SET_MOSHTDATA",
    "TLIFE": "PC_SET_LIFE_PARA",
}

class HexParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("HEX 文件解析器")
        self.setGeometry(100, 100, 800, 600)

        # 创建主布局
        layout = QVBoxLayout()

        # 创建文本框用于显示结果
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily("Courier New")  # 使用等宽字体
        layout.addWidget(self.text_edit)

        # 创建按钮用于加载 HEX 文件
        self.load_button = QPushButton("加载 HEX 文件")
        self.load_button.clicked.connect(self.load_hex_file)
        layout.addWidget(self.load_button)

        # 设置主窗口的中心部件
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def load_hex_file(self):
        # 打开文件对话框选择 HEX 文件
        file_path, _ = QFileDialog.getOpenFileName(self, "打开 HEX 文件", "", "(*.*);;HEX 文件 (*.hex)")
        if not file_path:
            return

        # 使用 intelhex 库加载 HEX 文件
        try:
            ih = IntelHex(file_path)
        except Exception as e:
            self.text_edit.append(f"加载 HEX 文件失败：{e}")
            return

        # 解析结构体数据
        parsed_data = self.parse_hex_data(ih)

        # 显示解析结果
        self.text_edit.clear()
        for struct_name, data in parsed_data.items():
            self.text_edit.append(f"\n==== {struct_name} @ {STRUCT_ADDRESSES[struct_name]:#08x} ====")
            self.text_edit.append("-" * 70)
            self.text_edit.append(f"{'变量名':<25} | {'原始字节':<20} | {'十进制值':<15}")
            self.text_edit.append("-" * 70)
            for var_name, hex_bytes, dec_val in data:
                self.text_edit.append(f"{var_name:<25} | {hex_bytes:<20} | {dec_val:<15}")
            self.text_edit.append("\n")
    def parse_hex_data(self, ih):
        """
        严格按字节解析的增强版本
        """
        parsed_data = {}
        for struct_name, address in STRUCT_ADDRESSES.items():
            fmt = STRUCT_FORMATS[struct_name]
            size = struct.calcsize(fmt)
            
            try:
                # 读取原始字节
                data_bytes = ih.tobinstr(start=address, size=size)
                # 解析为元组
                values = struct.unpack(fmt, data_bytes)
                # 转换为十六进制字符串
                hex_values = [f"0x{b:02X}" for b in data_bytes]
                print(struct_name, data_bytes)
                print(type(hex_values))
                print(type(hex_values[0]))
                print(type(data_bytes))
                hex_byte_array = []

                # 处理有符号值
                dec_values = []
                for i, (var_name, value) in enumerate(zip(STRUCT_VARIABLES[struct_name], values)):
                    # 根据格式字符判断符号
                    fmt_char = fmt[1:][i]  # 跳过字节序字符
                    byte_len = struct.calcsize(fmt_char)
                    if byte_len == 1:
                        hex_byte_array.append(f"0x{value:02X}")
                    elif byte_len == 2:
                        hex_byte_array.append(f"0x{value:04X}")
                    elif byte_len == 4:
                        hex_byte_array.append(f"0x{value:08X}")
                        pass
                    if fmt_char in ('h', 'l'):
                        dec_values.append(str(value))  # 保留符号
                    else:
                        dec_values.append(str(value & 0xFFFF_FFFF))  # 无符号显示
                
                # 按字节对齐显示
                display_data = []
                byte_offset = 0
                i = 0
                for var_name, dec_val in zip(STRUCT_VARIABLES[struct_name], dec_values):
                    byte_len = struct.calcsize(fmt[1:][i])  # 计算变量字节长度
                    display_data.append((
                        var_name,
                        ''.join(hex_byte_array[i]),
                        dec_val
                    ))
                    byte_offset += byte_len
                    i += 1
                parsed_data[struct_name] = display_data
                
            except Exception as e:
                self.text_edit.append(f"解析 {struct_name} 失败: {str(e)}")
        
        return parsed_data
    def decode_cmd_hex_data(self, cmd:bytes, data_bytes:bytearray):
        """
        严格按字节解析的增强版本
        """
        parsed_data = {}
        if cmd in STRUCT_COMMANDS.values():
            pass
        else:
            return None
        if STRUCT_COMMANDS[cmd] in STRUCT_GET_CMD.values():
            pass
        elif STRUCT_COMMANDS[cmd] in STRUCT_SET_CMD.values():
            return None

        for struct_name, cmd_num in STRUCT_COMMANDS.items():
            try:
                if cmd_num == cmd:
                    fmt = STRUCT_FORMATS[struct_name]
                    size = struct.calcsize(fmt)
                else:
                    continue
            
                # 读取原始字节
                # data_bytes = ih.tobinstr(start=address, size=size)
                # 解析为元组
                values = struct.unpack(fmt, data_bytes)
                # 转换为十六进制字符串
                hex_values = [f"0x{b:02X}" for b in data_bytes]
                print(struct_name, data_bytes)
                print(type(hex_values))
                print(type(hex_values[0]))
                print(type(data_bytes))
                hex_byte_array = []

                # 处理有符号值
                dec_values = []
                for i, (var_name, value) in enumerate(zip(STRUCT_VARIABLES[struct_name], values)):
                    # 根据格式字符判断符号
                    fmt_char = fmt[1:][i]  # 跳过字节序字符
                    byte_len = struct.calcsize(fmt_char)
                    if byte_len == 1:
                        hex_byte_array.append(f"0x{value:02X}")
                    elif byte_len == 2:
                        hex_byte_array.append(f"0x{value:04X}")
                    elif byte_len == 4:
                        hex_byte_array.append(f"0x{value:08X}")
                        pass
                    if fmt_char in ('h', 'l'):
                        dec_values.append(str(value))  # 保留符号
                    else:
                        dec_values.append(str(value & 0xFFFF_FFFF))  # 无符号显示
                
                # 按字节对齐显示
                display_data = []
                byte_offset = 0
                i = 0
                for var_name, dec_val in zip(STRUCT_VARIABLES[struct_name], dec_values):
                    byte_len = struct.calcsize(fmt[1:][i])  # 计算变量字节长度
                    display_data.append((
                        var_name,
                        ''.join(hex_byte_array[i]),
                        dec_val
                    ))
                    byte_offset += byte_len
                    i += 1
                parsed_data[struct_name] = display_data
                
            except Exception as e:
                self.text_edit.append(f"解析 {struct_name} 失败: {str(e)}")
        
        return parsed_data



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HexParserApp()
    window.show()
    sys.exit(app.exec())