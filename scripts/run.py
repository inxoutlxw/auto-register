"""快速运行自动注册脚本（无头模式 + MailTM 邮箱）。

用法:
    python scripts/run.py                  # 注册 1 个
    python scripts/run.py 5                # 循环注册最多 5 个，间隔 60 分钟
    python scripts/run.py 5 30             # 循环注册最多 5 个，间隔 30 分钟
    python scripts/run.py 0 30             # 无限循环，间隔 30 分钟（Ctrl+C 停止）
    python scripts/run.py 0 5              # 无限循环，间隔 5 分钟
"""

import argparse
import os
import subprocess
import sys
import time

def main():
    parser = argparse.ArgumentParser(
        description="快速运行自动注册脚本（无头模式 + MailTM 邮箱）。",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""用法示例:
    python scripts/run.py                  # 注册 1 个
    python scripts/run.py 5                # 循环注册最多 5 个，间隔 60 分钟
    python scripts/run.py 5 30             # 循环注册最多 5 个，间隔 30 分钟
    python scripts/run.py 0 30             # 无限循环，间隔 30 分钟（Ctrl+C 停止）
    python scripts/run.py 0 5              # 无限循环，间隔 5 分钟
"""
    )
    parser.add_argument("count", type=int, nargs="?", default=1, help="注册数量，0 为无限 (默认: 1)")
    parser.add_argument("interval_minutes", type=int, nargs="?", default=60, help="循环间隔，单位分钟 (默认: 60)")
    parser.add_argument("--site", type=str, default="qwen", help="目标站点名称 (默认: qwen)")

    args = parser.parse_args()
    
    count = args.count
    interval_sec = args.interval_minutes * 60
    site = args.site
    
    # 确定项目根目录和引擎入口
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cli_path = os.path.join(project_root, "src", "cli.py")
    
    # 强制设置环璄变量，使用 mailtm 提供者
    env = os.environ.copy()
    env["AUTO_REGISTER_EMAIL_PROVIDER"] = "mailtm"
    
    cmd = [sys.executable, cli_path, "--site", site, "--headless"]
    
    registered = 0
    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始第 {registered + 1} 次注册任务 (站点: {site})...")
            
            # 使用 subprocess 启动新进程可避免循环调用导致 Playwright / 内存泄漏
            result = subprocess.run(cmd, cwd=project_root, env=env)
            
            if result.returncode == 0:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 第 {registered + 1} 次注册成功完成！")
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 第 {registered + 1} 次注册任务异常退出。")
            
            registered += 1
            
            # 检查跳出条件（0为无限循环）
            if count > 0 and registered >= count:
                print(f"\n已达到目标注册数量 ({count})，任务结束。")
                break
            
            print(f"等待 {args.interval_minutes} 分钟后进行下一次注册 (按 Ctrl+C 中止)...")
            time.sleep(interval_sec)
            
    except KeyboardInterrupt:
        print("\n\n用户手动中止了循环任务。")
        sys.exit(0)

if __name__ == "__main__":
    main()
