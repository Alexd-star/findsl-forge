import pytest

from findsl.official.external.matching import canonical_scope_name, match_scope_target
from findsl.official.external.providers.eastmoney import (
    BoardDefinition,
    EastmoneyBoardProvider,
    ExternalProviderError,
    security_market_code,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    def __init__(self, pages):
        self.pages = pages
        self.trust_env = True

    def get(self, _url, *, params, timeout, headers):
        assert timeout > 0
        assert "User-Agent" in headers
        return _Response(self.pages[int(params["pn"])])


class _UnavailableBrowserSession:
    def get(self, *_args, **_kwargs):
        raise RuntimeError("browser fallback unavailable")


def test_constituent_fetch_fails_over_between_public_shards():
    class _ShardSession:
        trust_env = True

        def __init__(self):
            self.hosts = []

        def get(self, url, **_kwargs):
            self.hosts.append(url.split("/")[2])
            if url.startswith("https://29."):
                raise ConnectionError("primary shard closed")
            return _Response(
                {
                    "rc": 0,
                    "data": {
                        "total": 1,
                        "diff": [{"f12": "600000", "f14": "浦发银行"}],
                    },
                }
            )

    session = _ShardSession()
    provider = EastmoneyBoardProvider(
        session=session,
        browser_session=_UnavailableBrowserSession(),
        curl_json_loader=False,
        max_attempts=1,
    )

    rows = provider.list_constituents(BoardDefinition("concept", "BK1", "测试"))

    assert [(item.code, item.name) for item in rows] == [("600000", "浦发银行")]
    assert session.hosts == ["29.push2.eastmoney.com", "7.push2.eastmoney.com"]


def test_provider_uses_injected_curl_loader_after_http_clients_fail():
    class _OfflineSession:
        trust_env = True

        def get(self, *_args, **_kwargs):
            raise ConnectionError("requests unavailable")

    curl_hosts = []

    def curl_loader(url, _params):
        curl_hosts.append(url.split("/")[2])
        if url.startswith("https://29."):
            raise ConnectionError("first curl shard unavailable")
        return {
            "rc": 0,
            "data": {
                "total": 1,
                "diff": [{"f12": "600000", "f14": "浦发银行"}],
            },
        }

    provider = EastmoneyBoardProvider(
        session=_OfflineSession(),
        browser_session=_UnavailableBrowserSession(),
        curl_json_loader=curl_loader,
        max_attempts=1,
    )

    rows = provider.list_constituents(BoardDefinition("concept", "BK1", "测试"))

    assert rows[0].code == "600000"
    assert curl_hosts == ["29.push2.eastmoney.com", "7.push2.eastmoney.com"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"max_attempts": 0}, "max_attempts"),
        ({"backoff_seconds": -1}, "backoff_seconds"),
    ],
)
def test_provider_rejects_invalid_retry_policy(kwargs, message):
    with pytest.raises(ValueError, match=message):
        EastmoneyBoardProvider(session=_Session({}), **kwargs)


def test_provider_paginates_and_rejects_empty_payloads():
    session = _Session(
        {
            1: {"rc": 0, "data": {"total": 3, "diff": [{"f12": "BK1", "f14": "算力概念"}, {"f12": "BK2", "f14": "白酒"}]}},
            2: {"rc": 0, "data": {"total": 3, "diff": [{"f12": "BK3", "f14": "机器人"}]}},
        }
    )
    provider = EastmoneyBoardProvider(session=session)

    boards = provider.list_boards("concept")

    assert [board.code for board in boards] == ["BK1", "BK2", "BK3"]
    assert session.trust_env is False
    with pytest.raises(ValueError, match="unsupported"):
        provider.list_boards("unknown")


def test_provider_rejects_pagination_that_ends_before_declared_total():
    session = _Session(
        {
            1: {
                "rc": 0,
                "data": {
                    "total": 3,
                    "diff": [{"f12": "BK1", "f14": "算力概念"}],
                },
            },
            2: {"rc": 0, "data": {"total": 3, "diff": []}},
        }
    )
    provider = EastmoneyBoardProvider(session=session)

    with pytest.raises(ExternalProviderError, match="received 1 of 3 rows"):
        provider.list_boards("concept")


def test_provider_reuses_exact_raw_response_cache(tmp_path):
    first_session = _Session(
        {1: {"rc": 0, "data": {"total": 1, "diff": [{"f12": "BK1", "f14": "算力概念"}]}}}
    )
    first = EastmoneyBoardProvider(session=first_session, cache_dir=tmp_path)
    assert first.list_boards("concept")[0].code == "BK1"

    class _OfflineSession:
        trust_env = True

        def get(self, *_args, **_kwargs):
            raise AssertionError("cached request must not reach the network")

    second = EastmoneyBoardProvider(session=_OfflineSession(), cache_dir=tmp_path)
    assert second.list_boards("concept")[0].name == "算力概念"
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_scope_matching_is_conservative_and_suffix_aware():
    boards = (
        BoardDefinition("concept", "BK1", "算力概念"),
        BoardDefinition("industry", "BK2", "白酒行业"),
        BoardDefinition("concept", "BK3", "机器人执行器"),
    )

    assert canonical_scope_name("ＡＩ 概念板块") == "ai"
    assert match_scope_target("算力", boards).board.code == "BK1"
    assert match_scope_target("白酒板块", boards).board.code == "BK2"
    assert match_scope_target("完全不存在的范围", boards) is None


@pytest.mark.parametrize(
    ("code", "market"),
    [
        ("600000", 1),
        ("688001", 1),
        ("000001", 0),
        ("300001", 0),
        ("302132", 0),
        ("920001", 103),
        ("123456", None),
    ],
)
def test_security_market_code(code, market):
    assert security_market_code(code) == market
