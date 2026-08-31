from argparse import ArgumentParser, FileType
from parser import RtIpcParser
from c.gen import CGenerator
from rust.gen import RustGenerator
from pathlib import Path
from info import add_group_info, dump_group_info

def main():
    langs = ["c", "rust", "cpp"]
    argparser = ArgumentParser(
        prog="rtipcc",
        description="Compile Schema and generate code",
    )
    arggroup = argparser.add_mutually_exclusive_group(required=False)
    arggroup.add_argument(
        "-s", "--server", action="store_true", help="generate server code"
    )
    arggroup.add_argument(
        "-c", "--client", action="store_true", help="generate client code"
    )
    argparser.add_argument(
        "-l", "--lang", choices=langs, required=True, help="output programming language"
    )
    argparser.add_argument("-o", "--output", type=Path, required=True)
    argparser.add_argument("schema", type=Path, help="RTIPC schema file")

    ns = argparser.parse_args()
    parser = RtIpcParser()
    groups, structs = parser.parse(ns.schema)

    for group in groups: 
        add_group_info(group)

    match ns.lang:
        case "c":
            gen = CGenerator()
        case "rust":
            gen = RustGenerator()
        case _:
            raise RuntimeError("language " + ns.lang + " not supported")
            
    gen.write(ns.output, ns.schema.stem, groups, structs)


if __name__ == "__main__":
    main()
