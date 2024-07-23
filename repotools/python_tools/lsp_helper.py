from typing import List, Tuple, Union
import jedi
import os

from repotools.python_tools import tree_sitter_related
import project_utils.common_utils as utils  # TODO: remove dependency

# Fetching a logger with IST adjusted time
logger = utils.fetch_ist_adjusted_logger()


def fetch_script_obj_for_file_in_repo(file_path: str, repo_path: str, environment_path: str):
    """
    Fetches the Jedi script object for a file in a repository.

    Args:
        file_path (str): The path of the file.
        repo_path (str): The path of the repository.
        environment_path (str): The path of the environment.

    Returns:
        jedi.Script: The script object for the file.
    """
    project_obj = jedi.Project(repo_path)

    environment_obj = jedi.create_environment(environment_path, safe=False)

    _project_obj_path = os.path.normpath(
        os.path.abspath(str(project_obj.path)))
    _file_path = os.path.normpath(os.path.abspath(file_path))

    # Ensure the file is within the project directory
    assert (_file_path.startswith(_project_obj_path))

    script = jedi.Script(path=file_path, project=project_obj,
                         environment=environment_obj)
    return script


def fetch_external_references(_script_obj, only_global_scope=False):
    """
    Fetches external references from the script object.

    Args:
        _script_obj (jedi.Script): The script object.
        only_global_scope (bool): Whether to fetch only global scope references.

    Returns:
        list: List of possible external references.
    """
    # Get names from the script object, considering all scopes if only_global_scope is False
    possible_external_references = _script_obj.get_names(
        all_scopes=not only_global_scope, references=True, definitions=True)

    return possible_external_references


def fetch_references_in_script(
        _script_obj, filter_outside_repo_dir, fetch_goto_obj=False, only_global_scope=False, restrict_local_spans=None):
    """
    Takes a script object and fetches symbols in the file.
    * Can contain duplicate references
    * Can contain references which are not definitions

    Args:
        _script_obj (jedi.Script): The script object.
        filter_outside_repo_dir (str): Directory to filter outside references.
        fetch_goto_obj (bool): Whether to fetch the goto object.
        only_global_scope (bool): Whether to fetch only global scope references.
        restrict_local_spans (list): List of local spans to restrict references.

    Returns:
        list: List of candidate references.
    """

    # Normalize and get the absolute path of the filter directory
    filter_outside_repo_dir = os.path.abspath(
        os.path.normpath(filter_outside_repo_dir))

    # Fetch external references from the script object
    possible_external_references = fetch_external_references(
        _script_obj, only_global_scope=only_global_scope)

    # Sort references by line and column where reference has been made
    possible_external_references = sorted(
        possible_external_references, key=lambda x: (x.line, x.column))

    # Restrict references to specified local spans if provided
    if restrict_local_spans is not None:
        possible_external_references = [_ref for _ref in possible_external_references if any([
            tree_sitter_related.SpanRelated.has_span_overlap(y,
                                                             (_ref.get_definition_start_position(), _ref.get_definition_end_position()))
            for y in restrict_local_spans
        ])]

    # Initialize list for candidate references
    candidate_references = []

    # Iterate over possible external references
    for _ref in possible_external_references:
        defn_goto_obj = None
        MAX_TRIES = 2

        # Try to get the definition goto object. This should ideally NOT be in a WHILE LOOP. However, since JEDI has cache issues, we try `MAX_TRIES` number of times before giving up.
        while MAX_TRIES > 0:
            MAX_TRIES -= 1
            defn_goto_obj = dsu_goto_parent(_ref)
            if defn_goto_obj is not None:
                break

        # Ensure definition goto object is not None
        assert (defn_goto_obj is not None)

        # Only deal with classes and functions
        if defn_goto_obj.type not in ['class', 'function']:
            continue

        # Filter out references outside the specified directory
        if (filter_outside_repo_dir is not None) and (
                filter_outside_repo_dir not in str(defn_goto_obj.module_path)):
            continue

        # Filter out builtin modules
        if defn_goto_obj.in_builtin_module():
            continue

        # Create a dictionary for the reference
        obj = dict()
        ref_start_pos, ref_end_pos = _ref.get_definition_start_position(
        ), _ref.get_definition_end_position()
        defn_start_pos, defn_end_pos = defn_goto_obj.get_definition_start_position(
        ), defn_goto_obj.get_definition_end_position()
        obj['local_span'] = ref_start_pos, ref_end_pos
        obj['local_coordinates'] = _ref.line, _ref.column
        obj['local_type'] = _ref.type
        obj['local_code'] = _ref.get_line_code()
        obj['global_span'] = defn_start_pos, defn_end_pos
        obj['global_coordinates'] = defn_goto_obj.line, defn_goto_obj.column
        obj['global_type'] = defn_goto_obj.type
        obj['global_fqdn'] = defn_goto_obj.full_name
        obj['local_fqdn'] = _ref.full_name
        obj['global_module'] = str(defn_goto_obj.module_path)

        # Include goto object if specified
        if fetch_goto_obj:
            obj['goto_obj'] = defn_goto_obj

        # Add reference to candidate references list
        candidate_references.append(obj)

    # Add reference ID to each candidate reference
    candidate_references = [{"ref_id_in_file": i, **x}
                            for i, x in enumerate(candidate_references)]
    return candidate_references


