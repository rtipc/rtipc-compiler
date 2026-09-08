from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from lark import Lark, Transformer, v_args
from lark.tree import Meta
from protocol import Channel, Field, Group, Primitive, Struct


class StructType(Enum):
    STRUCT = 1
    UNION = 2


@dataclass
class ParsedType:
    type: str | Primitive
    length: int


@dataclass
class ParsedField:
    meta: Meta
    name: str
    type: ParsedType


@dataclass
class ParsedStruct:
    meta: Meta
    name: str
    type: StructType
    fields: list[ParsedField]


@dataclass
class ParsedChannel:
    meta: Meta
    name: str
    type: str
    add_msgs: int
    eventfd: bool


@dataclass
class ParsedGroup:
    meta: Meta
    name: str
    c2s: list[ParsedChannel]
    s2c: list[ParsedChannel]


class StructNotFoundException(Exception):
    def __init__(self, name, line):
        super().__init__(f"struct {name} in line {line} not defined")


class AlreadyDefinedException(Exception):
    def __init__(self, name, line):
        super().__init__(f"struct {name} in line {line} already defined")


class RtIpcTransformer(Transformer):
    INT = int
    CNAME = str
    fields = list
    eventfd = bool
    channels = list

    @v_args(inline=True)
    def length(self, length: int) -> int:
        return length

    @v_args(inline=True)
    def name(self, name: str) -> str:
        return name

    @v_args(inline=True)
    def primitive(self, str_prim: str) -> ParsedType:
        try:
            primitive = Primitive[str_prim.upper()]
            return ParsedType(primitive, 1)
        except ValueError:
            raise SyntaxError(f"unnown primitive: {str_prim}")

    @v_args(inline=True)
    def add_msgs(self, add_msgs: str) -> int:
        return int(add_msgs)

    @v_args(inline=True)
    def type(self, name: str) -> ParsedType:
        return ParsedType(name, 1)

    @v_args(inline=True)
    def array(self, type: ParsedType, length: int) -> ParsedType:
        type.length = length
        return type

    @v_args(inline=True, meta=True)
    def field(self, meta: Meta, name: str, type: ParsedType) -> ParsedField:
        return ParsedField(meta, name, type)

    @v_args(inline=True, meta=True)
    def struct(self, meta: Meta, name: str, fields: list[ParsedField]) -> ParsedStruct:
        return ParsedStruct(meta, name, StructType.STRUCT, fields)

    @v_args(inline=True, meta=True)
    def union(self, meta: Meta, name: str, fields: list[ParsedField]) -> ParsedStruct:
        return ParsedStruct(meta, name, StructType.UNION, fields)

    @v_args(inline=True, meta=True)
    def channel(
        self, meta: Meta, name: str, type: ParsedType, add_msgs: int, eventfd: bool
    ) -> ParsedChannel:
        return ParsedChannel(meta, name, type.type, add_msgs, eventfd)

    @v_args(inline=True, meta=True)
    def group(
        self,
        meta: Meta,
        name: str,
        c2s_channels: list[ParsedChannel],
        s2c_channels: list[ParsedChannel],
    ) -> ParsedGroup:
        return ParsedGroup(meta, name, c2s_channels, s2c_channels)

    def true(self, _):
        return True

    def false(self, _):
        return False

    def start(self, children):
        return children


class RtIpcParser:
    def __init__(self):

        lark_path = Path(__file__).parent
        self.parser = Lark.open(
            lark_path / "rtipc.lark",
            rel_to=__file__,
            parser="lalr",
            propagate_positions=True,
        )

    def create_field(self, field: ParsedField, structs: list[Struct]):
        if isinstance(field.type.type, str):
            type = structs.get(field.type.type)
            if type is None:
                raise StructNotFoundException(field.type.type, field.meta.line)
            return Field(field.name, type, field.type.length)
        else:
            return Field(field.name, field.type.type, field.type.length)

    def process_struct(
        self, parsed_struct: ParsedStruct, structs: list[Struct]
    ) -> Struct:
        fields = []
        for parsed_field in parsed_struct.fields:
            if isinstance(parsed_field.type.type, str):
                type = structs.get(parsed_field.type.type)
                if type is None:
                    raise StructNotFoundException(
                        parsed_field.type.type, parsed_field.meta.line
                    )
                field = Field(parsed_field.name, type, parsed_field.type.length)
                fields.append(field)
            else:
                field = Field(
                    parsed_field.name, parsed_field.type.type, parsed_field.type.length
                )
                fields.append(field)

        return Struct(
            parsed_struct.name,
            parsed_struct.type == StructType.UNION,
            fields,
            None,
        )

    def process_group(self, parsed_group: ParsedGroup, structs: list[Struct]) -> Group:
        s2c = []
        c2s = []

        for parsed_channel in parsed_group.c2s:
            type = structs.get(parsed_channel.type)
            if type is None:
                raise StructNotFoundException(
                    parsed_channel.type, parsed_channel.meta.line
                )
            channel = Channel(
                parsed_channel.name,
                type,
                parsed_channel.add_msgs,
                parsed_channel.eventfd,
            )
            c2s.append(channel)

        for parsed_channel in parsed_group.s2c:
            type = structs.get(parsed_channel.type)
            if type is None:
                raise StructNotFoundException(
                    parsed_channel.type, parsed_channel.meta.line
                )
            channel = Channel(
                parsed_channel.name,
                type,
                parsed_channel.add_msgs,
                parsed_channel.eventfd,
            )
            s2c.append(channel)

        return Group(parsed_group.name, c2s, s2c, "")

    def parse(self, path: Path) -> (list[Group], list[Struct]):
        content = path.read_text(encoding="utf-8")
        tree = self.parser.parse(content)
        schema = RtIpcTransformer().transform(tree)
        structs = {}
        groups = {}

        for node in schema:
            match node:
                case ParsedStruct():
                    if node.name in structs:
                        raise AlreadyDefinedException(node.name, node.meta.line)
                    struct = self.process_struct(node, structs)
                    structs[node.name] = struct
                case ParsedGroup():
                    if node.name in groups:
                        raise AlreadyDefinedException(node.name, node.meta.line)
                    group = self.process_group(node, structs)
                    groups[node.name] = group

        return (groups.values(), structs.values())
