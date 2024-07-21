import os
import pdb
import time
import socket
import atexit
import logging
import pathlib
import subprocess
import unicodedata
import numpy as np
from tree_sitter import Node
from typing import List, Tuple, Optional
from .fqcn import FQCN
from . import tree_sitter_api
from .Scorer.unixcoder import UniXcoder

# Ensure the below import order is not changed
# csharp_setup_utils module also handles essential env-var setup
from project_utils.csharp_setup_utils import setup_dotnet, setup_multilspy
from .fqcn import FQCNKind

def find_free_port() -> int:
    """Function to find a free port starting from start_port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))   # LEt OS figure out random port
    port = sock.getsockname()[1]
    sock.close()
    return port


class CSharpTools:

    server_proc: Optional[subprocess.Popen] = None
    auto_shutdown_server = True

    def shutdown_server(self):
        """ Try to bring down server in most cases, so as to minimize zombie procs """
        if self.auto_shutdown_server == False:
            return
        if self.server_proc is None:
            return
        logging.warning("Terminating LSP API server")
        self.server_proc.terminate()

    def __init__(self, repo_root_dir: str, class_name : str, filename: str):
        setup_dotnet()
        setup_multilspy()

        # Initial parameters
        max_retries = 10  # Maximum number of retries
        retry_delay = 1   # Delay between retries in seconds

        # Try to find a free port
        atexit.register(self.shutdown_server)

        for attempt in range(max_retries + 1):
            port = find_free_port()
            command = ["gunicorn", "--timeout", "100", "-b", f"127.0.0.1:{port}", "repotools.csharp_tools.flask_server:app"]

            try:
                # TODO: Handle termination of process on completion
                self.server_proc = subprocess.Popen(command, env=os.environ)
            except subprocess.CalledProcessError as e:
                print(f"Attempt {attempt+1}/{max_retries+1}: Failed to start on port {port}.")
                if attempt < max_retries:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Maximum retries exceeded. Exiting.")
                    break
            else:
                break  # Exit the loop if subprocess.run() succeeds

        time.sleep(5)  # Necessary so that gunicorn server has enough time to spin up
        self.repo_root_dir = repo_root_dir
        self.instance_fpath = filename
        from .omnisharp_api import OmniSharpApi
        self.api = OmniSharpApi(repo_root_dir, filename, port)
        self.no_cousins = False
        self.embedding_model = UniXcoder("microsoft/unixcoder-base")
        self.embedding_model.cuda()
        self.embedding_model_members = self.embedding_model  #UniXcoder("microsoft/unixcoder-base-nine")
        self.embedding_model_members.cuda()

    def get_imports(self, file_contents: str) -> str:
        """ Get the list of import suggestions for the current file """
        import_suggestions_list = self.api.get_imports(file_contents)
        ret_list = []
        for symbol_name, suggestion_list in import_suggestions_list:
            if len(suggestion_list) > 1:
                suffix = " (Pick only one):\n"
            else:
                suffix = ':\n'
            ret_str = f"For resolving the symbol '{symbol_name}', the following import suggestions were found{suffix}"
            ret_str += "\n".join(suggestion_list)
            ret_list.append(ret_str)
        import_suggestions_str = "\n".join(ret_list)
        return import_suggestions_str + '\n'

    def get_related_snippets(self, search_string: str, top_k: int=5) -> str:
        """Returns the repocoder code snippets given the search string"""
        snippets = []
        window_size=20
        sliding_size=10
        fpaths_list = []
        weight_list = []
        ban_list = []
        if self.no_cousins == True:
            # ban_list = set(self.instance.cousins_list)
            pass
        for fpath in pathlib.Path(self.repo_root_dir).glob("**/*.cs"):
            abs_fpath = str(fpath)
            if abs_fpath == self.instance_fpath:
                continue
            if abs_fpath.endswith("Program.cs") or abs_fpath.endswith("AssemblyInfo.cs"):
                continue
            if "/obj/" in abs_fpath or "/bin/" in abs_fpath:
                continue
            multiplier = 1.0
            if abs_fpath in ban_list:
                multiplier = 0.0
            with open(fpath, encoding='utf-8-sig') as f:
                lines = f.read().splitlines()
            l = len(lines)
            for ndx in range(0, l, sliding_size):
                snippets.append("\n".join(lines[ndx:min(ndx + window_size, l)]))
                fpaths_list.append(abs_fpath)
                weight_list.append(multiplier)
        top_snippets = []
        top_scores = []
        scores_list = self.embedding_model.get_score(search_string, snippets, use_cache=True)
        scores_list = np.array(scores_list) * np.array(weight_list)
        top_k_idx = np.argsort(scores_list)[-1*top_k:]
        for i, idx in enumerate(top_k_idx):
            top_snippets.append(f"####From file {fpaths_list[idx]}:\n```start```csharp\n{snippets[idx]}\n```end```\n")
            top_scores.append(scores_list[idx])
        return top_snippets, top_scores

    def get_signature(self,
                      class_name: str,
                      method_name: str,
                      class_fqcn: Optional[FQCN] = None) -> Tuple[List[str], str]:
        """Returns the signature of the method given the class name and method name
        The method also returns an error message if generated.
        """
        if class_fqcn is None:
            most_likely_fqcn, candidates = self.api.get_fqcn(class_name)
            if most_likely_fqcn is not None:
                candidates = [most_likely_fqcn]
            elif len(candidates) == 0:
                print(f"No fqcn for class with name {class_name} found")
                return [], f"{class_name} not found"
            results = []
            for candidate in candidates:
                if candidate is None:
                    continue
                signatures, err_msg = self.get_signature(class_name, method_name, class_fqcn=candidate)
                if err_msg is not None:
                    continue
                results.extend(signatures)
            if len(results) == 0:
                print(f"No method with name {method_name} found in class {class_name}")
                return [], f"No method with name {method_name} found in class {class_name}"
            return results, None
        if class_fqcn.fqcn_type == FQCNKind.ENUM:
            print(f"WARNING: get_signature called for enum type: {class_fqcn.fqcn}")
        instance_signatures = self.api.get_instance_method_signature(class_fqcn, method_name=method_name)
        static_signatures = self.api.get_static_method_signature(class_fqcn, method_name=method_name)
        inherited_signatures = self.api.get_inherited_method_signature(class_fqcn, method_name=method_name)
        abstract_signatures = self.api.get_abstract_members(class_fqcn, name_filter=method_name)
        if len(instance_signatures) + len(static_signatures) \
            + len(inherited_signatures) + len(abstract_signatures) == 0:
            return [], f"No method with name {method_name} found in class {class_name}"
        return instance_signatures + static_signatures + inherited_signatures + abstract_signatures, None


    def get_class_info(self, class_name: str, ranking_query_string: str,
                       class_fqcn: Optional[FQCN] = None) -> Tuple[str, bool]:
        """Returns the class information given the class name"""
        if class_fqcn is None:
            most_likely_fqcn, candidates = self.api.get_fqcn(class_name)
            if most_likely_fqcn is not None:
                candidates = [most_likely_fqcn]
            elif len(candidates) == 0:
                print(f"No fqcn for class {class_name} found")
                return f"Type {class_name} not found", False
            results = []
            for candidate in candidates:
                class_info, status = self.get_class_info(class_name, ranking_query_string=ranking_query_string, class_fqcn=candidate)
                if status is True:
                    results.append(class_info)
            if len(results) == 0:
                return f"No information found for type {class_name}", False
            return "\n###########\n".join(results), True
        result_str = f"Type {class_fqcn.fqcn} information:\n"
        if class_fqcn.fqcn_type != FQCNKind.ENUM:
            if class_fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
                ctors_str = f"The type {class_fqcn.fqcn} is a static class and does not have constructors"
            else:
                ctors = self.api.get_constructor(fqcn=class_fqcn)
                if len(ctors) == 0:
                    ctors_str = ""
                else:
                    ctors_str = f"The {class_fqcn.fqcn_type.value} type {class_fqcn.fqcn} has constructors with the following signatures\n" + "\n".join(ctors)

            method_info, member_info = self.get_members(class_fqcn, ranking_query_string)
            # static_members, instance_members = self.get_members(class_fqcn)
            # static_members, instance_members = self.get_relevant_members(
            #     thought, static_members, instance_members)
            if len(member_info) == 0:
                members_str = ""
            else:
                members_str = f"The {class_fqcn.fqcn_type.value} type {class_fqcn.fqcn} has the following members\n" + "\n".join(member_info)
            if len(method_info) == 0:
                methods_str = ""
            else:
                methods_str = f"The {class_fqcn.fqcn_type.value} type {class_fqcn.fqcn} has the following methods\n" + "\n".join(method_info)
            if ctors_str == "" and members_str == "" and methods_str == "":
                return f"No information found for type {class_fqcn.fqcn}", False
            result_str += f"{ctors_str}\n{members_str}\n{methods_str}\n"
            return result_str, True
        else:
            enum_members = self.api.get_enum_values(fqcn=class_fqcn)
            if len(enum_members) == 0:
                return f"No information found for type {class_fqcn.fqcn}", False
            result_str += f"{class_fqcn.fqcn} is an enum type with the following enumeration values:\n"
            result_str += "\n".join(enum_members) + '\n'
            # result_str += f"The enum type {class_fqcn.fqcn} has the following members\n" + "\n".join(enum_members)
            return result_str, True

    def get_relevant_code(self, search_str: str, top_k: int=5):
        relevant_classes, class_scores = self.get_relevant_classes(search_str, top_k)
        relevant_snippets, snippet_scores = self.get_related_snippets(search_str, top_k)
        cp, sp = 0, 0
        result_codes = []
        for _ in range(3):
            if class_scores[cp] > snippet_scores[sp]:
                result_codes.append(relevant_classes[cp])
                cp += 1
            else:
                result_codes.append(relevant_snippets[sp])
                sp += 1
        return "\n".join([f"#### Code Piece {i+1}:\n{code}" for i,code in enumerate(result_codes)])

    def get_relevant_members(self, search_str: str, members_list: List[str],
                             keys_list: List[str], top_k=10):
        members_list = [ unicodedata.normalize('NFKD', x) for x in members_list]
        scores = self.embedding_model_members.get_score(search_str, members_list)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return (
            [members_list[i] for i in top_indices ],
            [keys_list[i] for i in top_indices]
        )

    def get_members(self, class_fqcn: FQCN, thought: str = None):
        if class_fqcn.fqcn_type == FQCNKind.ENUM:
            print(f"WARNING: get_members called for enum type: {class_fqcn.fqcn}")
        if class_fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            instance_members, instance_methods = [], []
            inherited_members, inherited_methods = [], []
            protected_members, protected_methods = [], []
            abstract_methods = []
        else:
            abstract_methods = self.api.get_abstract_members(fqcn=class_fqcn)
            instance_members, instance_methods = self.api.get_instance_members(fqcn=class_fqcn)
            inherited_members, inherited_methods = self.api.get_inherited_members(fqcn=class_fqcn)
            protected_members, protected_methods = [], []
            for member in inherited_members:
                if member in instance_members:
                    continue
                protected_members.append(member)
            for method in inherited_methods:
                if method in instance_methods:
                    continue
                protected_methods.append(method)
        static_members, static_methods = self.api.get_static_members(fqcn=class_fqcn)
        # if thought is not None:
        #     (
        #         abstract_methods, instance_methods,
        #         static_methods, protected_methods
        #     ) = self.get_relevant_members(thought, abstract_methods, instance_methods)
        #     (
        #         instance_members, protected_members, static_members
        #     ) = self.get_relevant_members(thought, instance_members, protected_members)
        containing_list = [
            (abstract_methods, "(abstract method - SUBCLASSES MUST DEFINE)"),
            (instance_methods, "(instance method)"),
            (protected_methods, "(protected method - ONLY SUBCLASSES CAN USE)"),
            (static_methods, "(static method)"),
        ]
        member_list, key_list = [], []
        for temp_list, method_info in containing_list:
            for method in temp_list:
                member_list.append(method)
                key_list.append(method_info)
        if len(member_list) > 0:
            filtered_method_list, filtered_key_list = self.get_relevant_members(thought, member_list, key_list)
            selected_method_info = [f"{method} {info}" for method, info in zip(filtered_method_list, filtered_key_list)]
        else:
            selected_method_info = []
            print(f"No methods found for class {class_fqcn.fqcn}")
        containing_list = [
            (instance_members, "(instance variable)"),
            (protected_members, "(protected variable - ONLY SUBCLASSES CAN USE)"),
            (static_members, "(static variable)"),
        ]
        member_list, key_list = [], []
        for temp_list, member_info in containing_list:
            for member in temp_list:
                member_list.append(member)
                key_list.append(member_info)
        if len(member_list) > 0:
            filtered_member_list, filtered_key_list = self.get_relevant_members(thought, member_list, key_list)
            selected_member_info = [ f"{member} {info}" for member, info in zip(filtered_member_list, filtered_key_list)]
        else:
            selected_member_info = []
            print(f"No members found for class {class_fqcn.fqcn}")
        return selected_method_info, selected_member_info
        abstract_methods = list(map(lambda x: x + " (abstract method - SUBCLASSES MUST DEFINE)",
                                    abstract_methods))
        instance_methods = list(map(lambda x: x + " (instance method)", instance_methods))
        instance_members = list(map(lambda x: x + " (instance variable)", instance_members))
        protected_methods = list(map(lambda x: x + " (protected method - ONLY SUBCLASSES CAN USE)", protected_methods))
        protected_members = list(map(lambda x: x + " (protected variable - ONLY SUBCLASSES CAN USE)", protected_members))
        static_methods = list(map(lambda x: x + " (static method)", static_methods))
        static_members = list(map(lambda x: x + " (static variable)", static_members))
        return (
            static_members + static_methods,
            instance_members + protected_members + instance_methods + protected_methods + abstract_methods,
        )


    def get_method_body(self, class_name: str, method_name: str,
                        fqcn: Optional[FQCN] = None) -> Tuple[List[str], str]:
        if fqcn is None:
            most_likely_fqcn, candidates = self.api.get_fqcn(class_name)
            if most_likely_fqcn is not None:
                candidates = [most_likely_fqcn]
            elif len(candidates) == 0:
                print(f"No fqcn for class with name {class_name} found")
                return [], f"Class {class_name} not found"
            method_bodies = []
            for candidate in candidates:
                res, msg = self.get_method_body(class_name, method_name, fqcn=candidate)
                if msg is None:
                    method_bodies.extend(res)
        else:
            if fqcn.fqcn_type == FQCNKind.ENUM:
                print(f"WARNING: get_method_body called for enum type: {fqcn.fqcn}")
            method_bodies = []
            methods_info = self.api.get_method_body(fqcn, method_name)
            # if len(methods_info) == 0:
            #     return f"No method with name {method_name} found in class {class_name}"
            for _, _, body in methods_info:
                method_bodies.append(body)
            if len(method_bodies) == 0:
                return [], f"No method with name {method_name} found in class {class_name}"
            return method_bodies, None


    def get_relevant_classes(self, search_str:str, top_k: int=5):
        # csharp_files = [str(x.absolute()) for x in pathlib.Path(repo_root_dir).glob("**/*.cs") ]
        class_signatures = []
        weight_list = []
        class_names = []
        fqcn_list = []
        ban_list = []
        if self.no_cousins == True:
            ban_list = set(self.instance.cousins_list)
        for fpath in pathlib.Path(self.src_prefix).glob("**/*.cs"):
            abs_fpath = str(fpath)
            if abs_fpath.endswith("AssemblyInfo.cs") or abs_fpath.endswith("Program.cs"):
                continue
            if "/obj/" in abs_fpath or "/bin/" in abs_fpath:
                continue
            for prefix in self.test_prefix:
                if abs_fpath.startswith(prefix):
                    break
            else:
                multiplier = 1.0
                if abs_fpath in ban_list:
                    multiplier = 0.0
                with open(fpath, encoding='utf-8-sig') as f:
                    file_content = f.read()
                ns_node = tree_sitter_api.get_namespace_node(file_content)
                if ns_node is None:
                    print(f"{fpath}\tnamespace node found to be None, Skipping")
                    continue
                class_nodes, static_class_nodes = tree_sitter_api.get_class_nodes(file_content)
                struct_nodes = tree_sitter_api.get_struct_nodes(file_content)
                record_nodes = tree_sitter_api.get_record_nodes(file_content)
                interface_nodes = tree_sitter_api.get_interface_nodes(file_content)
                # enum_nodes = tree_sitter_api.get_enum_nodes(file_content)
                data_list: List[Tuple[List[Node], FQCNKind]] = [
                    (class_nodes, FQCNKind.CLASS),
                    (struct_nodes, FQCNKind.STRUCT),
                    (record_nodes, FQCNKind.RECORD),
                    (interface_nodes, FQCNKind.INTERFACE),
                    (static_class_nodes, FQCNKind.STATIC_CLASS),
                    # (enum_nodes, FQCNKind.ENUM)
                ]
                for container_list, kind in data_list:
                    for class_node in container_list:
                        try:
                            class_name = class_node.child_by_field_name("name").text.decode()
                            fqcn = f"{ns_node.child_by_field_name('name').text.decode()}.{class_name}"
                            class_sig = self.get_class_signature(class_node)
                            class_signatures.append(class_sig)
                            class_names.append(class_name)
                            fqcn_list.append(FQCN(fqcn, kind))
                            weight_list.append(multiplier)
                        except ValueError as e:
                            continue
        score_list = self.embedding_model.get_score(search_str, class_signatures, use_cache=True)
        score_list = np.array(score_list) * np.array(weight_list)
        selected_indices = np.argsort(score_list)[-1:-top_k-1:-1]
        relevant_classes_info = []
        top_scores = []
        for i, idx in enumerate(selected_indices):
            fqcn: FQCN = fqcn_list[idx]
            if fqcn.fqcn_type == FQCNKind.INTERFACE:
                src_filepath = self.api.get_src_file(fqcn)
                iface_nodes = tree_sitter_api.get_interface_nodes(src_filepath)
                for iface_node in iface_nodes:
                    if iface_node.child_by_field_name('name') in fqcn.fqcn.split('.')[-1]:
                        break
                else:
                    continue
                tree_sitter_api.get_interface_info(iface_node)
            else:
                class_info = self.get_class_info(None, class_fqcn=fqcn, ranking_query_string=search_str)
            relevant_classes_info.append(class_info)
            top_scores.append(score_list[idx])
        return relevant_classes_info, top_scores

    def is_private_member(self, node: Node):
        for child in node.named_children:
            if child.type == "modifier":
                if child.text.decode() == "private":
                    return True
            if child.type == 'identifier':
                # Don't continue, you might encounter private set and trigger this func
                break
        return False

    def get_class_signature(self, class_node: Node):
        class_body = class_node.child_by_field_name("body")
        class_name = class_node.child_by_field_name("name")
        if class_body is None:
            print(f"{class_name} class_body found to be None, returning")
            return ""
        elements_list = []
        for child in class_body.named_children:
            if self.is_private_member(child):
                continue
            if child.type in ["method_declaration", "constructor_declaration"]:
                sig = tree_sitter_api.get_method_signature(child) + ';'
                elements_list.append(sig)
            else:
                elements_list.append(child.text.decode())
        byte_span = class_body.start_byte - class_node.start_byte
        class_declaration = class_node.text[0:byte_span].decode()
        class_signature = class_declaration + '\n{\n' + '\n'.join(elements_list) + '\n}'
        return class_signature


    def get_relevant_methods(self, search_str: str, top_k: int=5) -> List[str]:
        """ Get relevant methods for a given class """
        fqcns = self.api.get_available_fqcns()
        all_methods_defns = []
        all_methods_fqcns = []
        all_methods_signatures = []
        for fqcn in fqcns:
            method_bodies, err_msg = self.get_method_body(fqcn)
            if err_msg is not None:
                continue
            for method_name, method_signature, method_defn in method_bodies:
                all_methods_defns.extend(method_defn)              # Method body
                all_methods_fqcns.append(fqcn)                     # Fully CLASS qualified name
                all_methods_signatures.append(method_signature)    # Signature
        # Get cosine similarity scores with method defn, but only return corresp method signatures
        score_list = self.embedding_model.get_score(search_str, all_methods_defns, use_cache=True)
        topk_idx = np.argsort(score_list)[-1:-1-top_k:-1]
        selected_signatures = []
        top_scores = []
        for k, idx in enumerate(topk_idx):
            top_scores.append(score_list[idx])
            selected_signatures.append(
                # Example:
                # 1. public static createObj(DataRef obj) in class Repo.Core.Data.Container
                f"{str(k)}. {all_methods_signatures[idx]} in class {all_methods_fqcns[idx]}"
            )
        return selected_signatures

