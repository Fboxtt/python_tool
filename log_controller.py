import os
import datetime

class LogManager:
    _instance = None  # 类级别的变量，用于存储唯一实例

    @classmethod
    def get_instance(cls):
        """获取 LogManager 的唯一实例"""
        if cls._instance is None:
            cls._instance = LogManager()
            cls._instance.log_file_init()
        return cls._instance

    def log_file_init(self):
        """初始化日志文件，创建log文件夹并按日期生成日志文件"""
        # 获取当前日期作为文件名
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{current_date}.log"
        
        # 设置日志文件夹路径
        log_dir = os.path.join(os.getcwd(), "log")
        
        # 如果日志文件夹不存在，则创建
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
                print(f"创建日志文件夹: {log_dir}")
            except Exception as e:
                print(f"创建日志文件夹失败: {e}")
                return None
        
        # 完整的日志文件路径
        log_file_path = os.path.join(log_dir, log_filename)
        
        # 以追加模式打开日志文件（如果文件不存在会自动创建）
        try:
            self.log_file = open(log_file_path, 'a', encoding='utf-8')
            print(f"日志文件已初始化: {log_file_path}")
            
            # 写入日志头部信息
            self.log_file.write(f"\n{'='*50}\n")
            self.log_file.write(f"日志开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.log_file.write(f"{'='*50}\n\n")
            self.log_file.flush()  # 立即写入文件
            
        except Exception as e:
            print(f"打开日志文件失败: {e}")

    def write_log(self, message):
        """写入日志信息"""
        if hasattr(self, 'log_file') and self.log_file:
            try:
                # 获取当前时间
                current_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                # 写入日志
                self.log_file.write(f"[{current_time}] {message}\n")
                self.log_file.flush()  # 立即写入文件
            except Exception as e:
                print(f"写入日志失败: {e}")

    def close_log(self):
        """关闭日志文件"""
        if hasattr(self, 'log_file') and self.log_file:
            try:
                self.write_log("程序关闭")
                self.log_file.close()
                print("日志文件已关闭")
            except Exception as e:
                print(f"关闭日志文件失败: {e}") 