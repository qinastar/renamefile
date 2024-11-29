import PyInstaller.__main__
import os
import sys
import customtkinter
import site

def build_exe():
    # 确保在正确的目录中
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 获取 customtkinter 模块路径
    customtkinter_path = os.path.dirname(customtkinter.__file__)
    
    # PyInstaller 参数
    args = [
        'file_cleaner.py',  # 主脚本
        '--name=FileCleaner',  # 生成的 exe 名称
        '--noconsole',  # 不显示控制台窗口
        '--onefile',  # 打包成单个文件
        '--clean',  # 清理临时文件
        f'--add-data={customtkinter_path};customtkinter',  # 使用实际的 customtkinter 路径
        '--hidden-import=customtkinter',
        '--hidden-import=sqlite3',
        '--hidden-import=winshell',
        '--hidden-import=pathlib',
    ]
    
    # 运行 PyInstaller
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    build_exe() 