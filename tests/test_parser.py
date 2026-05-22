from findsl.parser import parse


def test_parse_nested_then_filter_rank():
    ast = parse('then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))')
    data = ast.to_dict()
    assert data["type"] == "FunctionCall"
    assert data["name"] == "then"
    assert len(data["args"]) == 2


def test_parse_window_comparison():
    ast = parse('filter(indicator("close") >= MAX(indicator("close"), 250))')
    assert ast.to_dict()["name"] == "filter"

