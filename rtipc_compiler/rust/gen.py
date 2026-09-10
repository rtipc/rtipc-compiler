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


def struct_name(name: str) -> str:
    return cat_name([name], NameStyle.PASCALCASE)


def struct_info_name(name: str) -> str:
    return cat_name([name, "info"], NameStyle.CONSTANTCASE)


def group_info_name(name: str) -> str:
    return cat_name([name, "info"], NameStyle.CONSTANTCASE)


def group_attr_fn_name(role: EndpointRole, name: str) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name([strrole, "group", name, "create"], NameStyle.SNAKECASE)


def direction_channels_name(name: str, direction: str) -> str:
    return cat_name(["group", name, direction, "channels"], NameStyle.SNAKECASE)


def gen_source(
    form: Formatter,
    groups: list[Group],
    structs: list[Struct],
):
    def gen_info(name: str, info: bytes):
        def gen_values():
            form.break_line(hex(info[0]) + ",")
            for c in info[1:-1]:
                form.put(hex(c) + ",", True)
            form.put(hex(info[-1]) + ",", True)

        if (info is None) or (info == ""):
            return ""
        form.add_line("#[allow(dead_code)]")
        form.put("pub const " + name + ": &[u8] = &[")
        gen_values()
        form.start_line("];")
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
            form.start_line("pub " + variable_name(field.name) + ": ")
            type = ""
            if isinstance(field.type, Primitive):
                type = primitive_name(field.type)
            elif isinstance(field.type, Struct):
                type = struct_name(field.type.name)
            else:
                raise TypeError("unsupported field type: " + str(field))

            if field.length > 1:
                form.put("[" + type + "; " + str(field.length) + "]")
            else:
                form.put(type)
            form.end_line(",")

        def start_struct(struct: Struct):
            form.add_line("#[repr(C)]")
            form.add_line("#[derive(Copy, Clone, Debug)]")
            form.start_line("pub ")
            if struct.is_union:
                form.put("union")
            else:
                form.put("struct")
            form.end_line(" " + struct_name(struct.name) + " {", 1)

        def end_struct():
            form.start_line("}", -1)
            form.blank_line()

        def gen_debug():
            def gen_debug_field(field: Field):
                if field.length == 1:
                    form.add_line(
                        'writeln!(f, "'
                        + field.name
                        + ':  {}", self.'
                        + variable_name(field.name)
                        + ")?;"
                    )
                else:
                    form.end_line(
                        "for (i, v) in self."
                        + variable_name(field.name)
                        + ".iter().enumerate() {",
                        1,
                    )
                    form.end_line(
                        'writeln!(f, "\\t'
                        + variable_name(field.name)
                        + '[{}]: {}", i, v)?;'
                    )
                    form.add_line("}", -1)

            form.end_line("impl fmt::Display for " + struct_name(struct.name) + " {", 1)
            form.end_line("fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {", 1)

            for field in struct.fields:
                gen_debug_field(field)
            form.end_line("Ok(())", -1)
            form.end_line("}", -1)
            form.end_line("}")
            form.blank_line()

        start_struct(struct)
        for field in struct.fields:
            gen_field(field)
        end_struct()
        gen_debug()

    def gen_group_attr(group: Group, role: EndpointRole):
        def gen_channel_attr(channel: Channel):
            eventfd = "true" if channel.eventfd else "false"
            form.end_line("ChannelAttr {", 1)
            form.add_line("additional_messages: " + str(channel.add_msgs) + ",")
            form.add_line(
                "message_size: unsafe { NonZeroUsize::new_unchecked(size_of::<"
                + struct_name(channel.type.name)
                + ">()) },"
            )
            form.add_line("eventfd: " + eventfd + ",")
            form.add_line("info: " + struct_info_name(channel.type.name) + ".to_vec(),")
            form.add_line("},", -1)

        def gen_channel_arrays():
            form.end_line("let c2s_channels: &[ChannelAttr] = &[", 1)

            for channel in group.c2s:
                gen_channel_attr(channel)

            form.add_line("];", -1)
            form.blank_line()

            form.end_line("let s2c_channels: &[ChannelAttr] = &[", 1)
            for channel in group.s2c:
                gen_channel_attr(channel)
            form.add_line("];", -1)

        form.end_line(
            "pub fn " + group_attr_fn_name(role, group.name) + "() -> GroupAttr {", 1
        )
        gen_channel_arrays()
        form.blank_line()
        form.end_line("GroupAttr {", 1)
        if role == EndpointRole.CLIENT:
            form.add_line("producers: c2s_channels.to_vec(),")
            form.add_line("consumers: s2c_channels.to_vec(),")
        else:
            form.add_line("producers: c2s_channels.to_vec(),")
            form.add_line("consumers: s2c_channels.to_vec(),")
        form.add_line("info: " + group_info_name(group.name) + ".to_vec(),")
        form.add_line("}", -1)
        form.add_line("}", -1)

    form.add_line("use std::num::NonZeroUsize;")
    form.add_line("use std::fmt;")
    form.add_line("use rtipc::{ChannelAttr, GroupAttr};")
    form.blank_line(2)
    gen_infos()
    for struct in structs:
        gen_struct(struct)
    for group in groups:
        gen_group_attr(group, EndpointRole.CLIENT)
        gen_group_attr(group, EndpointRole.SERVER)


def generate(path: Path, name: str, groups: list[Group], structs: list[Struct]):
    indent = Indent(IndentStyle.SPACES, 4)
    form = Formatter(indent, max_width=98)

    gen_source(form, groups, structs)

    file = path / (name + ".rs")

    file.write_text(form.take())
