import json

import pytest

from findsl.official.external.providers.baidu import BaiduRelatedBlockProvider
from findsl.official.external.providers.eastmoney import ExternalProviderError


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    trust_env = True

    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.batch_sizes = []

    def get(self, _url, *, params, headers, timeout):
        assert headers["Referer"].startswith("https://")
        assert timeout > 0
        self.batch_sizes.append(len(json.loads(params["stock"])))
        return _Response(next(self.payloads))


def _payload(*codes):
    return {
        "ResultCode": "0",
        "Result": {
            code: [
                {
                    "name": "行业",
                    "list": [
                        {
                            "name": "银行",
                            "describe": "申万一级",
                            "xcx_query": "query=480000&code=480000",
                        }
                    ],
                },
                {
                    "name": "概念",
                    "list": [
                        {
                            "name": "MSCI概念",
                            "xcx_query": "query=031027&code=031027",
                        }
                    ],
                },
            ]
            for code in codes
        },
    }


def test_provider_batches_at_source_limit_and_parses_typed_scopes():
    codes = [f"{index:06d}" for index in range(1, 22)]
    session = _Session((_payload(*codes[:20]), _payload(*codes[20:])))
    provider = BaiduRelatedBlockProvider(
        session=session, request_interval_seconds=0
    )

    rows = provider.list_classifications((code, f"证券{code}") for code in codes)

    assert len(rows) == 21
    assert session.batch_sizes == [20, 1]
    assert {(item.scope_type, item.name) for item in rows[0].scopes} == {
        ("industry", "银行"),
        ("concept", "MSCI概念"),
    }
    assert session.trust_env is False


def test_provider_rejects_a_partial_batch_instead_of_importing_membership_gaps():
    session = _Session((_payload("000001"),))
    provider = BaiduRelatedBlockProvider(
        session=session, request_interval_seconds=0
    )

    with pytest.raises(ExternalProviderError, match="000002"):
        provider.list_classifications(
            (("000001", "平安银行"), ("000002", "万科A"))
        )


def test_provider_reuses_atomic_raw_response_cache(tmp_path):
    first_session = _Session((_payload("000001"),))
    first = BaiduRelatedBlockProvider(
        session=first_session,
        cache_dir=tmp_path,
        request_interval_seconds=0,
    )
    first.list_classifications((("000001", "平安银行"),))

    class _OfflineSession:
        trust_env = True

        def get(self, *_args, **_kwargs):
            raise AssertionError("cached batch must not reach the network")

    second = BaiduRelatedBlockProvider(
        session=_OfflineSession(), cache_dir=tmp_path
    )
    assert second.list_classifications((("000001", "平安银行"),))[0].scopes
    assert len(tuple(tmp_path.glob("*.json"))) == 1
