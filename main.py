import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow,QTextEdit
from PyQt6 import uic

class UserInterface(QMainWindow):
    """客户版界面"""
    def __init__(self):
        super().__init__()
        # 获取ui文件路径
        if hasattr(sys, "_MEIPASS"):
            ui_path = os.path.join(sys._MEIPASS, "测试上位机.ui")
        else:
            ui_path = "测试上位机.ui"
        uic.loadUi(ui_path, self)  # 加载客户版UI
        self.setWindowTitle("正式版")
        self.setFixedSize(800, 600)
        # 客户版特有配置...

class DebugInterface(QMainWindow):
    """调试版界面"""
    def __init__(self):
        super().__init__()
        # 获取ui文件路径
        if hasattr(sys, "_MEIPASS"):
            ui_path = os.path.join(sys._MEIPASS, "测试上位机.ui")
        else:
            ui_path = "测试上位机.ui"
        uic.loadUi(ui_path, self)  # 加载调试版UI
        self.setWindowTitle("调试版")
        self.setFixedSize(1000, 800)
        # 调试版特有功能...
        self.setup_debug_tools()

    def setup_debug_tools(self):
        """初始化调试工具"""
        self.debug_console = QTextEdit()
        # self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.debug_console)

def main():
    app = QApplication(sys.argv)
    
    # 根据环境变量判断运行模式
    mode = os.getenv("APP_MODE", "debug")  # 默认调试模式
    
    # 加载对应界面
    if mode == "user":
        window = UserInterface()
    else:
        window = DebugInterface()
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()