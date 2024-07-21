# Python class for tools
from collections import Counter
from copy import deepcopy
import json
import re
import sys
import contextlib
import io
import traceback
import os
import tempfile
import numpy as np
from repotools.base_tools import BaseTools
from repotools.python_tools import tool_utils
from repotools.python_tools import lsp_helper
from repotools.python_tools import tree_sitter_related
import project_utils.common_utils as utils  # TODO: remove dependency
from project_utils.constants import PythonConstants
from repotools.python_tools.repocoder_related import RepoCoderEmbeddingHandler
from repotools.python_tools import embedding_related

# Fetch logger adjusted for IST (Indian Standard Time)
logger = utils.fetch_ist_adjusted_logger()


class PythonTools(BaseTools):
    """
    Python class for tools to analyze and manipulate Python code repositories.

    This class provides various utilities for working with Python projects,
    including code analysis, import suggestions, and code snippet retrieval.
    """

    def __init__(self, repo_root_dir: str,
                 relative_file_path_to_modify: str,
                 class_name: str = None,
                 conda_env_name: str = None):
        """
        Initialize the PythonTools instance.

        Args:
            repo_root_dir (str): The root directory of the repository.
            relative_file_path_to_modify (str): The relative path of the file to modify.
            class_name (str, optional): The name of the class to be generated or modified.
            conda_env_name (str, optional): The name of the Conda environment to use.
        """
        # Normalize and validate the repository root directory
        repo_root_dir = os.path.normpath(os.path.abspath(repo_root_dir))
        self.REPO_DIR = repo_root_dir
        assert os.path.exists(
            self.REPO_DIR), "Repository directory does not exist"

        # Generate a unique hash for the repository directory
        self.REPO_DIR_UNIQUE_HASH = utils.md5_dir(self.REPO_DIR)

        logger.debug(
            f"Repo root dir: {self.REPO_DIR} | Hash: {self.REPO_DIR_UNIQUE_HASH}")

        # Store the Conda environment name for reference resolution
        self.CONDA_ENV_NAME = conda_env_name

        # Set up cache-related variables
        self.fqdn_cache_file = os.path.join(
            PythonConstants.DIR_FOR_FQDN_CACHE, f"{self.REPO_DIR_UNIQUE_HASH}.json")

        self.relative_file_path_to_modify = relative_file_path_to_modify

    @property
    def CONDA_ENV_PATH(self):
        """
        Get the path to the Python executable in the Conda environment.

        Returns:
            str: The path to the Python executable.
        """
        return os.path.join(PythonConstants.CONDA_PREFIX, 'envs', self.CONDA_ENV_NAME)

    @property
    def file_to_modify_rel(self):
        """
        Get the relative path of the file to modify.

        Returns:
            str: The relative path of the file to modify.
        """
        return self.relative_file_path_to_modify

    @property
    def file_to_modify_abs(self):
        """
        Get the absolute path of the file to modify.

        Returns:
            str: The absolute path of the file to modify.
        """
        abs_path = os.path.normpath(os.path.join(
            self.REPO_DIR, self.file_to_modify_rel))
        assert os.path.exists(abs_path), "File to modify does not exist"
        return abs_path

    def process_python_file_fqdns(self, _tc_file_absolute_path: str):
        """
        Process a Python file to find the Fully Qualified Domain Names (FQDNs) of various entities.

        This function analyzes the file to find FQDNs of:
        * Global classes
        * Global functions
        * Immediate member functions of global classes
        * Global variables

        Args:
            _tc_file_absolute_path (str): The absolute path of the Python file to process.

        Returns:
            list: A list of dictionaries containing FQDN information for each entity.
        """
        # Fetch the script object for the file
        _script_obj = lsp_helper.fetch_script_obj_for_file_in_repo(
            file_path=_tc_file_absolute_path,
            repo_path=self.REPO_DIR,
            environment_path=self.CONDA_ENV_PATH)

        # Fetch class and function definition nodes
        clickable_nodes = tree_sitter_related.fetch_class_and_function_nodes_defn_identifiers(
            _tc_file_absolute_path)

        # Fetch references within the script
        # fetch all references generally. However, since we are restricting reference spans to those spans which correspond to function/class identifier names, we can be sure that all references belong to function/class.
        candidate_references = lsp_helper.fetch_references_in_script(
            _script_obj, filter_outside_repo_dir=self.REPO_DIR, restrict_local_spans=[y['span'] for y in clickable_nodes])

        # Ensure all references are classes or functions
        assert all([x['global_type'] in ['class', 'function']
                    for x in candidate_references]), "Invalid reference type found"

        # Retain only definitions and not references to external definitions
        candidate_references = [_ref for _ref in candidate_references if (
            (_ref['global_module'] == _tc_file_absolute_path) and (_ref['global_span'] == _ref['local_span']))]

        # Fetch global scope references
        global_scope_candidate_references = lsp_helper.fetch_references_in_script(
            _script_obj, filter_outside_repo_dir=self.REPO_DIR, only_global_scope=True, restrict_local_spans=[y['span'] for y in clickable_nodes])

        # Retain only classes and functions in global scope
        assert all([x['global_type'] in ['class', 'function']
                    for x in global_scope_candidate_references]), "Invalid global scope reference type found"
        global_scope_candidate_references = [_ref for _ref in global_scope_candidate_references if (
            (_ref['global_module'] == _tc_file_absolute_path) and (_ref['global_span'] == _ref['local_span']))]

        # Ensure global scope references are a subset of all references
        _all_candidate_fqdns = set([x['global_fqdn']
                                   for x in candidate_references])
        assert all(
            [x['global_fqdn'] in _all_candidate_fqdns for x in global_scope_candidate_references]), "Global scope references not a subset of all references"

        # Create a dictionary of FQDNs
        fqdns_df = {k['global_fqdn']: k for k in candidate_references}

        # Separate global classes and functions
        global_classes_fqdns = [x['global_fqdn'] for x in global_scope_candidate_references if (
            x['global_type'] == 'class')]
        global_functions_fqdns = [x['global_fqdn'] for x in global_scope_candidate_references if (
            x['global_type'] == 'function')]

        # Create an array of FQDNs with additional information
        fqdns_arr = [{**fqdns_df[x], 'scope': 'global', 'parent_fqdn': None}
                     for x in global_classes_fqdns+global_functions_fqdns]

        # Until now, we have details for all globally defined classes and functions.
        ############################

        # Now, it's time to deal with non-global entities.
        potential_parent_fqdns = set(
            deepcopy(global_functions_fqdns+global_classes_fqdns))
        potential_parent_fqdns = sorted(
            potential_parent_fqdns, key=lambda x: -len(x))

        num_secondary_functions = 0
        # Here, we are only interested in functions which are nested within some top-level class/function
        for _ref in candidate_references:
            if _ref['global_type'] != 'function':
                continue
            if _ref['global_fqdn'] in global_functions_fqdns:
                continue

            if _ref['global_fqdn'] is None:
                _ref['global_fqdn'] = _ref['local_fqdn']

            if _ref['global_fqdn'] is None:
                # the definition of the function starts at a position greater than the 4th column ie more than 1 indentation level => entity is nested atleast 2 times deepy.
                if _ref['global_span'][0][1] > 4:
                    continue

            # this function must be a child of some top-level class/function
            # Find the parent FQDN for nested functions
            found_parent_fqdns = [
                x for x in potential_parent_fqdns if _ref['global_fqdn'].startswith(f"{x}.")]
            assert len(
                found_parent_fqdns) == 1, "Multiple or no parent FQDNs found"
            parent_fqdn = found_parent_fqdns[0]

            remaining_dots = _ref['global_fqdn'].replace(
                f"{parent_fqdn}.", '').count('.')

            if remaining_dots == 0:
                fqdns_arr.append(
                    {**fqdns_df[_ref['global_fqdn']], 'scope': 'nested', 'parent_fqdn': parent_fqdn})
                num_secondary_functions += 1
            else:
                # Skip tertiary functions or deeper
                pass

        # Handle global variables
        left_sided_identifiers = tree_sitter_related.find_left_side_identifiers_of_assignments(
            _tc_file_absolute_path)

        # this is a list of all possible external variables which are being assigned to in the file in the GLOBAL SCOPE ONLY
        possible_external_variables = _script_obj.get_names(
            all_scopes=False,  # restrict to only global scope
            references=False,
            definitions=True)
        possible_external_variables = [
            x for x in possible_external_variables if x.full_name is not None]
        possible_external_variables = [
            x for x in possible_external_variables if x.type == 'statement']
        possible_external_variables = [x for x in possible_external_variables if any([tree_sitter_related.SpanRelated.has_span_overlap(y['span'],
                                                                                                                                       (x.get_definition_start_position(
                                                                                                                                       ), x.get_definition_end_position())
                                                                                                                                       ) for y in left_sided_identifiers])]
        global_variables_fqdns = []
        for _global_var in possible_external_variables:
            obj = dict()
            obj['local_span'] = obj['global_span'] = (
                _global_var.get_definition_start_position(), _global_var.get_definition_end_position())
            obj['local_type'] = obj['global_type'] = 'variable'
            obj['local_coordinates'] = obj['global_coordinates'] = (
                _global_var.line, _global_var.column)
            obj['local_fqdn'] = obj['global_fqdn'] = _global_var.full_name
            obj['scope'] = 'global'
            obj['parent_fqdn'] = None
            obj['local_code'] = _global_var.get_line_code()
            global_variables_fqdns.append(obj)

        # Combine all FQDNs
        fqdns_arr = fqdns_arr + global_variables_fqdns
        logger.info(
            f"FQDN available for {Counter([(x['scope'], x['global_type']) for x in fqdns_arr])}")
        return fqdns_arr

    def load_all_fqdns(self):
        """
        Load (and cache) the Fully Qualified Domain Names (FQDNs) of all entities in the repository.

        This method processes all Python files in the repository to extract FQDNs for classes,
        functions, and variables. It caches the results for faster subsequent access.

        FQDN (fully qualified domain name): Similar to the name defined as in https://jedi.readthedocs.io/en/latest/docs/api-classes.html#jedi.api.classes.Name . In short, FQDN is the identifier/key for every entity defined in the repository. While almost always, the FQDN will be a one-to-one mapping, there do exist some cases in Python where some entities may have the same FQDN due to the entity being a part of a conditional definition.

        Returns:
            None
        """

        # fetch all global entities
        # retain classes among global entities
        # for nested, only find functions separated by a dot

        # Check if FQDN cache file already exists
        if os.path.exists(self.fqdn_cache_file):
            logger.debug(
                f"FQDN cache file already exists at {self.fqdn_cache_file}")
            with open(self.fqdn_cache_file, 'r') as f:
                self.all_fqdns_df = json.load(f)
            self.all_python_files = list(self.all_fqdns_df.keys())
            return

        # Find all Python files in the main directory
        self.python_file_paths = sorted(tool_utils.find_python_files(
            self.REPO_DIR, filter_test_files=True, filter_out_unreadable_files=True))

        # a dict to store all fqdns in the repository at a per-file level. The key of the dict is the relative file path and the value is a list of fqdns in that file.
        self.all_fqdns_df = dict()

        # Process each Python file
        for _idx, _file in enumerate(self.python_file_paths):
            logger.info(
                f"[Finding FQDNs in file: {_idx}/{len(self.python_file_paths)}] {_file}")
            _rel_path = _file.replace(self.REPO_DIR, '')
            if _rel_path.startswith('/'):
                _rel_path = _rel_path[1:]
            self.all_fqdns_df[_rel_path] = self.process_python_file_fqdns(
                _file)
            logger.debug("---------")

        # Cache the results
        with open(self.fqdn_cache_file, 'w') as f:
            json.dump(self.all_fqdns_df, f, indent=4)

    def create_fqdn_index(self):
        """
        Create an index of all FQDNs in the repository.

        This method processes the loaded FQDNs and creates a searchable index
        with details such as span, coordinates, filename, type, scope, and parent FQDN.

        Returns:
            None
        """
        assert hasattr(
            self, 'all_fqdns_df'), "FQDNs must be loaded before creating index"

        all_fqdns = []

        # Create an index of FQDNs with detailed information
        self.fqdn_index = dict()
        for rel_file_name, possible_fqdns in self.all_fqdns_df.items():
            print(f"Processing file: {rel_file_name}")
            all_fqdns.extend([x['global_fqdn'] for x in possible_fqdns])
            for fqdn_obj in possible_fqdns:
                print(
                    f"Processing fqdn: {fqdn_obj['global_fqdn']} | type: {fqdn_obj['global_type']} | scope: {fqdn_obj['scope']}")
                self.fqdn_index[fqdn_obj['global_fqdn']] = fqdn_obj

        # Find and sort duplicates by frequency
        freq = Counter(all_fqdns)
        freq = sorted(freq.items(), key=lambda x: -x[1])

        # TODO: this should be false ig
        # assert(self.REPOTOOLS_ELEM['global_fqdn'] in self.fqdn_index)
        # del self.fqdn_index[self.REPOTOOLS_ELEM['global_fqdn']]

        # FIXME: Take steps to handle below and hen uncomment the assert. Currently, this may not hold true in some cases, for eg: cases where a function is defined in a conditional block OR when two functions which have the same name but different decorators ie getter/setter.
        # assert(len(all_fqdns) == len(set(all_fqdns)))

        return

    def fetch_relevant_details(self, relevant_fqdn):
        """
        Fetch relevant details for a given FQDN from the cache.

        Args:
            relevant_fqdn (str): The FQDN to fetch details for.

        Returns:
            dict: Relevant details for the given FQDN.
        """
        save_dir = os.path.join(
            PythonConstants.DIR_FOR_TOOL_INFO_CACHE, self.REPO_DIR_UNIQUE_HASH)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        str_to_hash = f"{relevant_fqdn}"
        hash_val = utils.fetch_hash(str_to_hash)
        possible_path = os.path.join(save_dir, f"{hash_val}.json")

        assert os.path.exists(
            possible_path), f"Cache file not found for FQDN: {relevant_fqdn}"

        with open(possible_path, 'r') as f:
            data = json.load(f)
            assert str_to_hash in data, f"FQDN {relevant_fqdn} not found in cache"
        return data[str_to_hash]

    def prep_embedding_tool(self):
        """
        Prepare the embedding tool for code snippet retrieval and analysis.

        This method initializes and prepares various components for embedding-based
        code analysis, including RepoCoderEmbeddingHandler and snippet arrays.

        Returns:
            None
        """
        ############## REPOCODER SNIPPETS #############
        # until now, the snippet array had embeddings for only the well-defined entities like global-classes and global-functions. Below, we add all the contiguous repocoder related snippets as well.
        # initialize the repocoder obj
        repocoder_obj = RepoCoderEmbeddingHandler(self.REPO_DIR)
        repocoder_obj.prepare_database()
        #####################   END   #######################
        ################# WELL-DEFINED ENTITIES SNIPPETS ###############

        # Prepare cache and create tool info cache
        self.create_tool_info_cache()

        # Filter and process global classes and functions
        fqdns_of_global_classes = [x for x in self.fqdn_index if self.fqdn_index[x]
                                   ['global_type'] == 'class' and self.fqdn_index[x]['scope'] == 'global']

        # remove the class to be generated
        # assert(global_fqdn_of_class_gen in fqdns_of_global_classes)
        # fqdns_of_global_classes = [x for x in fqdns_of_global_classes if x != global_fqdn_of_class_gen]
        fqdns_of_global_functions = [x for x in self.fqdn_index if self.fqdn_index[x]
                                     ['global_type'] == 'function' and self.fqdn_index[x]['scope'] == 'global']
        # assert(not(any([global_fqdn_of_class_gen in x for x in fqdns_of_global_functions])))

        self.snippet_arr = []

        # Process global classes
        for _fqdn in fqdns_of_global_classes:
            elem = self.fqdn_index[_fqdn]
            info_elem = self.fetch_relevant_details(_fqdn)[0]
            obj = {
                'file_path': elem['global_module'],
                'spanning_lines': [elem['global_span'][0][0], elem['global_span'][1][0]],
                'snippet_content': info_elem['res_fetch_class_prompt']['embedding_related'],
                'snippet_hash': utils.fetch_hash(info_elem['res_fetch_class_prompt']['embedding_related'])
            }
            self.snippet_arr.append(obj)

        # Process global functions
        for _fqdn in fqdns_of_global_functions:
            elem = self.fqdn_index[_fqdn]
            info_elem = self.fetch_relevant_details(_fqdn)[0]
            obj = {
                'file_path': elem['global_module'],
                'spanning_lines': [elem['global_span'][0][0], elem['global_span'][1][0]],
                'snippet_content': info_elem['definition_body'],
                'snippet_hash': utils.fetch_hash(info_elem['definition_body'])
            }
            self.snippet_arr.append(obj)

        # Sort and filter snippets
        self.snippet_arr = sorted(
            self.snippet_arr, key=lambda x: x['snippet_hash'])

        logger.info("Snippets fetched before filtering: %s", len(
            self.snippet_arr))

        # TODO: Implement filtering of snippets containing the class to be generated
        # self.snippet_arr = [x for x in self.snippet_arr if self.name_of_class_to_generate not in x['snippet_content']]

        logger.info("Snippets fetched AFTER filtering: %s", len(
            self.snippet_arr))

        # Add Snippet IDs and fetch embeddings
        self.snippet_arr = [{"snippet_idx": idx, **x}
                            for idx, x in enumerate(self.snippet_arr)]
        self.snippet_arr = [
            {**x, **RepoCoderEmbeddingHandler.fetch_embedding_lazily(x)} for idx, x in enumerate(self.snippet_arr)]

        # Process snippets without embeddings
        snippets_wanting_idx = [x['snippet_idx']
                                for x in self.snippet_arr if not x['stat']]
        snippet_content = [self.snippet_arr[x]['snippet_content']
                           for x in snippets_wanting_idx]
        embedding_arr = embedding_related.fetch_unixcoder_embeddings(
            snippet_content)

        for rem_idx, use_embedding in zip(snippets_wanting_idx, embedding_arr):
            self.snippet_arr[rem_idx]['stat'] = True
            self.snippet_arr[rem_idx]['embedding'] = use_embedding
            RepoCoderEmbeddingHandler.insert_in_cache(
                self.snippet_arr[rem_idx])

        self.embedding_mat = np.array(
            [x['embedding'] for x in self.snippet_arr])

        logger.debug(
            f"Initial embedding mat shapes: {self.embedding_mat.shape=} {repocoder_obj.embedding_mat.shape=}")

        # Merge repocoder-snippet embedding matrices and snippet arrays
        self.embedding_mat = np.vstack(
            (self.embedding_mat, repocoder_obj.embedding_mat))
        logger.debug(f"Final embedding mat shapes: {self.embedding_mat.shape}")
        self.snippet_arr = self.snippet_arr + repocoder_obj.snippet_arr
        self.snippet_arr = [{"snippet_idx": idx, **x}
                            for idx, x in enumerate(self.snippet_arr)]

        self.repocoder_obj = repocoder_obj

    # ... (previous code remains the same)

    def create_tool_info_cache(self):
        """
        Create a cache of tool information for each FQDN in the repository.

        This method processes all FQDNs in the repository and stores detailed
        information about each entity (class, function, variable) in a cache
        for quick retrieval.

        Returns:
            None
        """
        save_dir = os.path.join(
            PythonConstants.DIR_FOR_TOOL_INFO_CACHE, self.REPO_DIR_UNIQUE_HASH)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Process all FQDNs in the repository
        # assume access to fqdns list in self.all_fqdns_df
        all_fqdns_within_repo = []
        for _filename, fqdns_list_in_file in self.all_fqdns_df.items():
            all_fqdns_within_repo.extend(fqdns_list_in_file)

        # Filter out variables, keeping only classes and functions
        all_fqdns_within_repo = [
            x for x in all_fqdns_within_repo if x['global_type'] != 'variable']
        logger.info(
            f"Distribution of fqdns: {Counter([x['global_type'] for x in all_fqdns_within_repo])}")
        all_fqdns_within_repo = [x for x in all_fqdns_within_repo if x['global_type'] in [
            'class', 'function']]  # FIXME:

        tot_errors = 0
        for ELEM_FQDN in all_fqdns_within_repo:
            try:
                str_to_hash = f"{ELEM_FQDN['global_fqdn']}"
                hash_id = utils.fetch_hash(str_to_hash)
                save_path = os.path.join(save_dir, f"{hash_id}.json")

                # Create empty file if it doesn't exist
                if not os.path.exists(save_path):
                    with open(save_path, 'w') as fd:
                        json.dump({}, fd)

                hashed_dict = json.load(open(save_path, 'r'))
                if str_to_hash in hashed_dict:
                    continue

                logger.info("Environment path: %s", self.CONDA_ENV_PATH)

                # Fetch relevant information for the FQDN
                elem = lsp_helper.fetch_relevant_elem(
                    ELEM_FQDN['global_module'], self.REPO_DIR, ELEM_FQDN['global_fqdn'], ELEM_FQDN["global_type"], self.CONDA_ENV_PATH)

                if isinstance(elem, list):
                    hashed_dict[str_to_hash] = [x.__dict__ for x in elem]
                else:
                    assert False, "Expected a list of elements"
                    hashed_dict[str_to_hash] = elem.__dict__

                # Save the updated information
                with open(save_path, 'w') as fd:
                    json.dump(hashed_dict, fd, indent=1)
                    logger.info(
                        f"Saved the entity object for hash: {str_to_hash} at {save_path}")
            except Exception as e:
                logger.exception(
                    f"Error in processing: {ELEM_FQDN['global_fqdn']}")
                tot_errors += 1
                continue

        logger.debug(f"Total errors: {tot_errors=}")

    def get_imports(self, file_content: str) -> str:
        """
        Analyze the given file content and suggest imports.

        This method processes the file content, identifies undefined symbols,
        and suggests possible imports for those symbols.

        Args:
            file_content (str): The content of the file to analyze.

        Returns:
            str: A formatted string containing import suggestions.
        """
        # check if path is absolute or relative
        if not os.path.isabs(file_content):
            file_content = os.path.join(self.REPO_DIR, file_content)
        self.code_to_analyze = open(file_content).read()  # TODO: Modify
        assert hasattr(
            self, 'all_fqdns_df'), "FQDNs must be loaded before analyzing imports"

        logger.debug(f"get_imports()")

        # Create a temporary file for analysis
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=True) as temp_file:
            # Remove existing imports
            all_lines = self.code_to_analyze.split("\n")

            #TODO FIXME: Think more about this
            # all_lines = [x for x in all_lines if not x.startswith("import ")]
            # all_lines = [x for x in all_lines if not x.startswith("from ")]
            self.code_to_analyze = "\n".join(all_lines)

            # Write processed code to the temporary file
            temp_file.write(self.code_to_analyze)
            temp_file.flush()

            # Get the path of the temporary file
            temp_file_path = temp_file.name
            _linter_error_df = tool_utils.fetch_linter_errors(
                temp_file_path, self.CONDA_ENV_NAME)
            print(f"The path to the temporary file is: {temp_file_path}")

        # Find all undefined symbols errors
        linter_errors = _linter_error_df['error_list']
        undefined_symbols = set()
        for curr_err in linter_errors:
            if curr_err['symbol'] == 'undefined-variable':
                possible_undefined_symbols = extract_single_quoted(
                    curr_err['message'])
                assert len(
                    possible_undefined_symbols) == 1, "Expected one undefined symbol per error"
                undefined_symbols.add(possible_undefined_symbols[0])

        logger.debug("All undefined symbols: %s", undefined_symbols)

        # Generate import suggestions
        IMPORT_SUGGESTION_MSG = f"Import suggestions for file:\n\n"
        for _symbol in undefined_symbols:
            suggested_imports = self.get_suggested_symbol_imports(_symbol)

            IMPORT_SUGGESTION_MSG += f"\n## Suggestions for symbol `{_symbol}`:\n"
            suggestion_msg_list = []
            for _suggested_import in suggested_imports:
                _msg = ""
                if _suggested_import['possible_import_statement'] != "":
                    _msg = f"{_suggested_import['possible_import_statement']} | "
                _msg += f"`{_suggested_import['fqdn']}` ,  {_suggested_import['comments']}"

                suggestion_msg_list.append(_msg)

            # putting in a set since duplicates may arise due to multiple definitions of the same symbol
            suggestion_msg_list = set(list(suggestion_msg_list))
            suggestion_msg_list = sorted(suggestion_msg_list, reverse=True)
            if len(suggestion_msg_list) == 0:
                IMPORT_SUGGESTION_MSG += "No suggestions found for this symbol within the repository. There might be some external library which you might need to use."
            else:
                IMPORT_SUGGESTION_MSG += "\n".join(
                    [f"* {x}" for x in suggestion_msg_list])
        print(IMPORT_SUGGESTION_MSG)
        return IMPORT_SUGGESTION_MSG

    def get_suggested_symbol_imports(self, symbol_wanted):
        """
        Get suggested imports for a given symbol.

        This method searches the repository for possible imports that match
        the given symbol, considering both module-level and global-level imports.

        Args:
            symbol_wanted (str): The symbol to find import suggestions for.

        Returns:
            list: A list of dictionaries containing import suggestions.
        """
        assert hasattr(
            self, 'all_fqdns_df'), "FQDNs must be loaded before suggesting imports"

        path_of_file_where_code_gen = self.file_to_modify_rel
        fqdn_of_file_where_code_gen = self.fetch_fqdn_from_filepath(
            path_of_file_where_code_gen)

        suggested_imports = []

        # Check for module level imports
        for rel_file_name, possible_fqdns in self.all_fqdns_df.items():
            rel_file_fqdn = self.fetch_fqdn_from_filepath(rel_file_name)

            all_fqdn_parts = rel_file_fqdn.split(".")
            if all_fqdn_parts[-1] == symbol_wanted:
                assert (all_fqdn_parts[-1] == symbol_wanted)
                rem_import = ".".join(all_fqdn_parts[:-1])
                if rem_import == "":
                    import_statement = f"import {symbol_wanted}"
                else:
                    import_statement = f"from {rem_import} import {symbol_wanted}"
                suggested_imports.append({'fqdn': rel_file_fqdn, 'comments': f'represents the module `{rel_file_name}`',
                                          'possible_import_statement': import_statement})

            # Check for global level imports (classes, functions)
            possible_fqdns = [
                x for x in possible_fqdns if x['scope'] == 'global']
            possible_fqdns = [x for x in possible_fqdns if x['global_fqdn'].split(
                ".")[-1] == symbol_wanted]

            for _fqdn in possible_fqdns:
                # NOTE: The import will be different if from the same file. In that case, there will be no import, although this case should not happen
                all_fqdn_parts = _fqdn['global_fqdn'].split(".")
                assert (all_fqdn_parts[-1] == symbol_wanted)

                if rel_file_fqdn == fqdn_of_file_where_code_gen:
                    possible_import_statement = "No import needed as the generated class and entity are in the same file"
                else:
                    fqdn_file_from_where_imported = ".".join(
                        all_fqdn_parts[:-1])
                    assert (fqdn_file_from_where_imported != "")
                    possible_import_statement = f"from {fqdn_file_from_where_imported} import {symbol_wanted}"

                suggested_imports.append(
                    {'fqdn': _fqdn['global_fqdn'], 'comments': f'represents a {_fqdn["global_type"]} in the module `{rel_file_name}`', 'possible_import_statement': possible_import_statement})

        return suggested_imports

    @staticmethod
    def fetch_fqdn_from_filepath(relative_path):
        """
        Convert a relative file path to its Fully Qualified Domain Name (FQDN).

        This method handles special cases like __init__.py files and converts
        the file path to a dot-separated FQDN.

        Args:
            relative_path (str): The relative path of the file.

        Returns:
            str: The FQDN representation of the file path.
        """
        # Handle __init__.py files
        init_py_string = "__init__.py"
        if init_py_string in relative_path:
            relative_path = relative_path.replace(init_py_string, '')

        # Remove trailing and leading slashes
        relative_path = relative_path.strip('/')

        # Convert path separators to dots
        ans = relative_path.replace('/', '.')

        # Remove .py extension
        ans = ans.replace('.py', '')

        return ans

    def get_relevant_code(self, search_string: str) -> str:
        """
        Retrieve relevant code snippets based on the given search string.

        This method uses the RepoCoderEmbeddingHandler to find and return
        the most relevant code snippets matching the search string.

        Args:
            search_string (str): The search string to find relevant code.

        Returns:
            str: A formatted string containing relevant code snippets.
        """
        assert hasattr(
            self, 'all_fqdns_df'), "FQDNs must be loaded before searching for relevant code"

        top_snippets = RepoCoderEmbeddingHandler.fetch_top_k_snippets(
            search_string, self.snippet_arr,  self.embedding_mat, top_k=3)
        context_string = RepoCoderEmbeddingHandler.convert_snippet_arr_to_context_string(
            top_snippets)

        print(context_string)
        return context_string

    def get_matching_classes(self, query_class_name):
        """
        Find classes matching the given query class name.

        This method searches the FQDN index for classes that match the given
        name, either by class name or full FQDN.

        Args:
            query_class_name (str): The class name or FQDN to search for.

        Returns:
            list: A list of matching FQDNs.
        """
        matching_fqdns = []
        for curr_fqdn, curr_fqdn_elem in self.fqdn_index.items():
            if curr_fqdn_elem['global_type'] != 'class':
                continue
            class_name = curr_fqdn.split('.')[-1]
            if (query_class_name is None) or (query_class_name == class_name) or (query_class_name == curr_fqdn):
                matching_fqdns.append(curr_fqdn)
        matching_fqdns = [x for x in matching_fqdns if x !=
                          "sklearn.manifold._t_sne.TSNE"]  # FIXME: Remove this hardcoded exclusion
        return matching_fqdns

    def get_class_info(self, query_class_name: str, ranking_query_string: str = None) -> str:
        """
        Retrieve information about classes matching the given query.

        This method searches for classes matching the query and returns
        detailed information about them.

        Args:
            query_class_name (str): The class name to search for.
            ranking_query_string (str, optional): Additional query string for ranking results.

        Returns:
            str: A formatted string containing information about matching classes.
        """
        assert hasattr(
            self, 'all_fqdns_df'), "FQDNs must be loaded before getting class info"
        print(f"get_class_info({query_class_name})")
        if not isinstance(query_class_name, str):
            ans = "Invalid argument provided. Argument type must be string"
            print(ans)
            return ans

        matching_fqdns = self.get_matching_classes(query_class_name)

        matching_fqdn_elems_df = {
            k: self.fetch_relevant_details(k) for k in matching_fqdns}
        class_results = []
        for _elem, _val in matching_fqdn_elems_df.items():
            if isinstance(_val, list):
                class_results.extend(_val)
            else:
                class_results.append(_val)

        ans = ""
        if len(class_results) == 0:
            ans = "No matching results found!"
            print(ans)
            return ans
        ans = f"<Total {len(class_results)} result(s) found:>\n"
        for _idx, _class in enumerate(class_results):
            # FIXME: FIlter out those lines which contain information about the class to be generated
            ans += f"## Details about shortlisted result ID {_idx}:\n"
            ans += _class['res_fetch_class_stuff']
            ans += "\n"
        print(ans)
        return ans

    def get_related_snippets(self, search_string: str) -> str:
        """
        Retrieve related code snippets based on the given search string.

        This method uses the RepoCoderEmbeddingHandler to find and return
        the most related code snippets matching the search string.

        Args:
            search_string (str): The search string to find related snippets.

        Returns:
            str: A formatted string containing related code snippets.
        """
        assert (hasattr(self, 'all_fqdns_df'))

        top_snippets = RepoCoderEmbeddingHandler.fetch_top_k_snippets(
            search_string, self.repocoder_obj.snippet_arr,  self.repocoder_obj.embedding_mat, top_k=3)
        context_string = RepoCoderEmbeddingHandler.convert_snippet_arr_to_context_string(
            top_snippets)

        print(context_string)
        return context_string

    def execute_statements(self, statements):
        if "get_relevant_code" in statements:
            statements = statements.replace("\n", "\t")
        statements = f"self.{statements}"
        # Create StringIO objects to capture the output and error
        captured_output = io.StringIO()
        captured_error = io.StringIO()

        logger.debug(f"Executing: {statements}")
        # Redirect the standard output and standard error streams
        with contextlib.redirect_stdout(captured_output), contextlib.redirect_stderr(captured_error):
            try:
                # Execute the statements
                exec(statements)
                error_code = 0
            except Exception as E:
                print("Error: ", E)
                # Print the traceback to the standard error stream
                traceback.print_exc()
                error_code = 1

        # Get the captured output and error
        output = captured_output.getvalue()
        error = captured_error.getvalue()
        # print("OUTPUT: ", output)

        # converting absolute paths to relative paths
        _init_str, _rep_str = "Defined in `/", "Defined in `./"
        output = output.replace(_init_str, _rep_str)

        return {"output": output, "error": error, "error_code": error_code}

    def get_signature(self,  *args):
        if len(args) == 1:
            method_name = args[0]
            class_name = None
        else:
            class_name, method_name = args[0], args[1]
        assert (hasattr(self, 'all_fqdns_df'))
        logger.debug(f"get_signature({class_name}, {method_name})")
        _res = self.get_method_artifacts(class_name, method_name)
        signature_ans = _res['signature_ans']
        print(signature_ans)
        return signature_ans

    def get_method_body(self, *args):
        if len(args) == 1:
            method_name = args[0]
            class_name = None
        else:
            class_name, method_name = args[0], args[1]

        assert (hasattr(self, 'all_fqdns_df'))
        logger.debug(f"get_method_body({class_name}, {method_name})")
        _res = self.get_method_artifacts(class_name, method_name)
        body_ans = _res['body_ans']
        print(body_ans)
        return body_ans

    def get_matching_methods(self, query_method_name):
        matching_fqdns = []
        # find all matching methods
        for curr_fqdn, curr_fqdn_elem in self.fqdn_index.items():
            if curr_fqdn_elem['global_type'] != 'function':
                continue
            method_name = curr_fqdn.split('.')[-1]
            if (query_method_name == method_name) or (query_method_name == curr_fqdn):
                matching_fqdns.append(curr_fqdn)
        return matching_fqdns

    def get_method_artifacts(self, class_name, method_name):
        assert (hasattr(self, 'all_fqdns_df'))

        if type(method_name) != str:
            ans = "Invalid argument provided. Argument type must be string"
            return {"signature_ans": ans, "body_ans": ans}

        matching_fqdns_func = self.get_matching_methods(method_name)
        matching_fqdns_class = self.get_matching_classes(class_name)
        # incorporate None
        # matching_fqdns_class = self.get_matching_classes(class_name)
        matching_fqdn_elems_df = {
            k: self.fetch_relevant_details(k) for k in matching_fqdns_func}

        func_results = []
        for _elem, _val in matching_fqdn_elems_df.items():
            if type(_val) == list:
                func_results.extend(_val)
            else:
                func_results.append(_val)

        # go through all func_results
        _new_func_results = []
        for func_res in func_results:
            parent_class = func_res['parent_class']
            if parent_class is None:
                # this should be a top-level function
                # it should be included ONLY if class_name is None
                if class_name is None:
                    _new_func_results.append(func_res)
            else:
                # this function belongs to a class
                # here, class name cannot be None
                # if class_name is None:
                #     continue
                matching_class_elems = {k: self.fetch_relevant_details(
                    k) for k in matching_fqdns_class}
                _stat = False
                for _class_elem in matching_class_elems.values():
                    all_members = []
                    if type(_class_elem) == list:
                        for __class_elem in _class_elem:
                            all_members.extend(
                                __class_elem['member_functions'])
                    else:
                        all_members.extend(_class_elem['member_functions'])
                    if func_res['full_name'] in all_members:
                        _stat = True
                        break
                if _stat:
                    _new_func_results.append(func_res)
        func_results = _new_func_results

        # now, find outputs
        signature_ans = ""
        body_ans = ""

        if len(func_results) == 0:
            return {"signature_ans": "No matching results found!", "body_ans": "No matching results found!"}

        for _idx, _func in enumerate(func_results):
            signature_ans += f"## Details about shortlisted result ID {_idx}:\n"
            signature_ans += _func['res_fetch_function_stuff']
            signature_ans += "\n"

            body_ans += f"## Details about shortlisted result ID {_idx}:\n"
            body_ans += _func['res_fetch_function_stuff'] + \
                f"\n```python\n{_func['definition_body']}\n```"
            body_ans += "\n"
        return {"signature_ans": signature_ans, "body_ans": body_ans}


