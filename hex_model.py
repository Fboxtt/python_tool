from intelhex import IntelHex
import traceback

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