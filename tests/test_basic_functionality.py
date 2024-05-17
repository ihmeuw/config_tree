import pickle
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

from layered_config_tree import (
    ConfigNode,
    ConfigurationError,
    ConfigurationKeyError,
    DuplicatedConfigurationError,
    LayeredConfigTree,
)


@pytest.fixture(params=list(range(1, 5)))
def layers(request: pytest.FixtureRequest) -> list[str]:
    return [f"layer_{i}" for i in range(1, request.param + 1)]


@pytest.fixture
def layers_and_values(layers: list[str]) -> dict[str, str]:
    return {layer: f"test_value_{i+1}" for i, layer in enumerate(layers)}


@pytest.fixture
def empty_node(layers: list[str]) -> ConfigNode:
    return ConfigNode(layers, name="test_node")


@pytest.fixture
def full_node(layers_and_values: dict[str, str]) -> ConfigNode:
    n = ConfigNode(list(layers_and_values.keys()), name="test_node")
    for layer, value in layers_and_values.items():
        n.update(value, layer, source="test_source")
    return n


@pytest.fixture
def empty_tree(layers: list[str]) -> LayeredConfigTree:
    return LayeredConfigTree(layers=layers)


def test_node_creation(empty_node: ConfigNode) -> None:
    assert not empty_node
    assert not empty_node.accessed
    assert not empty_node.metadata
    assert not repr(empty_node)
    assert not str(empty_node)


def test_full_node_update(full_node: ConfigNode) -> None:
    assert full_node
    assert not full_node.accessed
    assert len(full_node.metadata) == len(full_node._layers)
    assert repr(full_node)
    assert str(full_node)


def test_node_update_no_args() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer=None, source="some_source")
    assert n._values["base"] == ("some_source", "test_value")

    n = ConfigNode(["layer_1", "layer_2"], name="test_node")
    n.update("test_value", layer=None, source="some_source")
    assert "layer_1" not in n._values
    assert n._values["layer_2"] == ("some_source", "test_value")


def test_node_update_with_args() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer=None, source="test")
    assert n._values["base"] == ("test", "test_value")

    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer="base", source="test")
    assert n._values["base"] == ("test", "test_value")

    n = ConfigNode(["layer_1", "layer_2"], name="test_node")
    n.update("test_value", layer=None, source="test")
    assert "layer_1" not in n._values
    assert n._values["layer_2"] == ("test", "test_value")

    n = ConfigNode(["layer_1", "layer_2"], name="test_node")
    n.update("test_value", layer="layer_1", source="test")
    assert "layer_2" not in n._values
    assert n._values["layer_1"] == ("test", "test_value")

    n = ConfigNode(["layer_1", "layer_2"], name="test_node")
    n.update("test_value", layer="layer_2", source="test")
    assert "layer_1" not in n._values
    assert n._values["layer_2"] == ("test", "test_value")

    n = ConfigNode(["layer_1", "layer_2"], name="test_node")
    n.update("test_value", layer="layer_1", source="test")
    n.update("test_value", layer="layer_2", source="test")
    assert n._values["layer_1"] == ("test", "test_value")
    assert n._values["layer_2"] == ("test", "test_value")


def test_node_frozen_update() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.freeze()
    with pytest.raises(ConfigurationError):
        n.update("test_val", layer=None, source=None)


def test_node_bad_layer_update() -> None:
    n = ConfigNode(["base"], name="test_node")
    with pytest.raises(ConfigurationKeyError):
        n.update("test_value", layer="layer_1", source=None)


def test_node_duplicate_update() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer=None, source=None)
    with pytest.raises(DuplicatedConfigurationError):
        n.update("test_value", layer=None, source=None)


def test_node_get_value_with_source_empty(empty_node: ConfigNode) -> None:
    with pytest.raises(ConfigurationKeyError):
        empty_node._get_value_with_source(layer=None)

    for layer in empty_node._layers:
        with pytest.raises(ConfigurationKeyError):
            empty_node._get_value_with_source(layer=layer)

    assert not empty_node.accessed


def test_node_get_value_with_source(full_node: ConfigNode) -> None:
    assert full_node._get_value_with_source(layer=None) == (
        "test_source",
        f"test_value_{len(full_node._layers)}",
    )

    for i, layer in enumerate(full_node._layers):
        assert full_node._get_value_with_source(layer=layer) == (
            "test_source",
            f"test_value_{i+1}",
        )

    assert not full_node.accessed


