import json
import os
import sys
import project_utils.common_utils as utils  # remove dependency

logger = utils.fetch_ist_adjusted_logger()


def is_test_file(file_path):
    """
    Determines whether a file is a test-related file or not.

    Args:
        file_path (str): The path of the file to be checked.

    Returns:
        bool: True if the file is a test-related file, False otherwise.

    Criteria to decide whether a file is a test-related file or not:
    - If the file name contains "_test" or "test_".
    - If the file path contains the directory "tests/".

    Reference: https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html#test-discovery
    """
    file_path_name = os.path.basename(file_path)
    if "_test" in file_path_name:
        return True
    if "test_" in file_path_name:
        return True
    if 'tests/' in file_path:
        return True
    return False


def find_python_files(directory, filter_test_files=True, filter_out_unreadable_files=True):
    """
    Fetch all python files in the given directory.

    Args:
        directory (str): The directory to search for python files.
        filter_test_files (bool, optional): Whether to filter out test files. Defaults to True.
        filter_out_unreadable_files (bool, optional): Whether to filter out unreadable files. Defaults to True.

    Returns:
        list: A list of absolute paths to the python files found.
    """
    directory = os.path.normpath(os.path.abspath(directory))
    python_files = []
    for root, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.normpath(
                    os.path.abspath(os.path.join(root, file))))
    logger.debug(
        "[ToolObj] Total number of python files found: %s", len(python_files))

    if filter_test_files:
        exclude_status = [(x, is_test_file(x.replace(directory, "")))
                          for x in python_files]
        files_to_exclude = [x[0] for x in exclude_status if x[1]]
        logger.debug(
            "[RepoCoderObj] Files being excluded (truncated) is: %s", files_to_exclude[:10])
        python_files = [x[0] for x in exclude_status if not x[1]]
    logger.debug(
        "[ToolObj] Total number of python files after filtering out test files: %s", len(python_files))

    if filter_out_unreadable_files:
        # ignore python files which are unreadable such as latin-text
        del_files = set()
        for _file in python_files:
            try:
                with open(_file, 'r') as f:
                    f.read()
            except Exception as e:
                # logger.exception(f"Error in reading file: {_file}")
                del_files.add(_file)

        logger.debug("Skipping files (truncated): %s", list(del_files)[:10])
        python_files = [
            x for x in python_files if x not in del_files]

        logger.debug(
            f"Total number of python files found (after removing test-files + unreadable files): {len(python_files)}")

    return python_files


def get_virtual_env_name():
    # Infer the name from the path to the Python executable
    executable_path = sys.executable
    path_parts = executable_path.split(os.sep)
    # Look for a directory name typically associated with a virtual environment
    if 'bin' in path_parts:
        env_index = path_parts.index('bin') - 1
        return path_parts[env_index]

    # If none of the above methods worked, we're likely not in a virtual environment
    return None

def fetch_linter_errors(file_name, env_name):
    env_name = get_virtual_env_name()
    file_content = open(file_name, "r").read()
    logger.debug("Going to file linter errors for file: %s", file_name)
    logger.debug("File content is: %s", file_content)

    bash_script = f'''
#!/bin/bash

eval "$(conda shell.bash hook)"
conda activate {env_name}

pylint --errors-only --output-format=json {file_name}
    
    '''
    res = utils.execute_bash_script(bash_script)

    try:
        json_arr = json.loads(res['stdout'])
    except Exception as E:
        logger.debug(f"Result: {json.dumps(res, indent=1)}")
        logger.exception(f"Some error in reading pylint json output: {E}")
        json_arr = []
        raise E
    json_arr = [x for x in json_arr if x['type'] == "error"]

    # remove_message_ids = set(["E1101", "E0401", "E0213", "E1136", 'E0011'])
    keep_message_ids = set([
        "E0102",  # (function-redefined)
        'E0103',  # not in loop
        'E0104',  # return outside function
        # no value for parameter (less arguments supplied than needed)
        'E1120',
        'E0602',  # undefined variable

    ])

    # print("Remove message ids are: ", remove_message_ids)
    json_arr = [x for x in json_arr if x['message-id']
                in keep_message_ids]

    content_now = open(file_name, "r").read()
    all_lines = content_now.split("\n")
    # for _err in json_arr:
    #     _err['line'] = _err['line'] - 1
    #     all_lines[_err['line']] += f"# [{_err['message-id']}] Linter Error: {_err['message']}"
    # for curr_line in all_lines:
    #     if "# Linter" not in curr_line:
    #         curr_line = "."
    error_df = {}
    for _err in json_arr:
        _err['line'] = _err['line'] - 1
        if _err['line'] not in error_df:
            error_df[_err['line']] = []
        error_df[_err['line']].append(
            f"[{_err['message-id']}]  {_err['message']}")
    hint_str = ""
    for _line, _errors in error_df.items():
        hint_str += f"Line {_line+1} | {all_lines[_line]} | Errors: {' ; '.join(_errors)}\n"

    # print(json.dumps(json_arr, indent=2))
    return {"error_list": json_arr, "hint_str": hint_str}
