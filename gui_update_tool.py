import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk


APP_NAME = "ZAY_POS"
DEFAULT_REPO = "focuseyes1989-debug/ZAY_POS"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROJECT_ROOT = Path(__file__).resolve().parent


class ReleaseToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ZAY POS - Release Tool")
        self.root.geometry("980x720")
        self.root.minsize(880, 620)

        self.log_queue = queue.Queue()
        self.current_process = None
        self.worker_thread = None
        self.running = True
        self.cancel_requested = False

        self.version_var = tk.StringVar(value=self.detect_default_version())
        self.token_var = tk.StringVar(value=os.getenv("GITHUB_TOKEN", ""))
        self.repo_var = tk.StringVar(value=DEFAULT_REPO)
        self.recreate_release_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.flush_log_queue)

    def setup_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            header,
            text="ZAY POS Release Tool",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Build EXE, build launcher, generate update, and upload release.",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        settings = ttk.LabelFrame(outer, text="Release Settings", padding=10)
        settings.grid(row=1, column=0, sticky="ew", pady=(12, 10))

        ttk.Label(settings, text="Version").grid(row=0, column=0, sticky="w")
        self.version_entry = ttk.Entry(settings, textvariable=self.version_var, width=18)
        self.version_entry.grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(settings, text="GitHub Repo").grid(row=0, column=2, sticky="w")
        self.repo_entry = ttk.Entry(settings, textvariable=self.repo_var, width=34)
        self.repo_entry.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(settings, text="GitHub Token").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.token_entry = ttk.Entry(settings, textvariable=self.token_var, width=46, show="*")
        self.token_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))

        self.recreate_check = ttk.Checkbutton(
            settings,
            text="Delete and recreate release if it already exists",
            variable=self.recreate_release_var,
        )
        self.recreate_check.grid(row=2, column=1, columnspan=3, sticky="w", pady=(8, 0))
        settings.columnconfigure(3, weight=1)

        actions = ttk.LabelFrame(outer, text="Actions", padding=10)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        self.build_exe_btn = ttk.Button(actions, text="1. Build EXE", command=self.run_build_exe)
        self.build_exe_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.build_launcher_btn = ttk.Button(
            actions,
            text="2. Build Launcher",
            command=self.run_build_launcher,
        )
        self.build_launcher_btn.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        self.generate_btn = ttk.Button(
            actions,
            text="3. Generate Update",
            command=self.run_generate_update,
        )
        self.generate_btn.grid(row=0, column=2, sticky="ew", padx=(0, 8))

        self.upload_btn = ttk.Button(actions, text="4. Upload Update", command=self.run_upload_update)
        self.upload_btn.grid(row=0, column=3, sticky="ew", padx=(0, 8))

        self.run_all_btn = ttk.Button(actions, text="Run All", command=self.run_all)
        self.run_all_btn.grid(row=0, column=4, sticky="ew")

        self.view_version_btn = ttk.Button(actions, text="View version.json", command=self.view_version_json)
        self.view_version_btn.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(8, 0))

        self.open_update_btn = ttk.Button(actions, text="Open update_build", command=self.open_update_folder)
        self.open_update_btn.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))

        self.open_dist_btn = ttk.Button(actions, text="Open dist", command=self.open_dist_folder)
        self.open_dist_btn.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(8, 0))

        self.stop_btn = ttk.Button(actions, text="Stop", command=self.stop_current_task, state="disabled")
        self.stop_btn.grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=(8, 0))

        self.clear_btn = ttk.Button(actions, text="Clear Log", command=self.clear_log)
        self.clear_btn.grid(row=1, column=4, sticky="ew", pady=(8, 0))

        for index in range(5):
            actions.columnconfigure(index, weight=1)

        log_frame = ttk.LabelFrame(outer, text="Output Log", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew")
        self.output_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=22,
        )
        self.output_text.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        footer = ttk.Frame(outer)
        footer.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=260)
        self.progress.grid(row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

    def detect_default_version(self):
        for path in (
            PROJECT_ROOT / "update_build" / "version.json",
            PROJECT_ROOT / "version.json",
            PROJECT_ROOT / "update_server" / "version.json",
        ):
            try:
                with path.open("r", encoding="utf-8") as file:
                    version = json.load(file).get("version", "")
                if VERSION_RE.match(version):
                    return version
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass
        return "1.0.0"

    def validate_version(self):
        version = self.version_var.get().strip()
        if not VERSION_RE.match(version):
            messagebox.showerror("Invalid Version", "Version must use x.y.z format, for example 1.0.8.")
            return None
        return version

    def validate_repo(self):
        repo = self.repo_var.get().strip()
        if not REPO_RE.match(repo):
            messagebox.showerror("Invalid Repo", "GitHub repo must use owner/name format.")
            return None
        return repo

    def get_zip_path(self, version):
        return PROJECT_ROOT / "update_build" / f"{APP_NAME}_v{version}_update.zip"

    def build_python_command(self, *parts):
        return [sys.executable, *parts]

    def run_build_exe(self):
        version = self.validate_version()
        if version:
            self.start_tasks([self.create_build_exe_task(version)])

    def run_build_launcher(self):
        version = self.validate_version()
        if version:
            self.start_tasks([self.create_build_launcher_task(version)])

    def run_generate_update(self):
        version = self.validate_version()
        repo = self.validate_repo()
        if version and repo:
            self.start_tasks([self.create_generate_update_task(version, repo)])

    def run_upload_update(self):
        version = self.validate_version()
        if not version:
            return

        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("GitHub Token Required", "Enter a GitHub token or set GITHUB_TOKEN.")
            return

        repo = self.validate_repo()
        if not repo:
            return

        zip_path = self.get_zip_path(version)
        if not zip_path.exists():
            messagebox.showerror("Zip Not Found", f"Update zip was not found:\n{zip_path}")
            return

        self.start_tasks([self.create_upload_update_task(version, token, repo, zip_path)])

    def run_all(self):
        version = self.validate_version()
        if not version:
            return

        token = self.token_var.get().strip()
        repo = self.validate_repo()
        if not repo:
            return
        if not token:
            should_continue = messagebox.askyesno(
                "Run Without Upload?",
                "No GitHub token was entered. Run build and generate steps only?",
            )
            if not should_continue:
                return

        tasks = [
            self.create_build_exe_task(version),
            self.create_build_launcher_task(version),
            self.create_generate_update_task(version, repo),
        ]
        if token:
            tasks.append(self.create_upload_update_task(version, token, repo, self.get_zip_path(version)))

        self.start_tasks(tasks)

    def create_build_exe_task(self, version):
        return {
            "name": "Build EXE",
            "command": self.build_python_command("build_exe.py"),
            "input": f"{version}\n",
        }

    def create_build_launcher_task(self, version):
        return {
            "name": "Build Launcher",
            "command": self.build_python_command("build_launcher.py"),
            "input": f"{version}\n",
        }

    def create_generate_update_task(self, version, repo):
        return {
            "name": "Generate Update",
            "command": self.build_python_command(
                "scripts/generate_update.py",
                "--version",
                version,
                "--repo",
                repo,
            ),
            "input": "\n",
        }

    def create_upload_update_task(self, version, token, repo, zip_path):
        release_answer = "y" if self.recreate_release_var.get() else "n"
        return {
            "name": "Upload Update",
            "command": self.build_python_command(
                "scripts/upload_update.py",
                "--version",
                version,
                "--zip",
                str(zip_path),
                "--repo",
                repo,
            ),
            "input": f"{release_answer}\n",
            "env": {"GITHUB_TOKEN": token},
            "mask": token,
        }

    def start_tasks(self, tasks):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Task Running", "Please wait for the current task to finish.")
            return

        self.cancel_requested = False
        self.set_busy(True)
        self.worker_thread = threading.Thread(target=self.run_tasks_worker, args=(tasks,), daemon=True)
        self.worker_thread.start()

    def run_tasks_worker(self, tasks):
        total = len(tasks)
        all_ok = True
        try:
            for index, task in enumerate(tasks, start=1):
                if self.cancel_requested:
                    all_ok = False
                    break
                self.log_section(f"Step {index}/{total}: {task['name']}")
                if not self.run_subprocess(task):
                    all_ok = False
                    break
            if all_ok and not self.cancel_requested:
                self.queue_status("Completed successfully")
                self.queue_log("\nAll selected release steps completed successfully.")
            elif self.cancel_requested:
                self.queue_status("Cancelled")
                self.queue_log("\nTask cancelled.")
            else:
                self.queue_status("Failed")
                self.queue_log("\nWorkflow stopped because a step failed.")
        finally:
            self.current_process = None
            self.log_queue.put(("busy", False))

    def run_subprocess(self, task):
        command = task["command"]
        command_for_log = self.command_to_text(command)
        if task.get("mask"):
            command_for_log = command_for_log.replace(task["mask"], "***")

        self.queue_status(f"Running: {task['name']}")
        self.queue_log(f"Command: {command_for_log}")

        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.setdefault("PYTHONUTF8", "1")
            env.update(task.get("env", {}))

            self.current_process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                startupinfo=startupinfo,
            )

            input_text = task.get("input", "")
            if input_text:
                stdin_handle = self.current_process.stdin
                if stdin_handle is not None:
                    try:
                        stdin_handle.write(input_text)
                        stdin_handle.flush()
                        stdin_handle.close()
                    except (BrokenPipeError, OSError):
                        pass

            assert self.current_process.stdout is not None
            for line in self.current_process.stdout:
                if task.get("mask"):
                    line = line.replace(task["mask"], "***")
                self.queue_log(line.rstrip())
                if self.cancel_requested:
                    self.terminate_current_process()
                    break

            return_code = self.current_process.wait()
            if self.cancel_requested:
                return False
            if return_code == 0:
                self.queue_log(f"{task['name']} completed successfully.")
                return True
            self.queue_log(f"{task['name']} failed with exit code {return_code}.")
            return False
        except FileNotFoundError as exc:
            self.queue_log(f"Could not start command: {exc}")
            return False
        except Exception as exc:
            self.queue_log(f"Error while running {task['name']}: {exc}")
            return False
        finally:
            self.current_process = None

    def command_to_text(self, command):
        return " ".join(f'"{part}"' if " " in str(part) else str(part) for part in command)

    def terminate_current_process(self):
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def stop_current_task(self):
        self.cancel_requested = True
        self.terminate_current_process()
        self.queue_status("Stopping...")

    def set_busy(self, is_busy):
        state = "disabled" if is_busy else "normal"
        buttons = [
            self.build_exe_btn,
            self.build_launcher_btn,
            self.generate_btn,
            self.upload_btn,
            self.run_all_btn,
            self.view_version_btn,
            self.open_update_btn,
            self.open_dist_btn,
            self.clear_btn,
        ]
        for button in buttons:
            button.config(state=state)
        self.stop_btn.config(state="normal" if is_busy else "disabled")
        if is_busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def log_section(self, title):
        self.queue_log("")
        self.queue_log("=" * 72)
        self.queue_log(title)
        self.queue_log("=" * 72)

    def queue_log(self, message):
        self.log_queue.put(("log", message))

    def queue_status(self, message):
        self.log_queue.put(("status", message))

    def flush_log_queue(self):
        if not self.running:
            return
        try:
            while True:
                kind, message = self.log_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(message)
                elif kind == "busy":
                    self.set_busy(message)
                else:
                    self.output_text.insert(tk.END, f"{message}\n")
                    self.output_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.flush_log_queue)

    def clear_log(self):
        self.output_text.delete("1.0", tk.END)

    def view_version_json(self):
        path = PROJECT_ROOT / "update_build" / "version.json"
        if not path.exists():
            messagebox.showerror("version.json Not Found", f"File was not found:\n{path}")
            return
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showerror("Read Failed", f"Could not read version.json:\n{exc}")
            return

        self.log_section("update_build/version.json")
        self.queue_log(json.dumps(data, indent=2, ensure_ascii=False))
        self.queue_status("version.json displayed")

    def open_update_folder(self):
        self.open_folder(PROJECT_ROOT / "update_build")

    def open_dist_folder(self):
        self.open_folder(PROJECT_ROOT / "dist")

    def open_folder(self, path):
        path.mkdir(exist_ok=True)
        try:
            os.startfile(path)
        except AttributeError:
            selected = filedialog.askdirectory(initialdir=path)
            if selected:
                self.queue_log(f"Selected folder: {selected}")
        except OSError as exc:
            messagebox.showerror("Open Folder Failed", str(exc))

    def on_close(self):
        self.running = False
        self.cancel_requested = True
        self.terminate_current_process()
        self.root.destroy()


def main():
    root = tk.Tk()
    ReleaseToolGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()