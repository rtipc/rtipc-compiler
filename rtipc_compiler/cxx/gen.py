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
            return "std::int8_t"
        case Primitive.U8:
            return "std::uint8_t"
        case Primitive.I16:
            return "std::int16_t"
        case Primitive.U16:
            return "std::uint16_t"
        case Primitive.I32:
            return "std::int32_t"
        case Primitive.U32:
            return "std::uint32_t"
        case Primitive.F32:
            return "float"
        case Primitive.I64:
            return "std::int64_t"
        case Primitive.U64:
            return "std::uint64_t"
        case Primitive.F64:
            return "double"
        case Primitive.I128:
            raise RuntimeError("I128 not supported")
        case Primitive.U128:
            raise RuntimeError("U128 not supported")
        case Primitive.F128:
            raise RuntimeError("F128 not supported")
        case _:
            raise RuntimeError("unknown primitive type")


def header_name(name: str) -> str:
    return name + ".h"


def source_start(form: Formatter, includes: list[str]):
    for inc in includes:
        if inc == "":
            form.blank_line(1)
        else:
            form.add_line("#include " + inc)
    form.blank_line(2)


def field_name(name: str) -> str:
    return convert_name(name, NameStyle.SNAKECASE)


def function_acquire_name(role: str, group_name: str, channel_name: str) -> str:
    return cat_name([role, group_name, "acquire", channel_name], NameStyle.SNAKECASE)


def struct_name(name: str) -> str:
    return cat_name([name], NameStyle.PASCALCASE)


def struct_info_name(name: str) -> str:
    return cat_name(["c", "channel", name, "info"], NameStyle.SNAKECASE)


def group_info_name(name: str) -> str:
    return cat_name(["c", "group", name, "info"], NameStyle.SNAKECASE)


def group_attr_name(role: EndpointRole, name: str) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name([strrole, "group", name], NameStyle.SNAKECASE)


def direction_channels_name(name: str, direction: str) -> str:
    return cat_name(["c", name, direction, "channels"], NameStyle.SNAKECASE)


def consumer_channels_name(role: EndpointRole, name: str) -> str:
    direction = "s2c" if role == EndpointRole.CLIENT else "c2s"
    return direction_channels_name(name, direction)


def producer_channels_name(role: EndpointRole, name: str) -> str:
    direction = "c2s" if role == EndpointRole.CLIENT else "s2c"
    return direction_channels_name(name, direction)


def acquire_function_name(
    role: EndpointRole, group_name: str, channel_name: str
) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name([strrole, group_name, "acquire", channel_name], NameStyle.SNAKECASE)