def test_node_get_value_empty(empty_node: ConfigNode) -> None:
    with pytest.raises(ConfigurationKeyError):
        empty_node.get_value()

    for layer in empty_node._layers:
        with pytest.raises(ConfigurationKeyError):
            empty_node.get_value()

    assert not empty_node.accessed


def test_node_get_value(full_node: ConfigNode) -> None:
    assert full_node.get_value() == f"test_value_{len(full_node._layers)}"
    assert full_node.accessed
    full_node._accessed = False

    assert full_node.get_value(layer=None) == f"test_value_{len(full_node._layers)}"
    assert full_node.accessed
    full_node._accessed = False

    for i, layer in enumerate(full_node._layers):
        assert full_node.get_value(layer=layer) == f"test_value_{i + 1}"
        assert full_node.accessed
        full_node._accessed = False

    assert not full_node.accessed


def test_node_repr() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer="base", source="test")
    s = """\
        base: test_value
            source: test"""
    assert repr(n) == textwrap.dedent(s)

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer="base", source="test")
    s = """\
        base: test_value
            source: test"""
    assert repr(n) == textwrap.dedent(s)

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer=None, source="test")
    s = """\
        layer_1: test_value
            source: test"""
    assert repr(n) == textwrap.dedent(s)

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer="base", source="test")
    n.update("test_value", layer="layer_1", source="test")
    s = """\
        layer_1: test_value
            source: test
        base: test_value
            source: test"""
    assert repr(n) == textwrap.dedent(s)


def test_node_str() -> None:
    n = ConfigNode(["base"], name="test_node")
    n.update("test_value", layer="base", source="test")
    s = "base: test_value"
    assert str(n) == s

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer="base", source="test")
    s = "base: test_value"
    assert str(n) == s

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer=None, source="test")
    s = "layer_1: test_value"
    assert str(n) == s

    n = ConfigNode(["base", "layer_1"], name="test_node")
    n.update("test_value", layer="base", source="test")
    n.update("test_value", layer="layer_1", source="test")
    s = "layer_1: test_value"
    assert str(n) == s


def test_tree_creation(empty_tree: LayeredConfigTree) -> None:
    assert len(empty_tree) == 0
    assert not empty_tree.items()
    assert not empty_tree.values()
    assert not empty_tree.keys()
    assert not repr(empty_tree)
    assert not str(empty_tree)
    assert not empty_tree._children
    assert empty_tree.to_dict() == {}


def test_tree_coerce_dict() -> None:
    d: dict[str, Any]
    d, s = {}, "test"
    assert LayeredConfigTree._coerce(d, s) == (d, s)
    d, s = {"key": "val"}, "test"
    assert LayeredConfigTree._coerce(d, s) == (d, s)
    d = {"key1": {"sub_key1": ["val", "val", "val"], "sub_key2": "val"}, "key2": "val"}
    s = "test"
    assert LayeredConfigTree._coerce(d, s) == (d, s)


def test_tree_coerce_str() -> None:
    s = "test"
    d = """\
    key: val"""
    assert LayeredConfigTree._coerce(d, s) == ({"key": "val"}, s)
    d = """\
    key1:
        sub_key1:
            - val
            - val
            - val
        sub_key2: val
    key2: val"""
    r = {"key1": {"sub_key1": ["val", "val", "val"], "sub_key2": "val"}, "key2": "val"}
    assert LayeredConfigTree._coerce(d, s) == (r, s)
    d = """\
        key1:
            sub_key1: [val, val, val]
            sub_key2: val
        key2: val"""
    r = {"key1": {"sub_key1": ["val", "val", "val"], "sub_key2": "val"}, "key2": "val"}
    assert LayeredConfigTree._coerce(d, s) == (r, s)


def test_tree_coerce_yaml(tmp_path: Path) -> None:
    d = """\
     key1:
         sub_key1:
             - val
             - val
             - val
         sub_key2: [val, val]
     key2: val"""
    r = {
        "key1": {"sub_key1": ["val", "val", "val"], "sub_key2": ["val", "val"]},
        "key2": "val",
    }
    s = "test"
    p = tmp_path / "model_spec.yaml"
    with p.open("w") as f:
        f.write(d)
    assert LayeredConfigTree._coerce(str(p), s) == (r, s)
    assert LayeredConfigTree._coerce(str(p), None) == (r, str(p))


