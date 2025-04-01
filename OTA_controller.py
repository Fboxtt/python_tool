from PyQt6.QtCore import QObject, pyqtSignal
import time
import traceback
from enum import IntEnum
from typing import List, Optional
from datetime import datetime
# from OTA_controller import OtaController  # 更新导入语句

# 定义错误常量
ERR_NO = 0
ERR_ALL_CHECK = 1

class BmsCmdType(IntEnum):
    READ_IC_INF = 0x71
    DOWNLOAD_BUFFER = 0x75
    ENTER_BOOTMODE = 0x76
    WRITE_FLASH = 0x77
    REC_TOTAL_CHECKSUM = 0x78
    # READ_FLASH = 0x79  # 未使用
    # ENTER_APP = 0x7A  # 未使用
    BMS_MCU_OPEN = 0x7B
    # DOWNLOAD_BACKUP = 0x7C  # 未使用
    # RESTORE_BACKUP = 0x7D  # 未使用

class DownloadErr(IntEnum):
    DOWNLOAD_OK = True
    PACKET_NUM_LENTH_ERR = 1
    DOWNLOAD_DONE = 2
    BMS_NACK = 3
    CMD_TYPE_ERR = 4
    CHECKSUM_ACK = 5
    JUST_ERASE = 6

class ComStatus(IntEnum):
    NO_START = 0
    SENDING = 1
    RECEIVING = 2
    FAILED = 3

class ReceveDataStatus(IntEnum):
    ERR_NO = 0
    ERR_CMD_LEN = 1
    ERR_CHKSUM = 2
    ERR_NOTHING = 3

ERR_NO = 0
ERR_CMD_LEN = 1
ERR_CHKSUM = 2
ERR_NOTHING = 3
# 命令常量
PC_SET_WRITE_FLASH = 0x77
PC_SET_ALL_CHECKSUM = 0x78
PC_SET_DOWNLOAD_BUFFER = 0x75
PC_SET_DOWNLOAD_BACKUP = 0x7C

