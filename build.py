import os
import shutil
import PyInstaller.__main__
import subprocess
import sys
def build_exe(mode: str):
    """编译指定版本的EXE"""
    print(f"正在编译 {mode} 版本...")
    
    # 清理旧构建文件
    shutil.rmtree("build", ignore_errors=True)
    shutil.rmtree(f"dist/{mode}_version", ignore_errors=True)
    
    # 生成运行时钩子文件
    with open(f"runtime_hook_{mode}.py", "w") as f:
        f.write(f"import os\nos.environ['APP_MODE'] = '{mode}'")
    
    # 构建参数
    args = [
        "newblue3_17.py",
        f"--name={mode}",
        "--onefile",
        "--windowed",
        # f"--icon=build/icon.ico",
        "--add-data=测试上位机.ui;Dest",
        f"--distpath=dist/{mode}_version",
        # "--workpath=build",
        # "--specpath=build",
        f"--runtime-hook=runtime_hook_{mode}.py",
        "--clean",
        "--noconfirm",
        # 排除PySide6以避免冲突
        "--exclude-module=PySide6",
        "--exclude-module=PySide6.QtCore",
        "--exclude-module=PySide6.QtGui", 
        "--exclude-module=PySide6.QtWidgets",
        "--exclude-module=shiboken6"
    ]
    
    # 调试版额外配置
    if mode in ["debugApp","firstuse"]:
        args += [
            "--debug=all",
            "--console"  # 调试版显示控制台
        ]
    
    PyInstaller.__main__.run(args)
    os.remove(f"runtime_hook_{mode}.py")  # 清理临时文件

def convert_ui_to_py(ui_file, py_file):
    """转换UI文件为Python文件 - 使用PyQt6"""
    try:
        # 使用PyQt6的pyuic6工具
        result = subprocess.run([
            'pyuic6', ui_file, '-o', py_file
        ], check=True, capture_output=True, text=True)
        
        print(f"UI转换成功: {ui_file} -> {py_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"UI转换失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except FileNotFoundError:
        print("pyuic6 命令未找到，尝试使用 Python 模块方式...")
        try:
            # 使用 Python -m PyQt6.uic.pyuic 方式调用
            result = subprocess.run([
                sys.executable, '-m', 'PyQt6.uic.pyuic',
                ui_file, '-o', py_file
            ], check=True, capture_output=True, text=True)
            
            print(f"UI转换成功: {ui_file} -> {py_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Python模块方式也失败: {e}")
            return False

if __name__ == "__main__":
    # 转换UI文件
    convert_ui_to_py('测试上位机.ui', 'ui_main.py')
    convert_ui_to_py('monitor_interface.ui', 'ui_monitor.py')
    # 编译两个版本

    for mode in ["userApp", "debugApp","firstuse"]:
        build_exe(mode)
    
    print("编译完成！")
    print("生成的 EXE 位置：")
    print("- 用户版: dist/user_version/MyApp.exe")
    print("- 调试版: dist/debug_version/MyApp.exe")