def test_single_layer() -> None:
    d = LayeredConfigTree()
    d.update({"test_key": "test_value", "test_key2": "test_value2"})

    assert d.test_key == "test_value"
    assert d.test_key2 == "test_value2"

    with pytest.raises(DuplicatedConfigurationError):
        d.test_key2 = "test_value3"

    assert d.test_key2 == "test_value2"
    assert d.test_key == "test_value"


def test_dictionary_style_access() -> None:
    d = LayeredConfigTree()
    d.update({"test_key": "test_value", "test_key2": "test_value2"})

    assert d["test_key"] == "test_value"
    assert d["test_key2"] == "test_value2"

    with pytest.raises(DuplicatedConfigurationError):
        d["test_key2"] = "test_value3"

    assert d["test_key2"] == "test_value2"
    assert d["test_key"] == "test_value"


def test_get_missing_key() -> None:
    d = LayeredConfigTree()
    with pytest.raises(ConfigurationKeyError):
        _ = d.missing_key


def test_set_missing_key() -> None:
    d = LayeredConfigTree()
    with pytest.raises(ConfigurationKeyError):
        d.missing_key = "test_value"
    with pytest.raises(ConfigurationKeyError):
        d["missing_key"] = "test_value"


def test_multiple_layer_get() -> None:
    d = LayeredConfigTree(layers=["first", "second", "third"])
    d._set_with_metadata("test_key", "test_with_source_value", "first", source=None)
    d._set_with_metadata("test_key", "test_value2", "second", source=None)
    d._set_with_metadata("test_key", "test_value3", "third", source=None)

    d._set_with_metadata("test_key2", "test_value4", "first", source=None)
    d._set_with_metadata("test_key2", "test_value5", "second", source=None)

    d._set_with_metadata("test_key3", "test_value6", "first", source=None)

    assert d.test_key == "test_value3"
    assert d.test_key2 == "test_value5"
    assert d.test_key3 == "test_value6"


def test_outer_layer_set() -> None:
    d = LayeredConfigTree(layers=["inner", "outer"])
    d._set_with_metadata("test_key", "test_value", "inner", source=None)
    d._set_with_metadata("test_key", "test_value3", layer=None, source=None)
    assert d.test_key == "test_value3"
    assert d["test_key"] == "test_value3"

    d = LayeredConfigTree(layers=["inner", "outer"])
    d._set_with_metadata("test_key", "test_value", "inner", source=None)
    d.test_key = "test_value3"
    assert d.test_key == "test_value3"
    assert d["test_key"] == "test_value3"

    d = LayeredConfigTree(layers=["inner", "outer"])
    d._set_with_metadata("test_key", "test_value", "inner", source=None)
    d["test_key"] = "test_value3"
    assert d.test_key == "test_value3"
    assert d["test_key"] == "test_value3"


def test_update_dict() -> None:
    d = LayeredConfigTree(layers=["inner", "outer"])
    d.update({"test_key": "test_value", "test_key2": "test_value2"}, layer="inner")
    d.update({"test_key": "test_value3"}, layer="outer")

    assert d.test_key == "test_value3"
    assert d.test_key2 == "test_value2"


def test_update_dict_nested() -> None:
    d = LayeredConfigTree(layers=["inner", "outer"])
    d.update(
        {"test_container": {"test_key": "test_value", "test_key2": "test_value2"}},
        layer="inner",
    )
    with pytest.raises(DuplicatedConfigurationError):
        d.update({"test_container": {"test_key": "test_value3"}}, layer="inner")

    assert d.test_container.test_key == "test_value"
    assert d.test_container.test_key2 == "test_value2"

    d.update({"test_container": {"test_key2": "test_value4"}}, layer="outer")

    assert d.test_container.test_key2 == "test_value4"


def test_source_metadata() -> None:
    d = LayeredConfigTree(layers=["inner", "outer"])
    d.update({"test_key": "test_value"}, layer="inner", source="initial_load")
    d.update({"test_key": "test_value2"}, layer="outer", source="update")

    assert d.metadata("test_key") == [
        {"layer": "inner", "source": "initial_load", "value": "test_value"},
        {"layer": "outer", "source": "update", "value": "test_value2"},
    ]


def test_exception_on_source_for_missing_key() -> None:
    d = LayeredConfigTree(layers=["inner", "outer"])
    d.update({"test_key": "test_value"}, layer="inner", source="initial_load")

    with pytest.raises(ConfigurationKeyError):
        d.metadata("missing_key")


