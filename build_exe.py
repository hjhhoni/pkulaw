import PyInstaller.__main__
import os

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 图标文件路径（如果有的话）
icon_path = os.path.join(current_dir, 'icon.ico')

# 打包命令
PyInstaller.__main__.run([
    '.\\北大法典爬虫GUI.py',  # 主程序文件
    '--name=北大法宝爬虫',  # 生成的EXE文件名
    '--onefile',  # 打包成单个EXE文件
    '--windowed',  # 使用窗口模式，不显示控制台
    f'--icon={icon_path}',  # 设置图标（如果有的话）
    '--clean',  # 清理临时文件
    # '--add-data=d:\\副业\\项目\\爬北大法典\\urls.txt;.',  # 添加数据文件
    '--noconfirm',  # 不询问确认
])

print("打包完成！")
