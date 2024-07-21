# C# Tools Usage instructions

## Setup
The tools api for C# makes use of the `Omnisharp` Language server, but we do not use it directly. Instead we use an existing repo called `multilspy` (actually a fork of the original repo) to interface with the language server. In order to set this up, a setup script is provided.

- First run the following command.

      # The force flag (optional) is to ensure that a clean copy of multilspy is setup
      python setup.py --force

   The `monitors4codegen` directory should've been created in the `external/csharp` directory. Additionally the `moniters4codegen` symlink should also have been created in the `csharp_tools` directory.

- Next, use `gunicorn` to setup the server

      gunicorn --timeout 100 repotools.csharp_tools.flask_server:app


## Troubleshooting

#### `flask_server.py` code hangs up when `initialize` request is sent from `omnisharp_api.py`

- This is most often due to the following line in the `external/csharp/monitors4codegen/src/monitors4codegen/multilspy/language_servers/omnisharp/omnisharp.py` file.
- The file in question is responsible for instantiating the `Omnisharp` server, by compiling the necessary flags and building the corresponding command required to spawn a process.
- This process can fail, either due to the built command having encoding issues (some chars might not be escaped correctly) or missing env variables (Both `PATH` and `DOTNET_ROOT` need to be set in order for the command to work and Omnisharp to be initialized)

#### LSP outputs are empty, or calls timout

- A timeout of 100 seconds is set to ensure that the server has enough time to compute results for the provided request. Try increasing it if necessary.
- If increasing the timeout has no effect on the results, try to clean and rebuild the repo in the `temp/csharp/working_repo`
- Omnisharp requires the repo to be built in order to provide suggestions, especially for library functions and such.
