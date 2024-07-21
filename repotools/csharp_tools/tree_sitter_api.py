from tree_sitter import Node
from typing import List, Tuple
from tree_sitter_languages import get_parser

parser = get_parser("c_sharp")

def get_root_node(code: str):
    tree = parser.parse(bytes(code, "utf8"))
    return tree.root_node

def get_namespace_node(code: str) -> Node:
    root_node = get_root_node(code)
    for child in root_node.children:
        if child.type in [
            "file_scoped_namespace_declaration",
            "namespace_declaration",
        ]:
            return child
        if child.type == "ERROR":
            text = child.text.decode().strip()
            if text.startswith("namespace"):
                print("Unable to parse node, but namespace found, skipping.")

def is_class_static(node: Node) -> bool:
    for child in node.children:
        if child.type == 'modifier' and child.text.decode() == 'static':
            return True
    return False

def get_class_nodes(code: str) -> Tuple[List[Node], List[Node]]:
    namespace_node = get_namespace_node(code)
    class_nodes = []
    static_class_nodes = []
    try:
        for child in namespace_node.children:
            if child.type == "class_declaration":
                if is_class_static(child):
                    static_class_nodes.append(child)
                else:
                    class_nodes.append(child)
            elif child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type == "class_declaration":
                        if is_class_static(gchild):
                            static_class_nodes.append(gchild)
                        else:
                            class_nodes.append(gchild)
    except Exception as e:
        print(e)
    return class_nodes, static_class_nodes

def get_struct_nodes(code) -> List[Node]:
    namespace_node = get_namespace_node(code)
    struct_nodes = []
    try:
        for child in namespace_node.children:
            if child.type == "struct_declaration":
                struct_nodes.append(child)
            elif child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type == "struct_declaration":
                        struct_nodes.append(gchild)
    except Exception as e:
        print(e)
    return struct_nodes

def get_interface_nodes(code) -> List[Node]:
    namespace_node = get_namespace_node(code)
    interface_nodes = []
    try:
        for child in namespace_node.children:
            if child.type == "interface_declaration":
                interface_nodes.append(child)
            elif child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type == "interface_declaration":
                        interface_nodes.append(gchild)
    except Exception as e:
        print(e)
    return interface_nodes

def get_record_nodes(code) -> List[Node]:
    namespace_node = get_namespace_node(code)
    record_nodes = []
    try:
        for child in namespace_node.children:
            if child.type in [
                "record_struct_declaration",
                "record_declaration"
            ]:
                record_nodes.append(child)
            elif child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type in [
                        "record_struct_declaration",
                        "record_declaration"
                    ]:
                        record_nodes.append(gchild)
    except Exception as e:
        print(e)
    return record_nodes

def get_enum_nodes(code) -> List[Node]:
    namespace_node = get_namespace_node(code)
    enum_nodes = []
    try:
        for child in namespace_node.children:
            if child.type in [ "enum_declaration" ]:
                enum_nodes.append(child)
            elif child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type in [ "enum_declaration" ]:
                        enum_nodes.append(gchild)
    except Exception as e:
        print(e)
    return enum_nodes

# def get_class_signature(class_node: Node) -> str:
#     start_idx = class_node.start_byte
#     for child in class_node.children:
#         if child.type == "declaration_list":
#             end_idx = child.start_byte
#     return class_node.text[0: end_idx-start_idx].decode()

def get_method_signature(method_node: Node):
    start_idx = method_node.start_byte
    method_name = method_node.child_by_field_name("name").text.decode()
    body = method_node.child_by_field_name("body")
    try:
        end_idx = method_node.end_byte
        end_idx = body.start_byte
    except Exception as e:
        print(f"{method_name} Method body is None")
        return method_node.text.decode()
    return method_node.text[0: end_idx-start_idx].decode()


def get_method_nodes(container_node: Node):
    method_nodes: List[Node] = []
    try:
        for child in container_node.children:
            if child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type == "method_declaration":
                        method_nodes.append(gchild)
    except Exception as e:
        print(e)
    return method_nodes

def get_ctor_nodes(container_node: Node):
    ctor_nodes: List[Node] = []
    try:
        for child in container_node.children:
            if child.type == "declaration_list":
                for gchild in child.children:
                    if gchild.type == "constructor_declaration":
                        ctor_nodes.append(gchild)
    except Exception as e:
        print(e)
    return ctor_nodes


# def filter_nodes_by_