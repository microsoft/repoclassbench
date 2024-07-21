"""Java class for tools"""

import asyncio
import os
import threading
import zipfile
import gdown
from repotools.base_tools import BaseTools
from repotools.java_tools.EclipseJDTLS import EclipseJDTLS
from repotools.java_tools.class_info_tool import ClassInfoTool
from repotools.java_tools.signature_tool import SignatureTool
from repotools.java_tools.get_relevant_code import RelevantCodeTool
from repotools.java_tools.import_tool import ImportTool
from repotools.java_tools.tree_sitter_utils import get_tree
from repotools.java_tools.unixcoder import UniXcoder

import torch

from repotools.java_tools.utils import lsp_runner

class JavaTools(BaseTools):
    """Java class for tools"""

    def __init__(self, repo_root_dir: str, class_name: str = None, file_path: str = None):
        
        assert file_path is not None, "file_path cannot be None"

        if not os.path.exists("external/java/jdk-17.0.6"):                
            with zipfile.ZipFile("external/java/jdk-17.0.6.zip", "r") as zip_ref:
                zip_ref.extractall("external/java")

        if not os.path.exists("external/java/language-server-files"):
            if not os.path.exists("external/java/language-server-files.zip"):
                data_url = "https://drive.google.com/uc?id=1QS8cae9VqWoFrSA88ozty4gMhBRSNKC8"
                gdown.download(data_url, "external/java/language-server-files.zip", quiet=False)

            with zipfile.ZipFile("external/java/language-server-files.zip", "r") as zip_ref:
                zip_ref.extractall("external/java")

        ## Give permissions
        for root, dirs, files in os.walk("external/java"):
            for d in dirs:
                os.chmod(
                    os.path.join(root, d), 0o777
                )  # Set permissions for directories
            for f in files:
                os.chmod(os.path.join(root, f), 0o777)  # Set permissions for files
        
        self.abs_repo_root_dir = os.path.join(os.getcwd(),repo_root_dir)
        
        self.embedding_model = UniXcoder("microsoft/unixcoder-base")
        self.get_relevant_code_object = RelevantCodeTool(self,self.abs_repo_root_dir)
        if torch.cuda.is_available():
            self.embedding_model.cuda()

        self.running_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.running_loop)
        asyncio_running_thread = threading.Thread(
            target=self.running_loop.run_forever
        )
        
        # Sets the thread as a daemon so that it will terminate when the main thread terminates
        asyncio_running_thread.setDaemon(True)
        asyncio_running_thread.start()
        
        self.content=""#\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n"

        # Add a scratchpad file to the repo
        self.abs_file_path=os.path.join(self.abs_repo_root_dir, file_path)
        with open(
            self.abs_file_path,
            "w", encoding="utf-8"
        ) as f:
            f.write(self.content)
        
        # Create language server object
        self.language_server = EclipseJDTLS(
            self.abs_repo_root_dir,
            ws_dir=os.path.join(os.getcwd(),"temp/java/working_repo/ws_dir"),
            dep_folder_path=os.path.join(os.getcwd(),"external/java/language-server-files"),
        )


        while True:
            asyncio_tasks_list = []
            servers_stopped_events = []
            server_started = threading.Event()
            exit_event = asyncio.Event()
            server_stopped = threading.Event()
            # Calling run_coroutine_threadsafe from main thread
            asyncio_tasks_list.append(
                ## LSP runner is a thread that runs the language server and send the exit singal when it ends
                asyncio.run_coroutine_threadsafe(
                    lsp_runner(self.language_server, server_started, exit_event, server_stopped),
                    self.running_loop,
                )
            )
            servers_stopped_events.append(server_stopped)

            # Main thread waiting for server to start
            try:
                server_started.wait(timeout=10)
            except Exception:
                # Servers not started, retrying
                continue
            # Main thread woke after server started
            break

        self.language_server.initialize_scratchpad_file(self.abs_file_path)

        self.import_tool=ImportTool(self.language_server,self.abs_file_path,self.running_loop)
        self.class_info_tool=ClassInfoTool(self.language_server,self.abs_file_path,self.abs_repo_root_dir,self.running_loop)
        self.signature_tool=SignatureTool(self.language_server,self.abs_file_path,self.abs_repo_root_dir,self.running_loop)

    def get_imports(self, file_content: str) -> str:
        """Returns the suggested imports given the file content"""
        try:
            rv="Suggested imports:\n"+self.import_tool.get_imports(file_content)    
        except Exception as e:
            rv="Suggested imports:\n"+" Unable to retrieve imports" + str(e)
        return rv

    def get_relevant_code(self, search_string: str) -> str:
        """Returns the relevant code snippets given the search string"""
        return self.get_relevant_code_object.get_relevant_code(search_string)

    def get_signature(self, class_name: str, method_name: str) -> str:
        """Returns the signature of the method given the class name and method name"""
        return self.signature_tool.get_signature_formatted(class_name, method_name)

    def get_method_body(self, class_name: str, method_name: str) -> str:
        """Returns the body of the method given the class name and method name"""
        classes = get_tree(
            self.abs_repo_root_dir,
            [],
        )
        class_names=list(filter(lambda x:x.split(".")[-1]==class_name,list(classes.keys())))
        if class_names==[]:
            return "Class not found in the repository"
        required_definitions = "\n".join([a[:1000] for a in list(filter(lambda x:method_name+"(" in x,list(classes[class_names[0].strip()].values())))])
        return required_definitions

    def get_class_info(self, class_name: str, ranking_query_string: str = None) -> str:
        """Returns the class information given the class name"""
        return self.class_info_tool.get_class_info_formatted(class_name, ranking_query_string, embedding_model=self.embedding_model)


    def get_related_snippets(self, search_string: str) -> str:
        """Returns the repocoder code snippets given the search string"""
        return self.get_relevant_code_object.get_relevant_snippets(search_string)