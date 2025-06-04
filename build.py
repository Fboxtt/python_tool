import os
import shutil
import PyInstaller.__main__

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
        "--noconfirm"
    ]
    
    # 调试版额外配置
    if mode in ["debugApp","firstuse"]:
        args += [
            "--debug=all",
            "--console"  # 调试版显示控制台
        ]
    
    PyInstaller.__main__.run(args)
    os.remove(f"runtime_hook_{mode}.py")  # 清理临时文件

if __name__ == "__main__":
    # 编译两个版本
    for mode in ["userApp", "debugApp","firstuse"]:
        build_exe(mode)
    
    print("编译完成！")
    print("生成的 EXE 位置：")
    print("- 用户版: dist/user_version/MyApp.exe")
    print("- 调试版: dist/debug_version/MyApp.exe")