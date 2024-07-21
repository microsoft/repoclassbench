import re
import time
import logging
import pathlib
import requests
import traceback
import numpy as np
from sys import exit
from enum import Enum
from tree_sitter import Node
from typing import Dict, Any, List, Optional, Tuple, Union
from . import tree_sitter_api
from .fqcn import FQCN, FQCNKind
from .monitors4codegen.multilspy.multilspy_types import CompletionItemKind, CompletionItem  # type: ignore


DEFAULT_PORT = 8000
CLIENT_TIMEOUT = 120  # in seconds

class APIName(str, Enum):
    GET_IMPORTS = "get_imports/"
    GET_SIGNATURE_HELP = "get_signature_help/"
    GET_COMPLETIONS = "get_completions/"
    RESOLVE_COMPLETIONS = "resolve_completions/"
    INITIALIZE = "initialize/"
    RESET = "reset/"
    SHUTDOWN = "shutdown/"

def get_lc(content: str, idx: int):
    """ Given an index to a string position, get corresp line and char number """
    l, c = 0, 0
    current_idx = 0
    lines = content.split("\n")
    for line in lines:
        if current_idx + len(line) >= idx:
            c = idx - current_idx
            break
        current_idx += len(line) + 1
        l += 1
    return l, c

def len_prefix_match(ns_name: str, candidate: str) -> int:
    """ Return number of nesting levels in the namespace's name that match the candidate """
    ns_name_tokens = ns_name.split(".")
    candidate_tokens = candidate.split(".")
    for i in range(min(len(ns_name_tokens), len(candidate_tokens))):
        if ns_name_tokens[i] != candidate_tokens[i]:
            return i
    return 0

class OmniSharpApi:

    def __init__(self, repo_root_dir: str, filename: str, port: int = DEFAULT_PORT):
        #update global default port
        global DEFAULT_PORT
        DEFAULT_PORT = port
        # Below map is used to get the fully qualified class name(s) from a class name
        self.cname2fqcn_map: Dict[str, List[FQCN]] = {}
        # Below map is used to get the source file path from a fully qualified class name
        self.fqcn2src_map: Dict[str, str] = {}

        self.repo_root_dir = repo_root_dir
        self.instance_contents = ""
        self.instance_fpath = filename

        reset_r = requests.post(f"http://127.0.0.1:{DEFAULT_PORT}/{APIName.INITIALIZE.value}", json={
            'filename': self.instance_fpath
        })
        print("reset_r.json()")
        print(reset_r)

        if reset_r.status_code != 200:
            print(f"Critical Error initializing LSP for instance: {self.instance_fpath}")
            exit(0)

        print("Server handshake successful")
        print("Compiling FQCN map")
        self.compile_fqcn_map()
        print("FQCN map computed")
        self.req_timeout = 10

    def shutdown(self):
        r = requests.post(f"http://127.0.0.1:{DEFAULT_PORT}/{APIName.SHUTDOWN.value}")
        if r.status_code != 200:
            print(f"Critical Error shutting down LSP")
            raise Exception
        print("Successfully shutdown LSP")

    def initialize(self):
        r = requests.post(f"http://127.0.0.1:{DEFAULT_PORT}/{APIName.INITIALIZE.value}", json={
            'filename': self.instance_fpath
        })
        if r.status_code != 200:
            print(f"Critical Error initializing LSP for instance: {self.instance_fpath}")
            exit(0)
        print("Successfully initialized LSP")

    def make_request(self, request_name, data: Dict[str, Any]) -> Optional[Union[List, Dict]]:
        """ Make a POST request to the given url with the given data """
        for i in range(3):
            try:
                print(f"{request_name} -> Trial {i+1}/3")
                r = requests.post(f"http://127.0.0.1:{DEFAULT_PORT}/{request_name}", json=data, timeout=CLIENT_TIMEOUT)
                break
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error: {e}")
                self.shutdown()
                self.initialize()
        else:
            print("Request Failed")
            return None
        # RESET no longer needed, fixed in multilspy code
        # reset_r = requests.post(f"http://127.0.0.1:{DEFAULT_PORT}/{APIName.RESET.value}", json=data, timeout=5)
        # if reset_r.status_code != 200:
        #     print(f"Critical Error resetting file {data['filename']}")
        #     exit(0)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"server side error: {r.status_code}")
            return None

    def get_src_file(self, fqcn: FQCN) -> Optional[str]:
        """ Returns the abs filepath given a class' fully qualified class name"""
        if fqcn.fqcn in self.fqcn2src_map:
            return self.fqcn2src_map[fqcn.fqcn]
        print(f"Class {fqcn.fqcn} not found in the fqcn2src_map, skipping")
        return None