def dsu_goto_parent(_elem, max_times=100):
    """
    Recursively fetches the parent element using goto.

    Args:
        _elem (jedi.api.classes.Name): The element to fetch the parent for.
        max_times (int): Maximum number of recursive calls.

    Returns:
        jedi.api.classes.Name: The parent element.
    """
    try:
        # Try to get the goto element
        _goto_elem = _elem.goto(follow_imports=True)
    except Exception as E:
        # Log exception if any
        logger.exception(
            "Returning None in dsu for elem: %s: Error: %s", _elem, E)
        return None

    # Return None if no goto element found
    if len(_goto_elem) == 0:
        return None

    # Return the goto element if it is the same as the original element
    if _goto_elem[0] == _elem:
        return _goto_elem[0]

    # Return None if maximum recursive calls reached
    if max_times <= 0:
        logger.error(
            "Max times reached for dsu_goto_parent for elem: %s and potential parent: %s .  Now, returning None.",
            _elem,
            _goto_elem[0])
        return None

    # Recursively call dsu_goto_parent for the goto element
    return dsu_goto_parent(_goto_elem[0], max_times - 1)


def fetch_relevant_elem(file_name, repo_dir, fqdn_use, expected_type, env_path):
    """Initializes the relevant elem with the appropriate class"""
    _script_obj = fetch_script_obj_for_file_in_repo(
        file_name, repo_dir, env_path)
    # find all names in file
    all_names = _script_obj.get_names(
        all_scopes=True, references=False, definitions=True)
    all_names = [x for x in all_names if x.full_name == fqdn_use]
    # assert(len(all_names) == 1) # there can be multiple: see /home/t-agarwalan/Desktop/swebench_colm/scratch_folder/testbed_for_repos/pvlib__pvlib-python-1854/pvlib/modelchain.py `def dc_model`
    all_names = [dsu_goto_parent(x) for x in all_names]
    all_names = [_y for _y in all_names if _y is not None]
    # wanted_name = all_names[0]
    all_names = [x for x in all_names if x.type == expected_type]
    assert (len(all_names) > 0)
    assert (len(set([x.type for x in all_names])) == 1)
    # assert(wanted_name.type == expected_type)
    # assert(wanted_name.type in ['class', 'function'])
    if expected_type == 'class':
        entity_obj = [ClassObj(wanted_name, file_name, repo_dir, env_path)
                      for wanted_name in all_names]
        # entity_obj = ClassObj(wanted_name, file_name, repo_dir, env_path)
    else:
        entity_obj = [FunctionObj(
            wanted_name, file_name, repo_dir, env_path) for wanted_name in all_names]

    return entity_obj


