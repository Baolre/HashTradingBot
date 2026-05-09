"""打包脚本：生成独立 exe（内嵌 Python）。"""
import subprocess
import sys
from pathlib import Path

def main():
    root = Path(__file__).parent
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "HashTradingBot",
        "--add-data", f"{root / 'config.yaml'};.",
        "--icon", "NONE",
        "main.py",
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)
    print("Done → dist/HashTradingBot.exe")

if __name__ == "__main__":
    main()
