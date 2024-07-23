import os
import re
import time
import uuid
import atexit
import asyncio
import logging
import pathlib
import threading
import traceback
from typing import Dict, Any
from flask import Flask, request, jsonify
from project_utils.csharp_setup_utils import PROJECT_ROOT_DIR

exp_dir = os.path.join(PROJECT_ROOT_DIR, "temp/csharp/working_repo/StabilityMatrix/")

from .monitors4codegen.multilspy import SyncLanguageServer                # type: ignore
from .monitors4codegen.multilspy.multilspy_config import MultilspyConfig  # type: ignore
from .monitors4codegen.multilspy.multilspy_logger import MultilspyLogger  # type: ignore

app = Flask(__name__)

OLD_CODE_CACHE = ""

logger = MultilspyLogger(logging.DEBUG, logging.FileHandler("multilspy.log"))
config = MultilspyConfig.from_dict({"code_language": 'csharp'})
SLSP = SyncLanguageServer.create(config, logger, exp_dir)
LSP = SLSP.language_server

LOOP = None
LOOP_THREAD = None
CTX = None
OMNISHARP_ISALIVE = False

server_logger = app.logger.getChild("flask_server")
server_logger.setLevel(logging.DEBUG)

# Uncomment to enable server logging
# os.makedirs("./csharp_server_logs", exist_ok=True)
# logfile_path = f"./csharp_server_logs/{str(uuid.uuid4())[:8]}.txt"
# server_logger.info(f"Logging to file: {logfile_path}")
# server_logger.addHandler(logging.FileHandler(logfile_path, mode='w'))

@app.route('/initialize/', methods=["POST"])
def initialize():
    global OLD_CODE_CACHE, LOOP, LOOP_THREAD, CTX, SLSP, OMNISHARP_ISALIVE
    if request.method == "POST":
        json_data = request.json
        filename:str = json_data['filename']  # abs filepath
        if not pathlib.Path(filename).is_file():
            server_logger.error(f"Invalid filepath provided {filename}")
            raise Exception
        server_logger.info(f"Initializing with filename {filename}")
        if OMNISHARP_ISALIVE == True:
            server_logger.info("Omnisharp is already alive")
        else:
            LOOP = asyncio.new_event_loop()
            LOOP_THREAD = threading.Thread(target=LOOP.run_forever, daemon=True)
            LOOP_THREAD.start()
            CTX = SLSP.language_server.start_server()
            asyncio.run_coroutine_threadsafe(CTX.__aenter__(), loop=LOOP).result()
            SLSP.loop = LOOP
            SLSP.language_server.server_started = True
            with SLSP.open_file(filename):
                OLD_CODE_CACHE = SLSP.get_open_file_text(filename)
        server_logger.info(f"Initialized")
        server_logger.debug(f"old code:\n{OLD_CODE_CACHE}")
        OMNISHARP_ISALIVE = True
        return jsonify({"status": "initialized"})
    else:
        server_logger.error(f"{request.method} method invokation in initialize")
        raise Exception

@app.route('/shutdown/', methods=["POST"])
def shutdown():
    global OLD_CODE_CACHE, LOOP, LOOP_THREAD, CTX, SLSP, OMNISHARP_ISALIVE
    if request.method == "POST":
        server_logger.info("Shutdown requested")
        if OMNISHARP_ISALIVE == True:
            server_logger.info("Omnisharp is alive, shutting down")
            asyncio.run_coroutine_threadsafe(CTX.__aexit__(None, None, None), loop=LOOP).result()
            LOOP.call_soon_threadsafe(LOOP.stop)
            LOOP_THREAD.join()
            OMNISHARP_ISALIVE = False
            server_logger.info("Omnisharp shutdown")
        return jsonify({"status": "shutdown"})
    else:
        server_logger.error(f"{request.method} method invokation in shutdown")
        raise Exception

@app.route('/reset/', methods=["POST"])
def reset():
    if request.method == "POST":
        json_data = request.json
        filename:str = json_data['filename']
        if not pathlib.Path(filename).is_file():
            server_logger.error(f"Invalid filepath provided {filename}")
            raise Exception
        with SLSP.open_file(filename):
            SLSP.update_open_file(filename, OLD_CODE_CACHE)
        server_logger.info(f"reset for {filename}")
        server_logger.debug(f"old code:\n{OLD_CODE_CACHE}")
        return jsonify({"status": "reset"})
    else:
        server_logger.error(f"{request.method} method invokation in reset")
        raise Exception