class EntityObj:
    def __init__(self, fqdn_goto_elem, file_path, repo_dir_where_used: str, env_path: str):
        """Initializes the EntityObj object.

        Args:
            goto_obj: The goto object from jedi.
            repo_dir_where_used (str): The repository directory where the entity is used.
            env_path (str): The path of the environment.
        """
        assert (fqdn_goto_elem.is_definition()
                and fqdn_goto_elem.type in ['function', 'class'])
        logger.debug("Initializing EntityObj for the entity: %s",
                     fqdn_goto_elem.full_name)
        self.goto_obj = fqdn_goto_elem
        self.name = self.goto_obj.name  # is_complex
        self.description = self.goto_obj.description  # def is_complex

        # is_complex(num, random_num=3, **kwargs) -> bool\n\nChecks if a given number is a complex number.
        # FIXME:
        # self.docstring = self.goto_obj.docstring()

        self.full_name = self.goto_obj.full_name  # __main__.Complex.is_complex

        self.global_span = self.goto_obj.get_definition_start_position(
        ), self.goto_obj.get_definition_end_position()

        self.repo_dir_where_used = str(os.path.normpath(
            os.path.abspath(repo_dir_where_used)))

        self.env_path = env_path

        # function global path
        self.global_path = str(os.path.normpath(
            os.path.abspath(self.goto_obj.module_path)))
        # assert(os.path.normpath(os.path.abspath(file_path)) == self.global_path)

        # TODO: body content
        self.definition_body = fetch_node_definition_body(
            self.goto_obj)
        _entity_breakup = tree_sitter_related.fetch_entity_artifacts(
            self.definition_body, self.entity_type)
        self.comprehensive_str = _entity_breakup['signature']
        self.pure_docstring = _entity_breakup['docstring']
        #########################################


