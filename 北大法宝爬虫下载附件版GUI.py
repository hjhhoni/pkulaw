from DrissionPage import Chromium, ChromiumPage
import time
import random
import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                            QWidget, QLabel, QLineEdit, QTextEdit, QFileDialog, QComboBox, 
                            QProgressBar, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

class CrawlerThread(QThread):
    """爬虫线程，避免界面卡死"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, crawler, mode):
        super().__init__()
        self.crawler = crawler
        self.mode = mode
        
    def run(self):
        try:
            # 重置爬虫状态
            self.crawler.state = 1
            
            if self.mode == 'collect':
                self.crawler.collect_urls(self)
                remaining = len(self.crawler.read_urls_from_file())
                self.finished_signal.emit(True, f"本页URL收集完成，当前共有{remaining}个URL待下载")
            elif self.mode == 'download':
                self.crawler.download_content(self)
                remaining = len(self.crawler.read_urls_from_file())
                if remaining > 0:
                    self.finished_signal.emit(True, f"本批次下载完成，还有{remaining}个URL待下载")
                else:
                    self.finished_signal.emit(True, "所有URL已下载完成")
                
        except Exception as e:
            self.update_signal.emit(f"发生错误: {str(e)}")
            self.finished_signal.emit(False, f"爬虫任务失败: {str(e)}")


class PkulawCrawler:
    def __init__(self):
        # 文件路径设置
        # 使用相对路径，这样打包后也能正常工作
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.urls_file = os.path.join(base_dir, 'urls.txt')
        self.folder_path = os.path.join(base_dir, 'downloads')
        
        # 爬虫状态
        self.state = 1
        
        # 等待时间区间设置
        self.min_wait_time = 1
        self.max_wait_time = 10
        
        # 确保保存目录存在
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
            
        # 初始化时连接浏览器
        try:
            print("正在连接到Chrome浏览器...")
            self.browser = Chromium('127.0.0.1:9333')
            self.page = self.browser.latest_tab
            print(f"已连接到浏览器，当前页面标题: {self.page.title}")
        except Exception as e:
            print(f"连接浏览器时出错: {e}")
            self.browser = None
            self.page = None
    
    def set_folder_path(self, path):
        """设置保存文件夹路径"""
        self.folder_path = path
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
    
    def collect_urls(self, thread=None):
        """收集列表页面的URL"""
        if thread:
            thread.update_signal.emit("开始收集URL...")
        else:
            print("开始收集URL...")
        
        try:
            # 每次点击按钮时重新连接浏览器
            if thread:
                thread.update_signal.emit("正在连接到Chrome浏览器...")
            else:
                print("正在连接到Chrome浏览器...")
                
            self.browser = Chromium('127.0.0.1:9333')
            
            self.page = self.browser.latest_tab
            now_url = str(self.page.url)[0:36]
            
            if thread:
                thread.update_signal.emit(f'当前页面标题: {self.page.title}')
            else:
                print(f'当前页面标题: {self.page.title}')
            
            # 获取已存储的URL集合
            existing_urls = self.read_urls_from_file()
            
            # 获取页面上的元素
            target = self.page.ele('tag:tbody')

            if not target:
                if thread:
                    thread.update_signal.emit("未找到tbody元素，请确认页面已正确加载")
                else:
                    print("未找到tbody元素，请确认页面已正确加载")
                return
            
            # print(now_url)
            items = target.eles('tag:tr')
            # if now_url == 'https://www.pkulaw.com/advanced/pfnl':
            #     items = target.eles('tag:tr')
            # elif now_url == 'https://www.pkulaw.com/advanced/law/':   
            #     items = self.page.eles('.list-title')
            #     print("测试：",items[0].ele('tag:a').attr('href'))

            # 计数器
            new_count = 0
            total_items = len(items)
            
            for i, item in enumerate(items):
                url = item.ele('tag:a').attr('href')
                if url not in existing_urls:
                    # 添加到集合并写入文件
                    existing_urls.add(url)
                    self.append_url_to_file(url)
                    if thread:
                        thread.update_signal.emit(f'添加成功: {url}')
                    else:
                        print(f'添加成功: {url}')
                    new_count += 1
                else:
                    if thread:
                        thread.update_signal.emit(f'已存在: {url}')
                    else:
                        print(f'已存在: {url}')
                
                # 更新进度
                if thread:
                    progress = int((i + 1) / total_items * 100)
                    thread.progress_signal.emit(progress)
            
            if thread:
                thread.update_signal.emit(f"URL收集完成，新增{new_count}个URL")
            else:
                print(f"URL收集完成，新增{new_count}个URL")

        except Exception as e:
            if thread:
                thread.update_signal.emit(f"收集URL时出错: {e}")
            else:
                print(f"收集URL时出错: {e}")
    
    def download_content(self, thread=None):
        """下载URL对应的详细内容"""
        # 重置爬虫状态，确保每次下载都是从正常状态开始
        self.state = 1
        
        if thread:
            thread.update_signal.emit("开始下载内容...")
        else:
            print("开始下载内容...")
        
        # 使用已有的浏览器实例，打开新标签页用于下载，保留登录状态
        if self.browser:
            page = self.browser.new_tab()
        else:
            # 如果没有已连接的浏览器实例，则创建新的实例
            page = ChromiumPage()
        
        # 读取所有URL
        urls = self.read_urls_from_file()
        
        if not urls:
            if thread:
                thread.update_signal.emit("没有URL需要下载")
            else:
                print("没有URL需要下载")
            return
        
        total_urls = len(urls)
        if thread:
            thread.update_signal.emit(f"共有{total_urls}个URL等待下载")
        else:
            print(f"共有{total_urls}个URL等待下载")
        
        # 下载计数
        success_count = 0
        
        # 设置每次下载的URL数量限制，可以根据需要调整
        batch_size = 10000
        urls_list = list(urls)[:batch_size]
        
        for i, url in enumerate(urls_list):  # 每次只处理一部分URL
            try:
                # 保护机制，使用用户设置的等待时间区间
                wait_time = random.randint(self.min_wait_time, self.max_wait_time)
                if thread:
                    thread.update_signal.emit(f"等待{wait_time}秒...")
                else:
                    print(f"等待{wait_time}秒...")
                time.sleep(wait_time)
                
                if self.state == 0:
                    if thread:
                        thread.update_signal.emit("程序被中断")
                    else:
                        print("程序被中断")
                    break
                
                # 下载内容
                page.get(url)
                time.sleep(2)
                
                # 获取文本内容
                # wenben1 = page.ele('.fields').text
                # wenben2 = page.ele('.fulltext').text
                # wenben = wenben1 + '\n' + wenben2
                wenben1 = page.ele('.fulltext-wrap')
                title = wenben1.ele('.title').text
                wenben = wenben1.ele('.content').text
                try:
                    wenben2 = wenben1.ele('#divFullText')
                    fujian = wenben2.eles('tag:a')
                    for f in fujian:
                        href = f.attr('href')
                        page.download(href, self.folder_path, f.text)
                        print(f.attr('href'))
                        time.sleep(1)
                except Exception as e:
                    print("出错ww：",e)
                    pass
                print(title)
                if thread:
                    thread.update_signal.emit(f"正在下载: {title}")
                else:
                    print(f"正在下载: {title}")
                # 处理文件名中的非法字符
                for c in "*?:<>|/\\":
                    if c in title:
                        title = title.replace(c, '某')
                
                # 保存到文件
                file_path = os.path.join(self.folder_path, f'{title}.txt')
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(wenben)
                
                # 下载成功后从文件中删除该URL
                self.remove_url_from_file(url)
                success_count += 1
                if thread:
                    thread.update_signal.emit(f"下载成功: {title}")
                    # 更新进度
                    progress = int((i + 1) / len(urls_list) * 100)
                    thread.progress_signal.emit(progress)
                else:
                    print(f"下载成功: {title}")
                
            except Exception as e:
                if thread:
                    thread.update_signal.emit(f'下载失败 {url}: {e}')
                else:
                    print(f'下载失败 {url}: {e}')
                # 如果是致命错误，设置状态为0中断程序
                if "无法连接" in str(e) or "timeout" in str(e).lower():
                    self.state = 0
                    if thread:
                        thread.update_signal.emit("检测到网络问题，程序中断")
                    else:
                        print("检测到网络问题，程序中断")
                    break
        
        # 关闭标签页（如果是新打开的）
        try:
            if self.browser:  # 如果使用的是已有的浏览器实例
                page.close()  # 关闭新打开的标签页
            else:  # 如果是新创建的浏览器实例
                page.quit()  # 完全关闭浏览器
        except Exception as e:
            if thread:
                thread.update_signal.emit(f"关闭标签页时出错: {str(e)}")
            else:
                print(f"关闭标签页时出错: {str(e)}")
                
        remaining = len(self.read_urls_from_file())
        if thread:
            thread.update_signal.emit(f"本次下载完成，成功下载{success_count}个文件，还剩{remaining}个URL待下载")
        else:
            print(f"本次下载完成，成功下载{success_count}个文件，还剩{remaining}个URL待下载")
    
    def read_urls_from_file(self):
        """从文件读取URL集合"""
        urls = set()
        if os.path.exists(self.urls_file):
            with open(self.urls_file, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url:
                        urls.add(url)
        return urls
    
    def append_url_to_file(self, url):
        """将URL追加到文件"""
        with open(self.urls_file, 'a', encoding='utf-8') as f:
            f.write(url + '\n')
    
    def remove_url_from_file(self, url_to_remove):
        """从文件中删除指定URL"""
        urls = self.read_urls_from_file()
        urls.discard(url_to_remove)
        
        with open(self.urls_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')


class PkulawCrawlerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.crawler = PkulawCrawler()
        self.init_ui()
        
    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle('北大法宝爬虫 - by hjhhoni')
        self.setGeometry(300, 300, 800, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:pressed {
                background-color: #2a66c8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit, QComboBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
                font-family: Consolas, Monaco, monospace;
            }
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4a86e8;
                width: 10px;
                margin: 0.5px;
            }
        """)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 设置组
        settings_group = QGroupBox("设置")
        settings_layout = QVBoxLayout(settings_group)
        
        # 文件夹选择
        folder_layout = QHBoxLayout()
        folder_label = QLabel("保存文件夹:")
        self.folder_edit = QLineEdit(self.crawler.folder_path)
        self.folder_edit.setReadOnly(True)
        browse_button = QPushButton("浏览...")
        browse_button.setFixedWidth(100)
        browse_button.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(browse_button)
        settings_layout.addLayout(folder_layout)
        
        # URL文件路径
        url_layout = QHBoxLayout()
        url_label = QLabel("URL文件:")
        self.url_edit = QLineEdit(self.crawler.urls_file)
        self.url_edit.setReadOnly(True)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit)
        settings_layout.addLayout(url_layout)
        
        # 等待时间设置
        wait_time_layout = QHBoxLayout()
        wait_time_label = QLabel("等待时间区间(秒):")
        self.min_wait_edit = QLineEdit(str(self.crawler.min_wait_time))
        self.min_wait_edit.setFixedWidth(50)
        wait_time_to_label = QLabel("到")
        self.max_wait_edit = QLineEdit(str(self.crawler.max_wait_time))
        self.max_wait_edit.setFixedWidth(50)
        wait_time_layout.addWidget(wait_time_label)
        wait_time_layout.addWidget(self.min_wait_edit)
        wait_time_layout.addWidget(wait_time_to_label)
        wait_time_layout.addWidget(self.max_wait_edit)
        wait_time_layout.addStretch()
        settings_layout.addLayout(wait_time_layout)
        
        main_layout.addWidget(settings_group)
        
        # 操作按钮组
        action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(action_group)
        
        self.collect_button = QPushButton("收集URL")
        self.collect_button.clicked.connect(lambda: self.start_crawler('collect'))
        
        self.download_button = QPushButton("下载内容")
        self.download_button.clicked.connect(lambda: self.start_crawler('download'))
        
        self.stop_button = QPushButton("停止爬虫")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_crawler)
        
        action_layout.addWidget(self.collect_button)
        action_layout.addWidget(self.download_button)
        action_layout.addWidget(self.stop_button)
        
        main_layout.addWidget(action_group)
        
        # 进度条
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(progress_group)
        
        # 日志输出
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
        
        # 添加版权信息
        copyright_label = QLabel("©2025 hjhhoni. All Rights Reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #888888; font-size: 17px; font-weight: bold;")
        main_layout.addWidget(copyright_label)
        
        # 状态栏
        self.statusBar().showMessage('就绪')
        
        # 显示窗口
        self.show()
        
        # 初始日志
        if self.crawler.page:
            self.log(f"已连接到浏览器，当前页面标题: {self.crawler.page.title}")
            self.log("请导航到目标页面，然后点击'收集URL'按钮")
        else:
            self.log("连接浏览器失败，请确保Chrome浏览器已打开并在端口9333上运行")
    
    def browse_folder(self):
        """浏览并选择保存文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹", self.crawler.folder_path)
        if folder:
            self.folder_edit.setText(folder)
            self.crawler.set_folder_path(folder)
            self.log("已设置保存文件夹: " + folder)
    
    def log(self, message):
        """添加日志消息"""
        self.log_text.append(message)
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def start_crawler(self, mode):
        """启动爬虫"""
        # 更新等待时间设置
        try:
            min_wait = int(self.min_wait_edit.text())
            max_wait = int(self.max_wait_edit.text())
            if min_wait > 0 and max_wait >= min_wait:
                self.crawler.min_wait_time = min_wait
                self.crawler.max_wait_time = max_wait
            else:
                self.log("等待时间设置无效，使用默认值")
                self.min_wait_edit.setText(str(1))
                self.max_wait_edit.setText(str(10))
                self.crawler.min_wait_time = 1
                self.crawler.max_wait_time = 10
        except ValueError:
            self.log("等待时间必须是整数，使用默认值")
            self.min_wait_edit.setText(str(1))
            self.max_wait_edit.setText(str(10))
            self.crawler.min_wait_time = 1
            self.crawler.max_wait_time = 10
        
        # 重置爬虫状态
        self.crawler.state = 1
        
        self.collect_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # 创建线程并连接信号
        self.crawler_thread = CrawlerThread(self.crawler, mode)
        self.crawler_thread.update_signal.connect(self.log)
        self.crawler_thread.progress_signal.connect(self.update_progress)
        self.crawler_thread.finished_signal.connect(self.crawler_finished)
        self.crawler_thread.start()
    
    def stop_crawler(self):
        """停止爬虫"""
        self.crawler.state = 0
        self.log("正在停止爬虫...")
        self.stop_button.setEnabled(False)
    
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def crawler_finished(self, success, message):
        """爬虫完成回调"""
        self.log(message)
        self.collect_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage('就绪')
        
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "错误", message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PkulawCrawlerGUI()
    sys.exit(app.exec_())