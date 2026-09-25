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
            return "int8_t"
        case Primitive.U8:
            return "uint8_t"
        case Primitive.I16:
            return "int16_t"
        case Primitive.U16:
            return "uint16_t"
        case Primitive.I32:
            return "int32_t"
        case Primitive.U32:
            return "uint32_t"
        case Primitive.F32:
            return "float"
        case Primitive.I64:
            return "int64_t"
        case Primitive.U64:
            return "uint64_t"
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


def function_acquire_name(
    prefix: str, role: str, group_name: str, channel_name: str
) -> str:
    return cat_name(
        [prefix, role, group_name, "acquire", channel_name], NameStyle.SNAKECASE
    )


def struct_name(prefix: str, name: str) -> str:
    return cat_name([prefix, name], NameStyle.SNAKECASE)

def struct_type_name(prefix: str, name: str) -> str:
    return cat_name([prefix, name, "t"], NameStyle.SNAKECASE)

def struct_info_name(prefix: str, name: str) -> str:
    return cat_name([prefix, "channel", name, "info"], NameStyle.SNAKECASE)


def group_info_name(prefix: str, name: str) -> str:
    return cat_name([prefix, "group", name, "info"], NameStyle.SNAKECASE)


def group_attr_name(prefix: str, role: EndpointRole, name: str) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name([prefix, strrole, "group", name], NameStyle.SNAKECASE)


def direction_channels_name(name: str, direction: str) -> str:
    return cat_name(["group", name, direction, "channels"], NameStyle.SNAKECASE)


def consumer_channels_name(role: EndpointRole, name: str) -> str:
    direction = "s2c" if role == EndpointRole.CLIENT else "c2s"
    return direction_channels_name(name, direction)


def producer_channels_name(role: EndpointRole, name: str) -> str:
    direction = "c2s" if role == EndpointRole.CLIENT else "s2c"
    return direction_channels_name(name, direction)


def acquire_function_name(
    prefix: str, role: EndpointRole, group_name: str, channel_name: str
) -> str:
    strrole = "client" if role == EndpointRole.CLIENT else "server"
    return cat_name(
        [prefix, strrole, group_name, "acquire", channel_name], NameStyle.SNAKECASE
    )


