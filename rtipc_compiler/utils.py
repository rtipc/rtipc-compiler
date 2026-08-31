from enum import Enum
import re


class IndentStyle(Enum):
    SPACES = " "
    TABS = "\t"


class NameStyle(Enum):
    CAMELCASE = 1
    SNAKECASE = 2


class Indent(object):
    def __init__(self, style: IndentStyle, n: int):
        self.style = style
        self.n = n
        self.current = 0

    def increase(self):
        self.current = self.current + 1

    def decrease(self):
        if self.current == 0:
            raise RuntimeError("can't decrease indent below zero")
        self.current = self.current - 1
        
    def line(self, content: str, n: int = 1) -> str:
        out = ""
        if (content is not None) and (content != ""):
            out = str(self) + content 
        out += "\n" * n 

    def __str__(self):
        return str(self.style.value) * self.n * self.current


def convert_name(name: str, style: NameStyle) -> str:
    if style == NameStyle.SNAKECASE:
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.lower()
    else:
        return re.sub(r"(?:^|_)(.)", lambda m: m.group(1).upper(), name)
