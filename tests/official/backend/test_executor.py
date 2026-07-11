import subprocess

from findsl.official.backend.executor import DorisExecutionConfig, execute_doris_query


def test_executor_uses_mysql_protocol_without_exposing_password_in_argv():
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout="SH\t600000\nSZ\t000001\n", stderr="")

    result = execute_doris_query(
        DorisExecutionConfig(host="127.0.0.1", port=9030, user="root", password="secret", database="newzl"),
        "SELECT mktcode, tgtcode FROM hsj_stock_hq_basic",
        runner=runner,
    )

    assert "secret" not in " ".join(captured["command"])
    assert captured["env"]["MYSQL_PWD"] == "secret"
    assert result.rows == (("SH", "600000"), ("SZ", "000001"))
    assert len(result.unordered_hash) == 64
