import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
import struct
from intelhex import IntelHex
from log_controller import LogManager
from PyQt6.QtCore import pyqtSignal
import json
import os

import traceback
# Define constants at the top of your file
CELL_COUNT = 16  # Adjust this value as needed
TEMP_COUNT = 5   # Adjust this value as needed

# ---------------------------- 结构体定义 ----------------------------
# 注意：所有格式字符串均已展开为具体字符，确保顺序严格匹配
STRUCT_FORMATS = {
    "PC_GET_BMS": "<"
        "LLLLLLLLLLLL"  # ulCHG_SwitchV(4) ~ ulBatt_OVP_Resume(4)
        "HHHH"
        "LLLL"
        "HHHH"
        "llllll"
        "hhhhhhhhhhhhhhhh"
        "hh",
    "PC_GET_KB": "<"
        "HH"
        "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH"
        "HhHhHhHhHhHh"
        "HHHHHHHHHHHHHHH",
    "PC_GET_OCP_DELAYTIME": "<HHHH",
    "PC_GET_CELL_CAP_PARA": "<LL",
    "PC_GET_MOSHTDATA": "<HHHH",
    "PC_GET_LIFE_PARA": "<HHLLL",
    "PC_GET_SBS": "<LL"  # ulPackV, ulBattV
        "HHHHHHHHHHHHHHHH"  # usCellV[CELL_COUNT]
        "l"  # lCurrent
        "hhhhh"  # sTemp[TEMP_COUNT]
        "HHH"  # usRemainAH, usFccAH, usBiaAH
        "LLLLL"  # ulOtherInfo, ulAlarmStatus, ulProtectStatus, ulFaultStatus, ulBalanceStatus
        "HH"  # usBattStatus, usSOC_Percent
        "LLL",  # ulSOH_Percent, ulDisTimes, ulTotalDisAH
    "PC_GET_VER": "<"
        "HHHH"    # usMajorVer, usMinorVer, usRevision, usCompileYear
        "BB"      # ucCompileMonth, ucCompileDay
        "30s"     # cHWversion (30 bytes)
        "40s",    # cFuncVersion (40 bytes)
    "PC_GET_INF": "<"
        "HHHHBBBB"  # TVER: bootVer
        "HHHHBBBB"  # TVER: app_Ver
        "HHHHBBBB"  # TVER: buffVer
        "HHHHBBBB"  # TVER: backVer
        "15s"     # icName (15 bytes)
        "B"       # writableArea (1 byte)
        "L"       # pcAddr (4 bytes)
        "L"       # uniqueID (4 bytes)
}

STRUCT_ADDRESSES = {
    "PC_GET_BMS": 0x500202,
    "PC_GET_KB": 0x5002C2,
    "PC_GET_OCP_DELAYTIME": 0x500322,
    "PC_GET_CELL_CAP_PARA": 0x500332,
    "PC_GET_MOSHTDATA": 0x500342,
    "PC_GET_LIFE_PARA": 0x500402
}

