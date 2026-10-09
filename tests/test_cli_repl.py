"""CLI REPL 交互会话测试：输入源注入、特殊命令、错误隔离、历史收集。"""
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import cli as cli_module
from tools.cli import _build_parser, _cmd_repl, _run_repl


class FakeInput:
    """注入式输入源：依次吐出命令，记录每次调用收到的 history 快照。"""

    def __init__(self, lines):
        self.lines = list(lines)
        self.history_seen = []

    def __call__(self, prompt, history):
        self.history_seen.append(list(history))
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


def run_repl(lines, monkeypatch=None, dispatch=None):
    fake = FakeInput(lines)
    if dispatch is not None:
        assert monkeypatch is not None, "注入 dispatch 需要 monkeypatch"
        monkeypatch.setattr("tools.cli._dispatch", dispatch)
    rc = _run_repl(Namespace(prompt="> "), input_fn=fake)
    return rc, fake


def test_exit_commands_quit():
    for word in ("exit", "quit", "q"):
        rc, fake = run_repl([word])
        assert rc == 0
        assert fake.lines == []  # 已消费全部输入


def test_eof_clean_exit():
    rc, fake = run_repl([])
    assert rc == 0
    assert fake.history_seen == [[]]


def test_help_lists_commands(capsys):
    rc, _ = run_repl(["help", "q"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "usage:" in out
    assert "repl" in out


def test_question_mark_alias_help(capsys):
    rc, _ = run_repl(["?", "q"])
    assert rc == 0
    assert "usage:" in capsys.readouterr().out


def test_executes_real_command(capsys):
    # --version 是 argparse 内置动作：真实执行 + SystemExit 被 REPL 捕获后继续
    rc, fake = run_repl(["--version", "q"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Writer Assistant" in out
    assert fake.history_seen == [[], []]  # --version 不进历史（SystemExit 分支）


def test_invalid_command_keeps_repl_alive(capsys):
    rc, fake = run_repl(["bogus-xyz", "--version", "q"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "invalid choice" in captured.err  # argparse 拒绝但不退出
    assert "Writer Assistant" in captured.out  # 后续命令正常执行


def test_command_error_isolation(monkeypatch):
    def boom(_args):
        raise RuntimeError("模拟命令内部故障")

    rc, _ = run_repl(["--version", "q"], monkeypatch=monkeypatch, dispatch=boom)
    assert rc == 0  # 异常被捕获，REPL 不崩溃


def test_error_does_not_kill_loop(monkeypatch):
    calls = []

    def flaky(args):
        calls.append(args.command)
        if len(calls) == 1:
            raise ValueError("第一次失败")
        return 0

    rc, _ = run_repl(["status", "status", "q"], monkeypatch=monkeypatch, dispatch=flaky)
    assert rc == 0
    assert calls == ["status", "status"]  # 失败后下一条照常执行


def test_blank_lines_skipped():
    rc, fake = run_repl(["", "   ", "--version", "q"])
    assert rc == 0
    assert fake.history_seen == [[], [], [], []]  # 空行不入历史也不执行


def test_history_collection(monkeypatch):
    captured = []

    def spy(args):
        captured.append(args.command)
        return 0

    rc, fake = run_repl(["status", "status", "q"], monkeypatch=monkeypatch, dispatch=spy)
    assert rc == 0
    assert captured == ["status", "status"]
    assert fake.history_seen[0] == []  # 第一条前无历史
    assert fake.history_seen[1] == ["status"]
    assert fake.history_seen[2] == ["status", "status"]


def test_help_not_in_history(monkeypatch):
    def spy(args):
        return 0

    rc, fake = run_repl(["help", "status", "q"], monkeypatch=monkeypatch, dispatch=spy)
    assert rc == 0
    assert fake.history_seen[2] == ["status"]  # help 不进入历史


def test_shlex_splits_arguments(monkeypatch, capsys):
    captured = []

    def spy(args):
        captured.append((args.command, getattr(args, "port", None)))
        return 0

    rc, _ = run_repl(["studio --port 9999", "q"], monkeypatch=monkeypatch, dispatch=spy)
    assert rc == 0
    assert captured == [("studio", 9999)]  # 引号/空格被 shlex 正确切分


def test_parser_has_repl_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["repl", "--prompt", ">> "])
    assert args.command == "repl"
    assert args.prompt == ">> "


def test_cmd_repl_prints_banner(monkeypatch, capsys):
    monkeypatch.setattr("tools.cli._run_repl", lambda args, input_fn=None: 0)
    rc = _cmd_repl(Namespace(prompt="> "))
    assert rc == 0
    assert "REPL" in capsys.readouterr().out


# ── 真实输入源的回归 ───────────────────────────────────────────────────────
# 上面所有用例都注入 input_fn，因此从未跑到 _repl_input 本体。
# 正是这个盲区让下面两个 bug 溜进了发布版：
#   1) `writer repl < /dev/null` 永久挂死——mintty 下 NUL 的 isatty() 返回 True，
#      代码走 msvcrt.getwch()，没有控制台输入就无限阻塞；
#   2) stdin 被关闭时 sys.stdin 是 None，`.isatty()` 直接 AttributeError 崩栈。


def test_repl_input_treats_missing_stdin_as_eof(monkeypatch):
    """stdin/stdout 被关闭时按 EOF 处理，不能崩栈。"""
    monkeypatch.setattr(cli_module.sys, "stdin", None)
    with pytest.raises(EOFError):
        cli_module._repl_input("> ", [])

    monkeypatch.setattr(cli_module.sys, "stdin", sys.stdin)
    monkeypatch.setattr(cli_module.sys, "stdout", None)
    with pytest.raises(EOFError):
        cli_module._repl_input("> ", [])


@pytest.mark.skipif(os.name != "nt", reason="Windows 专有的控制台判据回归")
def test_windows_console_probe_rejects_non_console_stdin(monkeypatch):
    """没有真控制台时必须判定为不可用，避免走到 msvcrt 阻塞读取。"""
    monkeypatch.setattr(cli_module.sys, "stdin", None)
    assert cli_module._windows_console_stdin_available() is False

    class _Broken:
        def fileno(self):
            raise OSError("bad handle")

    monkeypatch.setattr(cli_module.sys, "stdin", _Broken())
    assert cli_module._windows_console_stdin_available() is False


def test_repl_subprocess_exits_cleanly_with_redirected_stdin():
    """端到端回归：stdin 指向 NUL 时 REPL 必须干净退出（曾经永久挂死）。"""
    repo_root = Path(__file__).parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "tools.cli", "repl"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-400:]
