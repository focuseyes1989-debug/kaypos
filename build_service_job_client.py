from pathlib import Path
import shutil

import PyInstaller.__main__


APP_NAME = "KAY_Service_Job_Client"


def main() -> None:
    root = Path(__file__).resolve().parent
    for target in (root / "build" / APP_NAME, root / "dist" / APP_NAME):
        if target.exists():
            shutil.rmtree(target)
    PyInstaller.__main__.run([
        str(root / "service_job_client_main.py"),
        "--name", APP_NAME,
        "--specpath", str(root / "build"),
        "--noconfirm", "--clean", "--windowed", "--onedir",
        "--icon", str(root / "assets" / "icons" / "service_job.ico"),
        "--collect-submodules", "service_job_client",
        "--collect-submodules", "lite_pos",
    ])
    print(f"Built: {root / 'dist' / APP_NAME / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()
