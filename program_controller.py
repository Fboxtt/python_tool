from PyQt6.QtCore import QObject, pyqtSignal
import time
import traceback
from enum import IntEnum
from typing import List, Optional
from datetime import datetime


class ProgramController(QObject):
    # 定义信号
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    program_completed = pyqtSignal(bool)

    def __init__(self, serial_controller, hex_model):
        super().__init__()
        self.serial_controller = serial_controller
        self.hex_model = hex_model
        self.is_programming = False

    def start_programming(self):
        """开始烧录过程"""
        if not self.hex_model.hex_data or not self.serial_controller.model.is_connected:
            self.status_updated.emit("请先选择HEX文件并连接串口")
            return False

        self.is_programming = True
        try:
            # 获取数据
            data = self.hex_model.get_data()
            total_size = len(data)
            sent_size = 0

            # 发送开始烧录命令
            self.serial_controller.send_data_bytes(b'\xAA\x55\x01')  # 示例命令
            response = self._wait_for_response()
            if not response or response[0] != 0xAA:  # 检查响应
                raise Exception("设备未就绪")

            # 分包发送数据
            packet_size = 256  # 每包256字节
            while sent_size < total_size and self.is_programming:
                # 准备数据包
                packet = data[sent_size:sent_size + packet_size]
                packet_header = bytes([0xAA, 0x55, 0x02, len(packet)])
                
                # 发送数据包
                self.serial_controller.send_data_bytes(packet_header + packet)
                
                # 等待响应
                response = self._wait_for_response()
                if not response or response[0] != 0xAA:
                    raise Exception(f"数据包 {sent_size//packet_size} 发送失败")

                # 更新进度
                sent_size += len(packet)
                progress = int(sent_size * 100 / total_size)
                self.progress_updated.emit(progress)
                
                # 短暂延时，避免发送过快
                time.sleep(0.01)

            # 发送结束命令
            self.serial_controller.send_data_bytes(b'\xAA\x55\x03')
            response = self._wait_for_response()
            if not response or response[0] != 0xAA:
                raise Exception("烧录完成确认失败")

            self.status_updated.emit("烧录完成")
            self.program_completed.emit(True)
            return True

        except Exception as e:
            self.status_updated.emit(f"烧录失败: {str(e)}")
            traceback.print_exc()
            self.program_completed.emit(False)
            return False
        finally:
            self.is_programming = False

    def stop_programming(self):
        """停止烧录过程"""
        self.is_programming = False
        self.status_updated.emit("烧录已停止")

    def _wait_for_response(self, timeout=1.0) -> bytes:
        """等待设备响应"""
        try:
            start_time = time.time()
            response = b''
            
            while time.time() - start_time < timeout:
                data = self.serial_controller.model.read_data()
                if data:
                    response += data
                    if len(response) >= 2:  # 假设响应至少2字节
                        return response
                time.sleep(0.01)
            
            return b''
        except Exception as e:
            print(f"等待响应失败: {e}")
            traceback.print_exc()
            return b'' 




# 定义错误常量
ERR_NO = 0
ERR_ALL_CHECK = 1

class BmsCmdType(IntEnum):
    READ_IC_INF = 0x71
    DOWNLOAD_BUFFER = 0x75
    ENTER_BOOTMODE = 0x76
    WRITE_FLASH = 0x77
    REC_TOTAL_CHECKSUM = 0x78
    READ_FLASH = 0x79
    ENTER_APP = 0x7A
    DOWNLOAD_BACKUP = 0x7C
    RESTORE_BACKUP = 0x7D

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

