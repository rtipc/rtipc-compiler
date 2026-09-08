from dataclasses import dataclass
from pathlib import Path

from protocol import Channel, Field, Group, Primitive, Struct
from utils import Formatter, Indent, IndentStyle, NameStyle, convert_name


def primitive_name(primitive: Primitive) -> str:
    match primitive:
        case Primitive.BOOL:
            return "bool"
        case Primitive.I8:
            return "i8"
        case Primitive.U8:
            return "u8"
        case Primitive.I16:
            return "i16"
        case Primitive.U16:
            return "u16"
        case Primitive.I32:
            return "i32"
        case Primitive.U32:
            return "u32"
        case Primitive.F32:
            return "f32"
        case Primitive.I64:
            return "i64"
        case Primitive.U64:
            return "u64"
        case Primitive.F64:
            return "f64"
        case Primitive.I128:
            return "i128"
        case Primitive.U128:
            return "u128"
        case Primitive.F128:
            raise RuntimeError("F128 not supported")
        case _:
            raise RuntimeError("unknown primitive type")


def variable_name(name: str) -> str:
    return convert_name(name, NameStyle.SNAKECASE)


def struct_name(prefix: str, name: str) -> str:
    return cat_name([prefix, name], NameStyle.SNAKECASE)


def struct_info_name(prefix: str, name: str) -> str:
    return cat_name([prefix, name, "info"], NameStyle.SNAKECASE)


def group_info_name(prefix: str, name: str) -> str:
    return cat_name([prefix, "group", name, "info"], NameStyle.SNAKECASE)


def group_attr_name(prefix: str, role: str, name: str) -> str:
    return cat_name([prefix, role, "group", name], NameStyle.SNAKECASE)


def direction_channels_name(name: str, direction: str) -> str:
    return cat_name(["group", name, direction, "channels"], NameStyle.SNAKECASE)


@dataclass
class RustOption:
    filename: str
    outPath: str


class RustGenerator(object):
    def __init__(self):
        self.indent = Indent(IndentStyle.SPACES, 4)
        self.variableStyle = NameStyle.SNAKECASE
        self.structStyle = NameStyle.CAMELCASE

    def variableName(self, name: str) -> str:
        return convert_name(name, self.variableStyle)

    def structName(self, name: str) -> str:
        return convert_name(name, self.structStyle)

    def addLine(self, line: str):
        self.content = self.content + str(self.indent) + line + "\n"

    def generate(self, structs: list[Struct]):
        self.content = ""
        for struct in structs:
            self.addStruct(struct)
            self.addLine("")
        self.content = self.content + file_end

    def addField(self, field: Field):
        line = "pub " + self.variableName(field.name) + ": "
        if isinstance(field.type, Primitive):
            type = primitiveName(field.type)
        elif isinstance(field.type, Struct):
            type = self.structName(field.type.name)
        else:
            raise RuntimeError("unsupported field type: " + str(field))

        if field.length > 1:
            line = line + "[" + type + "; " + str(field.length) + "]"
        else:
            line = line + type
        line = line + ","
        self.addLine(line)

    def beginStruct(self, struct: Struct):
        self.addLine("#[repr(C)]")
        self.addLine("#[derive(Copy, Clone)]")
        line = "pub "
        if struct.is_union:
            line = line + "union"
        else:
            line = line + "struct"
        line = line + " " + self.structName(struct.name) + " {"
        self.addLine(line)
        self.indent.increase()

    def endStruct(self):
        self.indent.decrease()
        self.addLine("}")

    def addStruct(self, struct: Struct):
        self.beginStruct(struct)
        for field in struct.fields:
            self.addField(field)
        self.endStruct()

    def write(self, path: Path, name: str, structs: list[Struct]):
        self.generate(structs)

        file = path / (name + ".rs")

        file.write_text(self.content)