@app.route('/get_signature_help/', methods=["POST"])
def get_signature_help():
    NUM_RETRIES = 3
    if request.method == 'POST':
        json_data = request.json
        filename = json_data['filename']  # abs filepath
        if not pathlib.Path(filename).is_file():
            server_logger.error(f"Invalid filepath provided {filename}")
            return jsonify([])
        server_logger.info(f"getSignatureHelp for {filename}")
        code = json_data['code']
        lineno = json_data['lineno']
        colno  = json_data['colno']
        server_logger.debug(f"Code:\n{code}")
        server_logger.debug(f"Lineno: {lineno}\t Colno: {colno}")
        res = None
        try:
            for i in range(NUM_RETRIES):
                server_logger.debug(f"Attempt {i+1}/{NUM_RETRIES}")
                with SLSP.open_file(filename):
                    old_code = SLSP.get_open_file_text(filename)
                    server_logger.debug(f"Old code:\n{old_code}")
                    SLSP.update_open_file(filename, code)
                    res = SLSP.request_signature_help(filename, lineno, colno)
                    SLSP.update_open_file(filename, old_code)
                if res is None:
                    server_logger.info("None response from get_signature_help")
                    continue
                if len(res) == 0:
                    server_logger.info("No signatures found")
                    continue
                server_logger.info(f"{len(res)} signatures found")
                server_logger.info("get_signature_help concluded")
                return jsonify(res)
            server_logger.warning("No signatures found, returning empty list")
            return jsonify([])
        except Exception as e:
            server_logger.error("Error in get_signature_help")
            traceback.print_exc()
            raise e
    else:
        server_logger.error(f"{request.method} method invokation in get_signature_help")
        raise Exception


@app.route('/get_completions/', methods=["POST"])
def get_completions():
    NUM_RETRIES = 3
    if request.method == 'POST':
        json_data = request.json
        filename = json_data['filename']  # abs filepath
        if not pathlib.Path(filename).is_file():
            server_logger.error(f"Invalid filepath provided {filename}")
            raise Exception
        server_logger.info(f"getCompletions for {filename}")
        code = json_data['code']
        lineno = json_data['lineno']
        colno  = json_data['colno']
        allow_incomplete = False
        if 'allow_incomplete' in json_data:
            allow_incomplete = json_data['allow_incomplete']
        server_logger.debug(f"Code:\n{code}")
        server_logger.debug(f"Lineno: {lineno}\t Colno: {colno}")
        try:
            for i in range(NUM_RETRIES):
                server_logger.debug(f"Attempt {i+1}/{NUM_RETRIES}")
                with SLSP.open_file(filename):
                    old_code = SLSP.get_open_file_text(filename)
                    server_logger.debug(f"Old code:\n{old_code}")
                    SLSP.update_open_file(filename, code)
                    res = SLSP.request_completions(filename, lineno, colno, allow_incomplete=allow_incomplete)
                    SLSP.update_open_file(filename, old_code)
                server_logger.info("get_completions concluded")
                if res is None:
                    server_logger.info(f"None response from get_completions")
                    continue
                if len(res) == 0:
                    server_logger.info(f"No completions found")
                    continue
                server_logger.info(f"{len(res)} completions found")
                server_logger.info("get_completions concluded")
                return jsonify(res)
            server_logger.warning("No completions found, returning empty list")
            return jsonify([])
        except Exception as e:
            server_logger.error("Error in get_completions")
            traceback.print_exc()
        return jsonify([])
    else:
        server_logger.error(f"{request.method} method invokation in get_completions")
        raise Exception

@app.route('/resolve_completions/', methods=["POST"])
def resolve_completions():
    if request.method == 'POST':
        server_logger.info(f"resolve_completions invoked")
        json_data = request.json
        completions = json_data['completions']
        server_logger.info(f"Resolving {len(completions)} completions")
        resolved_completions = []
        for comp_item in completions:
            try:
                r = SLSP.resolve_completion(comp_item)
                if r is None:
                    server_logger.info("None response from resolve_completion")
                    continue
                resolved_completions.append(r)
            except Exception as e:
                server_logger.error(f"Error in resolve_completions: {e}")
                traceback.print_exc()
        return jsonify(resolved_completions)
    else:
        server_logger.error(f"{request.method} method invokation in get_completions")
        raise Exception