class OtaController:
    NO_DATA_TYPE_LENGTH = 4
    n00data_array = bytearray()
    def __init__(self):
        super().__init__()
        self.hex_length = 0
        self.packet_id = 0
        self.packet_size = 372
        self.packet_num = 0
        self.total_checksum_array = bytearray(2)
        
    def hex_init(self, hex_data:bytearray):
        """初始化hex文件数据
        
        将输入的hex数据进行处理，包括:
        1. 存储hex数据到n00data_array
        2. 计算数据包数量packet_num
        3. 如果数据长度不是packet_size的整数倍,用0xFF填充
        4. 计算总校验和存入total_checksum_array
        
        Args:
            hex_data: 输入的hex文件数据
        """
        self.n00data_array = bytearray(hex_data)
        self.hex_length = len(hex_data)
        print( "type hex_length = ", type(self.hex_length))
        if self.hex_length % self.packet_size != 0:
            self.packet_num = self.hex_length // self.packet_size + 1
            for i in range(self.packet_size - self.hex_length % self.packet_size):
                self.n00data_array.extend(bytearray([0xff]))
            # self.n00data_array.append(bytearray([0xFF] * (self.packet_size - self.hex_length % self.packet_size)))
            self.hex_length = len(self.n00data_array)
        else:   
            self.packet_num = self.hex_length // self.packet_size
        check_sum = 0
        for i in range(self.hex_length):
            check_sum += self.n00data_array[i]
        self.total_checksum_array[0] = check_sum & 0xff
        self.total_checksum_array[1] = (check_sum & 0xff00) // 0x100
        
    def get_download_data(self, cmd_type: BmsCmdType, packet_id: int = 0) -> bytes:
        """获取下载数据包
        
        根据命令类型和包ID生成下载数据包:
        1. WRITE_FLASH命令: 生成包含包ID、总包数和数据的数据包
        2. REC_TOTAL_CHECKSUM命令: 生成包含总校验和的数据包
        
        数据包格式:
        [0x00][长度高字节][长度低字节][单板类型][命令类型][0x55][0xAA][数据][校验和]
        
        Args:
            cmd_type: 命令类型(WRITE_FLASH或REC_TOTAL_CHECKSUM)
            packet_id: 数据包ID,默认为0
            
        Returns:
            生成的数据包字节数组,如果packet_id超出范围则返回None
        """
        send_data_array = bytearray()
        data_array = bytearray()
        
        if cmd_type == BmsCmdType.WRITE_FLASH:
            data_array.extend([packet_id + 1 & 0xFF])
            data_array.extend([(packet_id + 1 >> 8) & 0xFF])
            data_array.extend([self.packet_num & 0xFF])
            data_array.extend([(self.packet_num >> 8) & 0xFF])
            
            if packet_id < self.packet_num:
                data_array.extend(self.n00data_array[packet_id * self.packet_size:
                                                   packet_id * self.packet_size + self.packet_size])
            else:
                return None
                # data_array.extend(self.n00data_array[packet_id * self.packet_size:])
                # if self.hex_length % self.packet_size != 0:
                #     data_array.extend([0xFF] * (self.packet_size - self.hex_length % self.packet_size))
        
        if cmd_type == BmsCmdType.REC_TOTAL_CHECKSUM:
            data_array.extend(self.total_checksum_array)
            
        data_array_length = self.NO_DATA_TYPE_LENGTH + len(data_array)
        
        # 构建头部
        send_data_array.extend([0x00])
        send_data_array.extend([(data_array_length >> 8) & 0xFF])
        send_data_array.extend([data_array_length & 0xFF])
        send_data_array.extend([0x01])  # 单板类型
        send_data_array.extend([cmd_type & 0xFF])
        send_data_array.extend([0x55])
        send_data_array.extend([0xAA])
        send_data_array.extend(data_array)
        
        # 计算校验和
        check_sum = ((data_array_length >> 8) & 0xFF) + (data_array_length & 0xFF) + 0x01 + (cmd_type & 0xFF) + 0x55 + 0xAA
        for byte in data_array:
            check_sum += byte
        
        send_data_array.extend(bytearray([check_sum & 0xFF]))
        # print(f"Hex: {send_data_array.hex()}") 
        return send_data_array

    def stop_download(self):
        self.com_status = ComStatus.NO_START
        pass

