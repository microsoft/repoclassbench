import os
import json
import numpy as np
from copy import deepcopy
from . import embedding_related
from repotools.python_tools import embedding_related
from repotools.python_tools import tool_utils
import project_utils.common_utils as utils  # TODO: remove dependency
from project_utils.constants import PythonConstants

logger = utils.fetch_ist_adjusted_logger()


class RepoCoderEmbeddingHandler:
    """
    This class handles the embedding of code snippets for a given repository.
    It is responsible for preparing the database of embeddings and fetching
    snippets based on natural language queries.
    """

    # Directory where UnixCoder embeddings are cached
    CACHE_DIR = PythonConstants.CACHE_FOR_UNIXCODER_EMBEDDINGS

    def __init__(self, arg_repo_dir: str, name_of_class_to_generate=None):
        """
        Initialize the RepoCoderEmbeddingHandler.

        :param arg_repo_dir: Directory of the repository to handle.
        :param name_of_class_to_generate: Optional name of the class which is being tested for in the benchmark.
        """
        logger.info(
            "[RepoCoderDB] RepoCoderEmbeddingHandler being initialized for repo: %s", arg_repo_dir)
        logger.debug("[RepoCoderDB] Cache directory is: %s", self.CACHE_DIR)

        assert (os.path.exists(self.CACHE_DIR))

        self.repo_dir = arg_repo_dir
        assert (os.path.exists(self.repo_dir))

        self.python_file_paths = tool_utils.find_python_files(
            self.repo_dir, filter_test_files=True, filter_out_unreadable_files=True)

        # TODO: Match constants with Ajinkya
        self.WINDOW_SIZE = PythonConstants.REPOCODER_WINDOW_SIZE
        self.SLIDING_SIZE = PythonConstants.REPOCODER_SLIDING_SIZE

        self.name_of_class_to_generate = name_of_class_to_generate

        # Initialize the UniXcoder model and move it to the GPU
        self.model = embedding_related.UniXcoder("microsoft/unixcoder-base")
        self.model.to("cuda")

        # Flag to check if the database has been prepared
        self.have_prepped_database = False

    def prepare_database(self):
        """
        Prepare the database of code snippet embeddings.
        """
        # Return if the database has already been prepared
        if self.have_prepped_database:
            return

        logger.debug("[RepoCoderDB] Proceeding to prepare database")

        self.snippet_arr = []
        for _idx, _file in enumerate(self.python_file_paths):
            # Fetch snippets from each Python file and extend the snippet array
            self.snippet_arr.extend(self.fetch_snippets_from_python_file(
                _file, self.SLIDING_SIZE, self.WINDOW_SIZE))
        logger.debug("[RepoCoderDB] All snippets have been fetched from the repo. Total: %s", len(
            self.snippet_arr))

        self.snippet_arr = sorted(
            self.snippet_arr, key=lambda x: x['snippet_hash'])

        if self.name_of_class_to_generate is not None:
            self.snippet_arr = [
                x for x in self.snippet_arr if self.name_of_class_to_generate not in x['snippet_content']]

        # Add snippet IDs to each snippet
        self.snippet_arr = [{"snippet_idx": idx, **x}
                            for idx, x in enumerate(self.snippet_arr)]

        # Uncomment for experimentation
        # self.snippet_arr = self.snippet_arr[:512]

        # Fetch embeddings lazily (i.e., use cached embeddings if available)
        self.snippet_arr = [
            {**x, **self.fetch_embedding_lazily(x)} for idx, x in enumerate(self.snippet_arr)]

        # Find embeddings for snippets not already handled
        snippets_wanting_idx = [x['snippet_idx']
                                for x in self.snippet_arr if not x['stat']]
        snippet_content = [self.snippet_arr[x]['snippet_content']
                           for x in snippets_wanting_idx]
        logger.info("[RepoCoderDB] Total snippets are %s",
                    len(self.snippet_arr))
        logger.info(
            "[RepoCoderDB] Fetching embeddings for: %s snippets", len(snippet_content))

        logger.debug(
            "[RepoCoderDB] Fetching embeddings for snippets not already handled")
        embedding_arr = embedding_related.fetch_unixcoder_embeddings(
            snippet_content, self.model)

        logger.debug(
            "[RepoCoderDB] Updating the snippet_arr with newly fetched UnixCoder embeddings")
        # Update the snippet array with the new embeddings and save to cache
        for rem_idx, use_embedding in zip(snippets_wanting_idx, embedding_arr):
            self.snippet_arr[rem_idx]['stat'] = True
            self.snippet_arr[rem_idx]['embedding'] = use_embedding
            # Save the snippet with embedding to disk
            self.insert_in_cache(self.snippet_arr[rem_idx])

        # Create an embedding matrix from the embeddings
        self.embedding_mat = np.array(
            [x['embedding'] for x in self.snippet_arr])

        self.have_prepped_database = True
        logger.debug("[RepoCoderDB] RepoCoder database has been prepared.")

    @staticmethod
    def convert_snippet_arr_to_context_string(snippet_arr):
        """
        Convert an array of snippets into a formatted string for use as a prompt.

        :param snippet_arr: Array of snippet dictionaries.
        :return: A formatted string containing all snippets.
        """
        assert (len(snippet_arr) > 0)

        # Build the string for each snippet
        snippet_txt_arr = []
        for _idx, elem in enumerate(snippet_arr):
            snippet_txt_arr.append(
                f"<Snippet {_idx+1}, derived from {elem['file_path']} and lines ({elem['spanning_lines']})>\n```python\n{elem['snippet_content']}\n```\n<End of snippet {_idx+1}>")

        # Combine all snippets into a single string with headers
        complete_str = "\n".join(snippet_txt_arr)
        complete_str = "#### Beginning of snippets ####\n" + \
            complete_str + "\n#### End of snippets ####"
        return complete_str

    @staticmethod
    def insert_in_cache(snippet_elem):
        """
        Insert a snippet and its embedding into the cache.

        :param snippet_elem: The snippet dictionary containing the content and embedding.
        """
        # Extract the snippet content and hash value
        snippet_text, hash_val = snippet_elem['snippet_content'], snippet_elem['snippet_hash']

        # Construct the file path for the cache file
        file_path = os.path.join(
            RepoCoderEmbeddingHandler.CACHE_DIR, f"{hash_val}.json")

        # Ensure the cache file exists
        assert os.path.exists(file_path)

        # Load the existing cache data
        df = json.load(open(file_path, 'r'))

        df.append({'encoded_text': snippet_text,
                  'unixcoder_embedding': snippet_elem['embedding']})

        # Write the updated cache data back to the file
        with open(file_path, 'w') as fp:
            json.dump(df, fp)

    @staticmethod
    def fetch_top_k_snippets(nl_query, snippet_arr, embedding_mat, top_k=10):
        """
        Fetch the top-k most relevant snippets for a natural language query.

        :param nl_query: The natural language query string.
        :param snippet_arr: Array of snippet dictionaries.
        :param embedding_mat: The embedding matrix for all snippets.
        :param top_k: The number of top snippets to return.
        :return: A list of the top-k most relevant snippets.
        """
        logger.debug(
            "[RepoCoderDB] Fetching top %s snippets for the query (truncated): %s", top_k, nl_query[:50])

        # Fetch the embedding for the natural language query
        nl_embedding = embedding_related.fetch_unixcoder_embeddings([nl_query])[
            0]

        # Calculate the scores for each snippet by dot product with the query embedding
        individual_scores = np.dot(nl_embedding, np.array(embedding_mat).T)

        # Get the indices of the top-k highest scoring snippets
        top_k_indices = np.argsort(individual_scores)[::-1][:top_k]

        # Retrieve the top-k snippets, excluding their embeddings to save memory
        snippets_ret = [deepcopy(
            {**snippet_arr[x], "score": individual_scores[x], "embedding": None}) for x in top_k_indices]
        return snippets_ret

    @staticmethod
    def fetch_embedding_lazily(snippet_elem):
        """
        Lazily fetch the embedding for a snippet, using the cache if available.

        :param snippet_elem: The snippet dictionary containing the content and hash.
        :return: A dictionary with the status and embedding of the snippet.
        """
        snippet_text, hash_val = snippet_elem['snippet_content'], snippet_elem['snippet_hash']

        file_path = os.path.join(
            RepoCoderEmbeddingHandler.CACHE_DIR, f"{hash_val}.json")

        # If the cache file does not exist, create it with an empty list
        if not os.path.exists(file_path):
            with open(file_path, 'w') as fp:
                json.dump([], fp)

        # Load the cache data
        df = json.load(open(file_path, 'r'))

        # Check if the snippet is already in the cache
        for elem in df:
            if elem['encoded_text'] == snippet_text:
                # If found, return the status and the normalized embedding
                return {"stat": True, "embedding": normalize_python_arr(elem['unixcoder_embedding'])}

        # If not found, return status as False and no embedding
        return {"stat": False, "embedding": None}

    @staticmethod
    def fetch_snippets_from_python_file(py_file_path, sliding_size=10, window_size=20):
        """
        Fetch code snippets from a Python file using a sliding window approach.

        :param py_file_path: Path to the Python file.
        :param sliding_size: The step size for the sliding window.
        :param window_size: The size of the window to consider for each snippet.
        :return: A list of snippet dictionaries.
        """
        try:
            # Open the file and read all lines
            with open(py_file_path, 'r') as fd:
                all_lines = fd.readlines()
        except:
            # Log an error if the file cannot be read
            logger.error(
                "Error in reading file while fetching snippets: %s", py_file_path)
            return []

        # Get the total number of lines in the file
        num_lines = len(all_lines)

        # List to store the snippets
        snippet_arr = []

        # Use a sliding window to extract snippets
        for lb in range(0, num_lines, sliding_size):
            ub = min(lb + window_size, num_lines) - 1
            chosen_lines = all_lines[lb:ub+1]
            snippet_content = "".join(chosen_lines)
            obj = dict()
            obj['file_path'] = py_file_path
            obj['spanning_lines'] = [lb, ub]
            obj['snippet_content'] = snippet_content
            obj['snippet_hash'] = utils.fetch_hash(snippet_content)
            snippet_arr.append(obj)

        return snippet_arr


def normalize_python_arr(input_list):
    """
    Normalize a list of Python numbers.

    :param input_list: The list of numbers to normalize.
    :return: A normalized list of numbers.
    """
    input_array = np.array(input_list)
    norm = np.linalg.norm(input_array)
    normalized_array = input_array / norm
    normalized_list = normalized_array.tolist()
    return normalized_list
