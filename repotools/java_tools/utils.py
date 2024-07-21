import os
import pathlib
import threading
import asyncio


def notify_lsp_server_text_change(
    lsp, text, line1, col1, line2, col2, repo_root, class_file_path, file_change_id
):
    """Notify the LSP server that the text at the given line and column has changed."""
    lsp.server.notify.did_change_text_document(
        {
            "textDocument": {
                "version": file_change_id,
                "uri": pathlib.Path(os.path.join(repo_root, class_file_path)).as_uri(),
            },
            "contentChanges": [
                {
                    "range": {
                        "start": {"line": line1, "character": col1},
                        "end": {"line": line2, "character": col2},
                    },
                    "text": text,
                }
            ],
        }
    )


def notify_lsp_server_document_close(lsp, repo_root, class_file_path):
    """Notify the LSP server that the document has been closed."""
    lsp.server.notify.did_close_text_document(
        {
            "textDocument": {
                "uri": pathlib.Path(os.path.join(repo_root, class_file_path)).as_uri()
            }
        }
    )


async def lsp_runner(
    lsp,
    server_started_arg: threading.Event,
    exit_event_arg: asyncio.Event,
    server_stopped_arg: threading.Event,
):
    try:
        # Starting server in asyncio loop and waiting for server start
        async with lsp.start_server() as server:
            # Started server. Waking main thread.
            server_started_arg.set()
            # Asyncio loop waiting for exit event
            await exit_event_arg.wait()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            if server:
                await server.__aexit__(None, None, None)
                print("Server stopped")
        except Exception as e:
            print(f"Error while stopping the server: {e}")
        finally:
            server_stopped_arg.set()