class TextDecode:
    def __init__(self):
        # 初始化成员变量
        self.have_hex = False
        self.legality = ERR_NOTHING
        self.actual_len = 0
        self.address = 0x00
        self.bms_type = 0
        self.cmd = 0
        self.data_len = 0
        self.check_sum = 0
        self.cmd_ack = 0
        self.no80_cmd = 0
        self.actual_hex = bytearray()
        self.data_hex = bytearray()
        self.no_packet_len = 0
        self.no_packet_hex = bytearray()
        self.cmd_packet_num = 0

    def split_data(self, hex_data: bytearray):
        # 重置所有属性
        self.have_hex = False
        self.legality = ERR_NO
        self.actual_len = 0
        self.address = 0x00
        self.bms_type = 0
        self.cmd = 0
        self.data_len = 0
        self.check_sum = 0
        self.cmd_ack = 0
        self.is_download_cmd = False
        try:
            # 检查数据长度  
            if len(hex_data) >= 9:
                self.have_hex = True
                self.actual_hex = hex_data
                self.actual_len = len(hex_data)
            else:
                self.legality = ERR_CMD_LEN
                raise Exception("命令长度错误")

            # 解析数据
            self.address = self.actual_hex[0]
            self.data_len = self.actual_hex[1] * 0x100 + self.actual_hex[2] - 5
            self.bms_type = self.actual_hex[3]
            self.cmd = self.actual_hex[4]
            self.no80_cmd = self.actual_hex[4] & 0x7F
            self.cmd_ack = self.actual_hex[7]

            # 验证命令是否在 BmsCmdType 中
            
                
            for cmd_type in BmsCmdType:
                if self.no80_cmd == cmd_type.value:
                    self.is_download_cmd = True
                    break
            else:
                self.is_download_cmd = False

            # 计算校验和
            self.check_sum = 0
            for i in range(1, self.actual_len - 1):
                self.check_sum += self.actual_hex[i] & 0xFF

            # 检查命令类型
            if (self.cmd & 0x80) == 0:
                # 这是主机发送的数据，无法解析
                pass
            else:
                if self.actual_len != self.data_len + 9:
                    self.legality = ERR_CMD_LEN
                else:
                    self.data_hex = self.actual_hex[8:8 + self.data_len]

            # 检查特殊命令的数据长度
            if (self.no80_cmd not in [PC_SET_WRITE_FLASH, PC_SET_ALL_CHECKSUM, 
                                    PC_SET_DOWNLOAD_BUFFER, PC_SET_DOWNLOAD_BACKUP]):
                if self.actual_len != 9:
                    self.legality = ERR_CMD_LEN
                    raise Exception("命令长度错误")

            # 校验和检查
            if (self.check_sum & 0xFF) != (self.actual_hex[self.actual_len - 1] & 0xFF):
                print(f"checksum get = 0x{self.actual_hex[-1]:02x} cali = 0x{self.check_sum & 0xFF:02x}")
                self.legality = ERR_CHKSUM
                raise Exception("校验和错误")

            # 处理写入闪存命令
            if len(self.actual_hex) >= 11:
                if self.no80_cmd == PC_SET_WRITE_FLASH:
                    self.no_packet_len = self.data_len - 2  # 取长度
                    self.no_packet_hex = self.data_hex[2:2 + self.no_packet_len]
                    self.cmd_packet_num = (self.data_hex[0] & 0xFF) + (self.data_hex[1] & 0xFF) * 256
            # else:
            #     raise Exception("PC_SET_WRITE_FLASH命令长度错误")
        except Exception as e:
            print(f"接收命令无法解析: {e}")
            traceback.print_exc()

        if self.legality == ERR_NO:
            print(f"cmd = 0x{self.cmd:02x} cmd_ack = 0x{self.cmd_ack:02x} cmd_data_len = {self.data_len}")
        return
    

if __name__ == "__main__":
    # cmd = bytearray([0x00,0x00, 0x07, 0x01, 0xf7, 0x55 , 0xaa, 0x8a, 0x00, 0x88])
    # dcode0 = TextDecode()
    # dcode0.split_data(cmd)
    # print(f"cmd = 0x{dcode0.cmd:02x}")
    # print(f"cmd_ack = 0x{dcode0.cmd_ack:02x}")
    # print(f"legality = {dcode0.legality}")
    # print(f"actual_len = {dcode0.actual_len}")
    # print(f"address = 0x{dcode0.address:02x}")
    # print(f"bms_type = 0x{dcode0.bms_type:02x}")
    # print(f"data_len = {dcode0.data_len}")

    download_controller = OtaController()
    # download_controller.start_download(dcode0)
    hex_data = bytearray(1000)
    download_controller.hex_init(hex_data)
    print(f"packet num = ", download_controller.packet_num)
    print(download_controller.n00data_array,"lenth = ",len(download_controller.n00data_array))
    print(download_controller.total_checksum_array,"lenth = ",len(download_controller.total_checksum_array))
    print(f"packet 0 = ", download_controller.get_download_data(BmsCmdType.WRITE_FLASH,0))
    print(f"packet 1 = ", download_controller.get_download_data(BmsCmdType.WRITE_FLASH,1))
    print(f"packet 2 = ", download_controller.get_download_data(BmsCmdType.WRITE_FLASH,2))
    print(f"packet 3 = ", download_controller.get_download_data(BmsCmdType.WRITE_FLASH,3))

    print(f"check sum = ", download_controller.get_download_data(BmsCmdType.REC_TOTAL_CHECKSUM))
    # while True:
    #     # result = download_controller.process_download()
    #     # if result:
    #     #     # 处理返回结果
    #     #     pass
    #     time.sleep(0.01)  # 短暂延时，避免CPU占用过高
