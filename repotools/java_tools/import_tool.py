
import asyncio
import os
import pathlib

class ImportTool:
    def __init__(self,language_server, scratchpad_file_path, running_loop):
        self.language_server=language_server
        self.scratchpad_file_path=scratchpad_file_path
        self.running_loop=running_loop

        
    def _get_diagnotics(self, file_content):
        self.language_server.server.condn_satisfied.clear()
        def condn(x):
            try:
                return x["method"]=="textDocument/publishDiagnostics" and self.scratchpad_file_path in x["params"]["uri"]
            except Exception:
                return False
        
        self.language_server.server.condn=condn

        self.language_server.replace_text_in_scratchpad(file_content)
            
        async def wrapper():
            await self.language_server.server.condn_satisfied.wait()
        
        asyncio.run_coroutine_threadsafe(
            wrapper(),
            self.running_loop,
        ).result()
        relevant_object=[i for i in self.language_server.server.notification_list if condn(i)][-1]
        diagnostics=relevant_object["params"]["diagnostics"]
         
        unresolved={cname:[] for cname in list(set([i["message"].split(" ")[0] for i in diagnostics if "cannot be resolved" in i["message"]]))}
       
        return diagnostics, unresolved
        
    def _get_import_suggestions(self,diagnostics,unresolved):
        range2={
            "start": { "line": 0, "character": 0 },
            "end" : { "line": 0, "character" : len(self.language_server.current_text) }
        }
        try:
            res, choices=asyncio.run_coroutine_threadsafe(
                self.language_server.get_code_actions(self.scratchpad_file_path,range2,diagnostics),
                self.running_loop,
            ).result()
        except Exception as e:
            print("Error Getting imports",e)
            
        candidates=[]
        for choice in choices:
            candidates+=[tuple([f'"{candidate["fullyQualifiedName"]}"' for candidate in choice["arguments"][1][i]["candidates"]]) for i in range(len(choice["arguments"][1]))] ## Get the import candidates
        candidates=list(set(candidates))  ## Get the unique options
        set_of_conflicting_imports=set([candidate[0].split('.')[-1][:-1] for candidate in candidates])
        for candidate in candidates:
            if candidate[0].split('.')[-1][:-1] in unresolved:
                unresolved[candidate[0].split('.')[-1][:-1]]+=list([c1.replace("import ","").replace(";","").replace('"',"").replace("'","") for c1 in candidate])
            else:
                unresolved[candidate[0].split('.')[-1][:-1]]=list([c1.replace("import ","").replace(";","").replace('"',"").replace("'","") for c1 in candidate])
                    
        imports=[]
        for code_action in res:
            if "import" not in code_action["title"].lower():
                continue
            try:
                if "documentChanges" in code_action["command"]["arguments"][0]:                
                    for document_change in code_action["command"]["arguments"][0]["documentChanges"]:
                        if "edits" in document_change:
                            for edit in document_change["edits"]:
                                if "import " in edit["newText"]:
                                    imports.append(edit["newText"])
                else:
                    for document_change in code_action["command"]["arguments"][0]["changes"].values():
                        for edit in document_change:
                            if "import " in edit["newText"]:
                                imports.append(edit["newText"])
            except Exception as e:
                print(e)
        

        self.language_server.replace_text_in_scratchpad("")
        unique_imports=[]
        unique_imports_fq=[]    
        for imp3 in imports:
            imp2=imp3.replace("\n","").strip().split(";")[:-1]
            for imp in imp2:
                if imp.split(".")[-1] in unique_imports:
                    continue
                unique_imports.append(imp.split(".")[-1])
                unique_imports_fq.append(imp)
        
        for import_statement in unique_imports_fq:
            if import_statement.split(".")[-1] in set_of_conflicting_imports:
                continue
            if import_statement.split('.')[-1] in unresolved:
                unresolved[import_statement.split('.')[-1]]+=[import_statement.replace("import ","").replace(";","").replace('"',"").replace("'","")]
            else:
                unresolved[import_statement.split('.')[-1]]=[import_statement.replace("import ","").replace(";","").replace('"',"").replace("'","")]

        return unresolved
 
    def _format_import_suggestions(self,unresolved):
        import_natural_language_sentence=[]
        for unresolved_name, options in unresolved.items():
            fqdns=list(set(options))
            if len(fqdns)==1:
                import_natural_language_sentence.append(f"For {unresolved_name} you can use '{fqdns[0]}'")
            if len(fqdns)>1:                
                joiner="' and '"
                import_natural_language_sentence.append(f"For {unresolved_name} you can choose between '{joiner.join(list(fqdns))}'")
        return "\n".join(import_natural_language_sentence)
        
        
    
    def get_imports(self,file_content):
        
        diagnostics, unresolved=self._get_diagnotics(file_content)
        
        
        import_suggestions = self._get_import_suggestions(diagnostics,unresolved)        
               
        
        return self._format_import_suggestions(import_suggestions)