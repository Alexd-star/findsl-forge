from findsl.official.external.providers.ths import ThsConceptDefinition, ThsConceptProvider


class _Response:
    status_code = 200
    text = """
    <span class="page_info">1/1</span>
    <table class="m-table m-pager-table">
      <thead><tr><th>代码</th><th>名称</th></tr></thead>
      <tbody><tr><td>600000</td><td>浦发银行</td></tr></tbody>
    </table>
    """

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self):
        self.trust_env = True
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        return _Response()


def test_ths_provider_ignores_environment_proxy_and_reuses_cache(tmp_path):
    session = _Session()
    provider = ThsConceptProvider(
        session=session,
        cache_dir=tmp_path,
        request_interval_seconds=0,
        header_factory=lambda: {"User-Agent": "test"},
    )
    concept = ThsConceptDefinition("123", "测试概念", ("测试",))

    first = provider.list_constituents(concept)
    second = provider.list_constituents(concept)

    assert session.trust_env is False
    assert [(item.code, item.name) for item in first] == [("600000", "浦发银行")]
    assert second == first
    assert session.calls == 1
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_ths_provider_can_explicitly_use_environment_proxy():
    session = _Session()

    ThsConceptProvider(session=session, trust_environment_proxy=True)

    assert session.trust_env is True