class DownloadController:
    NO_DATA_TYPE_LENGTH = 4
    def __init__(self, serial_controller, hex_model):
        super().__init__()
        self.serial_controller = serial_controller
        self.hex_model = hex_model
        self.is_programming = False

        # HexDecode 的属性
        self.exist = False
        self.hex_length = 0
        self.address = 0
        self.extend_linear_address = 0
        self.data_type = 0
        self.erase_flag = False
        self.begin_download_state = False
        self.begin_erase_state = False
        self.packet_id = 0
        self.packet_size = 372
        self.packet_num = 0
        self.shake_success_time = 0
        self.download_backup_flag = False
        self.shake_backup_succ_time = 0
        self.write_success_time = 0
        self.hex_packet_ok: List[bool] = []
        
        self.packet_num_l_err = 0
        self.bms_nack = 0
        self.cmd_type_err = 0
        
        self.write_flash_cmd = 0
        self.download_start_time = datetime.now()
        
        # bytes 数据
        self.n00data_array = bytearray()
        # self.n01end_array = bytearray()
        # self.n02extend_array = bytearray()
        # self.n03start_array = bytearray()
        # self.n04extend_linear_array = bytearray()
        # self.n05start_linear_array = bytearray()
        # self.data_all = bytearray()
        # self.merge_hex_ok = False
        # self.hex_array: List[int] = []
        self.total_checksum_array = bytearray()
        
        # TestObject 的属性
        self.com_status = ComStatus.NO_START
        self.step = 0
        self.testing_key = ""
        self.status = None
        self.tested = None
        self.report_log = ""
        self.dcode0 = None
        self.dcode0 = TextDecode()  # 创建一个 TextDecode 实例

    def packet_to_send_string(self, cmd_type: BmsCmdType, packet_id: int = 0) -> str:
        send_data_array = bytearray()
        data_array = bytearray()
        
        if cmd_type == BmsCmdType.WRITE_FLASH:
            data_array.extend([packet_id + 1 & 0xFF])
            data_array.extend([(packet_id + 1 >> 8) & 0xFF])
            data_array.extend([self.packet_num & 0xFF])
            data_array.extend([(self.packet_num >> 8) & 0xFF])
            
            if packet_id < self.packet_num - 1:
                data_array.extend(self.n00data_array[packet_id * self.packet_size:
                                                   packet_id * self.packet_size + self.packet_size])
            else:
                data_array.extend(self.n00data_array[packet_id * self.packet_size:])
                if self.hex_length % self.packet_size != 0:
                    data_array.extend([0xFF] * (self.packet_size - self.hex_length % self.packet_size))
        
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
        
        send_data_array.extend([check_sum & 0xFF])
        
        return ' '.join([f"{b:02X}" for b in send_data_array])

    def start_download(self, received_data):
        self.dcode0.split_data(received_data)
        if not self.hex_model.hex_data or not self.serial_controller.model.is_connected:
            # self.status_updated.emit("请先选择HEX文件并连接串口")
            print("请先选择HEX文件并连接串口")
            return False
        write_str = ""
        
        if self.com_status == ComStatus.RECEIVING:
            if self.step == 3:
                if self.dcode0.cmd_ack == ERR_NO and self.dcode0.have_hex and self.dcode0.data_hex[0] == 0x00:
                    self.com_status = ComStatus.SENDING
                else:
                    self.com_status = ComStatus.FAILED
                    
            elif self.step == 4:
                if (self.dcode0.cmd_ack == ERR_NO and self.dcode0.have_hex and 
                    self.packet_num + 1 == self.dcode0.cmd_packet_num):
                    if self.packet_num + 1 < self.packet_num:
                        self.packet_num += 1
                    self.com_status = ComStatus.SENDING
                else:
                    self.com_status = ComStatus.FAILED
                    
            elif self.step == 5:
                if self.dcode0.cmd_ack == ERR_ALL_CHECK and self.dcode0.have_hex:
                    self.com_status = ComStatus.FAILED
                else:
                    self.com_status = ComStatus.SENDING
                    
            else:
                if self.dcode0.cmd_ack == ERR_NO and self.dcode0.have_hex:
                    self.com_status = ComStatus.SENDING
                else:
                    self.com_status = ComStatus.FAILED
                    
            if self.com_status == ComStatus.SENDING:
                if self.packet_num == 0 or self.packet_num + 1 == self.packet_num:
                    self.step += 1
                self.dcode0.have_hex = False
                
            elif self.com_status == ComStatus.FAILED:
                print(f"{self.testing_key} 测试失败 第{self.step}步失败")
                self.status = self.tested
                self.report_log = f"{self.testing_key}测试失败{self.step}步失败"
                return
                
        elif self.com_status == ComStatus.NO_START:
            self.com_status = ComStatus.SENDING
            self.step = 0
            
        # 处理不同步骤
        if self.step == 0:
            self.packet_num = 0
            write_str = self.packet_to_send_string(BmsCmdType.ENTER_BOOTMODE)
        elif self.step in [1, 2]:
            write_str = self.packet_to_send_string(BmsCmdType.ENTER_BOOTMODE)
        elif self.step == 3:
            write_str = self.packet_to_send_string(BmsCmdType.DOWNLOAD_BUFFER)
        elif self.step == 4:
            write_str = self.packet_to_send_string(BmsCmdType.WRITE_FLASH, self.packet_num)
        elif self.step == 5:
            write_str = self.packet_to_send_string(BmsCmdType.REC_TOTAL_CHECKSUM)
        elif self.step == 6:
            self.step = 0
            self.status = self.tested
            self.report_log = f"{self.testing_key}测试成功"
            return write_str
            
        self.com_status = ComStatus.RECEIVING
    def stop_download(self):
        self.com_status = ComStatus.NO_START
        pass

    def process_download(self):
        """处理下载流程：先读取数据，再开始下载"""
        try:
            # 1. 读取串口数据
            data = self.serial_controller.read_data()
            if data:
                # 3. 开始下载流程
                return self.start_download(data)
            return None
        except Exception as e:
            print(f"处理下载流程失败: {e}")
            traceback.print_exc()
            return None

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
            else:
                raise Exception("PC_SET_WRITE_FLASH命令长度错误")
        except Exception as e:
            print(f"接收命令无法解析: {e}")
            traceback.print_exc()

        if self.legality == ERR_NO:
            print(f"cmd = 0x{self.cmd:02x} cmd_ack = 0x{self.cmd_ack:02x} cmd_data_len = {self.data_len}")
        return
    

if __name__ == "__main__":
    cmd = bytearray([0x00,0x00, 0x07, 0x01, 0xf7, 0x55 , 0xaa, 0x8a, 0x00, 0x88])
    dcode0 = TextDecode()
    dcode0.split_data(cmd)
    print(f"cmd = 0x{dcode0.cmd:02x}")
    print(f"cmd_ack = 0x{dcode0.cmd_ack:02x}")
    print(f"legality = {dcode0.legality}")
    print(f"actual_len = {dcode0.actual_len}")
    print(f"address = 0x{dcode0.address:02x}")
    print(f"bms_type = 0x{dcode0.bms_type:02x}")
    print(f"data_len = {dcode0.data_len}")

    # download_controller = DownloadController()
    # download_controller.start_download(dcode0)

    while True:
        result = download_controller.process_download()
        if result:
            # 处理返回结果
            pass
        time.sleep(0.01)  # 短暂延时，避免CPU占用过高
