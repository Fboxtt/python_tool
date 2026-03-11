from intelhex import IntelHex
import traceback
import struct
import base64
import io

class HexFileModel:
    def __init__(self):
        self.filename = ""
        self.hex_data = None
        self.size = 0
        self.is_file_loaded = False
    def parse_hex_file(self, filename: str) -> bool:
        """解析 Intel HEX 文件"""
        try:
            self.filename = filename
            # IntelHex 会自动处理校验和
            self.hex_data = IntelHex(filename)
            # 获取数据范围
            start = self.hex_data.minaddr()
            end = self.hex_data.maxaddr()
            self.size = end - start + 1
            if self.size > 0:   
                self.is_file_loaded = True
                return True
            else:
                self.is_file_loaded = False
                return False
        except Exception as e:
            print(f"解析HEX文件失败: {e}")
            traceback.print_exc()
            self.filename = ""
            self.hex_data = None
            self.size = 0
            return False

    def load_builtin_hex(self, hex_b64_data: str = None) -> bool:
        """从内置固件加载HEX，接受base64编码字符串参数"""
        try:
            if hex_b64_data is None:
                from builtin_hex import BUILTIN_HEX_B64
                hex_b64_data = BUILTIN_HEX_B64
            raw = base64.b64decode(hex_b64_data)
            self.hex_data = IntelHex(io.StringIO(raw.decode('ascii')))
            start = self.hex_data.minaddr()
            end = self.hex_data.maxaddr()
            self.size = end - start + 1
            if self.size > 0:
                self.filename = '[内置固件]'
                self.is_file_loaded = True
                return True
            else:
                self.is_file_loaded = False
                return False
        except Exception as e:
            print(f"加载内置HEX失败: {e}")
            traceback.print_exc()
            self.filename = ""
            self.hex_data = None
            self.size = 0
            return False

    def get_file_info(self) -> dict:
        """获取文件信息"""
        return {
            "filename": self.filename,
            "size": self.size
        }

    def get_data(self) -> bytes:
        """获取解析后的数据"""
        if self.hex_data is None:
            return b''
        return bytes(self.hex_data.tobinarray())

    def get_version_info(self) -> dict:
        """从HEX文件固定地址读取固件版本号和唯一ID
        
        平台判断：
          - 中微：minaddr < 0x08000000，版本地址 0x30d0，UID地址 0x31d0
          - 国民：minaddr >= 0x08000000，版本地址 0x080041d0，UID地址 0x080042d0
        
        版本格式：<HHHHBBBB（主, 次, 修订, 年, 月, 日, 保留1, 保留2）
        UID格式：<L（4字节无符号整数）
        
        Returns:
            dict: {
                'platform': '中微' or '国民',
                'version_str': 'V2.0.49 (2025-03-06)',
                'uid_str': '0x01234567',
                'error': None or '错误信息'
            }
        """
        result = {'platform': '未知', 'version_str': '无法读取', 'uid_str': '无法读取', 'error': None}
        if self.hex_data is None:
            result['error'] = 'HEX未加载'
            return result
        try:
            min_addr = self.hex_data.minaddr()
            if min_addr >= 0x08000000:
                result['platform'] = '国民'
                version_addr = 0x080041d0
                uid_addr = 0x080042d0
            else:
                result['platform'] = '中微'
                version_addr = 0x30d0
                uid_addr = 0x31d0
            # 读取12字节版本结构 <HHHHBBBB
            ver_bytes = bytes([self.hex_data[version_addr + i] for i in range(12)])
            major, minor, rev, year, month, day, _, _ = struct.unpack('<HHHHBBBB', ver_bytes)
            result['version_str'] = f'V{major}.{minor}.{rev} ({year}-{month:02d}-{day:02d})'
            # 读取4字节唯一ID <L
            uid_bytes = bytes([self.hex_data[uid_addr + i] for i in range(4)])
            uid_val = struct.unpack('<L', uid_bytes)[0]
            result['uid_str'] = f'0x{uid_val:08X}'
        except Exception as e:
            result['error'] = str(e)
        return result