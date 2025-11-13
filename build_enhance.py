import os
import shutil
import PyInstaller.__main__
import subprocess
import sys

def build_exe(mode: str):
    """编译指定版本的EXE"""
    print(f"正在编译增强版 {mode} 版本...")
    
    # 清理旧构建文件
    shutil.rmtree("build", ignore_errors=True)
    shutil.rmtree(f"dist/enhanced_{mode}_version", ignore_errors=True)
    
    # 生成运行时钩子文件
    with open(f"runtime_hook_enhanced_{mode}.py", "w") as f:
        f.write(f"import os\nos.environ['APP_MODE'] = '{mode}'")
    
    # 构建参数
    args = [
        "enhanced_main_window.py",
        f"--name=enhanced_{mode}",
        "--onefile",
        "--windowed",
        # f"--icon=build/icon.ico",
        "--add-data=测试上位机.ui;Dest",
        f"--distpath=dist/enhanced_{mode}_version",
        # "--workpath=build",
        # "--specpath=build",
        f"--runtime-hook=runtime_hook_enhanced_{mode}.py",
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
    if mode in ["debugApp"]:
        args += [
            "--debug=all",
            "--console"  # 调试版显示控制台
        ]
    
    PyInstaller.__main__.run(args)
    os.remove(f"runtime_hook_enhanced_{mode}.py")  # 清理临时文件

if __name__ == "__main__":
    print("=" * 60)
    print("增强版BMS调试工具打包脚本")
    print("=" * 60)
    
    # 转换UI文件
    print("\n步骤1: 转换UI文件...")
    
    # 编译版本
    print("\n步骤2: 编译可执行文件...")
    for mode in ["userApp", "debugApp", "firstuse"]:
        print(f"\n正在编译 {mode} 版本...")
        build_exe(mode)
    
    print("\n" + "=" * 60)
    print("编译完成！")
    print("=" * 60)
    print("生成的 EXE 位置：")
    print("- 用户版: dist/enhanced_userApp_version/enhanced_userApp.exe")
    print("- 调试版: dist/enhanced_debugApp_version/enhanced_debugApp.exe")
    print("- 首次使用版: dist/enhanced_firstuse_version/enhanced_firstuse.exe")
    print("=" * 60)