#         # Below code does not always work...
#         template = f"""
# public class Demo
# {{
#     public void Test()
#     {{
#         {fqcn.fqcn} obj;
#     }}
# }}
# """
#         search_str = f"{fqcn.fqcn} obj;"
#         idx = template.index(search_str) + 1
#         lineno, colno = get_lc(template, idx)
#         with self.slsp.open_file(self.instance_fpath):
#             self.slsp.update_open_file(self.instance_fpath, template)
#             file_uri, _ = self.slsp.go_to_implementation(self.instance_fpath, lineno, colno)
#             self.slsp.update_open_file(self.instance_fpath, "")
#         implementation_fpath = unquote(urlparse(file_uri).path)
#         if not implementation_fpath.startswith(self.repo_root_dir):
#             logging.warning(f"Implementation for {fqcn.fqcn} not found within repo: {implementation_fpath}")
#             logging.warning("Skipping")
#             return None
#             # implementation_fpath = implementation_fpath[7:]
#         logging.warning("Implementation file path: (lsp-result:) " + implementation_fpath)
#         return implementation_fpath

    def get_imports(self, file_contents: str) -> List[Tuple[str, List[str]]]:
        """ Get lsp import suggestions for a given file content

        First saves the given file content to the lsp, while listening for diagnostic messages
        When a message arrives, it extracts relevant information and returns it
        """
        file_path = self.instance_fpath

        results = self.make_request(APIName.GET_IMPORTS.value, {
            'filename': file_path,
            'code': file_contents,
        })
        if results is not None:
            print(f"=> {results} Import suggestions received (1)")
            try:
                actions_list = results['actions']
            except:
                print({
                    'filename': file_path,
                    'code': file_contents,
                })
                time.sleep(10)
                results = self.make_request(APIName.GET_IMPORTS.value, {
                    'filename': file_path,
                    'code': file_contents,
                })
                actions_list = results['actions']

            print(f"=> {len(actions_list)} Import suggestions received")
            return actions_list
        else:
            print("No import suggestions received")
            return []

    # Verified, works with existing file, NOT SCRATCH FILE
    def get_constructor(self, fqcn: FQCN) -> List[str]:
        """ Given a class' fully qualified domain name, get available ctors """
        if fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            print(f"Class {fqcn.fqcn} is a static class, skipping")
            return []
        template = f"""
public class Demo
{{
    public void Temp()
    {{
        var a = new {fqcn.fqcn}();
    }}
}}
"""
        search_str = f"var a = new {fqcn.fqcn}("
        idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, idx)
        res: Optional[Dict] = self.make_request(APIName.GET_SIGNATURE_HELP.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno
        })
        ctor_signatures = []
        if res is not None and 'signatures' in res:
            print(f"=> {len(res['signatures'])} Constructor signatures found")
            for sig in res['signatures']:
                ctor_signatures.append(sig['label'])
        else:
            print(f"No constructor signatures found for {fqcn.fqcn}")
        return ctor_signatures

    def get_enum_values(self, fqcn: FQCN) -> List[str]:
        """ Given a class' fully qualified domain name, get available ctors """
        template = f"""
public class Demo
{{
    public void Temp()
    {{
        var obj = {fqcn.fqcn}.
    }}
}}
"""
        search_str = f"{fqcn.fqcn}."
        idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, idx)
        res: Union[CompletionItem, List[CompletionItem]] = self.make_request(APIName.GET_COMPLETIONS.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno,
            'allow_incomplete': True,
        })
        if res is not None and isinstance(res, list):
            enum_members = []
            for comp_item in res:
                if comp_item["kind"] == CompletionItemKind.EnumMember:
                    enum_members.append(comp_item['completionText'])
        elif res is not None:
            enum_members = [res['completionText']]
        else:
            print("No enum members found")
            enum_members = []
        print(f"=> {len(enum_members)} Enum members found")
        return enum_members

    def get_static_members(self, fqcn: FQCN) -> Tuple[List[str], List[str]]:
        """ Given a class' fully qualified class name, get available static members and methods """
        template = f"""
public class Demo
{{
    public void Test()
    {{
        {fqcn.fqcn}.
    }}
}}
"""
        search_str = f"{fqcn.fqcn}."
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_COMPLETIONS.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno,
            'allow_incomplete': True,
        })
        static_members, static_methods = self._proc_get_member_req(fqcn, res, static=True)
        return static_members, static_methods


    def get_inherited_members(self, fqcn: FQCN) -> Tuple[List[str], List[str]]:
        """ Given a class' fully qualified class name, get available inherited members and methods """
        if fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            print(f"Class {fqcn.fqcn} is a static class, skipping")
            return [], []
        template = f"""
public {fqcn.fqcn_type.value} Demo: {fqcn.fqcn}
{{
    public void Test()
    {{
        base.
    }}
}}"""
        search_str = "base."
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_COMPLETIONS.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno,
            'allow_incomplete': True,
        })
        inherited_members, inherited_methods = self._proc_get_member_req(fqcn, res, inherited=True)
        return inherited_members, inherited_methods

    # Very slow method, only works for in-repo files
    def get_abstract_members(self, fqcn: FQCN, name_filter:str = None) -> List[str]:
        """ Given a class' fully qualified class name, get available abstract members """
        src_file = self.get_src_file(fqcn)
        if src_file is None:
            print(f"Suitable source file not found within repo for {fqcn.fqcn}, skipping")
            # TODO: need to implement workaround for library references
            return []
        with open(src_file, encoding='utf-8-sig') as f:
            code = f.read()
        class_nodes, _ = tree_sitter_api.get_class_nodes(code)
        abstract_methods = []
        for class_node in class_nodes:
            class_name = class_node.child_by_field_name("name").text.decode()
            if fqcn.fqcn.split('.')[-1] == class_name:
                method_nodes = tree_sitter_api.get_method_nodes(class_node)
                for method_node in method_nodes:
                    method_name = method_node.child_by_field_name("name").text.decode()
                    if name_filter is not None and method_name != name_filter:
                        continue
                    method_sig = tree_sitter_api.get_method_signature(method_node)
                    if "abstract" in method_sig:
                        abstract_methods.append(method_sig)
        print(f"=> {len(abstract_methods)} abstract methods found")
        return abstract_methods

    def get_instance_members(self, fqcn: FQCN) -> Tuple[List[str], List[str]]:
        """ Given a class' fully qualified class name, get available instance members and methods"""
        if fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            print(f"Class {fqcn.fqcn} is a static class, skipping")
            return [], []
        template = f"""
public class Demo
{{
    public void Test()
    {{
        {fqcn.fqcn} obj;
        obj.
    }}
}}"""
        search_str = f"obj."
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_COMPLETIONS.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno,
            'allow_incomplete': True,
        })
        instance_members, instance_methods = self._proc_get_member_req(fqcn, res)
        return instance_members, instance_methods

    def get_static_method_signature(self, fqcn: FQCN, method_name: str) -> List[str]:
        """ Given a class' fully qualified class name and a method name, get the method's signature """
        template = f"""
public class Demo
{{
    public void Test()
    {{
        {fqcn.fqcn}.{method_name}()
    }}
}}
"""
        search_str = f"{fqcn.fqcn}.{method_name}("
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_SIGNATURE_HELP.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno
        })
        static_method_signatures = self._proc_get_signature_req(res)
        if len(static_method_signatures) == 0:
            logging.warning("No relevant static method signatures found")
        return static_method_signatures

    # Verified, works with existing file, NOT SCRATCH FILE
    def get_inherited_method_signature(self, fqcn: FQCN, method_name: str) -> List[str]:
        """ Given a class' fully qualified class name and a method name, get the method's signature \
        Can be used for abstract methods as well
        """
        if fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            print(f"Class {fqcn.fqcn} is a static class, skipping")
            return []
        template = f"""
public {fqcn.fqcn_type.value} Demo: {fqcn.fqcn}
{{
    public void Test()
    {{
        base.{method_name}()
    }}
}}"""
        search_str = f"base.{method_name}("
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_SIGNATURE_HELP.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno
        })
        inherited_method_signatures = self._proc_get_signature_req(res)
        if len(inherited_method_signatures) == 0:
            logging.warning("No relevant inherited method signatures found")
        return inherited_method_signatures

    # Verified, works with existing file, NOT SCRATCH FILE
    def get_instance_method_signature(self, fqcn: FQCN, method_name: str) -> List[str]:
        """ Given a class' fully qualified class name and a method name, get the method's signature """
        if fqcn.fqcn_type == FQCNKind.STATIC_CLASS:
            print(f"Class {fqcn.fqcn} is a static class, skipping")
            return []
        template = f"""
public class Demo
{{
    public void Test()
    {{
        {fqcn.fqcn}? obj;
        obj.{method_name}()
    }}
}}
"""
        search_str = f"obj.{method_name}("
        pointer_idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, pointer_idx)
        res = self.make_request(APIName.GET_SIGNATURE_HELP.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno
        })
        instance_method_signatures = self._proc_get_signature_req(res)
        if len(instance_method_signatures):
            logging.warning("No relevant instance method signatures found")
        return instance_method_signatures

    def get_signature(self, fqcn: FQCN, method_name: str,
                      static: bool = False, inherited: bool = False,
                      abstract: bool = False) -> List[str]:
        static_signatures = []
        inherited_signatures = []
        abstract_signatures = []
        instance_signatures = []
        if static:
            static_signatures = self.get_static_method_signature(fqcn, method_name=method_name)
        if inherited:
            inherited_signatures = self.get_instance_method_signature(fqcn, method_name=method_name)
        if abstract:
            abstract_signatures = self.get_abstract_members(fqcn, name_filter=method_name)
        if not static and not inherited and not abstract:
            instance_signatures = self.get_instance_method_signature(fqcn, method_name=method_name)
        return instance_signatures + static_signatures + inherited_signatures + abstract_signatures

    def _proc_get_signature_req(self, res) -> List[str]:
        method_signatures = []
        if res is not None and len(res) > 0:
            print(f"=> {len(res['signatures'])} method signatures found")
            for sig in res['signatures']:
                method_signatures.append(sig['label'])
        else:
            # TODO: Add error handling
            # logging.warning("No method signatures found")
            pass
        return method_signatures

    def skip_method(self, method_name):
        if method_name in [
            "Equals", "GetHashCode", "GetType",
            "MemberwiseClone", "Finalize",
            "ReferenceEquals", "ToString",
        ]:
            return True
        return False


    def _proc_get_member_req(self, fqcn: FQCN, res, static=False, inherited=False, abstract=False):
        members_list: List[str] = []
        methods_list: List[List[str]] = []
        method_completions_list = []
        if res is not None and len(res) > 0:
            print(f"=> {len(res)} members found in {fqcn.fqcn}")
            for comp_item in res:
                if comp_item["kind"] in [
                    CompletionItemKind.Property,
                    CompletionItemKind.Field
                ]:
                    members_list.append(comp_item['completionText'])
                elif comp_item["kind"] == CompletionItemKind.Method:
                    if self.skip_method(comp_item['completionText']):
                        continue
                    method_completions_list.append(comp_item)
                    # sig = self.get_signature(fqcn, comp_item['completionText'],
                    #                          abstract=abstract, inherited=inherited, static=static)
                    # methods_list.extend(sig)
            if len(method_completions_list) > 0:
                res_resolved = self.make_request(APIName.RESOLVE_COMPLETIONS.value, data={
                    'completions': method_completions_list
                })
                for comp_item in res_resolved:
                    if "documentation" in comp_item and "value" in comp_item["documentation"]:
                        docs: str = comp_item["documentation"]["value"]
                        docs = docs.removeprefix('```csharp').strip()
                        idx = docs.index('```')
                        if idx == -1:
                            continue
                        sig = docs[:idx].strip()
                        methods_list.append(sig)
        elif res is not None:
            print(f"=> {len(res)} members found in {fqcn.fqcn}")
        return members_list, methods_list

    def get_method_body(
            self,
            fqcn: FQCN,
            method_name: str = None,
        ) -> List[Tuple[str, str, str]]:
        """ Given a class' fully qualified class name and a method name, get the method's body

        If method_name is None, returns all methods' bodies
        NOTE: For convenience, for each method, the function returns the name, signature and body
        """

        implementation_fpath = self.get_src_file(fqcn)
        if implementation_fpath is None:
            logging.warning(f"Suitable source file not found within repo for {fqcn.fqcn}, skipping")
            return []
        code = open(implementation_fpath, encoding="utf-8-sig").read()
        class_nodes, _ = tree_sitter_api.get_class_nodes(code)
        class_name = fqcn.fqcn.split('.')[-1]
        for class_node in class_nodes:
            if class_node.child_by_field_name("name").text.decode() == class_name:
                break
        else:
            return []
        method_nodes = tree_sitter_api.get_method_nodes(class_node)
        results = []
        for method_node in method_nodes:
            node_identifier = method_node.child_by_field_name('name').text.decode()
            signature = tree_sitter_api.get_method_signature(method_node)
            if method_name is not None and node_identifier == method_name:
                return [(method_name, signature, method_node.text.decode())]
            elif method_name is None:
                results.append((node_identifier, signature, method_node.text.decode()))
            else:
                pass
        return results

    def get_available_fqcns(self) -> List[FQCN]:
        """ Get all available fully-qualified class names in the repo """
        return list(set(self.cname2fqcn_map.values()))

    def compile_fqcn_map(self):
        """ List all .cs files in the repo and compile a map of class names to fully-qualified class names """
        print("Compiling fqcn map")
        self.cname2fqcn_map = {}
        self.fqcn2src_map = {}
        for fpath in pathlib.Path(self.repo_root_dir).glob("**/*.cs"):
            abs_fpath = str(fpath)
            if abs_fpath.endswith("StabilityMatrix.Core/Models/Update/UpdateInfo.cs"):
                pass
            if abs_fpath.endswith("AssemblyInfo.cs") or abs_fpath.endswith("Program.cs"):
                continue
            if "/obj/" in abs_fpath or "/bin/" in abs_fpath:
                continue
            try:
                code = open(abs_fpath, encoding='utf-8-sig').read()
                namespace_node = tree_sitter_api.get_namespace_node(code)
                if namespace_node is None:
                    print("No namespaces declaration found in " + abs_fpath)
                    continue
                namespace_name = namespace_node.child_by_field_name('name').text.decode()
                class_nodes, static_class_nodes = tree_sitter_api.get_class_nodes(code)
                struct_nodes = tree_sitter_api.get_struct_nodes(code)
                record_nodes = tree_sitter_api.get_record_nodes(code)
                interface_nodes = tree_sitter_api.get_interface_nodes(code)
                enum_nodes = tree_sitter_api.get_enum_nodes(code)
                # print(f"{len(class_nodes):02d} classes, {len(struct_nodes):02d} structs, {len(record_nodes):02d} records found in {fpath}")
                data_list: List[Tuple[List[Node], FQCNKind]] = [
                    (class_nodes, FQCNKind.CLASS),
                    (static_class_nodes, FQCNKind.STATIC_CLASS),
                    (struct_nodes, FQCNKind.STRUCT),
                    (record_nodes, FQCNKind.RECORD),
                    (interface_nodes, FQCNKind.INTERFACE),
                    (enum_nodes, FQCNKind.ENUM)
                ]
                for container_list, fqcn_type in data_list:
                    for container_node in container_list:
                        try:
                            class_name = container_node.child_by_field_name('name').text.decode()
                            fqcn = f"{namespace_name}.{class_name}"
                            if fqcn in self.fqcn2src_map:
                                print(f"Possible partial function: {abs_fpath}:{fqcn}")
                            self.fqcn2src_map[fqcn] = abs_fpath
                            if class_name not in self.cname2fqcn_map:
                                self.cname2fqcn_map[class_name] = []
                            self.cname2fqcn_map[class_name].append(FQCN(fqcn, fqcn_type))
                        except Exception as e:
                            print(e)
                            print("$$\t\t" + abs_fpath)
                            print("$$\t\t" + fqcn_type.value)
                            print(container_node.text.decode())
                            print("$$")
            except Exception as e:
                print(e)
                print("$$\t" + abs_fpath)
                traceback.print_exc()

    def get_most_likely_fqcn(self, candidates: List[FQCN],
                             max_candidates = 5) -> Tuple[FQCN, List[FQCN]]:
        """ Given a list of candidates, return the most likely candidate and its index """
        if len(candidates) == 0:
            print("Called get_most_likely_fqcn with 0 candidates")
            return None, []
        code = self.instance_contents
        pattern = re.compile("namespace ([a-zA-Z_][a-zA-Z0-9_.]*)")
        match = pattern.search(code)
        if match is not None:
            ns_name = match.group(1)
            levels = []
            for candidate in candidates:
                levels.append(len_prefix_match(ns_name, candidate.fqcn))
            idx = np.argsort(levels)
            most_likely_fqcn = candidates[idx[0]]
            candidates_filtered = [ candidates[i] for i in idx[1:max_candidates-1] ]
            # candidates.pop(idx)   <- BUG. Deletes reference from cname2fqcn_map
            return most_likely_fqcn, candidates_filtered
        else:
            return None, candidates[:max_candidates]

    def get_most_likely_ext_fqcn(self, candidates: List[FQCN],
                                 max_candidates = 5) -> Tuple[FQCN, List[FQCN]]:
        """ Decision function for external refs

        The heuristic here is obtain the class identifier, free from template args and such
        And sort by length. The shortest candidate is the tightest match
        """
        pattern = re.compile("([a-zA-Z_][a-zA-Z0-9_.]*)")
        lengths = []
        if len(candidates) == 0:
            print("Called get_most_likely_ext_fqcn with 0 candidates")
            return None, []
        for candidate in candidates:
            match = pattern.search(candidate.fqcn)
            if match is not None:
                lengths.append(len(match.group(1)))
            else:
                lengths.append(len(candidate.fqcn))
        sorted_idx = np.argsort(lengths)
        if len(candidates) == 1:
            most_likely_fqcn = candidates[0]
            return most_likely_fqcn, []
        else:
            most_likely_fqcn = candidates[sorted_idx[0]]
            sorted_candidates = [ candidates[idx] for idx in sorted_idx[1:] ]
            return most_likely_fqcn, sorted_candidates[:max_candidates-1]

    def get_fqcn(self, class_name: str, max_candidates=5) -> Tuple[FQCN, List[FQCN]]:
        """ Get fully-qualified class name candidates for a given class name """
        if class_name in self.cname2fqcn_map:
            candidates = self.cname2fqcn_map[class_name]
            fcqn, candidates = self.get_most_likely_fqcn(candidates, max_candidates)
            return fcqn, candidates

        logging.warning(f"Searching for {class_name}, not found in fqcn_map")
        # If you're here, the class_name is a probably a library class
        template = f"""
public class Demo
{{
    public void Temp()
    {{
        {class_name}
    }}
}}
"""
        search_str = class_name
        idx = template.index(search_str) + len(search_str)
        lineno, colno = get_lc(template, idx)
        res = self.make_request(APIName.GET_COMPLETIONS.value, {
            'filename': self.instance_fpath,
            'code': template,
            'lineno': lineno,
            'colno': colno,
            'allow_incomplete': True,
        })
        if res is not None and len(res) > 0:
            op_list = []
            for comp_item in res:
                if 'label' in comp_item and class_name not in comp_item['label']:
                    continue
                if 'detail' not in comp_item:
                    continue
                module_name = comp_item['detail']
                # exact match is a bad idea:
                # eg: SomeClass<>
                # class_name won't have template_args, but comp_item will
                if comp_item["kind"] == CompletionItemKind.Class:
                    op_list.append(FQCN(f"{module_name}.{class_name}", FQCNKind.CLASS))
                elif comp_item["kind"] == CompletionItemKind.Interface:
                    op_list.append(FQCN(f"{module_name}.{class_name}", FQCNKind.INTERFACE))
                elif comp_item["kind"] == CompletionItemKind.Struct:
                    op_list.append(FQCN(f"{module_name}.{class_name}", FQCNKind.STRUCT))
                elif comp_item["kind"] == CompletionItemKind.Enum:
                    # Enum FQCNs not supported yet
                    pass
            if len(op_list) > 0:
                fcqn, candidates = self.get_most_likely_ext_fqcn(op_list, max_candidates)
                return fcqn, candidates
        # TODO: Add error handling
        return None, []