def gen_header(
    form: Formatter, prefix: str, groups: list[Group], structs: list[Struct]
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
        form.add_line("#ifdef __cplusplus")
        form.add_line('extern "C" {')
        form.add_line("#endif")
        form.blank_line(2)

    def header_end():
        form.blank_line(2)
        form.add_line("#ifdef __cplusplus")
        form.add_line("}")
        form.add_line("#endif")

    def gen_structs_defs():
        def gen_struct_def(struct: Struct):
            def gen_field(field: Field):
                if isinstance(field.type, Primitive):
                    form.put(primitive_name(field.type))
                elif isinstance(field.type, Struct):
                    if field.type.is_union:
                        form.put("union " + struct_name(prefix, field.type.name))
                    else:
                        form.put("struct " + struct_name(prefix, field.type.name))
                else:
                    raise TypeError("unsupported field type: " + str(field))
                form.put(" " + field_name(field.name))
                if field.length > 1:
                    form.put("[" + str(field.length) + "]")
                form.end_line(";")

            def start_struct():
                if struct.is_union:
                    form.put("typedef union")
                else:
                    form.put("typedef struct")
                form.end_line(" " + struct_name(prefix, struct.name) + " {", 1)

            def end_struct():
                form.start_line("} " + struct_type_name(prefix, struct.name) + ";", -1)
                form.blank_line()

            start_struct()

            for field in struct.fields:
                gen_field(field)

            end_struct()

        for struct in structs:
            gen_struct_def(struct)

    def gen_infos():
        for struct in structs:
            name = struct_info_name(prefix, struct.name)
            form.add_line("extern const ri_info_t " + name + ";")
            form.blank_line()
        form.blank_line()
        for group in groups:
            name = group_info_name(prefix, group.name)
            form.add_line("extern const ri_info_t " + name + ";")
            form.blank_line()

    def gen_groups_attrs():
        def gen_group_attr(group: Group, role: EndpointRole):
            def gen_channel_acquire_consumer(channel: Channel, index: int):
                func_name = acquire_function_name(
                    prefix, role, group.name, channel.name
                )
                form.add_line("ri_consumer_t* " + func_name + "(ri_group_t *group);")

            def gen_channel_acquire_producer(channel: Channel, index: int):
                func_name = acquire_function_name(
                    prefix, role, group.name, channel.name
                )
                form.add_line("ri_producer_t* " + func_name + "(ri_group_t *group);")

            name = group_attr_name(prefix, role, group.name)
            form.start_line("extern const ri_group_attr_t ")
            form.end_line(name + ";")

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
            form.blank_line()

    header_start(["<stdint.h>", "", "<rtipc/rtipc.h>"])
    gen_structs_defs()
    form.blank_line(1)
    gen_infos()
    form.blank_line()
    gen_groups_attrs()
    form.blank_line()
    header_end()


def gen_source(
    form: Formatter,
    header: str,
    prefix: str,
    groups: list[Group],
    structs: list[Struct],
):
    def gen_info(name: str, info: bytes, static: bool = True):
        def data_name() -> str:
            return cat_name([name, "data"], NameStyle.SNAKECASE)

        def gen_values():
            for c in info[:-1]:
                form.put(hex(c) + ",")
            form.put(hex(info[-1]))

        if (info is None) or (info == ""):
            return ""
        if static:
            form.put("static ")
        form.put("const uint8_t " + data_name() + "[] = {")
        gen_values()
        form.end_line("};")
        form.blank_line()

        form.end_line("const ri_info_t " + name + " = {", 1)
        form.end_line(".data = " + data_name() + ",")
        form.end_line(".size = sizeof(" + data_name() + ")", -1)
        form.end_line("};")
        form.blank_line()

    def gen_structs_infos():
        for struct in structs:
            name = struct_info_name(prefix, struct.name)
            gen_info(name, struct.info)
            form.blank_line()

    def gen_groups_infos():
        def gen_group_info(group: Group):
            name = group_info_name(prefix, group.name)
            gen_info(name, group.info)

        for group in groups:
            gen_group_info(group)

    def gen_groups_channels():
        def gen_channel_attr(channel: Channel):
            form.put("{")
            form.put(
                " .msg_size = sizeof(" + struct_type_name(prefix, channel.type.name) + "),"
            )
            form.put(" .add_msgs = " + str(channel.add_msgs) + ",")
            if channel.eventfd:
                form.put(" .eventfd = true,")
            else:
                form.put(" .eventfd = false,")
            form.end_line(
                " .info = " + struct_info_name(prefix, channel.type.name) + "},"
            )

        def gen_dir_channels(group_name: str, direction: str, channels: list[Channel]):
            form.end_line(
                "static const ri_channel_attr_t "
                + direction_channels_name(group.name, direction)
                + "[]"
                " = {",
                1,
            )
            for channel in channels:
                gen_channel_attr(channel)
            form.end_line("{ 0 },", -1)
            form.end_line("};")
            form.blank_line()

        for group in groups:
            gen_dir_channels(group.name, "c2s", group.c2s)
            gen_dir_channels(group.name, "s2c", group.s2c)
            form.blank_line()

    def gen_groups_attrs():
        def gen_group_attr(group: Group, role: EndpointRole):
            def gen_channel_acquire_consumer(channel: Channel, index: int):
                func_name = acquire_function_name(
                    prefix, role, group.name, channel.name
                )
                attr_name = group_attr_name(prefix, role, group.name)
                form.add_line("ri_consumer_t* " + func_name + "(ri_group_t *group)")
                form.end_line("{", 1)
                form.end_line(
                    "const ri_channel_attr_t *remote_attr = ri_group_get_consumer_attr(group, "
                    + str(index)
                    + ");"
                )
                form.end_line("if (!remote_attr) {", 1)
                form.add_line("return NULL;")
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "const ri_channel_attr_t *expect_attr = &"
                    + attr_name
                    + ".consumers["
                    + str(index)
                    + "];"
                )
                form.end_line(
                    "if (!ri_channel_attr_equal(expect_attr, remote_attr)) {", 1
                )
                form.end_line("return NULL;")
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "return ri_group_acquire_consumer(group, " + str(index) + ");"
                )
                form.add_line("}", -1)
                form.blank_line()

            def gen_channel_acquire_producer(channel: Channel, index: int):
                func_name = acquire_function_name(
                    prefix, role, group.name, channel.name
                )
                attr_name = group_attr_name(prefix, role, group.name)
                form.add_line("ri_producer_t* " + func_name + "(ri_group_t *group)")
                form.end_line("{", 1)
                form.end_line(
                    "const ri_channel_attr_t *remote_attr = ri_group_get_producer_attr(group, "
                    + str(index)
                    + ");"
                )
                form.end_line("if (!remote_attr) {", 1)
                form.add_line("return NULL;")
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "const ri_channel_attr_t *expect_attr = &"
                    + attr_name
                    + ".producers["
                    + str(index)
                    + "];"
                )
                form.end_line(
                    "if (!ri_channel_attr_equal(expect_attr, remote_attr)) {", 1
                )
                form.end_line("return NULL;")
                form.add_line("}", -1)
                form.blank_line()
                form.add_line(
                    "return ri_group_acquire_producer(group, " + str(index) + ");"
                )
                form.add_line("}", -1)
                form.blank_line()

            name = group_attr_name(prefix, role, group.name)
            form.start_line("const ri_group_attr_t ")
            form.end_line(name + " = {", 1)
            form.end_line(
                ".consumers = " + consumer_channels_name(role, group.name) + ","
            )
            form.end_line(
                ".producers = " + producer_channels_name(role, group.name) + ","
            )
            form.end_line(".info = " + group_info_name(prefix, group.name))
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

    source_start(form, ['"' + header + '"'])
    gen_structs_infos()
    form.blank_line()
    gen_groups_infos()
    form.blank_line()
    gen_groups_channels()
    gen_groups_attrs()


def generate(
    path: Path, prefix: str, name: str, groups: list[Group], structs: list[Struct]
):
    if prefix is None:
        prefix = ""
    indent = Indent(IndentStyle.SPACES, 4)
    form = Formatter(indent, max_width=75)

    gen_header(form, prefix, groups, structs)
    file = path / (name + ".h")
    file.write_text(form.take())

    gen_source(form, name + ".h", prefix, groups, structs)
    file = path / (name + ".c")
    file.write_text(form.take())