STRUCT_VARIABLES = {
    "PC_GET_BMS": [
        "ulCHG_SwitchV", "ulSwitch_PB_DiffV", 
        "ulCHG_Bls_StartV", "ulCHG_Bls_StopV",
        "ulPack_OVA_Threshold", "ulPack_OVA_Resume",
        "ulPack_OVP_Threshold", "ulPack_OVP_Resume",
        "ulBatt_OVA_Threshold", "ulBatt_OVA_Resume",
        "ulBatt_OVP_Threshold", "ulBatt_OVP_Resume",
        "usCell_OVA_Threshold", "usCell_OVA_Resume",
        "usCell_OVP_Threshold", "usCell_OVP_Resume",
        "ulBatt_UVA_Threshold", "ulBatt_UVA_Resume",
        "ulBatt_UVP_Threshold", "ulBatt_UVP_Resume",
        "usCell_UVA_Threshold", "usCell_UVA_Resume",
        "usCell_UVP_Threshold", "usCell_UVP_Resume",
        "lCHG_OCA_Threshold", "lCHG_OCA_Resume", "lCHG_OCP_Threshold",
        "lDIS_OCA_Threshold", "lDIS_OCA_Resume", "lDIS_OCP_Threshold",
        "sCHG_OTA_Threshold", "sCHG_OTA_Resume", "sCHG_OTP_Threshold", "sCHG_OTP_Resume",
        "sDIS_OTA_Threshold", "sDIS_OTA_Resume", "sDIS_OTP_Threshold", "sDIS_OTP_Resume",
        "sCHG_UTA_Threshold", "sCHG_UTA_Resume", "sCHG_UTP_Threshold", "sCHG_UTP_Resume",
        "sDIS_UTA_Threshold", "sDIS_UTA_Resume", "sDIS_UTP_Threshold", "sDIS_UTP_Resume",
        "sHEATER_START_T", "sHEATER_STOP_T",
    ],
    "PC_GET_KB": [
        "usPackVK", "usBattVK",
        *[f"usCellVK[{i}]" for i in range(16)],
        "usChgCurrK", "sChgCurrB",
        "usDisCurrK", "sDisCurrB",
        "usChgCurrSK", "sChgCurrSB",
        "usDisCurrSK", "sDisCurrSB",
        "usChgCurrSSK", "sChgCurrSSB",
        "usDisCurrSSK", "sDisCurrSSB",
        *[f"usTempK[{i}]" for i in range(8)]
    ],
    "PC_GET_OCP_DELAYTIME": [
        "ChgDelayCount_1C", "ChgDelayCount_2C",
        "DisDelayCount_1C", "DisDelayCount_2C"
    ],
    "PC_GET_CELL_CAP_PARA": [
        "ulModuleDesignCap", "ulModuleFactoryCap"
    ],
    "PC_GET_MOSHTDATA": [
        "sAlarm", "sAlarmRe", "sProtect", "sProtectRe"
    ],
    "PC_GET_LIFE_PARA": [
        "usSOC_Percent", "reserved", "ulSOH_Percent",
        "ulRemainPointmAs", "lSingleDis_Ah"
    ],
    "PC_GET_SBS": [
        "ulPackV", "ulBattV",
        *[f"usCellV[{i}]" for i in range(16)],
        "lCurrent",
        *[f"sTemp[{i}]" for i in range(5)],
        "usRemainAH", "usFccAH", "usBiaAH",
        "ulOtherInfo", "ulAlarmStatus", "ulProtectStatus", "ulFaultStatus", "ulBalanceStatus",
        "usBattStatus", "usSOC_Percent",
        "ulSOH_Percent", "ulDisTimes", "ulTotalDisAH"
    ],
    "PC_GET_INF": [
        "bootVer.usMajorVer", "bootVer.usMinorVer", "bootVer.usRevision", "bootVer.usYear", "bootVer.ucMonth", "bootVer.ucDay","bootVer.reserved","bootVer.reserved",
        "app_Ver.usMajorVer", "app_Ver.usMinorVer", "app_Ver.usRevision", "app_Ver.usYear", "app_Ver.ucMonth", "app_Ver.ucDay","app_Ver.reserved","app_Ver.reserved",
        "buffVer.usMajorVer", "buffVer.usMinorVer", "buffVer.usRevision", "buffVer.usYear", "buffVer.ucMonth", "buffVer.ucDay","buffVer.reserved","buffVer.reserved",
        "backVer.usMajorVer", "backVer.usMinorVer", "backVer.usRevision", "backVer.usYear", "backVer.ucMonth", "backVer.ucDay","backVer.reserved","backVer.reserved",
        "icName",
        "writableArea",
        "pcAddr",
        "uniqueID"
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
    "PC_SET_RT0_EN": 0x31,
    "PC_SET_RT1_EN": 0x32,
    "PC_SET_RT2_EN": 0x33,
    "PC_SET_RT0_OFF": 0x34,
    "PC_SET_RT1_OFF": 0x35,
    "PC_SET_RT2_OFF": 0x36,
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
    "PC_GET_INF" : 0x71
}

# 将所有字典组合成一个字典
config_data = {
    "STRUCT_FORMATS": STRUCT_FORMATS,
    "STRUCT_ADDRESSES": STRUCT_ADDRESSES,
    "STRUCT_VARIABLES": STRUCT_VARIABLES,
    "STRUCT_COMMANDS": STRUCT_COMMANDS
}

# 写入读出对应关系管理
WRITE_READ_COMMAND_MAPPING = {
    # 写入命令 : 读取命令
    "PC_SET_KB": "PC_GET_KB",
    "PC_SET_BMS": "PC_GET_BMS", 
    "PC_SET_OCP_DELAYTIME": "PC_GET_OCP_DELAYTIME",
    "PC_SET_CELL_CAP_PARA": "PC_GET_CELL_CAP_PARA",
    "PC_SET_LIFE_PARA": "PC_GET_LIFE_PARA",
    "PC_SET_MOSHTDATA": "PC_GET_MOSHTDATA",
}

# 读取写入对应关系管理（反向映射）
READ_WRITE_COMMAND_MAPPING = {
    # 读取命令 : 写入命令
    "PC_GET_KB": "PC_SET_KB",
    "PC_GET_BMS": "PC_SET_BMS",
    "PC_GET_OCP_DELAYTIME": "PC_SET_OCP_DELAYTIME", 
    "PC_GET_CELL_CAP_PARA": "PC_SET_CELL_CAP_PARA",
    "PC_GET_LIFE_PARA": "PC_SET_LIFE_PARA",
    "PC_GET_MOSHTDATA": "PC_SET_MOSHTDATA",
}

def get_write_command_from_read(read_command_name):
    """
    根据读取命令名称获取对应的写入命令名称
    
    Args:
        read_command_name (str): 读取命令名称，如 "PC_GET_LIFE_PARA"
    
    Returns:
        str: 对应的写入命令名称，如 "PC_SET_LIFE_PARA"，如果没有找到则返回 None
    """
    return READ_WRITE_COMMAND_MAPPING.get(read_command_name, None)

def get_read_command_from_write(write_command_name):
    """
    根据写入命令名称获取对应的读取命令名称
    
    Args:
        write_command_name (str): 写入命令名称，如 "PC_SET_LIFE_PARA"
    
    Returns:
        str: 对应的读取命令名称，如 "PC_GET_LIFE_PARA"，如果没有找到则返回 None
    """
    return WRITE_READ_COMMAND_MAPPING.get(write_command_name, None)

def get_write_command_code(read_command_name):
    """
    根据读取命令名称获取对应的写入命令代码
    
    Args:
        read_command_name (str): 读取命令名称，如 "PC_GET_LIFE_PARA"
    
    Returns:
        int: 对应的写入命令代码，如 0x40，如果没有找到则返回 None
    """
    write_command_name = get_write_command_from_read(read_command_name)
    if write_command_name and write_command_name in STRUCT_COMMANDS:
        return STRUCT_COMMANDS[write_command_name]
    return None

def get_read_command_code(write_command_name):
    """
    根据写入命令名称获取对应的读取命令代码
    
    Args:
        write_command_name (str): 写入命令名称，如 "PC_SET_LIFE_PARA"
    
    Returns:
        int: 对应的读取命令代码，如 0x41，如果没有找到则返回 None
    """
    read_command_name = get_read_command_from_write(write_command_name)
    if read_command_name and read_command_name in STRUCT_COMMANDS:
        return STRUCT_COMMANDS[read_command_name]
    return None

def can_command_be_written(read_command_name):
    """
    检查某个读取命令是否有对应的写入命令
    
    Args:
        read_command_name (str): 读取命令名称
    
    Returns:
        bool: 如果有对应的写入命令返回 True，否则返回 False
    """
    return read_command_name in READ_WRITE_COMMAND_MAPPING

def get_all_writable_commands():
    """
    获取所有可写入的命令对应关系
    
    Returns:
        dict: 所有可写入的命令对应关系字典
    """
    return READ_WRITE_COMMAND_MAPPING.copy()

# 更新配置数据，包含写入读出对应关系
config_data.update({
    "WRITE_READ_COMMAND_MAPPING": WRITE_READ_COMMAND_MAPPING,
    "READ_WRITE_COMMAND_MAPPING": READ_WRITE_COMMAND_MAPPING
})

class HexParserApp(QMainWindow):
    decode_data_ok_signal = pyqtSignal(int,dict)

    def __init__(self):
        super().__init__()
        self.initUI()
        self.set_config_file()
        self.struct_name_list = []
    def update_dict(self, target, source):
        """递归更新字典"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target:
                self.update_dict(target[key], value)
            else:
                target[key] = value
    def set_config_file(self):
        # 配置文件路径
        config_file_path = os.path.join(os.getcwd(), "default_config.json")

        # 检查配置文件是否存在
        if os.path.exists(config_file_path):
            try:
                # 读取现有配置文件
                with open(config_file_path, 'r', encoding='utf-8') as config_file:
                    existing_config = json.load(config_file)
                
                # 检查现有配置文件格式是否正确
                if isinstance(existing_config, dict):
                    # 比较现有配置文件与当前配置数据
                    if existing_config != config_data:
                        # 更新 config_data 为现有配置文件内容
                        self.update_dict(config_data, existing_config)
                    else:
                        print("配置文件已存在且内容相同，无需更新")
                else:
                    print("配置文件格式不正确，使用当前配置数据")
            except Exception as e:
                traceback.print_exc()
                print(f"读取配置文件失败: {e}")
        else:
            print("配置文件不存在，将创建新文件")

        # 将字典写入 JSON 文件
        with open(config_file_path, 'w', encoding='utf-8') as config_file:
            json.dump(config_data, config_file, ensure_ascii=False, indent=4)

        print(f"配置文件已生成或更新: {config_file_path}")
        pass
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
    def get_struct_name_list(self):
        for key, value in STRUCT_VARIABLES.items():
            struct_str = key
            for i in value:
                struct_str += "," + i
            self.struct_name_list.append(struct_str)
        return self.struct_name_list
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
    def decode_cmd_hex_data(self, cmd:int, data_bytes:bytes):
        """
        把二进制数据转换成字典数据
        """            
        parsed_data = {}
        if cmd in STRUCT_COMMANDS.values():
            for key, value in STRUCT_COMMANDS.items():
                if value == cmd:
                    struct_name = key
                    break
        else:
            LogManager.get_instance().write_log(f"解析 {cmd:02X} 失败: 无当前命令")
            return "no_cmd", None
        if struct_name not in STRUCT_FORMATS:
            LogManager.get_instance().write_log(f"解析 {struct_name} 失败: 这个命令没有预存格式细节")
            return struct_name, None
        try:
            fmt = STRUCT_FORMATS[struct_name]
            print(fmt)
            size = struct.calcsize(fmt)
            if size != len(data_bytes):
                print(f"解析 {struct_name} 失败: 数据长度不匹配, 目标长度: {size}, 实际长度: {len(data_bytes)}")
                LogManager.get_instance().write_log(f"解析 {struct_name} 失败: 数据长度不匹配, 目标长度: {size}, 实际长度: {len(data_bytes)}")
                return None, None
            
            # 解析为元组
            values = struct.unpack(fmt, data_bytes)
            
            # 处理有符号值
            dec_values = []
            hex_byte_array = []
            
            # 首先找到icName字段在values中的索引
            icname_index = None
            for i, var_name in enumerate(STRUCT_VARIABLES[struct_name]):
                if var_name == "icName":
                    icname_index = i
                    break
            
            for i, (var_name, value) in enumerate(zip(STRUCT_VARIABLES[struct_name], values)):
                if var_name == "icName":
                    # 检查value的类型并相应处理
                    if isinstance(value, bytes):
                        # 如果已经是bytes类型，直接解码
                        str_value = value.decode('utf-8', errors='replace').rstrip('\x00')
                        dec_values.append(str_value)
                        hex_bytes = ''.join([f"{b:02X}" for b in value])
                        hex_byte_array.append(hex_bytes)
                    else:
                        # 如果不是bytes类型，从原始数据中提取
                        # 假设icName是15字节长度，并且在数据中的位置可以计算
                        # 这里我们需要找到icName在data_bytes中的偏移量
                        # 一个简单的方法是从结尾往前数16字节（15字节icName + 1字节writableArea + 4字节pcAddr）
                        icname_bytes = data_bytes[-20:-5]  # 从末尾往前15字节
                        str_value = icname_bytes.decode('utf-8', errors='replace').rstrip('\x00')
                        dec_values.append(str_value)
                        hex_bytes = ''.join([f"{b:02X}" for b in icname_bytes])
                        hex_byte_array.append(hex_bytes)
                else:
                    # 处理数值字段
                    if isinstance(value, int):
                        if value < 256:
                            hex_byte_array.append(f"0x{value:02X}")
                        elif value < 65536:
                            hex_byte_array.append(f"0x{value:04X}")
                        else:
                            hex_byte_array.append(f"0x{value:08X}")
                        
                        # 根据约定确定符号
                        if var_name.startswith('s') or var_name.startswith('l'):
                            dec_values.append(str(value))  # 保留符号
                        else:
                            dec_values.append(str(value & 0xFFFF_FFFF))  # 无符号显示
                    else:
                        # 其他类型的值
                        hex_byte_array.append(str(value))
                        dec_values.append(str(value))
            
            # 按字节对齐显示
            display_data = []
            for i, (var_name, dec_val) in enumerate(zip(STRUCT_VARIABLES[struct_name], dec_values)):
                display_data.append((
                    var_name,
                    hex_byte_array[i],
                    dec_val
                ))
            parsed_data[struct_name] = display_data
            
        except Exception as e:
            traceback.print_exc()
            LogManager.get_instance().write_log(f"解析 {struct_name} 失败: {str(e)}")
        
        LogManager.get_instance().write_log("发射dic信号")
        return struct_name, parsed_data



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HexParserApp()
    str1 = "4A 9A 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 15 00 16 00 16 00 00 00 00 00 00 00 00 00 00 00 00 00 64 00 10 27 00 00 C0 00 01 00 20 10 00 00 00 00 00 00 10 00 00 00 00 00 00 00 00 00 01 00 64 00 00 00 00 00 00 00 00 00 00 00"
    # 转换成字节数据
    str1_bytes = bytearray.fromhex(str1.replace(" ", ""))
    # 测试数据

    test_data = bytearray([
        0x01, 0x00, 0x02, 0x00, 0x03, 0x00, 0xE7, 0x07, 0x0A, 0x0F, 0x00,0x00, # bootVer
        0x04, 0x00, 0x05, 0x00, 0x06, 0x00, 0xE7, 0x07, 0x0B, 0x14, 0x00,0x00, # app_Ver
        0x07, 0x00, 0x08, 0x00, 0x09, 0x00, 0xE7, 0x07, 0x0C, 0x19, 0x00,0x00, # buffVer
        0x0A, 0x00, 0x0B, 0x00, 0x0C, 0x00, 0xE8, 0x07, 0x01, 0x01, 0x00,0x00, # backVer
        0x49, 0x43, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38,  # icName
        0x39, 0x30, 0x31, 0x32, 0x33,  # icName (continued)
        0x01,  # writableArea
        0x78, 0x56, 0x34, 0x12,  # pcAddr
        0xD0, 0x34, 0x56, 0x78  # uniqueID
    ])

    # 解析测试数据
    struct_name, parsed_data = window.decode_cmd_hex_data(0x13, str1_bytes)
    print(f"Struct Name: {struct_name}")
    print("Parsed Data:")
    for var_name, hex_val, dec_val in parsed_data["PC_GET_SBS"]:
        print(f"{var_name}: {hex_val} | {dec_val}")

    window.show()
    sys.exit(app.exec())