#################################
##################
class ClassObj(EntityObj):
    def __init__(self, goto_obj, file_path,
                 repo_dir_where_used: str,
                 env_path: str):
        self.entity_type = "class"
        assert goto_obj.is_definition() and goto_obj.type in ['class']
        super().__init__(goto_obj, file_path, repo_dir_where_used, env_path)

        self.class_nl_summary: str = "<PENDING>"

        self.class_variables, self.instance_variables, self.member_functions, self.property_variables = self.fetch_class_children(
            self)

        self.res_fetch_class_stuff = self.fetch_class_stuff(self)

        self.res_fetch_class_prompt = {mode: self.fetch_class_prompt(self, mode=mode) for mode in ['fully_specified',
                                                                                                   'half_specified',
                                                                                                   'embedding_related']}
        self.member_functions = [x.full_name for x in self.member_functions]
        del self.goto_obj

    @staticmethod
    def fetch_class_completion_req_str(_class_go_obj):
        class_name = _class_go_obj.name
        str_add = f"\n{class_name}."
        return str_add

    @staticmethod
    def fetch_obj_completion_req_str(_class_go_obj):
        class_obj_name = "anmol_msr_class_obj"

        print(_class_go_obj.module_path)
        str_add = f"\n\n{class_obj_name} = {_class_go_obj.name}()\n{class_obj_name}."
        str_add = f"\n\n{class_obj_name}:{_class_go_obj.name} = cal()\n{class_obj_name}."

        return str_add

    @staticmethod
    def is_in_class_body(completion_obj, class_obj):
        if str(completion_obj.module_path) != class_obj.global_path:
            return False
        # print("Passing ")
        class_lb, class_ub = class_obj.goto_obj.get_definition_start_position(
        ),  class_obj.goto_obj.get_definition_end_position()
        var_lb, var_ub = completion_obj.get_definition_start_position(
        ),  completion_obj.get_definition_end_position()
        return var_lb >= class_lb and var_ub <= class_ub

    @staticmethod
    def find_functions_and_variables(global_path, repo_dir, env_path):
        new_script_obj = fetch_script_obj_for_file_in_repo(
            global_path, repo_dir, env_path)
        with open(global_path) as fd:
            all_lines = fd.readlines()
        line_id = len(all_lines)
        column_id = len(all_lines[-1])
        initial_completions = new_script_obj.complete(line_id, column_id)

        all_types = list(set([x.type for x in initial_completions]))
        print(all_types)
        # assert(all_types == ['statement', 'function', 'property'])
        assert (not any([y not in ['statement', 'function', 'property', 'class',
                                   'instance'  # path here: scratch_folder/testbed_for_repos/litestar-org__litestar-0001/litestar/enums.py
                                   ] for y in all_types]))
        statement_completions = list(
            filter(lambda x: x.type in ["statement", "property"], initial_completions))
        function_completions = list(
            filter(lambda x: x.type == "function", initial_completions))
        return statement_completions, function_completions

    @staticmethod
    def fetch_class_children(_class_obj):
        obj_completion_str = _class_obj.fetch_obj_completion_req_str(
            _class_obj.goto_obj)
        class_completion_str = _class_obj.fetch_class_completion_req_str(
            _class_obj.goto_obj)

        # print(_class_obj)

        # FIXME: Perturbed content handling
        _original_file_content = open(_class_obj.global_path).read()

        # get content to find class-related stuff
        _class_completion_file_new_content = _original_file_content + class_completion_str

        # get content to find things related to object
        _object_completion_file_new_content = _original_file_content + obj_completion_str

        # find the class variables
        with open(_class_obj.global_path, 'w') as fd:
            fd.write(_class_completion_file_new_content)
        # NOTE: Class statement completions gets class-variables only
        class_statement_completions, class_function_completions = _class_obj.find_functions_and_variables(
            _class_obj.global_path, _class_obj.repo_dir_where_used, _class_obj.env_path)
        ##########################
        # print("Class statement completions: ")
        # print(*class_statement_completions, sep="\n")
        # print("Class function completions: ")
        # print(*class_function_completions, sep="\n")

        ######################
        # _class_obj.class_statement_completions, _class_obj.class_function_completions = class_statement_completions, class_function_completions
        class_statement_completions = list(
            filter(lambda x: not x.in_builtin_module(), class_statement_completions))

        # ############################
        # print("After filtering stuff:")
        # print("Class statement completions: ")
        # print(*class_statement_completions, sep="\n")
        # print("Class function completions: ")
        # print(*class_function_completions, sep="\n")

        ##########################

        # property statement completions
        property_statement_completions = list(filter(lambda x: (x.parent(
        ).type == "class") and (x.type == "property"), class_statement_completions))

        # finding class variables
        class_statement_completions = list(filter(lambda x: (x.parent(
        ).type == "class") and (x.type in ["statement", 'instance']), class_statement_completions))
        class_statement_completions = sorted(class_statement_completions, key=lambda x: (
            not ClassObj.is_in_class_body(x, _class_obj), x.line))

        # get all class variables
        class_statement_completions = [
            x for x in class_statement_completions if x.module_path is not None]
        class_variables = [(x.name,
                            x.parent().full_name,
                            str(x.parent().module_path),
                            [y.name for y in x.infer()],
                            # x.parent(),
                            # body to find the initial value of the variable
                            fetch_node_definition_body(
                                x, one_liner=True)
                            ) for x in  # It looks like you have a comment `# Python` followed by
                           # `class_statement_completions` and `
                           class_statement_completions]

        # get all properties
        property_variables = [(x.name, x.parent().full_name, str(x.parent().module_path), [
                               y.name for y in x.infer()]) for x in property_statement_completions]

        ##############################################################################
        # FINDING INSTANCE VARIABLES and all types of methods
        with open(_class_obj.global_path, 'w') as fd:
            fd.write(_object_completion_file_new_content)
        object_statement_completions, object_function_completions = _class_obj.find_functions_and_variables(
            _class_obj.global_path, _class_obj.repo_dir_where_used, _class_obj.env_path)

        #  FINDING INSTANCE VARIABLES
        object_statement_completions = list(
            filter(lambda x: not x.in_builtin_module(), object_statement_completions))
        # the object variable has to lie within a function
        object_statement_completions = list(
            filter(lambda x: x.parent().type == "function", object_statement_completions))
        object_statement_completions = sorted(object_statement_completions, key=lambda x: (
            not ClassObj.is_in_class_body(x, _class_obj), x.line))
        object_variables = [(x.name, x.parent().full_name, str(x.parent().module_path), [
                             y.name for y in x.infer()]) for x in object_statement_completions]

        ####################################################################
        # FINDING MEMBER functions
        object_function_completions = list(
            filter(lambda x: not x.in_builtin_module(), object_function_completions))
        object_function_completions = [_x.goto()[0]
                                       for _x in object_function_completions]
        object_function_completions = [
            x for x in object_function_completions if x.type == "function"]
        # new additions (to prevent stub-related things)
        object_function_completions = [
            x for x in object_function_completions if x.module_path is not None]

        object_function_completions = [FunctionObj(
            _x, _class_obj.global_path, _class_obj.repo_dir_where_used, _class_obj.env_path) for _x in object_function_completions]
        ############################################################################
        # Restore the file with the original content
        with open(_class_obj.global_path, 'w') as fd:
            fd.write(_original_file_content)
        return class_variables, object_variables, object_function_completions, property_variables

    @staticmethod
    def fetch_class_stuff(_class_obj):
        # Design decision: Often in class info, one might have the option of whether to show private methods or not. In python, privacy is NOT enforced. Also, in a couple of repos, I found instances of private methods being used outside the class. So, I am going to show all methods.

        class_str = ""
        class_str += f"Class signature: {_class_obj.comprehensive_str}\n"
        ################
        _file_where_defined = _class_obj.global_path.replace(
            _class_obj.repo_dir_where_used, '')
        if _file_where_defined[0] == '/':
            _file_where_defined = _file_where_defined[1:]
        class_str += f"File where defined: {_file_where_defined}\n"
        ##########
        class_str += f"Class full name: {_class_obj.full_name}"

        # Sort functions
        functions = _class_obj.member_functions
        functions = sorted(functions, key=lambda x: (
            "__init__" != x.name, "__" in x.name, x.parent_class != _class_obj.name,
            #   x.goto_obj.line
        ))
        functions_string_arr = [
            "* " + FunctionObj.fetch_brief_function_stuff(x) for x in functions]
        if len(functions_string_arr) == 0:
            functions_string = "None of them are accessible"
        else:
            functions_string = "\n".join(functions_string_arr)
        class_str += f"\nFunctions accessible:\n{functions_string}"

        # Add variables
        variables_str = ""
        variables_str += "\nClass variables accessible:"
        class_var_arr = [
            f"* {x[0]} | defined in class `{x[1]}`" for x in _class_obj.class_variables]
        if len(class_var_arr) == 0:
            variables_str += " None"
        else:
            variables_str += "\n"+"\n".join(class_var_arr)
        variables_str += "\nInstance variables accessible:"
        instance_var_arr = [f"* {x[0]}" for x in _class_obj.instance_variables]
        if len(instance_var_arr) == 0:
            variables_str += " None"
        else:
            variables_str += "\n"+"\n".join(instance_var_arr)
        variables_str += "\nProperties accessible:"
        property_var_arr = [f"* {x[0]}" for x in _class_obj.property_variables]
        if len(property_var_arr) == 0:
            variables_str += " None"
        else:
            variables_str += "\n"+"\n".join(property_var_arr)
        class_str += variables_str
        # class_str += f"\nClass Short Description: {_class_obj.class_nl_summary}"
        return class_str

    @staticmethod
    def fetch_class_prompt(_class_obj, mode):
        # make sure private methods are not included etc
        # also, make sure that inherited methods are not included in NL-description based information

        assert (mode in ['fully_specified',
                'half_specified', 'embedding_related'])
        class_str = ""
        class_str += f"Class signature: {_class_obj.comprehensive_str}\n"
        ######
        _file_where_defined = _class_obj.global_path.replace(
            _class_obj.repo_dir_where_used, '')
        if _file_where_defined[0] == '/':
            _file_where_defined = _file_where_defined[1:]
        class_str += f"File where defined: {_file_where_defined}\n"
        ######
        # class_str += f"Class full name: {_class_obj.full_name}"
        class_str += f"\nDocstring: {_class_obj.pure_docstring}"
        ##########
        if True:
            variables_str = ""
            variables_str += "\nClass variables accessible:\n"
            use_arr = [x for x in _class_obj.class_variables if x[1]
                       == _class_obj.full_name]
            class_var_arr = [
                f"* {x[-1]}" for x in use_arr]
            variables_str += "\n".join(class_var_arr)+"\n"
            if len(class_var_arr) == 0:
                variables_str += "None"
            class_str += variables_str+'\n'
            class_str += "# Functions involved\n"

        functions = _class_obj.member_functions
        functions = sorted(functions, key=lambda x: (
            "__init__" != x.name, "__" in x.name, x.parent_class != _class_obj.name,
            #   x.goto_obj.line
        ))

        if True:
            b = 1
            # remove inherited
            functions = [
                x for x in functions if x.parent_class == _class_obj.name]
            a = 1
            if mode == 'embedding_related':
                # Do not consider private methods during embedding creation
                functions = [x for x in functions if ((x.name == '__init__')
                                                      or
                                                      (not x.name.startswith("_")))]
                d = 1
            c = 1

        _open_str, _close_str = "<Start of new function details>\n", "\n<End of new function details>"
        if "embedding_related" in mode:
            _open_str, _close_str = "", ""
        functions_string_arr = [
            _open_str + FunctionObj.fetch_function_for_prompt(x, mode) + _close_str for x in functions]
        if len(functions_string_arr) == 0:
            # functions_string = "None of them are accessible"
            functions_string = ""
        else:
            functions_string = "\n".join(functions_string_arr)

        class_str += "\n"+functions_string
        return class_str


