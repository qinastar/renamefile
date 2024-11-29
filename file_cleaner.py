import os
import json
import re
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
import sqlite3
from datetime import datetime, timedelta
import winshell

class FileCleanerConfig:
    def __init__(self):
        self.config_file = "cleaner_config.json"
        # 修改配置键名,使其更一致
        self.default_config = {
            "target_extensions": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v"],
            "remove_patterns": [
                "hhd800.com@",
                "18av.mm-cg.com@",
                "javdb.com@",
                "javbus.com@"
            ],
            "cleanup_extensions": [".url", ".ink", ".lnk", ".desktop"],
            "scan_subdirectories": True
        }
        self.config = self.load_config()
    
    def load_config(self):
        try:
            # 如果配置文件存在，则加载它
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 检查加载配置是否包含所必要的键
                    if all(key in loaded_config for key in self.default_config.keys()):
                        return loaded_config
                    else:
                        print("配置文件格式不完整，使用默认配置")
                        return self.create_default_config()
            else:
                # 如果配置文件不存在，创建默认配置
                return self.create_default_config()
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            return self.create_default_config()
    
    def create_default_config(self):
        """创建默认配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.default_config, f, indent=4, ensure_ascii=False)
            print("已创建默认配置文件")
            return self.default_config
        except Exception as e:
            print(f"创建默认配置文件时出错: {e}")
            return self.default_config
    
    def save_config(self, config):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件时出错: {e}")
            messagebox.showerror("错误", f"保存配置文件时出错: {e}")

class HistoryDatabase:
    def __init__(self):
        self.db_file = "cleaner_history.db"
        self.init_database()
    
    def init_database(self):
        with sqlite3.connect(self.db_file) as conn:
            # 使用字符串格式存储时间戳
            def adapt_datetime(dt):
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            
            def convert_datetime(s):
                return datetime.strptime(s.decode(), "%Y-%m-%d %H:%M:%S")
            
            sqlite3.register_adapter(datetime, adapt_datetime)
            sqlite3.register_converter("timestamp", convert_datetime)
            
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    new_path TEXT,
                    timestamp timestamp NOT NULL,
                    is_reverted INTEGER DEFAULT 0,
                    session_id TEXT,
                    details TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cleaning_sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time timestamp NOT NULL,
                    end_time timestamp,
                    target_directory TEXT NOT NULL,
                    files_renamed INTEGER DEFAULT 0,
                    files_deleted INTEGER DEFAULT 0,
                    status TEXT NOT NULL
                )
            ''')
            conn.commit()
    
    def add_operation(self, operation_type, original_path, new_path=None, session_id=None, details=None):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                # 将 datetime 对象转换为字符串
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    '''INSERT INTO operations 
                       (operation_type, original_path, new_path, timestamp, session_id, details) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (operation_type, str(original_path), str(new_path) if new_path else None, 
                     current_time, session_id, details)
                )
                conn.commit()
        except Exception as e:
            print(f"添加操作记录时生: {e}")
    
    def start_cleaning_session(self, directory):
        try:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            with sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO cleaning_sessions 
                       (session_id, start_time, target_directory, status) 
                       VALUES (?, ?, ?, ?)''',
                    (session_id, datetime.now(), directory, "进行中")
                )
                conn.commit()
            return session_id
        except Exception as e:
            print(f"开始清理会话时发生错误: {e}")
            return None
    
    def end_cleaning_session(self, session_id, files_renamed, files_deleted):
        try:
            with sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''UPDATE cleaning_sessions 
                       SET end_time = ?, files_renamed = ?, files_deleted = ?, status = ? 
                       WHERE session_id = ?''',
                    (datetime.now(), files_renamed, files_deleted, "已完成", session_id)
                )
                conn.commit()
        except Exception as e:
            print(f"结束清理会话时发生错误: {e}")
    
    def get_recent_operations(self, limit=100):
        try:
            with sqlite3.connect(self.db_file, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT * FROM operations 
                       WHERE is_reverted = 0 
                       ORDER BY timestamp DESC 
                       LIMIT ?''',
                    (limit,)
                )
                return cursor.fetchall()
        except Exception as e:
            print(f"获取最近操作记录时发生错误: {e}")
            return []
    
    def get_cleaning_sessions(self, limit=50):
        """获取清理会话历史"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM cleaning_sessions
                ORDER BY start_time DESC
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
    
    def mark_as_reverted(self, operation_id):
        """标记操作为已撤销"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE operations SET is_reverted = 1 WHERE id = ?',
                (operation_id,)
            )
            conn.commit()

class FileCleaner:
    def __init__(self):
        self.config = FileCleanerConfig()
        self.history_db = HistoryDatabase()
    
    def clean_directory(self, directory):
        results = {"renamed": [], "deleted": [], "skipped": []}
        session_id = self.history_db.start_cleaning_session(directory)
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = Path(root) / file
                    
                    # 处理视频文件重命名
                    if any(file.lower().endswith(ext) for ext in self.config.config["target_extensions"]):
                        for pattern in self.config.config["remove_patterns"]:
                            if pattern in file:
                                new_name = file.replace(pattern, "")
                                new_path = file_path.parent / new_name
                                
                                # 检查目标文件是否已存在
                                if new_path.exists():
                                    results["skipped"].append((file, new_name, "目标文件已存在"))
                                    self.history_db.add_operation(
                                        "skip",
                                        file_path,
                                        new_path,
                                        session_id,
                                        f"跳过重命名：目标文件 '{new_name}' 已存在"
                                    )
                                    continue
                                
                                file_path.rename(new_path)
                                results["renamed"].append((file, new_name))
                                self.history_db.add_operation(
                                    "rename",
                                    file_path,
                                    new_path,
                                    session_id,
                                    f"从文件名中移除了 '{pattern}'"
                                )
                    
                    # 删除快捷方式文件
                    if any(file.lower().endswith(ext) for ext in self.config.config["cleanup_extensions"]):
                        try:
                            # 尝试使用回收站删除
                            try:
                                winshell.delete_file(str(file_path))
                                results["deleted"].append(file)
                                self.history_db.add_operation(
                                    "delete",
                                    file_path,
                                    None,
                                    session_id,
                                    f"删除了快捷方式文件 (已移至回收站)"
                                )
                            except ImportError:
                                file_path.unlink()
                                results["deleted"].append(file)
                                self.history_db.add_operation(
                                    "delete",
                                    file_path,
                                    None,
                                    session_id,
                                    f"删除了快捷方式文件 (直接删除，不可撤销)"
                                )
                            except Exception as e:
                                print(f"删除文件到回收站失败: {e}")
                                file_path.unlink()
                                results["deleted"].append(file)
                                self.history_db.add_operation(
                                    "delete",
                                    file_path,
                                    None,
                                    session_id,
                                    f"删除了快捷方式文件 (回收站不可用，直接删除，不可撤销)"
                                )
                        except Exception as e:
                            print(f"删除文件失败: {e}")
                            self.history_db.add_operation(
                                "error",
                                file_path,
                                None,
                                session_id,
                                f"删除文件失败: {str(e)}"
                            )
                    
                if not self.config.config["scan_subdirectories"]:
                    break
            
            self.history_db.end_cleaning_session(
                session_id,
                len(results["renamed"]),
                len(results["deleted"])
            )
        except Exception as e:
            self.history_db.add_operation(
                "error",
                directory,
                None,
                session_id,
                f"清理过程中发生错误: {str(e)}"
            )
            raise e
        
        return results
    
    def revert_operation(self, operation):
        op_id, op_type, original_path, new_path, _, is_reverted, _, details = operation
        
        if is_reverted:
            return False
        
        try:
            if op_type == "rename":
                new_path = Path(new_path)
                original_path = Path(original_path)
                if new_path.exists():
                    new_path.rename(original_path)
                    self.history_db.mark_as_reverted(op_id)
                    return True
            elif op_type == "delete":
                # 检查操作详情是否包"不可撤销"标记
                if "不可撤销" in details:
                    self.history_db.mark_as_reverted(op_id)
                    return False
                
                # 尝试从回收站恢复文件
                original_path = Path(original_path)
                try:
                    # 尝试访问回收站
                    recycle_bin = winshell.recycle_bin()
                    # 取过去24小时内删除的文件
                    recent_time = datetime.now() - timedelta(days=1)
                    
                    for item in recycle_bin:
                        if (item.original_filename() == str(original_path) and 
                            item.recycle_date() > recent_time):
                            try:
                                item.undelete()  # 恢复文件
                                self.history_db.mark_as_reverted(op_id)
                                return True
                            except Exception as e:
                                print(f"从回收站恢复文件失败: {e}")
                                break
                    
                    # 如果没有找到文件或恢复失败
                    print("在回收站中未找到文件或恢复失败")
                    self.history_db.mark_as_reverted(op_id)
                    return False
                    
                except ImportError:
                    # 系统不支持回收站操作
                    print("系统不支持回收站操作")
                    self.history_db.mark_as_reverted(op_id)
                    return False
                except Exception as e:
                    print(f"访问回收站时发生错误: {e}")
                    self.history_db.mark_as_reverted(op_id)
                    return False
                
        except Exception as e:
            print(f"撤销操作失败: {e}")
            return False
        return False

class FileCleanerGUI:
    def __init__(self):
        self.cleaner = FileCleaner()
        self.current_sidebar = None
        self.sidebar_showing = False
        self.setup_gui()
    
    def ease_out_cubic(self, x):
        # 缓出三次方缓动函数，让动画结束时更加平滑
        return 1 - pow(1 - x, 3)
    
    def ease_in_cubic(self, x):
        # 缓入三次方缓动函数，让动画开始时更加平滑
        return x * x * x
    
    def ease_in_out_cubic(self, x):
        # 缓入缓出三次方缓动函数，两端都平滑
        if x < 0.5:
            return 4 * x * x * x
        else:
            return 1 - pow(-2 * x + 2, 3) / 2
    
    def toggle_sidebar(self, sidebar_frame):
        try:
            if self.current_sidebar:
                if self.current_sidebar == sidebar_frame:
                    # 如果点击的是当前显示的侧边栏，则隐藏它
                    self.hide_sidebar()
                else:
                    # 如果点击的是不同的侧边栏，直接切换
                    old_sidebar = self.current_sidebar
                    self.current_sidebar = sidebar_frame
                    
                    # 隐藏旧的侧边栏
                    old_sidebar.place_forget()
                    
                    # 显示新的侧边栏
                    sidebar_frame.place(
                        relx=0.65,
                        rely=0,
                        relwidth=0.35,
                        relheight=1.0
                    )
                    self.sidebar_showing = True
                    
                    # 如果是切换到历史记录，确保内容是最新的
                    if sidebar_frame == self.history_sidebar:
                        for child in sidebar_frame.winfo_children():
                            if isinstance(child, ctk.CTkFrame):
                                for subchild in child.winfo_children():
                                    if isinstance(subchild, ctk.CTkScrollableFrame):
                                        self.update_history_content(subchild)
                                        break
                                break
            else:
                # 如果当前没有显示侧边栏，则显示新的
                self.show_sidebar(sidebar_frame)
        except Exception as e:
            print(f"切换侧边栏时发生错误: {e}")
            self.cleanup_sidebar()
    
    def show_sidebar(self, sidebar_frame):
        if self.sidebar_showing:
            return
            
        try:
            self.current_sidebar = sidebar_frame
            self.sidebar_showing = True
            
            if sidebar_frame.winfo_exists():
                # 直接设置侧边栏的位置
                sidebar_frame.place(
                    relx=0.65,
                    rely=0,
                    relwidth=0.35,
                    relheight=1.0
                )
        except Exception as e:
            print(f"显示侧边栏时发生错误: {e}")
            self.current_sidebar = None
            self.sidebar_showing = False
    
    def hide_sidebar(self):
        if not self.sidebar_showing or not self.current_sidebar:
            return
            
        try:
            if self.current_sidebar and self.current_sidebar.winfo_exists():
                self.current_sidebar.place_forget()
            self.cleanup_sidebar()
        except Exception as e:
            print(f"隐藏侧边栏时发生错误: {e}")
            self.cleanup_sidebar()
    
    def cleanup_sidebar(self):
        """清理侧边栏状态的辅助方法"""
        if self.current_sidebar and self.current_sidebar.winfo_exists():
            self.current_sidebar.place_forget()
        self.current_sidebar = None
        self.sidebar_showing = False
    
    def setup_gui(self):
        # 设置较小的 DPI 缩放
        ctk.set_widget_scaling(1.0)  # 降低控件缩放比例
        ctk.set_window_scaling(1.0)  # 降低窗口缩放比例
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("文件清理工具")
        
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 计算窗口尺寸和位置（使用更小的默认尺寸）
        window_width = 800  # 减小默认宽度
        window_height = 600  # 减小默认高度
        
        # 确保窗口不会超出屏幕
        window_width = min(window_width, screen_width - 100)
        window_height = min(window_height, screen_height - 100)
        
        # 计算窗口位置使其居中
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口大小和位置
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 设置最小窗口大小
        self.root.minsize(600, 400)  # 设置更小的最小尺寸
        
        # 添加窗口大小变化事件处理
        self.root.bind("<Configure>", self.on_window_configure)
        
        # 创建背景框架
        self.bg_frame = ctk.CTkFrame(
            self.root,
            fg_color=("gray90", "gray10"),  # 亮/暗模式色
            corner_radius=15
        )
        self.bg_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 创建主框架（带圆角和阴影）
        self.main_frame = ctk.CTkFrame(
            self.bg_frame,
            corner_radius=12,
            fg_color=("gray85", "gray15"),
            border_width=1,
            border_color=("gray70", "gray25")
        )
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # 创建左侧操作区域（带角和阴影）
        self.left_frame = ctk.CTkFrame(
            self.main_frame,
            width=300,
            corner_radius=10,
            fg_color=("gray80", "gray20"),
            border_width=1,
            border_color=("gray70", "gray25")
        )
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)
        
        # 创建右侧日志区域（带圆角和阴影）
        self.right_frame = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color=("gray80", "gray20"),
            border_width=1,
            border_color=("gray70", "gray25")
        )
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # 添加标题（使用更现代的字体和样式）
        title_label = ctk.CTkLabel(
            self.left_frame,
            text="文件清理工具",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=24, weight="bold"),
            text_color=("gray20", "gray90")
        )
        title_label.pack(pady=(20, 15))
        
        # 添加说明文字（改样式）
        description = (
            "这个工具可以帮助你：\n\n"
            "1. 清理文件名中的网站标记\n"
            "2. 删除指定类型的文件\n"
            "3. 记录所有操作并支持撤销\n"
        )
        desc_label = ctk.CTkLabel(
            self.left_frame,
            text=description,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            justify="left",
            wraplength=250,
            text_color=("gray30", "gray80")
        )
        desc_label.pack(pady=(0, 20))
        
        # 选择目录区域（改进样）
        dir_frame = ctk.CTkFrame(
            self.left_frame,
            corner_radius=8,
            fg_color=("gray85", "gray15")
        )
        dir_frame.pack(fill="x", padx=15, pady=5)
        
        # 路径输入区域样式改进
        path_label = ctk.CTkLabel(
            dir_frame,
            text="目录路径",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            text_color=("gray20", "gray90")
        )
        path_label.pack(pady=(10, 0), padx=15, anchor="w")
        
        # 输入框和按钮容器
        path_input_frame = ctk.CTkFrame(
            dir_frame,
            fg_color="transparent"
        )
        path_input_frame.pack(fill="x", padx=15, pady=5)
        
        # 美化输入框
        self.path_entry = ctk.CTkEntry(
            path_input_frame,
            placeholder_text="输入或选择目录路径",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            height=32,
            corner_radius=6
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # 美化浏览按钮
        self.select_dir_btn = ctk.CTkButton(
            path_input_frame,
            text="浏览",
            command=self.select_directory,
            width=60,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        self.select_dir_btn.pack(side="right")
        
        # 美化确认按钮
        self.confirm_path_btn = ctk.CTkButton(
            dir_frame,
            text="确认路径",
            command=self.confirm_directory,
            width=120,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color="#17a2b8",
            hover_color="#138496"
        )
        self.confirm_path_btn.pack(pady=10)
        
        # 状态标签样式改进
        self.path_status_label = ctk.CTkLabel(
            dir_frame,
            text="状态：未选择目录",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            wraplength=250,
            text_color=("gray40", "gray70")
        )
        self.path_status_label.pack(pady=(0, 10))
        
        # 作按钮区域样式改
        buttons_frame = ctk.CTkFrame(
            self.left_frame,
            fg_color="transparent"
        )
        buttons_frame.pack(fill="x", padx=15, pady=20)
        
        # 美化设置按钮
        self.settings_btn = ctk.CTkButton(
            buttons_frame,
            text="规则设置",
            command=lambda: self.toggle_sidebar(self.settings_sidebar),
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color=("#6c757d", "#495057"),
            hover_color=("#5a6268", "#383d41")
        )
        self.settings_btn.pack(pady=5)
        
        # 美化历史记录按钮
        self.history_btn = ctk.CTkButton(
            buttons_frame,
            text="历史记录",
            command=lambda: self.toggle_sidebar(self.history_sidebar),
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color=("#6c757d", "#495057"),
            hover_color=("#5a6268", "#383d41")
        )
        self.history_btn.pack(pady=5)
        
        # 美化清理按钮
        self.clean_btn = ctk.CTkButton(
            buttons_frame,
            text="开始清理",
            command=self.start_cleaning,
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.clean_btn.pack(pady=5)
        
        # 右侧日志区域标题样式改进
        log_label = ctk.CTkLabel(
            self.right_frame,
            text="操作日志",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
            text_color=("gray20", "gray90")
        )
        log_label.pack(pady=(15, 10))
        
        # 美化日志文本框
        self.result_text = ctk.CTkTextbox(
            self.right_frame,
            width=600,
            height=600,
            corner_radius=8,
            border_width=1,
            border_color=("gray70", "gray30"),
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)
        )
        self.result_text.pack(pady=10, padx=15, fill="both", expand=True)
        
        # 创建设置侧边栏
        self.settings_sidebar = ctk.CTkFrame(self.root)
        self.setup_settings_sidebar()
        
        # 创建历史记录侧边栏
        self.history_sidebar = ctk.CTkFrame(self.root)
        self.setup_history_sidebar()
    
    def setup_settings_sidebar(self):
        # 设置侧边栏样式
        self.settings_sidebar.configure(
            corner_radius=15,
            border_width=1,
            border_color=("gray70", "gray30"),
            fg_color=("gray85", "gray15")
        )
        
        # 创建主容器，使用grid布局
        main_container = ctk.CTkFrame(
            self.settings_sidebar,
            fg_color="transparent"
        )
        main_container.pack(fill="both", expand=True)
        
        # 配置grid权重，使内容区域可以伸缩
        main_container.grid_rowconfigure(1, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # 标题栏样式
        header_frame = ctk.CTkFrame(
            main_container,
            fg_color="transparent"
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="规则设置",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
            text_color=("gray20", "gray90")
        )
        title_label.pack(side="left", padx=10)
        
        close_btn = ctk.CTkButton(
            header_frame,
            text="×",
            width=30,
            height=30,
            corner_radius=15,
            font=ctk.CTkFont(size=16),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self.hide_sidebar
        )
        close_btn.pack(side="right", padx=10)
        
        # 创建滚动框架
        scroll_frame = ctk.CTkScrollableFrame(main_container)
        scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # 目标文件扩展名设置
        self.target_ext_text = ctk.CTkTextbox(
            scroll_frame,
            width=250,
            height=60,  # 初始高度
            wrap="word"  # 自动换行
        )
        self.target_ext_text.insert("1.0", "\n".join(self.cleaner.config.config["target_extensions"]))
        self.add_setting_item(
            scroll_frame,
            "目标文件扩展名",
            "需要处理的文件格式，每行一个（例如: .mp4）",
            self.target_ext_text
        )
        
        # 要删除的模式设置
        self.patterns_text = ctk.CTkTextbox(
            scroll_frame,
            width=250,
            height=100,  # 初始高度
            wrap="word"  # 自动换行
        )
        self.patterns_text.insert("1.0", "\n".join(self.cleaner.config.config["remove_patterns"]))
        self.add_setting_item(
            scroll_frame,
            "需要删除的文件名模式",
            "要从文件名中删除的文本模式，每行一个",
            self.patterns_text
        )
        
        # 要清理的文件扩展名设置
        self.cleanup_ext_text = ctk.CTkTextbox(
            scroll_frame,
            width=250,
            height=60,  # 初始高度
            wrap="word"  # 自动换行
        )
        self.cleanup_ext_text.insert("1.0", "\n".join(self.cleaner.config.config["cleanup_extensions"]))
        self.add_setting_item(
            scroll_frame,
            "要清理的文件扩展名",
            "要删除的文件格式，每行一个（例如: .url）",
            self.cleanup_ext_text
        )
        
        # 是否扫描子目录
        self.scan_subdirs_var = ctk.BooleanVar(value=self.cleaner.config.config["scan_subdirectories"])
        scan_subdirs_checkbox = ctk.CTkCheckBox(
            scroll_frame,
            text="扫描子目录",
            variable=self.scan_subdirs_var
        )
        scan_subdirs_checkbox.pack(pady=10)
        
        # 创建底部按钮容器
        bottom_frame = ctk.CTkFrame(
            main_container,
            fg_color="transparent"
        )
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        # 保存按钮
        save_btn = ctk.CTkButton(
            bottom_frame,
            text="保存设置",
            command=self.save_current_settings,
            width=120,
            fg_color="#28a745",
            hover_color="#218838"
        )
        save_btn.pack(pady=10)
    
    def add_setting_item(self, parent, title, description, entry_widget):
        """辅助方法：添加设置项"""
        # 标题
        label = ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold")
        )
        label.pack(pady=(10, 0), anchor="w")
        
        # 描述
        desc = ctk.CTkLabel(
            parent,
            text=description,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color="gray"
        )
        desc.pack(anchor="w")
        
        # 输入框
        entry_widget.pack(pady=(5, 10))
    
    def save_current_settings(self):
        """保存当前设置"""
        new_config = {
            "target_extensions": [
                ext.strip() for ext in self.target_ext_text.get("1.0", "end-1c").split("\n")
                if ext.strip()  # 只保留非空行
            ],
            "remove_patterns": [
                pattern.strip() for pattern in self.patterns_text.get("1.0", "end-1c").split("\n")
                if pattern.strip()  # 只保留非空行
            ],
            "cleanup_extensions": [
                ext.strip() for ext in self.cleanup_ext_text.get("1.0", "end-1c").split("\n")
                if ext.strip()  # 只保留非空行
            ],
            "scan_subdirectories": self.scan_subdirs_var.get()
        }
        self.cleaner.config.save_config(new_config)
        self.cleaner.config.config = new_config
        self.hide_sidebar()
        messagebox.showinfo("成功", "设置已保存")
    
    def setup_history_sidebar(self):
        # 置侧边栏样式
        self.history_sidebar.configure(
            corner_radius=15,
            border_width=1,
            border_color=("gray70", "gray30"),
            fg_color=("gray85", "gray15")
        )
        
        # 创建主容器，使用grid布局
        main_container = ctk.CTkFrame(
            self.history_sidebar,
            fg_color="transparent"
        )
        main_container.pack(fill="both", expand=True)
        
        # 配置grid权重
        main_container.grid_rowconfigure(2, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # 标题栏
        header_frame = ctk.CTkFrame(
            main_container,
            fg_color="transparent"
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="操作历史",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
            text_color=("gray20", "gray90")
        )
        title_label.pack(side="left", padx=10)
        
        close_btn = ctk.CTkButton(
            header_frame,
            text="×",
            width=30,
            height=30,
            corner_radius=15,
            font=ctk.CTkFont(size=16),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self.hide_sidebar
        )
        close_btn.pack(side="right", padx=10)
        
        # 说明文字
        desc_label = ctk.CTkLabel(
            main_container,
            text="这里显示最近的100条操作记录，您可以选择撤销某些操作。\n注意：已删除的文件无法恢复。",
            wraplength=250,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color=("gray30", "gray80")
        )
        desc_label.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        # 历史记录显示区域
        history_frame = ctk.CTkScrollableFrame(
            main_container,
            corner_radius=8
        )
        history_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # 添加历史记录内容
        self.update_history_content(history_frame)
    
    def update_history_content(self, frame):
        # 清除现有内容
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            operations = self.cleaner.history_db.get_recent_operations()
            print(f"获取到 {len(operations)} 条历史记录")  # 添加调试信息
            
            if not operations:
                no_records_label = ctk.CTkLabel(
                    frame,
                    text="暂无操作记录",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=14)
                )
                no_records_label.pack(pady=20)
            else:
                for op in operations:
                    self.create_history_item(frame, op)
        except Exception as e:
            print(f"更新历史记录时发生错误: {e}")  # 添加错误日志
            error_label = ctk.CTkLabel(
                frame,
                text=f"加载历史记录时发生错误: {str(e)}",
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=14),
                text_color="red"
            )
            error_label.pack(pady=20)
    
    def create_history_item(self, frame, operation):
        try:
            op_id, op_type, original_path, new_path, timestamp_str, is_reverted, session_id, details = operation
            
            # 将字符串转换为 datetime 对象
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except:
                timestamp = datetime.now()  # 如果转换失败，使用当前时间
            
            # 为每个操作创建一个框架
            op_frame = ctk.CTkFrame(
                frame,
                corner_radius=8,
                fg_color=("gray85", "gray15")
            )
            op_frame.pack(fill="x", padx=5, pady=5)
            
            # 时间戳
            time_label = ctk.CTkLabel(
                op_frame,
                text=f"{timestamp:%Y-%m-%d %H:%M:%S}",
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold")
            )
            time_label.pack(anchor="w", padx=10, pady=(5, 0))
            
            # 操作详情
            if op_type == "rename":
                details_text = f"重命名:\n{os.path.basename(original_path)}\n→\n{os.path.basename(new_path)}"
            else:
                details_text = f"删除:\n{os.path.basename(original_path)}"
            
            if details:  # 如果有额外的详细信息
                details_text += f"\n详情: {details}"
            
            op_details = ctk.CTkLabel(
                op_frame,
                text=details_text,
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                justify="left",
                wraplength=250
            )
            op_details.pack(anchor="w", padx=10, pady=(5, 5))
            
            # 只有未撤销的操作才显示撤销按钮
            if not is_reverted:
                revert_btn = ctk.CTkButton(
                    op_frame,
                    text="撤销",
                    command=lambda o=operation: self.revert_history_operation(o),
                    width=80,
                    height=25,
                    corner_radius=6,
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                    fg_color="#dc3545",
                    hover_color="#c82333"
                )
                revert_btn.pack(anchor="w", padx=10, pady=(0, 5))
            else:
                status_label = ctk.CTkLabel(
                    op_frame,
                    text="已撤销",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                    text_color="gray"
                )
                status_label.pack(anchor="w", padx=10, pady=(0, 5))
        except Exception as e:
            print(f"创建历史记录项时发生错误: {e}")
            print(f"操作数据: {operation}")  # 添加更多调试信息
    
    def revert_history_operation(self, operation):
        op_id, op_type, original_path, new_path, _, _, _, details = operation
        
        # 检查是否是不可撤销的删除操作
        if op_type == "delete" and "不可撤销" in details:
            messagebox.showwarning("警告", 
                "此删除操作无法撤销，因为：\n"
                "1. 系统不支持回收站功能\n"
                "2. 或回收站功能不可用\n\n"
                "文件已被直接删除且无法恢复。")
            return
        
        if op_type == "rename":
            message = f"确定要将文件\n'{os.path.basename(new_path)}'\n改回为\n'{os.path.basename(original_path)}'\n吗？"
        else:
            message = (f"确定要尝试恢复删除的文件吗？\n"
                      f"文件：{os.path.basename(original_path)}\n"
                      f"注意：将尝试从回收站恢复文件。")
        
        if messagebox.askyesno("确认撤销", message):
            result = self.cleaner.revert_operation(operation)
            if result:
                messagebox.showinfo("成功", "操作已撤销")
            else:
                if op_type == "delete":
                    messagebox.showwarning("警告", 
                        "无法恢复文件，可能是因为：\n"
                        "1. 文件已从回收站清除\n"
                        "2. 回收站中找不到匹配的文件\n"
                        "3. 系统不支持回收站操作\n"
                        "4. 恢复过程中发生错误\n\n"
                        "该操作已标记为已撤销。")
                else:
                    messagebox.showerror("错误", "撤销操作失败，可能是文件已经不存在或被移动")
            
            # 立即刷新历史记录
            if self.current_sidebar == self.history_sidebar:
                for child in self.history_sidebar.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for subchild in child.winfo_children():
                            if isinstance(subchild, ctk.CTkScrollableFrame):
                                self.update_history_content(subchild)
                                # 强制更新显示
                                self.history_sidebar.update()
                                break
                        break
    
    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.confirm_directory()
    
    def confirm_directory(self):
        path = self.path_entry.get().strip()
        if not path:
            messagebox.showerror("错误", "请输入或选择目录路径")
            return
        
        if not os.path.exists(path):
            messagebox.showerror("错误", "目录不存在")
            return
        
        if not os.path.isdir(path):
            messagebox.showerror("错误", "所选路径不是目录")
            return
        
        self.path_status_label.configure(
            text=f"状态：已选择\n{path}",
            text_color="#28a745"
        )
    
    def start_cleaning(self):
        directory = self.path_entry.get().strip()
        if not directory or not os.path.isdir(directory):
            messagebox.showerror("错误", "请先选择有效的目录")
            return
        
        try:
            results = self.cleaner.clean_directory(directory)
            
            # 更新日志显示
            self.result_text.delete("1.0", "end")
            self.result_text.insert("end", "清理完成！\n\n")
            
            if results["renamed"]:
                self.result_text.insert("end", "重命名的文件：\n")
                for old_name, new_name in results["renamed"]:
                    self.result_text.insert("end", f"  {old_name} -> {new_name}\n")
            
            if results["skipped"]:
                self.result_text.insert("end", "\n跳过的文件：\n")
                for old_name, new_name, reason in results["skipped"]:
                    self.result_text.insert("end", f"  {old_name} -> {new_name} ({reason})\n")
            
            if results["deleted"]:
                self.result_text.insert("end", "\n删除的快捷方式：\n")
                for file in results["deleted"]:
                    self.result_text.insert("end", f"  {file}\n")
            
            # 如果历史记录侧边栏已经打开，则更新其内容
            if self.current_sidebar == self.history_sidebar:
                for child in self.history_sidebar.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for subchild in child.winfo_children():
                            if isinstance(subchild, ctk.CTkScrollableFrame):
                                self.update_history_content(subchild)
                                # 强制更新显示
                                self.history_sidebar.update()
                                break
                        break
            
            # 显示成功消息，包含跳过的文件数量
            messagebox.showinfo("成功", 
                f"清理完成！\n"
                f"重命名: {len(results['renamed'])} 个文件\n"
                f"删除: {len(results['deleted'])} 个文件\n"
                f"跳过: {len(results['skipped'])} 个文件"
            )
        
        except Exception as e:
            messagebox.showerror("错误", f"清理过程中发生错误：{str(e)}")
            print(f"错误详情: {e}")
    
    def run(self):
        self.root.mainloop()
    
    def save_settings(self, video_ext_entry, patterns_entry, shortcut_ext_entry, scan_subdirs_var, settings_window):
        new_config = {
            "video_extensions": [ext.strip() for ext in video_ext_entry.split(",")],
            "remove_patterns": [pattern.strip() for pattern in patterns_entry.split(",")],
            "shortcut_extensions": [ext.strip() for ext in shortcut_ext_entry.split(",")],
            "scan_subdirectories": scan_subdirs_var
        }
        self.cleaner.config.save_config(new_config)
        self.cleaner.config.config = new_config
        self.hide_sidebar()
        messagebox.showinfo("成功", "设置已保存")
    
    def on_window_configure(self, event):
        """处理窗口大小变化事件"""
        if event.widget == self.root:
            # 如果侧边栏是打开的，调整其位置
            if self.current_sidebar and self.sidebar_showing:
                self.current_sidebar.place(
                    relx=0.65,
                    rely=0,
                    relwidth=0.35,
                    relheight=1.0
                )

if __name__ == "__main__":
    app = FileCleanerGUI()
    app.run() 