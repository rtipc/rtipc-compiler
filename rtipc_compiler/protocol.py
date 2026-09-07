from typing import Union
from enum import Enum, IntEnum
from dataclasses import dataclass

PRIMITIVE_SIZE_MASK = 0x07
PRIMITIVE_SIZE_BOOLEAN = 0x00
PRIMITIVE_SIZE_8 = 0x01
PRIMITIVE_SIZE_16 = 0x02
PRIMITIVE_SIZE_32 = 0x03
PRIMITIVE_SIZE_64 = 0x04
PRIMITIVE_SIZE_128 = 0x05

PRIMITIVE_TYPE_MASK = 0x70
PRIMITIVE_TYPE_SIGNED = 0x00
PRIMITIVE_TYPE_UNSIGNED = 0x10
PRIMITIVE_TYPE_FLOAT = 0x20


class Primitive(IntEnum):
    BOOL = PRIMITIVE_SIZE_BOOLEAN
    I8 = PRIMITIVE_TYPE_SIGNED | PRIMITIVE_SIZE_8
    U8 = PRIMITIVE_TYPE_UNSIGNED | PRIMITIVE_SIZE_8
    I16 = PRIMITIVE_TYPE_SIGNED | PRIMITIVE_SIZE_16
    U16 = PRIMITIVE_TYPE_UNSIGNED | PRIMITIVE_SIZE_16
    I32 = PRIMITIVE_TYPE_SIGNED | PRIMITIVE_SIZE_32
    U32 = PRIMITIVE_TYPE_UNSIGNED | PRIMITIVE_SIZE_32
    F32 = PRIMITIVE_TYPE_FLOAT | PRIMITIVE_SIZE_32
    I64 = PRIMITIVE_TYPE_SIGNED | PRIMITIVE_SIZE_64
    U64 = PRIMITIVE_TYPE_UNSIGNED | PRIMITIVE_SIZE_64
    F64 = PRIMITIVE_TYPE_FLOAT | PRIMITIVE_SIZE_64
    I128 = PRIMITIVE_TYPE_SIGNED | PRIMITIVE_SIZE_128
    U128 = PRIMITIVE_TYPE_UNSIGNED | PRIMITIVE_SIZE_128
    F128 = PRIMITIVE_TYPE_FLOAT | PRIMITIVE_SIZE_128


@dataclass
class Struct:
    name: str
    is_union: bool
    fields: list["Field"]
    info: str


@dataclass
class Field:
    name: str
    type: Union[Struct, Primitive]
    length: int


@dataclass
class Channel:
    name: str
    type: Struct
    add_msgs: int
    eventfd: bool


@dataclass
class Group:
    name: str
    c2s: list[Channel]
    s2c: list[Channel]
    info: str