#################
class FunctionObj(EntityObj):
    def __init__(self, goto_obj, file_path, repo_dir_where_used: str, env_path: str):
        """
        Initializes a FunctionObj instance.

        :param goto_obj: The goto object.
        :param repo_dir_where_used: The repository directory where the function is used.
        :param env_path: The environment path.
        """
        self.entity_type = "function"
        assert goto_obj.is_definition() and goto_obj.type in ['function']
        super().__init__(goto_obj, file_path, repo_dir_where_used, env_path)

        # print("Func name is: ", self.full_name)
        # parent is which class
        self.parent_class, self.parent_class_defined_location = self.find_parent_details(
            self.goto_obj)

        # find decorators
        source_lines = open(self.global_path).readlines()
        _func_body_starting_line = self.goto_obj.get_definition_start_position()[
            0]
        self.func_decorators = self.get_decorators(
            source_lines, _func_body_starting_line)

        # self._fetch_function_stuff_res, self._fetch_brief_function_stuff_res, self._fetch_function_for_prompt_res = self.fetch_function_stuff(), self.fetch_brief_function_stuff() , self._fetch_function_for_prompt()
        self.res_fetch_function_stuff = self.fetch_function_stuff(self)
        self.res_fetch_brief_function_stuff = self.fetch_brief_function_stuff(
            self)
        self.res_fetch_function_for_prompt = {mode: self.fetch_function_for_prompt(self, mode=mode) for mode in ['fully_specified',
                                                                                                                 'half_specified',
                                                                                                                 'embedding_related']}

        del self.goto_obj

    @staticmethod
    def get_decorators(source_lines: List[str], function_starting_line: int) -> List[str]:
        """
        Gets the decorators of the function.

        :param source_lines: The source lines of the file where the function is defined.
        :param function_starting_line: The starting line of the function.
        :return: A list of decorators.
        """
        decorators = []
        lines = source_lines
        line = function_starting_line
        while line > 0:
            line -= 1
            current_line = lines[line - 1].strip()
            if current_line.startswith('@'):
                # print("Found decorator: ", current_line)
                decorators.append(current_line)
            else:
                break
        return decorators

    def __str__(self) -> str:
        """
        Returns the string representation of the FunctionObj instance.

        :return: The string representation of the FunctionObj instance.
        """
        return self.fetch_function_stuff(self)

    @staticmethod
    def fetch_function_stuff(_func) -> str:
        """
        Fetches the function stuff.

        :param _func: The function object.
        :return: The function stuff.
        """
        class_ownership_str = "Not a member of any class" if _func.parent_class is None else f"Member of `{_func.parent_class}` class"
        func_str = f"Signature: {_func.comprehensive_str} | Defined in `{_func.global_path.replace(_func.repo_dir_where_used, '')}` | {class_ownership_str}"
        if len(_func.func_decorators) != 0:
            func_str += f" | Decorators: {', '.join(_func.func_decorators)}"
        return func_str

    @staticmethod
    def fetch_brief_function_stuff(_func) -> str:
        """
        Fetches the brief function stuff.

        :param _func: The function object.
        :return: The brief function stuff.
        """
        class_ownership_str = "Not a member of any class" if _func.parent_class is None else f"Member of `{_func.parent_class}` class"
        func_str = f"Signature: {_func.comprehensive_str} | {class_ownership_str}"
        if len(_func.func_decorators) != 0:
            func_str += f" | Decorators: {', '.join(_func.func_decorators)}"
        return func_str

    @staticmethod
    def fetch_function_for_prompt(_func, mode):
        assert (mode in ['fully_specified',
                'half_specified', 'embedding_related'])
        ans_str = ""

        ans_str += f"Signature: {_func.comprehensive_str}"
        if len(_func.func_decorators) != 0:
            ans_str += f"\nDecorators: {', '.join(_func.func_decorators)}"
        if mode == 'fully_specified':
            ans_str += f"\nBody: {_func.definition_body}"
        elif mode == 'half_specified':
            ans_str += f"\nDocstring: {_func.pure_docstring}"
        else:
            assert (mode == 'embedding_related')
        return ans_str

    @staticmethod
    def find_parent_details(_function_go_obj) -> Tuple[Union[str, None], Union[str, None]]:
        """
        Finds the parent details of the function.

        :param _function_go_obj: The function goto object.
        :return: A tuple containing the parent class and the parent class defined location.
        """
        # TODO: check that parent itself is also a defined node
        parent = _function_go_obj.parent()
        if parent.type != "class":
            return None, None
        parent_class = parent.name
        parent_class_defined_location = str(parent.module_path)
        return parent_class, parent_class_defined_location