def extract_single_quoted(text):
    """
    Extracts all substrings within single quotes from the given text.

    :param text: The input string from which to extract substrings.
    :return: A list of substrings found within single quotes.
    """
    # Regular expression pattern to match any characters within single quotes
    pattern = r"'([^']*)'"

    # Find all matches using re.findall
    matches = re.findall(pattern, text)

    return matches


if __name__ == "__main__":
    path_dir = os.path.join(PythonConstants.ProjectDir, "repotools/tests/python/python_minibenchmark")
    print("Path: ", path_dir)
    # sys.exit(0)

    tools_obj = PythonTools(repo_root_dir=path_dir,
                            relative_file_path_to_modify="test_imports.py",
                            conda_env_name="repotools_env")
    tools_obj.load_all_fqdns()

    tools_obj.create_fqdn_index()
    tools_obj.prep_embedding_tool()

    # a = 1
    import_file = os.path.join(path_dir, "python/test_imports.py")
    tools_want = [
        "get_class_info('class_A')",
        "get_relevant_code('class to deal with Polar Complex numbers')",
        "get_related_snippets('about Goliath')",
        "get_method_body('class_A', 'cal')",
        "get_method_body('ComplexList', 'msr_add')",
        "get_signature('class_A', 'cal')",
        f"get_imports('{import_file}')",
    ]
    # tools_want = [f"self.{x}" for x in tools_want]

    for _tool in tools_want:
        print("#############################")
        print(_tool)
        output_ans = tools_obj.execute_statements(_tool)
        print(json.dumps(output_ans, indent=1))
        print(output_ans['output'])
        print("########################")

    # testing some other commands
    while True:
        ans = input("Enter command: ")
        output_ans = tools_obj.execute_statements(ans)
        print(output_ans)
