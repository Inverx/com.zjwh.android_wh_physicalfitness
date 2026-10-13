"""统一入口：``python -m whsport <命令> [参数]``。"""

import importlib
import sys

COMMANDS = {
    "login": ("whsport.cli.login_cli", "登录认证，换取并保存 Token/UID"),
    "run": ("whsport.cli.run_cli", "室外跑步打卡（--type 1 计分跑 / 4 自由跑）"),
    "indoor": ("whsport.cli.indoor_cli", "室内锻炼打卡"),
    "score": ("whsport.cli.score_cli", "学期成绩与完成情况查询"),
    "policy": ("whsport.cli.policy_cli", "学校跑步规则与电子围栏查询"),
    "history": ("whsport.cli.history_cli", "历史运动记录查询"),
    "rank": ("whsport.cli.rank_cli", "校园多维排行榜查询"),
    "gui": ("whsport.gui", "图形界面（Tkinter，最轻便）"),
    "rpc": ("whsport.rpc", "机器可读的 JSON-RPC 引擎接口（供 GUI/前端调用）"),
}


def _usage() -> None:
    print("用法: python -m whsport <命令> [参数]\n")
    print("命令:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<8} {desc}")
    print("\n示例: python -m whsport run --type 4 -d 2000 --time 720")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        _usage()
        return 0

    name = argv[0]
    if name not in COMMANDS:
        print(f"未知命令: {name}")
        _usage()
        return 2

    module = importlib.import_module(COMMANDS[name][0])
    sys.argv = [f"whsport {name}"] + argv[1:]
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