def fetch_node_definition_body(node_get_obj, file_path=None, one_liner=False):
    """Fetches the body of the node."""
    # assert (node_get_obj.is_definition())

    # starting_line in file, starting_column in line, ending_line in file, ending_column in line
    # extract the body of the function

    extracted_content_lines_arr = []
    start_line, start_col = node_get_obj.get_definition_start_position()
    end_line, end_col = node_get_obj.get_definition_end_position()
    # print("Coordinates:", (start_line, start_col), (end_line, end_col))

    # In JEDI, lines are one-based index. So, subtract line numbers by 1 to make it zero-indexing
    start_line, end_line = start_line-1, end_line-1
    if file_path is None:
        file_path = str(node_get_obj.module_path)

    logger.debug(
        f"Trying to fetch body of the node from coordinates : {(start_line, start_col, end_line, end_col)} and file path: {file_path}")
    with open(file_path, 'r') as f:
        # read file line by line
        for i, line in enumerate(f):
            if i == start_line:
                # first line of the function
                if start_line == end_line:
                    # single line function
                    # print(i)
                    extracted_content_lines_arr.append(line[start_col:end_col])
                else:
                    # multiline function
                    # print(i)
                    extracted_content_lines_arr.append(line[start_col:])
            elif i == end_line:
                # last line of the function
                # print(i)
                extracted_content_lines_arr.append(line[:end_col])
                break
            elif start_line < i < end_line:
                # print(i)
                # middle lines of the function
                extracted_content_lines_arr.append(line)
        str_found = "".join(extracted_content_lines_arr)
        # make sure that the extracted_code is a substring of the original file
        f.seek(0, 0)
        _all_code = f.read()
        # print("all_code: ", _all_code)
        assert (str_found in _all_code)
        if one_liner:
            str_found = [x.strip() for x in extracted_content_lines_arr]
            str_found = " ".join(str_found)
    return str_found