@app.route('/get_imports/', methods=["POST"])
def get_imports():
    NUM_RETRIES = 3
    METHOD_NAME = "textDocument/publishDiagnostics"
    if request.method == 'POST':
        # Ghost filepath is in the exp dir
        # true filepath is in the copy dir
        json_data = request.json
        filename = json_data['filename']  # abs filepath
        server_logger.info(f"getImports for {filename}")
        if not pathlib.Path(filename).is_file():
            server_logger.error(f"Invalid filepath provided {filename}")
            raise Exception
        code = json_data['code']
        server_logger.debug(f"Code:\n{code}")
        file_uri = pathlib.Path(filename).as_uri()
        async def diagnostics_callback(payload: Dict[str, Any]):
            """ Callback function that marks the diagnostics as received """
            if LSP.server.notification_semaphores.get(file_uri):
                # Set semaphore here, so that the main thread can continue
                LSP.server.set_notification_semaphore(file_uri)
            else:
                # print("Missing semaphore for file", file_uri)
                # TODO: add a warning for missing semaphore
                pass
        try:
            diagnostics = []
            with SLSP.open_file(filename):
                old_code = SLSP.get_open_file_text(filename)
                SLSP.update_open_file(filename, "")
                LSP.server.on_notification(METHOD_NAME, diagnostics_callback)

                for i in range(NUM_RETRIES):
                    try:
                        LSP.server.notification_list.clear()   # WARNING: Dangerous for multiple requests
                        server_logger.debug(f"Attempt {i+1}/{NUM_RETRIES}")
                        LSP.server.add_notification_semaphore(file_uri)
                        SLSP.update_open_file(filename, code)
                        diagnostics = get_diagnostics(file_uri)
                        break
                    except Exception as e:
                        server_logger.error(f"Error in get_diagnostics: {e}")
                    finally:
                        LSP.server.remove_notification_semaphore(file_uri)
                        SLSP.update_open_file(filename, "")
            if len(diagnostics) == 0:
                server_logger.error("No diagnostics received")
                return jsonify([])
            with SLSP.open_file(filename):
                actions_list = []
                for i in range(NUM_RETRIES):
                    try:
                        server_logger.debug(f"Attempt {i+1}/{NUM_RETRIES}")
                        actions_list = get_import_code_actions(filename, code, diagnostics)
                        break
                    except Exception as e:
                        server_logger.error(f"Error in get_import_code_actions: {e}")
                    finally:
                        SLSP.update_open_file(filename, old_code)
            if len(actions_list) == 0:
                server_logger.info("No actions found")
                return jsonify([])
            return jsonify({
                "actions": actions_list,
                "diagnostics": diagnostics,
                # "payloads": relevant_payloads
            })
        except Exception as e:
            server_logger.error("Error in get_imports")
            traceback.print_exc()
            return jsonify([])
    else:
        server_logger.error(f"{request.method} method invokation in get_imports")
        raise Exception

def get_diagnostics(file_uri:str):
    METHOD_NAME = "textDocument/publishDiagnostics"
    async def wrapper():
        """ Wait for the diagnostics to be received """
        await LSP.server.wait_for_notification(file_uri)
    asyncio.run_coroutine_threadsafe(
        wrapper(),
        LOOP
    )
    time.sleep(2)
    relevant_payloads = []
    for payload in LSP.server.notification_list:
        if payload.get("method") == METHOD_NAME:
            if payload['params']["uri"] == file_uri:
                relevant_payloads.append(payload)
    if len(relevant_payloads) == 0:
        server_logger.warning(f"No relevant payloads received for {file_uri}")
        raise Exception(f"No relevant payloads received for {file_uri}")
    server_logger.info(f"{len(relevant_payloads)} relevant payloads found")
    for rp in relevant_payloads:
        server_logger.debug(rp['params']['diagnostics'])
    diagnostics = relevant_payloads[-1]["params"]["diagnostics"]
    if len(diagnostics) == 0:
        server_logger.warning(f"No diagnostics found in the last payload")
        raise Exception("No diagnostics found.")
    return diagnostics

diagnostic_pattern = re.compile("The type or namespace name '([a-zA-Z_][a-zA-Z_0-9]*)' could not be found")
def get_import_code_actions(filename, code, diagnostics):
    symbol_name2diagnostics = {}
    for i, d in enumerate(diagnostics):
        if 'message' not in d:
            continue
        l = diagnostic_pattern.findall(d['message'])
        if len(l) == 0:
            continue
        symbol_name = l[0]
        if symbol_name in symbol_name2diagnostics:
            continue
        symbol_name2diagnostics[symbol_name] = i
    actions_list = []
    with SLSP.open_file(filename):
        old_code = SLSP.get_open_file_text(filename)
        SLSP.update_open_file(filename, code)
        for symbol_name, i in symbol_name2diagnostics.items():
            d = diagnostics[i]
            server_logger.info(f"Symbol name: {symbol_name}, index: {i}")
            start = (d['range']['start']['line'], d['range']['start']['character'])
            end = (d['range']['end']['line'], d['range']['end']['character'])
            try:
                res = SLSP.get_code_actions(filename, start, end, [diagnostics[i]])
                if res is None:
                    server_logger.info(f"None output from code actions for {symbol_name}")
                    continue
                res_filter = list(filter(
                    lambda x: "using" in x['title'] and x['title'].endswith(';'),
                    res))
                import_suggestions_list = [ r['title'] for r in res_filter]
                server_logger.info(f"{len(res_filter)} import suggestions found.")
                actions_list.append((symbol_name, import_suggestions_list))
            except Exception as e:
                server_logger.error(f"Error in get_code_actions: {symbol_name}, skipping")

        SLSP.update_open_file(filename, old_code)
    if len(actions_list) == 0:
        server_logger.warning("No actions found")
        raise Exception("No actions found")
    return actions_list

def cleanup():
    global LOOP, LOOP_THREAD, CTX, OMNISHARP_ISALIVE
    server_logger.info("Shutting down the server")
    if OMNISHARP_ISALIVE == True:
        server_logger.info("Omnisharp is alive, shutting down")
        asyncio.run_coroutine_threadsafe(CTX.__aexit__(None, None, None), loop=LOOP).result()
        LOOP.call_soon_threadsafe(LOOP.stop)
        LOOP_THREAD.join()
        server_logger.info("Omnisharp shutdown")

atexit.register(cleanup)

if __name__ == '__main__':
    app.run(debug=True)