def test_unused_keys() -> None:
    d = LayeredConfigTree(
        {"test_key": {"test_key2": "test_value", "test_key3": "test_value2"}}
    )

    assert d.unused_keys() == ["test_key.test_key2", "test_key.test_key3"]

    _ = d.test_key.test_key2

    assert d.unused_keys() == ["test_key.test_key3"]

    _ = d.test_key.test_key3

    assert not d.unused_keys()


def test_to_dict_dict() -> None:
    test_dict = {"configuration": {"time": {"start": {"year": 2000}}}}
    config = LayeredConfigTree(test_dict)
    assert config.to_dict() == test_dict


def test_to_dict_yaml(test_spec: Path) -> None:
    config = LayeredConfigTree(str(test_spec))
    with test_spec.open() as f:
        yaml_config = yaml.full_load(f)
    assert yaml_config == config.to_dict()


def test_equals() -> None:
    # TODO: Assert should succeed, instead of raising, once equality is
    # implemented for LayeredConfigTrees
    with pytest.raises(NotImplementedError):
        test_dict = {"configuration": {"time": {"start": {"year": 2000}}}}
        config = LayeredConfigTree(test_dict)
        config2 = LayeredConfigTree(test_dict.copy())
        assert config == config2


def test_to_from_pickle() -> None:
    test_dict = {"configuration": {"time": {"start": {"year": 2000}}}}
    second_layer = {"configuration": {"time": {"start": {"year": 2001}}}}
    config = LayeredConfigTree(test_dict, layers=["first_layer", "second_layer"])
    config.update(second_layer, layer="second_layer")
    unpickled = pickle.loads(pickle.dumps(config))

    # We can't just assert unpickled == config because
    # equals doesn't work with our custom attribute
    # accessor scheme (also why pickling didn't use to work).
    # See the previous xfailed test.
    assert unpickled.to_dict() == config.to_dict()
    assert unpickled._frozen == config._frozen
    assert unpickled._name == config._name
    assert unpickled._layers == config._layers


def test_freeze() -> None:
    config = LayeredConfigTree(data={"configuration": {"time": {"start": {"year": 2000}}}})
    config.freeze()

    with pytest.raises(ConfigurationError):
        config.update(data={"configuration": {"time": {"end": {"year": 2001}}}})


def test_retrieval_behavior() -> None:
    layer_inner = "inner"
    layer_middle = "middle"
    layer_outer = "outer"

    default_cfg_value = "value_a"

    layer_list = [layer_inner, layer_middle, layer_outer]
    # update the LayeredConfigTree layers in different order and verify that has no effect on
    #  the values retrieved ("outer" is retrieved when no layer is specified regardless of
    #  the initialization order
    for scenario in [layer_list, reversed(layer_list)]:
        cfg = LayeredConfigTree(layers=layer_list)
        for layer in scenario:
            cfg.update({default_cfg_value: layer}, layer=layer)
        assert cfg.get_from_layer(default_cfg_value) == layer_outer
        assert cfg.get_from_layer(default_cfg_value, layer=layer_outer) == layer_outer
        assert cfg.get_from_layer(default_cfg_value, layer=layer_middle) == layer_middle
        assert cfg.get_from_layer(default_cfg_value, layer=layer_inner) == layer_inner


def test_repr_display() -> None:
    expected_repr = """\
    Key1:
        override_2: value_ov_2
            source: ov2_src
        override_1: value_ov_1
            source: ov1_src
        base: value_base
            source: base_src"""
    # codifies the notion that repr() displays values from most to least overridden
    #  regardless of initialization order
    layers = ["base", "override_1", "override_2"]
    cfg = LayeredConfigTree(layers=layers)

    cfg.update({"Key1": "value_ov_2"}, layer="override_2", source="ov2_src")
    cfg.update({"Key1": "value_ov_1"}, layer="override_1", source="ov1_src")
    cfg.update({"Key1": "value_base"}, layer="base", source="base_src")
    assert repr(cfg) == textwrap.dedent(expected_repr)

    cfg = LayeredConfigTree(layers=layers)
    cfg.update({"Key1": "value_base"}, layer="base", source="base_src")
    cfg.update({"Key1": "value_ov_1"}, layer="override_1", source="ov1_src")
    cfg.update({"Key1": "value_ov_2"}, layer="override_2", source="ov2_src")
    assert repr(cfg) == textwrap.dedent(expected_repr)
