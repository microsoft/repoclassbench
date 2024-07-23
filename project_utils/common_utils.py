import datetime
import functools
import random
import os
import subprocess
import tempfile
import logging
import hashlib
import pytz
import tiktoken

from project_utils.constants import PythonConstants


class ISTFormatter(logging.Formatter):
    # formattter to convert the time to IST
    def formatTime(self, record, datefmt=None):
        # Create a datetime object from the timestamp
        dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)

        # Convert it to the desired timezone (+5:30 from UTC)
        dt = dt.astimezone(pytz.timezone("Asia/Kolkata"))

        # If datefmt is provided, use it to format the time
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.isoformat()


def fetch_ist_adjusted_logger(logger_name="__main__"):
    """Fetches a logger adjusted to initialize IST time in the logs"""
    logger_obj = logging.getLogger(logger_name)
    # find number of handlers already
    num_handlers = len(logger_obj.handlers)
    if num_handlers > 0:
        # logger has already been configured
        return logger_obj

    logger_obj.setLevel(logging.DEBUG)

    # add 2 new handlers
    c_handler = logging.StreamHandler()  # console handler
    c_handler.setLevel(logging.DEBUG)

    f_handler = logging.FileHandler(PythonConstants.LOG_FILE_PATH)
    f_handler.setLevel(logging.DEBUG)

    # Define the format to include thread ID
    log_format = "[%(levelname)s] %(module)s | %(lineno)d | PID: %(process)d | ThreadID: %(thread)d - %(asctime)s - %(message)s"

    # Use the custom formatter if needed or the default Formatter
    c_format = ISTFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    c_handler.setFormatter(c_format)

    f_format = ISTFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    f_handler.setFormatter(f_format)

    logger_obj.addHandler(c_handler)
    logger_obj.addHandler(f_handler)
    return logger_obj


def get_ist_time():
    """
    Get the current time in the Indian Standard Time (IST) timezone.

    Returns:
        str: The current time in the format 'YYYY-MM-DD HH:MM:SS TZOFFSET'.

    Example:
        >>> get_ist_time()
        '2022-01-01 12:34:56 IST+0530'
    """
    desired_timezone = pytz.timezone("Asia/Calcutta")
    current_time_utc = datetime.datetime.utcnow()
    current_time_in_desired_timezone = current_time_utc.replace(
        tzinfo=pytz.utc
    ).astimezone(desired_timezone)
    formatted_time = current_time_in_desired_timezone.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    return formatted_time


def execute_bash_script(script: str):
    """
    Execute a bash script with the given content.

    Args:
        script (str): The script can either be the path to a bash file or the contents of the bash file itself.

    Returns:
        dict: A dictionary containing the following keys:
            - 'stdout': The standard output of the executed script.
            - 'stderr': The standard error of the executed script.
            - 'exit_status': The exit status code of the executed script.
            - 'script_content': The content of the script that was executed.
            - 'running_timestamp': The timestamp when the script was executed.
    """

    # script can either be the path to a bash file or the contents of the
    # bash file itself
    script_path = script if os.path.exists(script) else None
    script_content = script if not os.path.exists(script) else None
    with tempfile.NamedTemporaryFile(
        prefix="temp_install_bash_",
        suffix=".sh",
        delete=True,
        dir=PythonConstants.DIR_TEMP_FILES,
    ) as temp:
        if not script_path:
            script_path = temp.name
            temp.write(script.encode())
            temp.flush()
        else:
            script_content = open(script_path, "r").read()
        assert os.path.exists(script_path)
        result = subprocess.run(["bash", script_path], capture_output=True, text=True)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_status": result.returncode,
        "script_content": script_content,
        "running_timestamp": get_ist_time(),
    }


def with_tempfile(prefix="", dir=PythonConstants.DIR_TEMP_FILES):
    """
    A decorator that creates a temporary file and passes it as an additional argument to the decorated function.

    Args:
        prefix (str, optional): Prefix for the temporary file name. Defaults to ''.
        dir (str, optional): Directory where the temporary file will be created. Defaults to PythonConstants.DIR_TEMP_FILES.

    Returns:
        function: Decorated function.

    Example:
        @with_tempfile(prefix='temp', dir='/path/to/temp/files')
        def process_data(data, temp_file):
            # Use the temporary file to process the data
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the current timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            # Create a temporary file with the specified prefix and directory
            with tempfile.NamedTemporaryFile(
                prefix=f"{timestamp}_{prefix}_{random.randint(1, 100000)}_", dir=dir
            ) as temp_file:
                # Call the decorated function with the temporary file as an
                # additional argument
                return func(*args, temp_file=temp_file, **kwargs)

        return wrapper

    return decorator


def estimate_token_cnt(code: str) -> int:
    """Estimate the number of tokens in the given code.

    Args:
        code (str): The code for which the token count needs to be estimated.

    Returns:
        int: The estimated number of tokens in the code.
    """
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = encoding.encode(code)
    return len(tokens)


def truncate_string_per_token(string_to_truncate, tokens_to_keep):
    """
    Truncates a string based on the number of tokens to keep.

    Args:
        string_to_truncate (str): The string to be truncated.
        tokens_to_keep (int): The number of tokens to keep.

    Returns:
        str: The truncated string.

    """
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = encoding.encode(string_to_truncate)
    # logger.debug(f"Truncating from {len(tokens)} to {tokens_to_keep}")
    return encoding.decode(tokens[:tokens_to_keep])


def fetch_hash(message) -> str:
    """
    Calculates the SHA256 hash of the given message.

    Args:
        message (str): The message to calculate the hash for.

    Returns:
        str: The hexadecimal representation of the SHA256 hash.
    """
    encoded_message = message.encode()

    hash_object = hashlib.sha256()
    hash_object.update(encoded_message)

    hex_dig = hash_object.hexdigest()
    return hex_dig


## >>>>>     For hashing directories   <<<<<
import hashlib
from pathlib import Path


def md5_update_from_file(filename, hash):
    assert Path(filename).is_file()
    with open(str(filename), "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash


def md5_file(filename):
    return md5_update_from_file(filename, hashlib.md5()).hexdigest()


def md5_update_from_dir(directory, hash):
    assert Path(directory).is_dir()
    for path in sorted(Path(directory).iterdir(), key=lambda p: str(p).lower()):
        hash.update(path.name.encode())
        if path.is_file():
            hash = md5_update_from_file(path, hash)
        elif path.is_dir():
            hash = md5_update_from_dir(path, hash)
    return hash


def md5_dir(directory):
    return md5_update_from_dir(directory, hashlib.md5()).hexdigest()
## >>>>>     For hashing directories   <<<<<
