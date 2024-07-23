
from contextlib import asynccontextmanager
import os
import json
import pathlib
import asyncio
import shutil

from .OLSPlibs.lsp.server import LanguageServer
from .OLSPlibs.lsp.types import (
    CompletionParams,
    DefinitionParams,
    InitializeParams,
    CompletionItem,
    CompletionList,
    SignatureHelpParams,
    CodeActionParams,
)

from typing import List, Tuple, Union, Any


class EclipseJDTLS:

    def get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        # Look into https://github.com/eclipse/eclipse.jdt.ls/blob/master/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/preferences/Preferences.java to understand all the options available
        with open("external/java/language-server-files/initialize_params.json", "r") as f:
            d: InitializeParams = json.load(f)

        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)

        d["processId"] = os.getpid()
        d["rootPath"] = repository_absolute_path
        d["rootUri"] = pathlib.Path(repository_absolute_path).as_uri()
        d["initializationOptions"]["workspaceFolders"] = [
            pathlib.Path(repository_absolute_path).as_uri()
        ]
        d["workspaceFolders"] = [
            {
                "uri": pathlib.Path(repository_absolute_path).as_uri(),
                "name": os.path.basename(repository_absolute_path),
            }
        ]
        bundles = []
        for bundle_rel_path in d["initializationOptions"]["bundles"]:
            bundle_abs_path = os.path.join(
                os.path.abspath(os.path.dirname(__file__)), bundle_rel_path
            )
            bundles.append(bundle_abs_path)
        d["initializationOptions"]["bundles"] = bundles

        for runtime in d["initializationOptions"]["settings"]["java"]["configuration"][
            "runtimes"
        ]:
            runtime["path"] = os.path.abspath(
                "external/java/jdk-17.0.6"
            )
        d["initializationOptions"]["settings"]["java"]["import"]["gradle"][
            "home"
        ] = os.path.join(
            self.dep_folder_path,"gradle-7.3.3"
        )
        d["initializationOptions"]["settings"]["java"]["import"]["gradle"]["java"][
            "home"
        ] = os.path.join(
            self.dep_folder_path,
            "launch_jres/17.0.6-linux-x86_64",
        )

        return d

    def initialize_scratchpad_file(self, scratchpad_file_path: str):
        self.scratchpad_file_path = scratchpad_file_path
        self.current_text = ""
        self.file_change_id = 0
        with open(scratchpad_file_path, "w") as f:
            f.write("")
        self.server.notify.did_open_text_document(
            {
                "textDocument": {
                    "version": self.file_change_id,
                    "languageId": "java",
                    "text": self.current_text,
                    "uri": pathlib.Path(self.scratchpad_file_path).as_uri(),
                }
            }
        )

    def __init__(self, repository_root_path: str, ws_dir: str, dep_folder_path: str):
        self.dep_folder_path = dep_folder_path
                

        self.import_choices=[]
        
        jre_path = os.path.join(
            self.dep_folder_path,
            "vscode-java/jre/17.0.6-linux-x86_64/bin/java",
        )
        lombok_jar_path = os.path.join(
            self.dep_folder_path,
            "vscode-java/lombok/lombok-1.18.24.jar",
        )
        # if os.path.exists(os.path.abspath("temp/java/working_repo/.cache")):
        #     shutil.rmtree(os.path.abspath("temp/java/working_repo/.cache"))
        shared_cache_location = os.path.abspath("temp/java/working_repo/.cache/.jdt/index")
        # jdtls_launcher_jar = os.path.join(
        #     self.dep_folder_path,
        #     "vscode-java/server/plugins/org.eclipse.equinox.launcher_1.6.400.v20210924-0641.jar",
        # )
        jdtls_launcher_jar = os.path.join(
            self.dep_folder_path,
            "repository/plugins/org.eclipse.equinox.launcher_1.6.900.v20240613-2009.jar",
        )

        ## Delete the working repo
        if os.path.exists(ws_dir):
            shutil.rmtree(ws_dir)

        os.makedirs(ws_dir, exist_ok=True)
        self.log_path = os.path.join(ws_dir, "log.txt")

        data_dir = os.path.join(ws_dir, "data_dir")
        jdtls_config_path = os.path.join(ws_dir, "config_path")

        jdtls_readonly_config_path = os.path.join(
            self.dep_folder_path,
            f"repository/config_{'win' if os.name=='nt' else 'linux' }",
        )

        # jdtls_readonly_config_path = os.path.join(
        #     self.dep_folder_path,
        #     f"vscode-java/server/config_{'win' if os.name=='nt' else 'linux' }",
        # )

        if not os.path.exists(jdtls_config_path):
            shutil.copytree(jdtls_readonly_config_path, jdtls_config_path)

        for static_path in [
            jre_path,
            lombok_jar_path,
            jdtls_launcher_jar,
            jdtls_config_path,
            jdtls_readonly_config_path,
        ]:
            assert os.path.exists(static_path), static_path

        cmd = f"export syntaxserver=false\ncd {repository_root_path}\n" + " ".join(
            [
                jre_path,
                "--add-modules=ALL-SYSTEM",
                "--add-opens",
                "java.base/java.util=ALL-UNNAMED",
                "--add-opens",
                "java.base/java.lang=ALL-UNNAMED",
                "--add-opens",
                "java.base/sun.nio.fs=ALL-UNNAMED",
                "-Declipse.application=org.eclipse.jdt.ls.core.id1",
                "-Dosgi.bundles.defaultStartLevel=4",
                "-Declipse.product=org.eclipse.jdt.ls.core.product",
                "-Djava.import.generatesMetadataFilesAtProjectRoot=false",
                "-Dfile.encoding=utf8",
                "-noverify",
                "-XX:+UseParallelGC",
                "-XX:GCTimeRatio=4",
                "-XX:AdaptiveSizePolicyWeight=90",
                "-Dsun.zip.disableMemoryMapping=true",
                "-Djava.lsp.joinOnCompletion=true",
                "-Xmx3G",
                "-Xms100m",
                "-Xlog:disable",
                "-Dlog.level=ALL",
                f"-javaagent:{lombok_jar_path}",
                f"-Djdt.core.sharedIndexLocation={shared_cache_location}",
                "-jar",
                jdtls_launcher_jar,
                "-configuration",
                jdtls_config_path,
                "-data",
                data_dir,
                "-clearPersistedState"
            ]
        )

        self.repository_root_path: str = repository_root_path
        self.completions_available = asyncio.Event()
        self.definition_available = asyncio.Event()
        self.code_actions_available = asyncio.Event()
        self.code_actions_resolutions_available = asyncio.Event()        
        self.document_diagnostics_available = asyncio.Event()
        self.service_ready_event = asyncio.Event()
        self.intellicode_enable_command_available = asyncio.Event()
        self.initialize_searcher_command_available = asyncio.Event()

        def logger(source, target, msg):
            self.on_log_message(f"{source} -> {target}: {str(msg)}\n")

        server = LanguageServer(cmd, logger=logger)
        self.server: LanguageServer = server

    @asynccontextmanager
    async def start_server(self):
        async def register_capability_handler(params):
            assert "registrations" in params
            for registration in params["registrations"]:
                # if True:
                #     self.anon_response_available.set()
                if registration["method"] == "textDocument/completion":
                    assert registration["registerOptions"]["resolveProvider"] == True
                    assert registration["registerOptions"]["triggerCharacters"] == [
                        ".",
                        "@",
                        "#",
                        "*",
                        " ",
                    ]
                    self.completions_available.set()
                if registration["method"] == "textDocument/definition":
                    self.definition_available.set()
                if registration["method"] == "textDocument/definition":
                    self.definition_available.set()
                if registration["method"] == "textDocument/diagnostic":
                    self.document_diagnostics_available.set()
                if registration["method"] == "textDocument/codeAction":
                    self.code_actions_available.set()
                if registration["method"] == "codeAction/resolve":
                    self.code_actions_resolutions_available.set()                                    
                if registration["method"] == "workspace/executeCommand":
                    if (
                        "java.intellicode.enable"
                        in registration["registerOptions"]["commands"]
                    ):
                        self.intellicode_enable_command_available.set()
            return

        async def lang_status_handler(params):
            if params["type"] == "ServiceReady" and params["message"] == "ServiceReady":
                self.service_ready_event.set()

        async def execute_client_command_handler(params):
            if params["command"] == "_java.reloadBundles.command":
                assert params["arguments"] == []
                return []
            if params["command"] == "java.action.organizeImports.chooseImports":
                self.import_choices.append(params)
                return [params["arguments"][1][0]["candidates"][0]]  ## Always choosing the first import, quick workaround
        
        async def execute_workspace_configuration_handler(params):
            return initialize_params["initializationOptions"]["settings"]

        

        async def do_nothing(params):
            return

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("language/status", lang_status_handler)
        self.server.on_notification("window/logMessage", self.on_log_message_async)
        self.server.on_request(
            "workspace/executeClientCommand", execute_client_command_handler
        )
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("window/workDoneProgress/create", do_nothing)        
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_request("workspace/configuration", execute_workspace_configuration_handler)

        #Starting EclipseJDTLS server process
        await self.server.start()
        # Get initialize params
        initialize_params = self.get_initialize_params(self.repository_root_path)

        # Sending initialize request and waiting for response
        init_response = await self.server.send.initialize(initialize_params)
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" not in init_response["capabilities"]
        assert "executeCommandProvider" not in init_response["capabilities"]

        self.server.notify.initialized({})

        self.server.notify.workspace_did_change_configuration(
            {"settings": initialize_params["initializationOptions"]["settings"]}
        )

        await self.intellicode_enable_command_available.wait()

        java_intellisense_members_path = os.path.join(
            self.dep_folder_path,
            "java_intellisense-members",
        )
        assert os.path.exists(java_intellisense_members_path)
        intellicode_enable_result = await self.server.send.execute_command(
            {
                "command": "java.intellicode.enable",
                "arguments": [True, java_intellisense_members_path],
            }
        )
        await self.service_ready_event.wait()
        # Service ready event received
        yield self

        # Sending shutdown request
        await self.server.send.shutdown()
        # Sending exit notification
        self.server.notify.exit()
        # Killing server process
        await self.server.stop()
        # Killed server process

    def on_log_message(self, x):
        with open(self.log_path, "a") as f:
            f.write(str(x) + "\n\n")  # + '\n' + full_stack()
        return

    async def on_log_message_async(self, x):
        self.on_log_message(x)

    async def complete(
        self,
        completion_params: CompletionParams,
        return_response: bool = False,
        return_empty_on_check_fail=False,
    ) -> Union[List, Tuple[List, Any]]:
        # print("I enter atleast 2")
        response = None
        num_retries = 0
        items=[]
        while response is None or (response["isIncomplete"] and num_retries < 10):
            await self.completions_available.wait()
            response: Union[
                List[CompletionItem], CompletionList, None
            ] = await self.server.send.completion(completion_params)
            num_retries += 1
            items += [item for item in response["items"] if item["kind"] != 14 and all([item["label"]!=i["label"] for i in items])]
            
            # print(response)
        all_method_signatures = items


        if response is None or response["isIncomplete"]:
            if return_response:
                return [], None, response
            else:
                return [], None


        legal_completions = []

        for item in items:
            assert "insertText" in item or "textEdit" in item
            if "insertText" in item:
                legal_completions.append((item["insertText"], item))
            elif "textEdit" in item and "range" in item["textEdit"]:
                new_dot_lineno, new_dot_colno = (
                    completion_params["position"]["line"],
                    completion_params["position"]["character"],
                )
                if all(
                    (
                        item["textEdit"]["range"]["start"]["line"] == new_dot_lineno,
                        item["textEdit"]["range"]["start"]["character"]
                        == new_dot_colno,
                        item["textEdit"]["range"]["start"]["line"]
                        == item["textEdit"]["range"]["end"]["line"],
                        item["textEdit"]["range"]["start"]["character"]
                        == item["textEdit"]["range"]["end"]["character"],
                    )
                ):
                    legal_completions.append((item["textEdit"]["newText"], item))
                else:
                    if return_empty_on_check_fail:
                        legal_completions = []
                        break
            elif "textEdit" in item and "insert" in item["textEdit"]:
                assert False
            else:
                assert False

        completion_set = set(el[0] for el in legal_completions)
        if completion_set.issubset(
            {
                "clone",
                "equals",
                "finalize",
                "getClass",
                "hashCode",
                "notify",
                "notifyAll",
                "toString",
                "wait",
            }
        ):
            legal_completions = []

        legal_completions2 = []
        for completion in legal_completions:
            if completion[0] in completion_set:
                legal_completions2.append(completion)
                completion_set.discard(completion[0])

        if return_response:
            return legal_completions, all_method_signatures, response
        else:
            return legal_completions, all_method_signatures

    async def get_definition(self, l, c, file_path) -> Union[List, Tuple[List, Any]]:
        definitions_params: DefinitionParams = {
            "position": {"line": l, "character": c},
            "textDocument": {"uri": pathlib.Path(file_path).as_uri()},
        }

        response = None
        num_retries = 0
        while response is None:
            await self.definition_available.wait()
            response = await self.server.send.definition(definitions_params)
            num_retries += 1

        if response is None:
            return response
        return response

    async def get_signatures(self, l, c, file_path) -> Union[List, Tuple[List, Any]]:
        signature_params: SignatureHelpParams = {
            "position": {"line": l, "character": c},
            "textDocument": {"uri": pathlib.Path(file_path).as_uri()},
        }

        response = None
        num_retries = 0
        while response is None:
            await self.definition_available.wait()
            response = await self.server.send.signature_help(signature_params)
            num_retries += 1

        if response is None:
            return response
        return response

    async def get_code_actions(
        self, file_path, range, diagnostics
    ) -> Union[List, Tuple[List, Any]]:
        self.import_choices=[]
        index = len(self.current_text)
        l = 0
        c = 0
        idx = 0
        while idx < index:
            if self.current_text[idx] == "\n":
                l += 1
                c = 1
            else:
                c += 1
            idx += 1
        
        code_action_params: CodeActionParams = {
            "textDocument": {"uri": pathlib.Path(file_path).as_uri()},
            "range": {
                "start": { "line": 0, "character": 0 },
                "end" : { "line": l, "character" : c}
                },
            "context": {"diagnostics":diagnostics}
        }
        
        response = None
        num_retries = 0
        while response is None:
            await self.code_actions_available.wait()
            response = await self.server.send.code_action(
                code_action_params
            )
            num_retries += 1

        return response, self.import_choices   ### In case there are import choices we return both choices

    def replace_text_in_scratchpad(self, text):
        self.file_change_id+=1
        self.server.notify.did_change_text_document(
            {
                "textDocument": {
                    "version": self.file_change_id,
                    "uri": pathlib.Path(self.scratchpad_file_path).as_uri(),
                },
                "contentChanges": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": len(self.current_text)},
                        },
                        "text": text,
                    }
                ],
            }
        )
        self.current_text=text





    async def get_completions(
        self,
        file_path,
        index=None
    ):
        if index is None:
            index = len(self.current_text)
        l = 0
        c = 0
        idx = 0
        while idx < index:
            if self.current_text[idx] == "\n":
                l += 1
                c = 1
            else:
                c += 1
            idx += 1
        
        completion_params: CompletionParams = {
            "position": {"line": l, "character": c},
            "textDocument": {"uri": pathlib.Path(file_path).as_uri()},
            "context": {
                "triggerKind": 1
            }
        }

        legal_completions1, signatures1, response1 = await self.complete(
            completion_params,
            return_response=True,
            return_empty_on_check_fail=False,
        )

        return legal_completions1, signatures1, response1