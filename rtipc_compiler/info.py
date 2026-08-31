from enum import IntEnum
from protocol import Group, Channel, Struct, Field, Primitive
from utils import Indent, IndentStyle
STRUCT_END = 0x80

FIELD_TYPE_MASK = 0x03


class FieldType(IntEnum):
    PRIMITIVE = 0x00
    STRUCT = 0x01
    UNION = 0x02


FIELD_LENGTH_MASK = 0x0C


class ArrayLengthSize(IntEnum):
    NONE = 0x00
    ONE = 0x04
    TWO = 0x08
    FOUR = 0x0C


UINT8_MAX = 0xFF
UINT16_MAX = 0xFFFF
UINT32_MAX = 0xFFFFFFFF

def str_primitive(primitive: int) -> str:
    return str(Primitive(primitive).name)


def enc_name(name: str) -> bytes:
    return len(name).to_bytes(1, "little") + name.encode("utf-8")


def dec_name(info: bytearray) -> str:
    name_length = info[0]
    name = info[1:name_length + 1].decode("utf-8")
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


def dec_array_length(type: int, info: bytearray) -> int:
    match type & FIELD_LENGTH_MASK:
        case ArrayLengthSize.NONE:            
            length = 0
        case ArrayLengthSize.ONE:
            length = info[0]
            del info[: 1]
        case ArrayLengthSize.TWO:
            length = int.from_bytes(info[0:2], byteorder="little")
            del info[: 2]
        case ArrayLengthSize.FOUR:
            length = int.from_bytes(info[0:4], byteorder="little")
            del info[: 4]
    return length + 1


def enc_field(field: Field, close_struct: bool) -> bytes:
    name = enc_name(field.name)
    (type, length) = enc_array_length(field.length)

    if close_struct:
        type |= STRUCT_END

    if isinstance(field.type, Primitive):
        type |= FieldType.PRIMITIVE
        tail = field.type.to_bytes(1, "little")
    else:
        if field.type.is_union:
            type |= FieldType.UNION
        else:
            type |= FieldType.STRUCT
        tail = enc_struct(field.type)
    return name + type.to_bytes(1, "little") + length + tail


def dump_field(info: bytearray, indent: Indent) -> str:
    out = ""
    name = dec_name(info)
    type = info[0]
    del info[: 1]
    array_length = dec_array_length(type, info)

    if array_length == 1:
        array = ""
    else:
        array = "[" + str(array_length) + "]"

    if type & STRUCT_END:
        indent.decrease()
        out += str(indent) + "}" + "\n"
        return out

    out += str(indent) + str(name) + array + ": "

    match type & FIELD_TYPE_MASK:
        case FieldType.PRIMITIVE:
            out += str_primitive(info[0])
            del info[0 : 1]
        case FieldType.STRUCT:
            out += "struct {"
            indent.increase()
        case FieldType.UNION:
            out += "union {"
            indent.increase()
    return out + "\n"


def enc_struct(struct: Struct) -> bytes:
    info = b''
    close_struct = False
    for field in struct.fields:
        info += enc_field(field, close_struct)
        if isinstance(field.type, Struct):
            close_struct = True
        else:
            close_struct = False
    return info


def add_group_info(group: Group):
    group.info = enc_name(group.name)
    for channel in group.c2s:
        channel.info = enc_name(channel.name) + enc_struct(channel.type)
        print(channel.info)
    for channel in group.s2c:
        channel.info = enc_name(channel.name) + enc_struct(channel.type)
        print(channel.info)


def dump_channel(info: bytearray, indent: Indent) -> str:
    name = dec_name(info)
    out = str(indent) + "channel " + name + ":" + "\n"
    indent.increase()
    while len(info) > 1:
        out += dump_field(info, indent)
    indent.decrease()
    return out


def dump_group_info(group: Group):
    indent = Indent(IndentStyle.SPACES, 2)
    info = bytearray(group.info)
    
    name = dec_name(info)
    print("group " + name + ":" )
    indent.increase()
    print(str(indent) + "c2s:")
    indent.increase()
    for channel in group.c2s:
        out = dump_channel(bytearray(channel.info), indent)
        print(out)
    indent.decrease()
    print(str(indent) + "s2c:")
    indent.increase()
    for channel in group.s2c:
        out = dump_channel(bytearray(channel.info), indent)
        print(out)
    indent.decrease()
