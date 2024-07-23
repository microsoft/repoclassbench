# C# Tools Usage instructions

## Setup
The tools api for C# makes use of the `Omnisharp` Language server, but we do not use it directly. Instead we use an existing repo called `multilspy` (actually a fork of the original repo) to interface with the language server. All the setup should happen automatically without requiring manual intervention. However, in case you want to run the setup for the dotnet SDK and multilspy manually, use the following command:

```bash
# The force flag (optional) is to ensure that a clean copy of multilspy is setup
python project_utils/csharp_setup_utils.py --force
```

Effects:
- The expected dotnet SDK should have been installed in `external/csharp/dotnet_dir`
- A symlink to the multilspy folder should also have been created in the `csharp_tools` directory.

## Troubleshooting

#### `flask_server.py` code hangs up when `initialize` request is sent from `omnisharp_api.py`

- This is most often due to a line in the `external/csharp/monitors4codegen/src/monitors4codegen/multilspy/language_servers/omnisharp/omnisharp.py` file.
- The file in question is responsible for instantiating the `Omnisharp` server, by compiling the necessary flags and building the corresponding command required to spawn a process.
- This process can fail, either due to the built command having encoding issues (some chars might not be escaped correctly) or missing env variables (Both `PATH` and `DOTNET_ROOT` need to be set in order for the command to work and Omnisharp to be initialized)
- Each of these steps are performed by code in the `project_utils/csharp_setup_utils.py` file.

#### LSP outputs are empty, or calls timout

- A timeout of 100 seconds is set to ensure that the server has enough time to compute results for the provided request. Try increasing it if necessary.
- If increasing the timeout has no effect on the results, try to clean and rebuild the repo in the `temp/csharp/working_repo`
- Omnisharp requires the repo to be built in order to provide suggestions, especially for library functions and such.


#### `get_related_snippets` takes too long to compute or crashes outright

- This tool call requires computing embeddings for a large number of candidate code (sections).
- If you don't have a GPU you might have to modify the code appropriately to run it on a CPU
- If you have a GPU, but are running out of GPU memory, try reducing the `BATCH_SIZE` parameter in `csharp_tools/Scorer/unixcoder.py` file. (Hint: A batch size of 8 works well for a GPU with 6GiB of memory. Tune accordingly)
- `get_related_snippets` stores caches embedding results in `csharp_tools/Scorer/`. So the time required to compute embeddings is a one-time cost. Recomputing the caches is necessary if the list of files (whose embeddings are being computed) changes

#### Debugging gunicorn server
- The code in `csharp_tools/flask_server.py` is responsible for communicating with Omnisharp and returning results back to the main code, and is meant to be run as a hosted server. We use gunicorn for this purpose.
- For ease of use, the provided code spawns a gunicorn server on its own as a child process. But as a result, the server logs are not accesible to the user.
- To fix this, uncomment the following lines in `flask_server.py`

```python
# os.makedirs("./csharp_server_logs", exist_ok=True)
# logfile_path = f"./csharp_server_logs/{str(uuid.uuid4())[:8]}.txt"
# server_logger.info(f"Logging to file: {logfile_path}")
# server_logger.addHandler(logging.FileHandler(logfile_path, mode='w'))
```

- This will save the server logs to files in csharp_server_logs/<some_id>.txt