def gen_header(
    form: Formatter, namespace: str, groups: list[Group], structs: list[Struct]
):
    def header_start(includes: list[str]):
        form.add_line("#pragma once")
        form.blank_line(2)
        for inc in includes:
            if inc == "":
                form.blank_line(1)
            else:
                form.add_line("#include " + inc)
        form.blank_line(2)
        if (namespace != None) and (namespace != ""):
            form.add_line("namespace " + namespace + " {")
            form.blank_line(2)

    def header_end():
        if (namespace != None) and (namespace != ""):
            form.blank_line(2)
            form.add_line("}")

    def gen_structs_defs():
        def gen_struct_def(struct: Struct):
            def gen_field(field: Field):
                if isinstance(field.type, Primitive):
                    form.put(primitive_name(field.type))
                elif isinstance(field.type, Struct):
                    form.put(struct_name(field.type.name))

                form.put(" " + field_name(field.name))
                if field.length > 1:
                    form.put("[" + str(field.length) + "]")
                form.end_line(";")

            def start_struct():
                if struct.is_union:
                    form.put("union")
                else:
                    form.put("struct")
                form.end_line(" " + struct_name(struct.name) + " {", 1)

            def end_struct():
                form.start_line("};", -1)
                form.blank_line()

            start_struct()

            for field in struct.fields:
                gen_field(field)

            end_struct()

        for struct in structs:
            gen_struct_def(struct)

    def gen_info(name: str, info: bytes = True):
        def gen_values():
            for c in info[:-1]:
                form.put(hex(c) + ",")
            form.put(hex(info[-1]))

        if (info is None) or (info == ""):
            return ""
        form.end_line("const rtipc::Info " + name + "{", 1)
        gen_values()
        form.end_line("};", -1)
        form.blank_line()

    def gen_structs_infos():
        for struct in structs:
            name = struct_info_name(struct.name)
            gen_info(name, struct.info)
            form.blank_line()

    def gen_groups_infos():
        def gen_group_info(group: Group):
            name = group_info_name(group.name)
            gen_info(name, group.info)

        for group in groups:
            gen_group_info(group)

    def gen_groups_channels():
        def gen_dir_channels(group_name: str, direction: str, channels: list[Channel]):
            def gen_channel_attr(channel: Channel):
                form.put("rtipc::ChannelAttr{")
                form.put(
                    " .message_size = sizeof(" + struct_name(channel.type.name) + "),"
                )
                form.put(" .additional_messages = " + str(channel.add_msgs) + ",")
                if channel.eventfd:
                    form.put(" .eventfd = true,")
                else:
                    form.put(" .eventfd = false,")
                form.end_line(" .info = " + struct_info_name(channel.type.name) + "},")

            form.end_line(
                "const std::vector<rtipc::ChannelAttr> "
                + direction_channels_name(group.name, direction)
                + "{",
                1,
            )
            for channel in channels:
                gen_channel_attr(channel)
            form.end_line("};", -1)
            form.blank_line()

        for group in groups:
            gen_dir_channels(group.name, "c2s", group.c2s)
            gen_dir_channels(group.name, "s2c", group.s2c)
            form.blank_line()

    def gen_groups_attrs():
        def gen_group_attr(group: Group, role: EndpointRole):
            def gen_channel_acquire_consumer(channel: Channel, index: int):
                func_name = acquire_function_name(role, group.name, channel.name)
                attr_name = group_attr_name(role, group.name)
                form.add_line(
                    "rtipc::Consumer<"
                    + struct_name(channel.type.name)
                    + "> "
                    + func_name
                    + "(rtipc::ChannelGroup &group)"
                )
                form.end_line("{", 1)
                form.end_line(
                    "auto remote_attr = group.get_consumer_attr(" + str(index) + ");"
                )
                form.blank_line()
                form.add_line(
                    "const auto& expect_attr = &"
                    + attr_name
                    + ".consumers["
                    + str(index)
                    + "];"
                )
                form.end_line("if (!(expect_attr == &remote_attr)) {", 1)
                form.end_line('throw rtipc::Error("attribute mismatch");')
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "return group.acquire_consumer<"
                    + struct_name(channel.type.name)
                    + ">("
                    + str(index)
                    + ");"
                )
                form.add_line("}", -1)
                form.blank_line()

            def gen_channel_acquire_producer(channel: Channel, index: int):
                func_name = acquire_function_name(role, group.name, channel.name)
                attr_name = group_attr_name(role, group.name)
                form.add_line(
                    "rtipc::Producer<"
                    + struct_name(channel.type.name)
                    + "> "
                    + func_name
                    + "(rtipc::ChannelGroup &group)"
                )
                form.end_line("{", 1)
                form.end_line(
                    "auto remote_attr = group.get_producer_attr(" + str(index) + ");"
                )
                form.blank_line()
                form.add_line(
                    "const auto& expect_attr = &"
                    + attr_name
                    + ".producers["
                    + str(index)
                    + "];"
                )
                form.end_line("if (!(expect_attr == &remote_attr)) {", 1)
                form.end_line('throw rtipc::Error("attribute mismatch");')
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "return group.acquire_producer<"
                    + struct_name(channel.type.name)
                    + ">("
                    + str(index)
                    + ");"
                )
                form.add_line("}", -1)
                form.blank_line()

            name = group_attr_name(role, group.name)
            form.start_line("const rtipc::GroupAttr ")
            form.end_line(name + " = {", 1)
            form.end_line(
                ".consumers = " + consumer_channels_name(role, group.name) + ","
            )
            form.end_line(
                ".producers = " + producer_channels_name(role, group.name) + ","
            )
            form.end_line(".info = " + group_info_name(group.name))
            form.add_line("};", -1)
            form.blank_line()

            if role == EndpointRole.CLIENT:
                for i, channel in enumerate(group.s2c):
                    gen_channel_acquire_consumer(channel, i)
                for i, channel in enumerate(group.c2s):
                    gen_channel_acquire_producer(channel, i)
            else:
                for i, channel in enumerate(group.c2s):
                    gen_channel_acquire_consumer(channel, i)
                for i, channel in enumerate(group.s2c):
                    gen_channel_acquire_producer(channel, i)

        for group in groups:
            gen_group_attr(group, EndpointRole.CLIENT)
            form.blank_line()
            gen_group_attr(group, EndpointRole.SERVER)
            form.blank_line(2)

    header_start(["<vector>", "", "<rtipc/rtipc.hpp>"])
    gen_structs_defs()
    form.blank_line(1)
    gen_structs_infos()
    gen_groups_infos()
    form.blank_line()
    gen_groups_channels()
    form.blank_line()
    gen_groups_attrs()
    header_end()


def generate(
    path: Path, namespace: str, name: str, groups: list[Group], structs: list[Struct]
):
    indent = Indent(IndentStyle.SPACES, 4)
    form = Formatter(indent, max_width=75)

    gen_header(form, namespace, groups, structs)
    file = path / (name + ".hpp")
    file.write_text(form.take())
