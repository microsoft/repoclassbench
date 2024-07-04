import os


class Constants:
    ...


class PythonConstants(Constants):
    """
    Configuration class for Python-related settings.
    """

    # Path where the repository has been cloned
    ProjectDir = os.path.join(os.path.dirname(__file__), '../')

    language = 'PYTHON'

    TMP_FOLDER_FOR_PYTHON = os.path.join(
        ProjectDir, "temp/python/scratch_folder/")
    os.makedirs(TMP_FOLDER_FOR_PYTHON, exist_ok=True)

    # Path where the logger needs to log
    LOG_FILE_PATH = os.environ.get(
        'LOG_FILE_PATH', os.path.join(TMP_FOLDER_FOR_PYTHON, 'log_files/file.log'))
    if not os.path.exists(os.path.dirname(LOG_FILE_PATH)):
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

    # Read-only copy of the repositories involved in the Python version of RepoClassBench
    directory_with_repos = os.path.join(
        TMP_FOLDER_FOR_PYTHON, "dir_for_repos_for_running_tests_para")

    # Path to the directory where the testbed repos are stored
    TESTBED_FOR_REPOS = os.path.join(
        TMP_FOLDER_FOR_PYTHON, "testbed_for_repos")
    if not os.path.exists(TESTBED_FOR_REPOS):
        os.makedirs(TESTBED_FOR_REPOS, exist_ok=True)

    # path which stores the expected testcases to pass for each task in RepoClassBench
    # TEST_DIRECTIVES_DIR = os.path.join(
    #     ProjectDir, 'data/input/python_dataset_intermediate_files/test_directives')

    # path used to store temporary files created by the harness
    DIR_TEMP_FILES = os.path.join(
        TMP_FOLDER_FOR_PYTHON, 'use_dir_for_dump_path')
    if not os.path.exists(DIR_TEMP_FILES):
        os.makedirs(DIR_TEMP_FILES, exist_ok=True)

    # Method related
    MAX_TOKENS_ALLOWED_IN_FEEDBACK = 2500
