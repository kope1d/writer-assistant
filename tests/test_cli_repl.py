"""CLI REPL 交互会话测试：输入源注入、特殊命令、错误隔离、历史收集。"""
from argparse import Namespace

import pytest

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
