import re
from dataclasses import dataclass
from enum import Enum


class EndpointRole(Enum):
    CLIENT = (1,)
    SERVER = 2


class IndentStyle(Enum):
    SPACES = " "
    TABS = "\t"


class NameStyle(Enum):
    CAMELCASE = 1
    CONSTANTCASE = 2
    SNAKECASE = 3
    PASCALCASE = 4


@dataclass
class LinePart:
    text: str
    add_space: bool


class Indent:
    def __init__(self, style: IndentStyle, num_tabs: int):
        self.style = style
        self.num_tabs = num_tabs
        self.current = 0
        self.spaces_per_tab = 4

    def to_spaces(self) -> int:
        length = self.num_tabs * self.current

        if self.style == IndentStyle.TABS:
            length *= self.spaces_per_tab
        return length

    def move(self, n: int):
        new_n = self.current + n
        if new_n < 0:
            raise RuntimeError("can't decrease indent below zero")
        self.current = new_n

    def set(self, n: int):
        if n < 0:
            raise RuntimeError("can't decrease indent below zero")
        self.current = n

    def increase(self):
        self.move(1)

    def decrease(self):
        self.move(-1)

    def line(self, content: str, n: int = 1) -> str:
        out = ""
        if (content is not None) and (content != ""):
            out = str(self) + content
        out += "\n" * n
        return out

    def __str__(self):
        return str(self.style.value) * self.num_tabs * self.current


class Formatter:
    def __init__(self, indent: Indent, max_width: int = -1):
        self.indent = indent
        self.out = ""
        self.line = []
        self.max_width = max_width
        self.space_per_tabs = 4

    def new_line(self):
        line = ""
        add_space = False
        for s in self.line:
            if (self.max_width > 0) and (
                self.indent.to_spaces() + len(line) + len(s.text) > self.max_width
            ):
                self.out += str(self.indent) + line + "\n"
                line = s.text
                add_space = False
            else:
                if s.add_space and add_space:
                    line += " "
                line += s.text

            add_space = s.add_space
        if line != "":
            self.out += str(self.indent) + line + "\n"
        self.line = []

    def start_line(self, text: str, indent_move: int = 0):
        self.new_line()
        self.indent.move(indent_move)
        self.put(text)

    def add_line(self, text: str, indent_move: int = 0):
        self.new_line()
        self.indent.move(indent_move)
        self.put(text)
        self.new_line()

    def put(self, text: str, add_space: bool = False):
        if (text is None) or (text == ""):
            return
        self.line.append(LinePart(text, add_space))

    def end_line(self, text: str, indent_move: int = 0):
        self.put(text)
        self.new_line()
        self.indent.move(indent_move)

    def blank_line(self, n: int = 1):
        self.new_line()
        self.out += "\n" * n

    def move_indent(self, n: int):
        self.indent.move(n)

    def take(self) -> str:
        self.new_line()
        out = self.out
        self.out = ""
        return out


def convert_name(name: str, style: NameStyle) -> str:
    if (style == NameStyle.SNAKECASE) or (style == NameStyle.CONSTANTCASE):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        if style == NameStyle.SNAKECASE:
            return name.lower()
        else:
            return name.upper()
    else:
        name = re.sub(r"(?:^|_)(.)", lambda m: m.group(1).upper(), name)
        if style == NameStyle.SNAKECASE:
            return name[:1].lower() + name[1:]
        else:
            return name[:1].upper() + name[1:]


def cat_name(substrings: list[str], style: NameStyle) -> str:
    substrings = [s for s in substrings if s.strip()]
    if (style == NameStyle.SNAKECASE) or (style == NameStyle.CONSTANTCASE):
        return "_".join(convert_name(substring, style) for substring in substrings)
    else:
        return "".join(convert_name(substring, style) for substring in substrings)
