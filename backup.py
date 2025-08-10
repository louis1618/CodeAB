import os
import shutil
import time
import schedule
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import json
import webbrowser
import sys
import customtkinter as ctk

# --- 파일 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FOLDER_PATH = os.path.join(SCRIPT_DIR, 'logs')
SETTINGS_FILE_PATH = os.path.join(SCRIPT_DIR, 'settings.json')
FONT_FILE_PATH = os.path.join(SCRIPT_DIR, 'font', '온글잎 콘콘체.ttf')

CustomFont = None
CustomFont_Bold = None

# --- 설정 관리 함수 ---
def create_default_settings():
    """기본 settings.json 파일을 생성하고 반환"""
    default_settings = {
        "backup_interval_minutes": 10,
        "backup_destination_folder": "",
        "projects": []
    }
    try:
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)
        return default_settings
    except Exception as e:
        messagebox.showerror("오류", f"기본 설정 파일 생성 중 오류 발생: {e}\n프로그램을 종료합니다.")
        sys.exit(1)

def load_settings():
    """settings.json 파일에서 설정 불러오기 및 유효성 검사"""
    if not os.path.exists(SETTINGS_FILE_PATH):
        # 파일이 없으면 새로 생성
        return create_default_settings()
    
    try:
        with open(SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # 필수 요소 누락 여부 확인
            if 'backup_interval_minutes' not in settings or \
               'backup_destination_folder' not in settings or \
               'projects' not in settings:
                return create_default_settings()
            return settings
    except json.JSONDecodeError:
        # JSON 형식 오류 시 새로 생성
        messagebox.showwarning("경고", "settings.json 파일이 손상되어 새로 생성합니다.")
        return create_default_settings()
    except Exception as e:
        messagebox.showerror("오류", f"설정 파일을 불러오는 중 오류 발생: {e}\n프로그램을 종료합니다.")
        sys.exit(1)

def save_settings(settings):
    """설정을 settings.json 파일에 저장"""
    try:
        with open(SETTINGS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"설정 저장 중 오류 발생: {e}")

# --- 백업 로직 함수 ---
def create_backup(settings, log_callback):
    """
    여러 프로젝트를 백업하는 함수
    """
    log_callback("백업 시작...")
    try:
        timestamp_str = datetime.now().strftime('%Y-%m-%d_%HH-%MM-%SS')
        backup_base_path = os.path.join(settings["backup_destination_folder"], f'backup_{timestamp_str}')

        if not os.path.exists(settings["backup_destination_folder"]):
            os.makedirs(settings["backup_destination_folder"])

        for project in settings["projects"]:
            project_name = project['name']
            project_path = project['path']
            exclude_patterns = project.get('exclude_folders', [])
            
            if not os.path.exists(project_path):
                log_callback(f"경로를 찾을 수 없습니다: {project_path}. 이 프로젝트는 건너뜁니다.")
                continue

            destination_path = os.path.join(backup_base_path, project_name)

            log_callback(f"  └─ '{project_name}' 프로젝트 백업 중...")

            try:
                shutil.copytree(
                    project_path, 
                    destination_path,
                    ignore=shutil.ignore_patterns(*exclude_patterns)
                )
                log_callback(f"     └─ '{project_name}' 백업 완료")
            except Exception as e:
                log_callback(f"     └─ '{project_name}' 백업 중 오류 발생: {e}")

        log_callback(f"전체 백업 완료: {backup_base_path}")
        return True, backup_base_path
    except Exception as e:
        log_callback(f"전체 백업 중 오류 발생: {e}")
        return False, None

# --- GUI 애플리케이션 클래스 ---
class BackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        if sys.platform.startswith('win'):
            # Windows에서는 .ico 파일만 지원합니다.
            try:
                self.iconbitmap('CodeAB.ico')
            except tk.TclError:
                # 파일이 없을 경우 오류가 발생할 수 있으므로 예외 처리를 해줍니다.
                print("Warning: CodeAB.ico file not found.")
        # macOS나 Linux의 경우 .png 파일을 사용할 수 있습니다.
        # self.iconphoto(False, tk.PhotoImage(file='CodeAB.png')) 

        global CustomFont, CustomFont_Bold
        if os.path.exists(FONT_FILE_PATH):
            CustomFont = ctk.CTkFont(family="온글잎 콘콘체", size=12)
            CustomFont_Bold = ctk.CTkFont(family="온글잎 콘콘체", size=14, weight="bold")
        else:
            CustomFont = ctk.CTkFont(family="나눔고딕", size=12)
            CustomFont_Bold = ctk.CTkFont(family="나눔고딕", size=14, weight="bold")

        self.title("Code AB")
        self.geometry("800x600")
        
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.settings = load_settings()
        self.backup_thread = None
        self.last_backup_path = None
        self.is_running = True
        self.current_log_file_path = os.path.join(LOG_FOLDER_PATH, f'log_{datetime.now().strftime("%Y-%m-%d_%HH-%MM-%SS")}.txt')
        self.all_log_content = ""

        self.create_widgets()
        self.update_ui_from_settings()

        # 설정 값이 비어있으면 초기 설정 모달 띄우기
        if self.settings.get("backup_destination_folder") == "" or not self.settings.get("projects"):
            self.show_initial_setup_modal()

        self.run_scheduler_thread()
        self.manual_backup()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """GUI 위젯 생성 및 배치"""
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.pack(expand=True, fill='both', padx=10, pady=10)

        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(expand=True, fill='both', padx=10, pady=10)
        self.tabview.add("로그")
        self.tabview.add("설정")

        # 로그 탭
        log_tab = self.tabview.tab("로그")
        
        log_header_frame = ctk.CTkFrame(log_tab, fg_color="transparent")
        log_header_frame.pack(fill='x', padx=5, pady=5)
        ctk.CTkLabel(log_header_frame, text="로그 파일:", font=CustomFont).pack(side='left', padx=5)

        self.log_file_options = self.get_log_files()
        self.log_file_combobox = ctk.CTkComboBox(log_header_frame, values=self.log_file_options, command=self.load_log_file, font=CustomFont)
        self.log_file_combobox.set("현재 로그")
        self.log_file_combobox.pack(side='left', padx=5, expand=True, fill='x')
        
        search_frame = ctk.CTkFrame(log_tab, fg_color="transparent")
        search_frame.pack(fill='x', padx=5, pady=5)
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, placeholder_text="로그 검색...", font=CustomFont)
        self.search_entry.pack(side='left', expand=True, fill='x', padx=5)
        self.search_button = ctk.CTkButton(search_frame, text="검색", command=self.search_logs, font=CustomFont)
        self.search_button.pack(side='left', padx=5)
        
        self.log_text_widget = ctk.CTkTextbox(log_tab, state='disabled', font=CustomFont)
        self.log_text_widget.pack(expand=True, fill='both', padx=5, pady=5)

        log_control_frame = ctk.CTkFrame(log_tab, fg_color="transparent")
        log_control_frame.pack(fill='x', padx=5, pady=5)
        
        self.backup_button = ctk.CTkButton(log_control_frame, text="수동 백업", command=self.manual_backup, font=CustomFont)
        self.backup_button.pack(side='left', padx=5)

        self.open_folder_button = ctk.CTkButton(log_control_frame, text="백업 폴더 열기", command=self.open_last_backup_folder, state="disabled", font=CustomFont)
        self.open_folder_button.pack(side='left', padx=5)

        # 설정 탭
        settings_frame = self.tabview.tab("설정")
        interval_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        interval_frame.pack(fill='x', padx=10, pady=10)
        ctk.CTkLabel(interval_frame, text="백업 주기 (분):", font=CustomFont).pack(side='left', padx=5)
        self.interval_var = tk.StringVar()
        self.interval_entry = ctk.CTkEntry(interval_frame, textvariable=self.interval_var, font=CustomFont)
        self.interval_entry.pack(side='left', padx=5, expand=True, fill='x')
        ctk.CTkButton(interval_frame, text="주기 저장", command=self.save_interval, font=CustomFont).pack(side='left', padx=10)

        dest_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        dest_frame.pack(fill='x', padx=10, pady=5)
        ctk.CTkLabel(dest_frame, text="백업 저장 폴더:", font=CustomFont).pack(side='left', padx=5)
        self.dest_var = tk.StringVar()
        self.dest_entry = ctk.CTkEntry(dest_frame, textvariable=self.dest_var, font=CustomFont)
        self.dest_entry.pack(side='left', padx=5, expand=True, fill='x')
        ctk.CTkButton(dest_frame, text="경로 저장", command=self.save_destination, font=CustomFont).pack(side='left', padx=10)

        ctk.CTkLabel(settings_frame, text="백업할 프로젝트 목록:", font=CustomFont_Bold).pack(anchor='w', padx=10, pady=(10, 5))
        
        self.project_listbox = tk.Listbox(settings_frame, selectmode='SINGLE', height=10, bg="#2b2b2b", fg="#ffffff", selectbackground="#1f538d", selectforeground="#ffffff", borderwidth=0, font=CustomFont)
        self.project_listbox.pack(fill='x', padx=10, pady=5)
        
        project_control_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        project_control_frame.pack(fill='x', padx=10, pady=5)
        ctk.CTkButton(project_control_frame, text="추가", command=self.add_project, font=CustomFont).pack(side='left', padx=5)
        ctk.CTkButton(project_control_frame, text="수정", command=self.edit_project, font=CustomFont).pack(side='left', padx=5)
        ctk.CTkButton(project_control_frame, text="삭제", command=self.remove_project, font=CustomFont).pack(side='left', padx=5)

    def show_initial_setup_modal(self):
        """초기 설정을 안내하는 모달 창 표시"""
        modal = ctk.CTkToplevel(self)
        modal.title("초기 설정 안내")
        modal.geometry("400x200")
        modal.transient(self)
        modal.grab_set()

        ctk.CTkLabel(modal, text="""환영합니다! 자동 백업을 시작하려면
백업 폴더와 프로젝트를 설정해야 합니다.

설정 탭으로 이동하여 설정을 완료해주세요.""", font=CustomFont).pack(padx=20, pady=20)
        
        def close_modal():
            modal.destroy()
            self.tabview.set("설정") # 설정 탭으로 이동

        ctk.CTkButton(modal, text="확인", command=close_modal, font=CustomFont).pack(pady=10)


    def get_log_files(self):
        """logs 폴더의 로그 파일 목록을 반환"""
        if not os.path.exists(LOG_FOLDER_PATH):
            return ["현재 로그"]
        
        log_files = sorted([f for f in os.listdir(LOG_FOLDER_PATH) if f.startswith('log_') and f.endswith('.txt')], reverse=True)
        return ["현재 로그"] + log_files

    def load_log_file(self, filename):
        """선택된 로그 파일을 텍스트 위젯에 로드"""
        self.log_text_widget.configure(state='normal')
        self.log_text_widget.delete("1.0", tk.END)
        
        if filename == "현재 로그":
            content = self.all_log_content
            self.log_text_widget.insert(tk.END, content)
        else:
            try:
                file_path = os.path.join(LOG_FOLDER_PATH, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.log_text_widget.insert(tk.END, content)
            except Exception as e:
                self.log_text_widget.insert(tk.END, f"로그 파일을 불러오는 데 실패했습니다: {e}")
        
        self.log_text_widget.configure(state='disabled')
        self.log_text_widget.see(tk.END)

    def log_message(self, message):
        """GUI와 파일에 로그 메시지 기록"""
        timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
        full_message = f"{timestamp} {message}\n"
        
        self.all_log_content += full_message
        
        current_log_selected = (self.log_file_combobox.get() == "현재 로그")
        
        self.log_text_widget.configure(state='normal')
        if current_log_selected:
            self.log_text_widget.insert(tk.END, full_message)
            self.log_text_widget.see(tk.END)
        self.log_text_widget.configure(state='disabled')
        
        if not os.path.exists(LOG_FOLDER_PATH):
            os.makedirs(LOG_FOLDER_PATH)
        
        with open(self.current_log_file_path, 'a', encoding='utf-8') as f:
            f.write(full_message)

    def search_logs(self):
        """로그 텍스트에서 키워드를 검색하고 결과만 표시"""
        keyword = self.search_var.get().lower()
        
        self.log_text_widget.configure(state='normal')
        self.log_text_widget.delete("1.0", tk.END)
        
        lines = self.all_log_content.split('\n')
        search_results = [line for line in lines if keyword in line.lower()]
        
        if search_results:
            self.log_text_widget.insert(tk.END, "\n".join(search_results))
        else:
            self.log_text_widget.insert(tk.END, "검색 결과가 없습니다.")
        
        self.log_text_widget.configure(state='disabled')
        self.log_text_widget.see(tk.END)

    def update_ui_from_settings(self):
        """설정 데이터를 기반으로 UI 업데이트"""
        self.interval_var.set(str(self.settings["backup_interval_minutes"]))
        self.dest_var.set(self.settings["backup_destination_folder"])
        self.project_listbox.delete(0, tk.END)
        for project in self.settings["projects"]:
            self.project_listbox.insert(tk.END, f"{project['name']} -> {project['path']}")

    def save_interval(self):
        """백업 주기 설정 저장"""
        try:
            interval = int(self.interval_var.get())
            if interval > 0:
                self.settings["backup_interval_minutes"] = interval
                save_settings(self.settings)
                self.log_message(f"백업 주기가 {interval}분으로 변경되었습니다. 다음 백업부터 적용됩니다.")
                self.reschedule_backup()
            else:
                self.log_message("유효하지 않은 백업 주기입니다. 양의 정수를 입력하세요.")
        except ValueError:
            self.log_message("유효하지 않은 백업 주기입니다. 양의 정수를 입력하세요.")

    def save_destination(self):
        """백업 저장 폴더 설정 저장"""
        new_dest = self.dest_var.get().strip()
        if os.path.exists(new_dest):
            self.settings["backup_destination_folder"] = new_dest
            save_settings(self.settings)
            self.log_message(f"백업 저장 폴더가 '{new_dest}'(으)로 변경되었습니다.")
        else:
            self.log_message("유효하지 않은 백업 저장 폴더 경로입니다. 폴더가 존재하는지 확인하세요.")
    
    def add_project(self):
        """프로젝트 추가 팝업"""
        self.project_dialog("추가")

    def edit_project(self):
        """프로젝트 수정 팝업"""
        selected_index = self.project_listbox.curselection()
        if not selected_index:
            self.log_message("수정할 프로젝트를 선택해주세요.")
            return
        self.project_dialog("수정", selected_index[0])

    def project_dialog(self, action, index=None):
        """프로젝트 추가/수정 다이얼로그"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"프로젝트 {action}")
        dialog.geometry("400x250")
        dialog.transient(self)
        dialog.grab_set()

        name_var = tk.StringVar()
        path_var = tk.StringVar()
        exclude_var = tk.StringVar()

        if action == "수정":
            project = self.settings["projects"][index]
            name_var.set(project.get('name', ''))
            path_var.set(project.get('path', ''))
            exclude_var.set(", ".join(project.get('exclude_folders', [])))

        ctk.CTkLabel(dialog, text="커스텀 이름:", font=CustomFont).pack(pady=(10,0))
        ctk.CTkEntry(dialog, textvariable=name_var, width=300, font=CustomFont).pack()
        ctk.CTkLabel(dialog, text="경로:", font=CustomFont).pack(pady=(5,0))
        ctk.CTkEntry(dialog, textvariable=path_var, width=300, font=CustomFont).pack()
        ctk.CTkLabel(dialog, text="제외할 폴더/파일 (쉼표로 구분):", font=CustomFont).pack(pady=(5,0))
        ctk.CTkEntry(dialog, textvariable=exclude_var, width=300, font=CustomFont).pack()

        def save_project():
            name = name_var.get().strip()
            path = path_var.get().strip()
            exclude_str = exclude_var.get().strip()
            
            if not name or not path:
                self.log_message("이름과 경로를 모두 입력해주세요.")
                return
            
            exclude_list = [item.strip() for item in exclude_str.split(',') if item.strip()]
            
            new_project = {"name": name, "path": path, "exclude_folders": exclude_list}
            if action == "추가":
                self.settings["projects"].append(new_project)
            elif action == "수정":
                self.settings["projects"][index] = new_project
            
            save_settings(self.settings)
            self.update_ui_from_settings()
            self.log_message(f"프로젝트가 성공적으로 {action}되었습니다.")
            dialog.destroy()

        ctk.CTkButton(dialog, text="저장", command=save_project, font=CustomFont).pack(pady=10)

    def remove_project(self):
        """선택된 프로젝트 삭제"""
        selected_index = self.project_listbox.curselection()
        if not selected_index:
            self.log_message("삭제할 프로젝트를 선택해주세요.")
            return

        del self.settings["projects"][selected_index[0]]
        save_settings(self.settings)
        self.update_ui_from_settings()
        self.log_message("프로젝트가 성공적으로 삭제되었습니다.")

    def manual_backup(self):
        """수동 백업 버튼 기능"""
        self.log_message("수동 백업이 요청되었습니다.")
        if self.backup_thread and self.backup_thread.is_alive():
            self.log_message("백업 작업이 이미 진행 중입니다.")
            return

        def backup_task():
            success, backup_path = create_backup(self.settings, self.log_message)
            if success:
                self.last_backup_path = backup_path
                self.open_folder_button.configure(state="normal")
            
        self.backup_thread = threading.Thread(target=backup_task, daemon=True)
        self.backup_thread.start()

    def open_last_backup_folder(self):
        """마지막 백업 폴더 열기"""
        if self.last_backup_path and os.path.exists(self.last_backup_path):
            webbrowser.open(self.last_backup_path)
        else:
            self.log_message("열 수 있는 백업 폴더가 없습니다.")

    def run_scheduler_thread(self):
        """스케줄러를 별도 스레드에서 실행"""
        def scheduler_task():
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)
        
        self.scheduler_thread = threading.Thread(target=scheduler_task, daemon=True)
        self.scheduler_thread.start()
        
        self.reschedule_backup()

    def reschedule_backup(self):
        """백업 주기 변경 시 스케줄 재설정"""
        schedule.clear()
        interval = self.settings["backup_interval_minutes"]
        schedule.every(interval).minutes.do(self.manual_backup)

    def on_closing(self):
        """프로그램 종료 시 호출"""
        self.is_running = False
        self.log_message("자동 백업 스크립트가 종료되었습니다.")
        self.destroy()

if __name__ == "__main__":
    app = BackupApp()
    app.mainloop()