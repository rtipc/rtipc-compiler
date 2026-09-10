from pathlib import Path

from protocol import Channel, Field, Group, Primitive, Struct
from utils import (
    EndpointRole,
    Formatter,
    Indent,
    IndentStyle,
    NameStyle,
    cat_name,
    convert_name,
)


def primitive_name(primitive: Primitive) -> str:
    name = "ctypes."
    match primitive:
        case Primitive.BOOL:
            name += "c_bool"
        case Primitive.I8:
            name += "c_int8"
        case Primitive.U8:
            name += "c_uint8"
        case Primitive.I16:
            name += "c_int16"
        case Primitive.U16:
            name += "c_uint16"
        case Primitive.I32:
            name += "c_int32"
        case Primitive.U32:
            name += "c_uint32"
        case Primitive.F32:
            name += "c_float"
        case Primitive.I64:
            name += "c_int64"
        case Primitive.U64:
            name += "c_uint64"
        case Primitive.F64:
            name += "c_double"
        case Primitive.I128:
            raise RuntimeError("i128 not supported")
        case Primitive.U128:
            raise RuntimeError("u128 not supported")
        case Primitive.F128:
            raise RuntimeError("F128 not supported")
        case _:
            raise RuntimeError("unknown primitive type")
    return name


def variable_name(name: str) -> str:
    return convert_name(name, NameStyle.SNAKECASE)


def struct_name(name: str) -> str:
    return cat_name([name], NameStyle.PASCALCASE)


def struct_info_name(name: str) -> str:
    return cat_name([name, "info"], NameStyle.CONSTANTCASE)


def group_info_name(name: str) -> str:
    return cat_name([name, "info"], NameStyle.CONSTANTCASE)


def group_channels_name(name: str, direction: str) -> str:
    return cat_name([name, direction, "channels"], NameStyle.SNAKECASE)


def group_attr_name(role: EndpointRole, name: str) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name([strrole, "group", name], NameStyle.SNAKECASE)


def direction_channels_name(name: str, direction: str) -> str:
    return cat_name(["group", name, direction, "channels"], NameStyle.SNAKECASE)


def gen_source(
    form: Formatter,
    groups: list[Group],
    structs: list[Struct],
):
    def gen_info(name: str, info: bytes):
        def gen_values():
            for c in info[:-1]:
                form.put(hex(c) + ",", True)

        if (info is None) or (info == ""):
            return ""
        form.start_line(name + " = bytes([")
        gen_values()
        form.end_line("]);")
        form.blank_line()

    def gen_infos():
        for struct in structs:
            name = struct_info_name(struct.name)
            gen_info(name, struct.info)

        for group in groups:
            name = group_info_name(group.name)
            gen_info(name, group.info)

    def gen_struct(struct: Struct):
        def gen_field(field: Field):
            type = ""
            if isinstance(field.type, Primitive):
                type = primitive_name(field.type)
            elif isinstance(field.type, Struct):
                type = struct_name(field.type.name)
            else:
                raise TypeError("unsupported field type: " + str(field))
            form.put('("' + variable_name(field.name) + '", ' + type)
            if field.length > 1:
                form.put(" * " + str(field.length))
            form.end_line("),")

        form.start_line("class " + struct_name(struct.name) + "(")
        if struct.is_union:
            form.put("ctypes.Union")
        else:
            form.put("ctypes.Structure")
        form.end_line("):", 1)
        form.end_line("_fields_ = [", 1)

        for field in struct.fields:
            gen_field(field)
        form.move_indent(-1)
        form.end_line("]", -1)
        form.blank_line(2)

    def gen_channel_arrays(group: Group, direction: str):
        def gen_channel_attr(channel: Channel):
            eventfd = "True" if channel.eventfd else "False"

            form.start_line("ChannelAttr(" + str(channel.add_msgs))
            form.put(", ctypes.sizeof(" + struct_name(channel.type.name) + ")")
            form.put(", " + eventfd)
            form.end_line(", " + struct_info_name(channel.type.name) + "),")

        channels = group.c2s if direction == "c2s" else group.s2c

        if not channels:
            return

        form.end_line(group_channels_name(group.name, direction) + " = [", 1)

        for channel in channels:
            gen_channel_attr(channel)

        form.add_line("]", -1)
        form.blank_line()

    def gen_group_attr(group: Group, role: EndpointRole):
        form.start_line(group_attr_name(role, group.name) + " = GroupAttr(")
        if role == EndpointRole.CLIENT:
            form.put(group_channels_name(group.name, "c2s") + ", ")
            form.put(group_channels_name(group.name, "s2c") + ", ")
        else:
            form.put(group_channels_name(group.name, "s2c") + ", ")
            form.put(group_channels_name(group.name, "c2s") + ", ")
        form.end_line(group_info_name(group.name) + ")")

    form.add_line("import ctypes")
    form.blank_line()
    form.add_line("from pyrtipc import ChannelAttr, GroupAttr")
    form.blank_line()
    
    gen_infos()
    for struct in structs:
        gen_struct(struct)
    for group in groups:
        gen_channel_arrays(group, "c2s")
        gen_channel_arrays(group, "s2c")
        gen_group_attr(group, EndpointRole.CLIENT)
        gen_group_attr(group, EndpointRole.SERVER)


def generate(path: Path, name: str, groups: list[Group], structs: list[Struct]):
    indent = Indent(IndentStyle.SPACES, 4)
    form = Formatter(indent, max_width=98)

    gen_source(form, groups, structs)

    file = path / (name + ".py")

    file.write_text(form.take())
