import asyncio
import time

import numpy as np
from repotools.java_tools.EclipseJDTLS import EclipseJDTLS

def create_batches(input_list, batch_size):
    batches = []
    for i in range(0, len(input_list), batch_size):
        batch = input_list[i:i + batch_size]
        batches.append(batch)
    return batches


class SignatureTool:
    def __init__(self, language_server, abs_file_path, abs_repo_root_dir, running_loop):
        self.language_server : EclipseJDTLS = language_server
        self.abs_file_path = abs_file_path
        self.abs_repo_root_dir = abs_repo_root_dir
        self.running_loop = running_loop
        
    def get_signature(self,class_name, method_name, static=False, protected=False, abstract=False):

        if static:
            modified_class_name_or_object_name = "\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n"+";\n" + class_name + "." + method_name + "("
        elif protected:
            modified_class_name_or_object_name = "public class a extends " + class_name + "{\npublic a(){\nsuper." + method_name + "("
        elif abstract:
            modified_class_name_or_object_name = "public class a{\npublic class b extends " + class_name + ";\npublic a(){\nb c;\nc."+method_name+ "("
        else:
            modified_class_name_or_object_name = (
                "\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n" + class_name + " a;\na." + method_name+ "("
            )
        self.language_server.replace_text_in_scratchpad(modified_class_name_or_object_name)
        
        (
            completions,
            signatures,
            response,
        ) = asyncio.run_coroutine_threadsafe(
            self.language_server.get_completions(
                self.abs_file_path,
                index=len(self.language_server.current_text)-1
            ),self.running_loop
        ).result()
        self.language_server.replace_text_in_scratchpad("")
        
        return [sig["detail"] for sig in signatures if "detail" in sig]

    def get_fqdns(self,class_name):
        self.language_server.replace_text_in_scratchpad("\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n"+ class_name)
        (
            completions,
            signatures,
            response,
        ) = asyncio.run_coroutine_threadsafe(
            self.language_server.get_completions(
                self.abs_file_path,
                index=len(self.language_server.current_text)-1
            ),
            self.running_loop,
        ).result()

        self.language_server.replace_text_in_scratchpad("")

        final_fqdns=[]
        for sig in signatures:
            if "detail" in sig:
                if "(" in sig["detail"]:
                    fqdn=".".join(sig["detail"].split("(")[0].split(".")[:-1])
                    if fqdn.endswith("."+class_name):
                        final_fqdns.append(fqdn)
                else:
                    if sig["detail"].endswith("."+class_name) or sig["detail"]==class_name:
                        final_fqdns.append(sig["detail"])
                    
        return list(set(final_fqdns))

    def get_signature_formatted(self, class_name, method_name):
        all_sigs=[]
        fqdns=self.get_fqdns(class_name)
        for fqdn in fqdns:
            signatures1 = self.get_signature(
                fqdn, method_name=method_name, static=False
            )
            signatures2 = self.get_signature(
                fqdn, method_name=method_name, static=True
            )

            signatures3 = self.get_signature(
                fqdn, method_name=method_name, protected=True
            )        

            

            signatures4 = self.get_signature(
                fqdn, method_name=method_name, abstract=True
            )
            
            signatures4 = [
                "abstract "+signature for signature in signatures4 if (signature not in signatures1) and (signature not in signatures2) and (signature not in signatures3)
            ]                  

            signatures3 = [
                "protected "+signature for signature in signatures3 if (signature not in signatures1) and (signature not in signatures2)
            ]                

            signatures1 = [
                "public "+signature for signature in signatures1
            ]
            
            signatures2 = [
                "static "+signature for signature in signatures2
            ]

                
            signatures = signatures1 + signatures2 + signatures3 + signatures4
            signatures = [
                signature for signature in signatures if ((method_name+"(") in signature or (method_name+" :") in signature)
            ]
            signatures = [
                signature.split(":")[1] + " " + signature.split(":")[0]
                for signature in signatures
            ]        
            all_sigs+=signatures
        return str(all_sigs)
