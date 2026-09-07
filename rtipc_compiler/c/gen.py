from dataclasses import dataclass
from pathlib import Path
from protocol import Struct, Field, Primitive
from utils import Indent, Formatter, convert_name, cat_name, IndentStyle, NameStyle

file_begin = """#pragma once

$include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
"""

file_end = """
#ifdef __cplusplus
}
#endif
"""


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


#static const char c_grp_dir_channel_info[] = {0x1, 0x3 0x4}; 

#const ri_channel_attr_t client2server_channels[] = {
#    (ri_channel_attr_t) { .add_msgs = 0, .msg_size = sizeof(msg_command_t), .eventfd = 1, .info = { .data = COMMAND_INFO, .size = sizeof(COMMAND_INFO) }},
#  { 0 },
#};


#const ri_channel_attr_t server2client_channels[] = {
#  (ri_channel_attr_t) { .add_msgs = 0, .msg_size = sizeof(msg_response_t), .eventfd = 1, .info = { .data = RESPONSE_INFO, .size = sizeof(RESPONSE_INFO) }},
#  (ri_channel_attr_t) { .add_msgs = 10, .msg_size = sizeof(msg_event_t), .eventfd = 1, .info = { .data = EVENT_INFO, .size = sizeof(EVENT_INFO) }},
#  { 0 },
#};

#const ri_group_attr_t grp_attr = {
#    .consumers = server2client_channels,
#    .producers = client2server_channels,
#    .info = { .data = GROUP_INFO, .size = sizeof(GROUP_INFO) }
#};


def header_name(name: str) -> str:
    return name + ".h"


def variable_name(name: str) -> str:
    return convert_name(name, NameStyle.SNAKECASE)


def struct_name(prefix: str, struct_name: str) -> str:
    return cat_name([prefix, struct_name], NameStyle.SNAKECASE)


def struct_info_name(prefix: str, struct_name: str) -> str:
    return cat_name([prefix, struct_name, "info"], NameStyle.SNAKECASE)

    
def group_attr_name(prefix: str, group_name: str) -> str:
    return cat_name([prefix, "group", group_name], NameStyle.SNAKECASE)


def direction_channels_name(group_name: str, direction: str) -> str:
    return cat_name(["group", group_name, direction, "channels"], NameStyle.SNAKECASE)    


def gen_source(form: Formatter, header: str, prefix: str, groups: list[Groups], structs: list[Struct]):
    def gen_infos():
        def struct_info_data_name(channel_name: str) -> str:
            return struct_info_name(prefix, channel_name) + "_data"
            
        def gen_info(struct: Struct):
            def gen_values(info: bytes):
                for c in info[:-1]:
                    form.put(hex(c) + ",")
                form.put(hex(info[-1]))
            if (struct.info is None) or (struct.info == ""):
                return ""

            form.put("static const uint8_t " + struct_info_data_name(struct.name) + "[] = {")
            gen_values(struct.info)
            form.end_line("};")
            form.blank_line()
            
            form.end_line("const ri_info_t " + struct_info_name(prefix, struct.name) + " = { ", 1)
            form.end_line(".data = " + struct_info_data_name(struct.name) + ",")
            form.end_line(".size = sizeof(" + struct_info_data_name(struct.name) + ")", -1)
            form.end_line("};")
            
        for struct in structs:
            gen_info(struct)
            form.blank_line(2)
            
    def gen_groups_attrs():
        def gen_group_attr(group: Group):
            def gen_channel_attr(channel: Channel):
                form.put("(ri_channel_attr_t) {")
                form.put(" .add_msgs = " + str(channel.add_msgs) + "," )
                form.put(" .msg_size = sizeof(" + struct_info_name(prefix, channel.type.name) + "),")
                if channel.eventfd:
                    form.end_line(" .eventfd = 1 },")
                else:
                    form.end_line(" .eventfd = 0 },")
            def gen_dir_channels(group_name: str, direction: str, channels: list[Channel]):
                form.end_line("static const ri_channel_attr_t " + direction_channels_name(group.name, direction) + "[]"  " = { ", 1)
                for channel in channels:
                    gen_channel_attr(channel)
                form.end_line("{ 0 },", -1) 
                form.end_line("};") 
                form.blank_line() 
                            
            gen_dir_channels(group.name, "c2s", group.c2s)
            gen_dir_channels(group.name, "s2c", group.s2c)
            
            form.end_line("const ri_group_attr_t " + group_attr_name(prefix, group.name) + " = { ", 1)
            form.end_line(".consumers = " + direction_channels_name(group.name, "s2c") + ",")
            form.end_line(".producers = " + direction_channels_name(group.name, "c2s")) 
            form.end_line("};") 
        for group in groups:
            gen_group_attr(group)
            form.blank_line()
        
    form.add_line("#include \"" + header + "\"")
    form.blank_line(2)
    
    gen_infos()
    form.blank_line()
    gen_groups_attrs()
    
    
def gen_header(form: Formatter, prefix: str, groups: list[Groups], structs: list[Struct]):
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
                    raise RuntimeError("unsupported field type: " + str(field))
                form.put(" " + variable_name(field.name))
                if field.length > 1:
                    form.put("[" + str(field.length) + "]")
                form.end_line(";")

            def start_struct():
                if struct.is_union:
                    form.put("union")
                else:
                    form.put("struct")
                form.end_line(" " + struct_name(prefix, struct.name) + " {", 1)

            def end_struct():
                form.start_line("};", -1)
                form.blank_line()

            start_struct()
            
            for field in struct.fields:
                gen_field(field)
                
            end_struct()
            
        for struct in structs:
            gen_struct_def(struct)
    form.add_line("#pragma once")
    form.blank_line(2)
    form.add_line("#include <stdint.h>")
    form.blank_line(1)
    form.add_line("#include <rtipc/rtipc.h>")
    form.blank_line(2)
    gen_structs_defs()


@dataclass
class CStyle:
    prefix = ""
    variableStyle = NameStyle.SNAKECASE
    structStyle = NameStyle.SNAKECASE
    indent = Indent(IndentStyle.SPACES, 4)
    def __init__(self):
        self.form = Formatter(indent) 
    

class CGenerator(object):
    def __init__(self):
        self.indent = Indent(IndentStyle.SPACES, 4)
        self.prefix = ""
        self.variableStyle = NameStyle.SNAKECASE
        self.structStyle = NameStyle.SNAKECASE







    def write(self, path: Path, name: str, groups: list[Group], structs: list[Struct]):
        indent = Indent(IndentStyle.SPACES, 4)
        form = Formatter(indent, max_width = 75)
        gen_header(form, "rpc", groups, structs)
        header = path / (name + ".h")
        header.write_text(form.take())
        
        gen_source(form, name + ".h", "rpc", groups, structs)
        source = path / (name + ".c")
        source.write_text(form.take())
       
        #out = gen_source(indent, name, groups, structs)
        #print("header: \n" + out)
        
        #gen_structs_infos(form, structs)
        #gen_groups_attrs(form, groups)
        #out = form.take()
        #out = gen_source(indent, name, groups, structs)
        #print("source: \n")
        #self.generate(structs)
        #out = gen_group_infos(indent: Indent, group: Group)
       
        

