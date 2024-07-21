import os
import traceback

from tree_sitter_languages import get_parser

parser = get_parser("java")

def list_java_files_in_directory(directory):
    java_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path[-5:] == ".java":
                java_files.append(file_path)
    return java_files


def get_method_body(method_name,line,file_content):    
    """Finds start and end line of a node.
    :return: start line, end line
    """
    try:
        method_name=method_name.decode('utf-8')
    except:
        pass
    
    method_from_start = "\n".join(file_content.split("\n")[line-1:])    ##Making the assumption that the signature fits in one line
    flag=False
    flag2=False
    flag_name=False
    bracket_count=0
    # print("Method from start _____")
    # print(method_from_start)
    for i,c in enumerate(method_from_start):        
        # sys.stdout.write(c)
        # sys.stdout.write(str(bracket_count))        
        # sys.stdout.write(str(flag))        
        
        if c=='"':
            flag2=not flag2
        if not flag_name:
            if method_from_start[i:i+len(method_name)]==method_name:
                flag_name=True
            continue
        elif not flag:
            if c=="{":
                flag=True
                bracket_count=1            
                # sys.stdout.write("bracket_count"+str(bracket_count))                
            continue
        else:
            if c=="{" and (not flag2):
                bracket_count+=1
                # sys.stdout.write("bracket_count"+str(bracket_count))                                                                
            elif c=="}" and (not flag2):
                bracket_count-=1
                # sys.stdout.write("bracket_count"+str(bracket_count))                
        if bracket_count==0:
            # print("RETURNING",method_from_start,i)            
            return method_from_start[:i+1]
    ### We have failed to return the method here, so lets just return everything
    return method_from_start

# def get_method_body(line, file_content):
#     """Finds start and end line of a node.
#     :return: start line, end line
#     """
#     method_from_start = "\n".join(file_content.split("\n")[line - 1 :])
#     print(method_from_start)
#     flag = False
#     bracket_count = 0
#     for i, c in enumerate(method_from_start):
#         if not flag:
#             if c == "{":
#                 flag = True
#                 bracket_count = 1
#             continue
#         else:
#             if c == "{":
#                 bracket_count += 1
#             elif c == "}":
#                 bracket_count -= 1
#         if bracket_count == 0:
#             return method_from_start[: i + 1]
#     raise Exception


def filter_nodes(root_node, node_types):
    method_definitions = []

    # Traverse the tree in a depth-first manner
    stack = [root_node]

    while stack:
        node = stack.pop()

        # Check if the node represents a method or constructor declaration in Java
        if node.type in node_types:
            method_definitions.append(node)

        # Push child nodes onto the stack for further exploration
        for child in node.children:
            stack.append(child)

    return method_definitions



def extract_method_info(node, java_code):
    method_name = None
    method_code = None
    method_signature = None

    for child in node.children:
        if child.type == "formal_parameters":
            method_signature = child.text
        if child.type == "identifier":
            method_name = child.text
            # Include parameters in method name
            if method_signature:
                method_name += method_signature
        elif child.type == "block":
            start_line = child.start_point[0]
            method_code = get_method_body(method_name, start_line, java_code)
    
    # method_name = None
    # method_code = None
    # method_signature = None

    # for child in node.children:
    #     if child.type == "formal_parameters":
    #         method_signature = child.text
    #     if child.type == "identifier":
    #         method_name = child.text
    #     elif child.type == "block":
    #         start_line = child.start_point[0]
    #         method_code = get_method_body(method_name, start_line, java_code)
    #         # print("I got back method_code",method_code)
    
    return method_name.decode()+method_signature.decode(), method_code


def extract_class_info(node):
    for child in node.children:
        if child.type == "identifier":
            class_name = child.text
    return class_name




def get_tree_from_text(text):
    classes = {}
    root_node = parser.parse(bytes(text, "utf8")).root_node
    class_definitions = filter_nodes(
        root_node, ["record_declaration", "class_declaration"]
    )
    for class_node in class_definitions:
        method_definitions = filter_nodes(
            root_node, ["method_declaration", "constructor_declaration"]
        )
        class_info = {}
        for method in method_definitions:
            method_name, method_code = extract_method_info(method, text)
            if method_code == None:
                continue
            class_info[method_name] = method_code
        classes[extract_class_info(class_node).decode()] = class_info
    return classes


def get_tree(repo_dir, exclude_files):
    classes = {}
    java_files = list_java_files_in_directory(repo_dir)
    for file in java_files:
        if file in exclude_files or any(
            [exclude_file in file for exclude_file in exclude_files]
        ):
            continue
        with open(file, "r") as f:
            file_content = f.read()
        d1=get_tree_from_text(file_content)        
        if len(d1)>0:           
            package_name=list(filter(lambda x:"package " in x,file_content.split("\n")))[0].split(" ")[1].split(";")[0]+"."                
            d2={(package_name+list(d1.keys())[0]):list(d1.values())[0]}
            classes.update(d2)
    return classes



def get_class_from_text(text):
    classes = {}
    root_node = parser.parse(bytes(text, "utf8")).root_node
    class_definitions = filter_nodes(
        root_node, ["record_declaration", "class_declaration"]
    )
    for class_node in class_definitions:        
        for child in class_node.children:
            if child.type == "identifier":
                class_name = (child.text).decode('utf-8')
            if child.type == "class_body":
                class_body = "\n".join(text.split(child.text.decode())[0].split("\n")[-2:])+child.text.decode()
    if len(class_definitions)==0:
        return {}
    return {class_name: class_body}


def get_classes_dict(repo_dir, exclude_files):
    classes = {}
    java_files = list_java_files_in_directory(repo_dir)
    for file in java_files: 
        # if file=="/home/t-adeshpande/MGD/dataCompare/src/main/java/com/vince/xq/antrl4/HiveSqlParser.java":
        #     continue
        # print(file)       
        if file in exclude_files or any(
            [exclude_file in file for exclude_file in exclude_files]
        ):
            continue
        with open(file, "r") as f:
            file_content = f.read()
        try:
            if "package " not in file_content:
                continue            
            package_name=list(filter(lambda x:"package " in x,file_content.split("\n")))[0].split(" ")[1].split(";")[0]+"."
            d1=get_class_from_text(file_content)
            if len(d1)>0:
                d2={(package_name+list(d1.keys())[0]):list(d1.values())[0]}
                classes.update(d2)
        except:
            print(traceback.format_exc())

    return classes
