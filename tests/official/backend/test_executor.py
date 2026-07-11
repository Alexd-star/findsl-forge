import subprocess

from findsl.official.backend.executor import DorisExecutionConfig, execute_doris_query, execute_doris_query_digest


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


def test_digest_executor_streams_rows_without_materializing_result_set():
    captured = {}

    class Stream:
        def __iter__(self):
            return iter(["0\t600000\t2026-04-14\n", "1\t000001\t2026-04-14\n"])

    class Process:
        stdout = Stream()
        stderr = Stream()
        returncode = 0

        def wait(self, timeout=None):
            return 0

    def popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return Process()

    result = execute_doris_query_digest(
        DorisExecutionConfig(host="127.0.0.1", port=9030, user="root", password="secret", database="newzl"),
        "SELECT mktcode,tgtcode,bizdate FROM hsj_stock_hq_basic ORDER BY mktcode,tgtcode,bizdate",
        popen_factory=popen,
    )

    assert result.row_count == 2
    assert len(result.sha256) == 64
    assert "secret" not in " ".join(captured["command"])
