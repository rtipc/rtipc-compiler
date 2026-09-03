from enum import IntEnum

from protocol import Field, Group, Primitive, Struct
from utils import Indent, IndentStyle

FIELD_TYPE_MASK = 0x03


class FieldType(IntEnum):
    PRIMITIVE = 0x01
    STRUCT = 0x02
    UNION = 0x03


ARRAY_LENGTH_SIZE_MASK = 0x0C
NUM_FIELD_SIZE_MASK = 0x30


class ArrayLengthSize(IntEnum):
    NONE = 0x00
    ONE = 0x04
    TWO = 0x08
    FOUR = 0x0C


class NumFieldsSize(IntEnum):
    ONE = 0x00
    TWO = 0x10
    FOUR = 0x20


UINT8_MAX = 0xFF
UINT16_MAX = 0xFFFF
UINT32_MAX = 0xFFFFFFFF


def str_primitive(primitive: int) -> str:
    return str(Primitive(primitive).name)


def enc_name(name: str) -> bytes:
    return len(name).to_bytes(1, "little") + name.encode("utf-8")


def dec_name(info: bytearray) -> str:
    name_length = info[0]
    name = info[1 : name_length + 1].decode("utf-8")
    del info[: name_length + 1]
    return name


def enc_array_length(length: int) -> (int, bytes):
    if length <= 1:
        return (ArrayLengthSize.NONE, b"")
    length = length - 1
    if length <= UINT8_MAX:
        return (ArrayLengthSize.ONE, length.to_bytes(1, "little"))
    if length <= UINT16_MAX:
        return (ArrayLengthSize.TWO, length.to_bytes(2, "little"))
    if length <= UINT32_MAX:
        return (ArrayLengthSize.FOUR, length.to_bytes(4, "little"))


def dec_array_length(token: int, info: bytearray) -> int:
    match token & ARRAY_LENGTH_SIZE_MASK:
        case ArrayLengthSize.NONE:
            length = 0
        case ArrayLengthSize.ONE:
            length = info[0]
            del info[:1]
        case ArrayLengthSize.TWO:
            length = int.from_bytes(info[0:2], byteorder="little")
            del info[:2]
        case ArrayLengthSize.FOUR:
            length = int.from_bytes(info[0:4], byteorder="little")
            del info[:4]
    return length + 1


def enc_num_fields(num: int) -> (int, bytes):
    if num <= UINT8_MAX:
        return (NumFieldsSize.ONE, num.to_bytes(1, "little"))
    if num <= UINT16_MAX:
        return (NumFieldsSize.TWO, num.to_bytes(2, "little"))
    if num <= UINT32_MAX:
        return (NumFieldsSize.FOUR, num.to_bytes(4, "little"))


def dec_num_fields(token: int, info: bytearray) -> int:
    match token & NUM_FIELD_SIZE_MASK:
        case NumFieldsSize.ONE:
            num = info[0]
            del info[:1]
        case NumFieldsSize.TWO:
            num = int.from_bytes(info[0:2], byteorder="little")
            del info[:2]
        case NumFieldsSize.FOUR:
            num = int.from_bytes(info[0:4], byteorder="little")
            del info[:4]
    return num


def enc_primitive(primitive: Primitive, array_length: int) -> bytes:
    (array_length_size, info_array_length) = enc_array_length(array_length)
    token = array_length_size | FieldType.PRIMITIVE
    return token.to_bytes(1, "little") + info_array_length + primitive.to_bytes()


def enc_struct(struct: Struct, array_length: int) -> bytes:
    (array_length_size, info_array_length) = enc_array_length(array_length)
    (num_fields_size, info_num_fields) = enc_num_fields(len(struct.fields))

    token = array_length_size | num_fields_size

    if struct.is_union:
        token |= FieldType.UNION
    else:
        token |= FieldType.STRUCT

    info = token.to_bytes(1, "little") + info_array_length + info_num_fields

    for field in struct.fields:
        info += enc_field(field)

    return info


def enc_field(field: Field) -> bytes:
    info = enc_name(field.name)

    if isinstance(field.type, Primitive):
        info += enc_primitive(field.type, field.length)
    else:
        info += enc_struct(field.type, field.length)

    return info


def add_group_info(group: Group):
    group.info = enc_name(group.name)
    for channel in group.c2s:
        group.info += enc_name(channel.name)
        if channel.type.info is None:
            channel.type.info = enc_struct(channel.type, 1)
    for channel in group.s2c:
        group.info += enc_name(channel.name)
        if channel.type.info is None:
            channel.type.info = enc_struct(channel.type, 1)


def dump_fields(num_fields: int, info: bytearray, indent: Indent) -> str:
    indent.increase()
    out = ""
    for _ in range(num_fields):
        out += dump_field(info, indent)
    indent.decrease()
    return out


def dump_field(info: bytearray, indent: Indent) -> str:
    out = ""
    name = dec_name(info)
    token = info[0]
    del info[:1]
    array_length = dec_array_length(token, info)

    if array_length == 1:
        array = ""
    else:
        array = "[" + str(array_length) + "]"

    line = str(name) + array + ": "

    field_type = token & FIELD_TYPE_MASK
    if field_type == FieldType.PRIMITIVE:
        out += indent.line(line + str_primitive(info[0]))
        del info[0:1]
    else:
        num_fields = dec_num_fields(token, info)
        if field_type == FieldType.STRUCT:
            out += indent.line(line + "struct {")
        else:
            out += indent.line(line + "union {")
        out += dump_fields(num_fields, info, indent)
    return out


def dump_channel(name: str, info: bytearray, indent: Indent) -> str:
    indent.increase()
    token = info[0]
    del info[:1]
    line = "channel " + name + ": "
    match token & FIELD_TYPE_MASK:
        case FieldType.STRUCT:
            line += "struct"
        case FieldType.UNION:
            line += "union"
    out = indent.line(line + " {")

    num_fields = dec_num_fields(token, info)
    out += dump_fields(num_fields, info, indent)
    out += indent.line("}")
    indent.decrease()
    return out


def dump_group_info(group: Group):
    indent = Indent(IndentStyle.SPACES, 2)
    info = bytearray(group.info)
    name = dec_name(info)
    out = indent.line("group " + name + ":")
    indent.increase()
    out += indent.line("c2s:")
    for channel in group.c2s:
        out += dump_channel(dec_name(info), bytearray(channel.type.info), indent)
    out += indent.line("s2c:")
    for channel in group.s2c:
        out += dump_channel(dec_name(info), bytearray(channel.type.info), indent)
    print(out)
