import os
import sys
import asyncio
import logging
import pathlib
import threading
from repotools.csharp_tools import CSharpTools
from repotools.csharp_tools.omnisharp_api import OmniSharpApi
from project_utils.csharp_setup_utils import PROJECT_ROOT_DIR

TOOLS_DIR = os.path.join(PROJECT_ROOT_DIR, "repotools/csharp_tools")
MULTILSPY_REPO_DIR = os.path.join(PROJECT_ROOT_DIR, "external/csharp/monitors4codegen")
SYMLINK_PATH = os.path.join(TOOLS_DIR, "monitors4codegen")
EXP_DIR = os.path.join(PROJECT_ROOT_DIR, "temp/csharp/working_repo/StabilityMatrix")

test_logger = logging.getLogger("test_logger")
test_logger.setLevel(logging.INFO)

class TestToolsCSharp:


    # def test_csharp_tools_install(self):
    #     """  Test correct multilspy installation """
    #     assert pathlib.Path(MULTILSPY_REPO_DIR).exists(), "multilspy doesn't seem to be installed. Run setup.py first"
    #     assert pathlib.Path(SYMLINK_PATH).is_symlink(), "Link to external multilspy library missing/broken"
    #     assert pathlib.Path(SYMLINK_PATH).resolve() == pathlib.Path(os.path.join(MULTILSPY_REPO_DIR, 'src/monitors4codegen')), \
    #             "monitors4codegen Link pointing to wrong target"
    #     import_path = os.path.join(MULTILSPY_REPO_DIR, "src")
    #     filename = os.path.join(EXP_DIR, "StabilityMatrix.Core/Updater/UpdateStatusChangedEventArgs.cs")
    #     sys.path.append(import_path)
    #     if DOTNET_ROOT_DIR not in os.environ['PATH']:
    #         os.environ['PATH'] += os.pathsep + DOTNET_ROOT_DIR
    #     if "DOTNET_ROOT" not in os.environ:
    #         os.environ['DOTNET_ROOT'] = DOTNET_ROOT_DIR
    #     try:
    #         from monitors4codegen.multilspy import SyncLanguageServer               # type: ignore
    #         from monitors4codegen.multilspy.multilspy_config import MultilspyConfig # type: ignore
    #         from monitors4codegen.multilspy.multilspy_logger import MultilspyLogger # type: ignore

    #         logger = MultilspyLogger(logging.INFO, logging.FileHandler("multilspy.log"))
    #         config = MultilspyConfig.from_dict({"code_language": 'csharp'})
    #         SLSP = SyncLanguageServer.create(config, logger, EXP_DIR)

    #         LOOP = asyncio.new_event_loop()
    #         LOOP_THREAD = threading.Thread(target=LOOP.run_forever, daemon=True)
    #         LOOP_THREAD.start()
    #         CTX = SLSP.language_server.start_server()
    #         asyncio.run_coroutine_threadsafe(CTX.__aenter__(), loop=LOOP).result()
    #         SLSP.loop = LOOP
    #         SLSP.language_server.server_started = True
    #         with SLSP.open_file(filename):
    #             CODE_CACHE = SLSP.get_open_file_text(filename)
    #         logger.debug(CODE_CACHE)
    #     except Exception as e:
    #         assert False, str(e)
    #     finally:
    #         # Find an remove modification to sys.path var
    #         idx = sys.path.index(import_path)
    #         sys.path.pop(idx)

    def test_get_imports(self):
        """ Test get_imports() api
        Necessary to spawn flask_server prior to running this test"""
        filename = os.path.join(EXP_DIR, "StabilityMatrix.Core/Updater/UpdateStatusChangedEventArgs.cs")
        api = CSharpTools(EXP_DIR, "", filename)
        try:
            import_suggestions = api.get_imports(
    """
    namespace StabilityMatrix.Core.Updater;
    public class UpdateStatusChangedEventArgs : EventArgs
    {
        public UpdateInfo? LatestUpdate { get; init; }
        public IReadOnlyDictionary<UpdateChannel, UpdateInfo> UpdateChannels { get; init; } =
            new Dictionary<UpdateChannel, UpdateInfo>();
        public DateTimeOffset CheckedAt { get; init; } = DateTimeOffset.UtcNow;
    }
    """     )
            test_logger.info(import_suggestions)
        except Exception as e:
            assert False, str(e)
        finally:
            pass
            # api.shutdown()

    def test_get_signature(self):
        """ Test get_signature() api
        Necessary to spawn flask_server prior to running this test """
        filename = os.path.join(EXP_DIR, "StabilityMatrix.Core/Database/LiteDbContext.cs")
        api = CSharpTools(EXP_DIR, "", filename)
        try:
            outputs = api.get_signature("GenerationParameters", "Parse")
        except Exception as e:
            assert False, str(e)
        finally:
            # api.shutdown()
            pass
        assert outputs[1] is None, outputs[1]
        test_logger.info(outputs[0])

    def test_get_class_info(self):
        """ Test get_class_info() api
        Necessary to spawn flask_server prior to running this test """
        filename = os.path.join(EXP_DIR, "StabilityMatrix.Core/Database/LiteDbContext.cs")
        sketchy_desc = "The public partial record GenerationParameters, located in the StabilityMatrix.Core.Models namespace, \
            represents the parameters for generating a stability matrix. This class is JSON serializable. It includes several \
            methods for parsing and handling data. The 'TryParse' method attempts to parse a string into a GenerationParameters \
            object, returning false if the string is null, whitespace, or cannot be parsed. The 'Parse' method also parses a \
            string into a GenerationParameters object, but throws a ValidationException if the string cannot be parsed. The \
            'ParseLine' method parses a string of fields into a dictionary, with fields separated by commas and key-value pairs \
            separated by colons. The 'UnquoteValue' method removes quotes from a quoted field, if present. The 'GetComfySamplers' \
            method converts the current Sampler string into a ComfySampler and ComfyScheduler, if possible. The 'GetSample' \
            method returns a sample GenerationParameters object for UI preview. Lastly, the 'ParametersFieldsRegex' method is \
            a generated regex method for parsing parameters fields.\""
        api = CSharpTools(EXP_DIR, "", filename)
        try:
            outputs = api.get_class_info("GenerationParameters", sketchy_desc)
        except Exception as e:
            assert False, str(e)
        finally:
            # api.shutdown()
            pass
        assert outputs[1]
        test_logger.info('\n'+outputs[0])


    # def test_get_related_code(self):
    #     """ Test get_related_code() api """


    def test_get_related_snippets(self):
        """ Test RAG system
        Necessary to spawn flask_server prior to running this test

        May fail due to GPU out of memory, tweak batch size in unixcoder.py file
        """
        filename = os.path.join(EXP_DIR, "StabilityMatrix.Core/Database/LiteDbContext.cs")
        sketchy_desc = "The public partial record GenerationParameters, located in the StabilityMatrix.Core.Models namespace, \
            represents the parameters for generating a stability matrix. This class is JSON serializable. It includes several \
            methods for parsing and handling data. The 'TryParse' method attempts to parse a string into a GenerationParameters \
            object, returning false if the string is null, whitespace, or cannot be parsed. The 'Parse' method also parses a \
            string into a GenerationParameters object, but throws a ValidationException if the string cannot be parsed. The \
            'ParseLine' method parses a string of fields into a dictionary, with fields separated by commas and key-value pairs \
            separated by colons. The 'UnquoteValue' method removes quotes from a quoted field, if present. The 'GetComfySamplers' \
            method converts the current Sampler string into a ComfySampler and ComfyScheduler, if possible. The 'GetSample' \
            method returns a sample GenerationParameters object for UI preview. Lastly, the 'ParametersFieldsRegex' method is \
            a generated regex method for parsing parameters fields.\""
        api = CSharpTools(EXP_DIR, "", filename)
        try:
            outputs, scores = api.get_related_snippets(sketchy_desc)
        except Exception as e:
            assert False, str(e)
        finally:
            # api.shutdown()
            pass
        test_logger.info('\n'+'\n####<------->\n'.join(outputs))
