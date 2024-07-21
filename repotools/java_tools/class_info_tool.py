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


class ClassInfoTool:
    def __init__(self, language_server, abs_file_path, abs_repo_root_dir, running_loop):
        self.language_server : EclipseJDTLS = language_server
        self.abs_file_path = abs_file_path
        self.abs_repo_root_dir = abs_repo_root_dir
        self.running_loop = running_loop
        
    def get_member(self,class_name, static=False, protected=False, abstract=False, abstract_control=False, member_name=""):
        if static:
            modified_class_name_or_object_name = "\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n"+";\n" + class_name + "." + member_name
        elif protected:
            modified_class_name_or_object_name = "public class a extends " + class_name + "{\npublic a(){\nsuper." + member_name
        elif abstract:
            modified_class_name_or_object_name = "public class a{\npublic class b extends " + class_name + ";\npublic a(){\nb c;\nc." + member_name
        elif abstract_control:        
            modified_class_name_or_object_name = "public class a{\n" + member_name
        else:
            modified_class_name_or_object_name = "\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\n" + class_name + " a;\na." + member_name

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
        
        return_value = []
        for completion in completions:
            try:
                if "(" in completion[1]["label"]:
                    label=completion[1]["label"]
                    fqdn_label=label
                    fqdn_params=completion[1]["data"]["signature"].split("(")[1].split(")")[0].split(";")[:-1]
                    corrected_fqdn_params=[]
                    for param in fqdn_params:
                        if ">" in param and "<" not in param:
                            corrected_fqdn_params[-1]+=param
                        else:
                            corrected_fqdn_params.append(param)
                    fqdn_params=corrected_fqdn_params
                    for i,fqdn_param in enumerate(fqdn_params):                    
                        if len(fqdn_param)>0 and fqdn_param[0]=="L":
                            try:
                                fqdn_label=fqdn_label.replace("("+completion[1]["label"].split("(")[1].split(")")[0].split(",")[i].split(" ")[0]+" ","("+fqdn_param.replace(";","")[1:]+" ")
                                fqdn_label=fqdn_label.replace(", "+completion[1]["label"].split("(")[1].split(")")[0].split(",")[i].split(" ")[1]+" ",", "+fqdn_param.replace(";","")[1:]+" ")
                            except:
                                pass
                    return_value.append(fqdn_label + "  (method)")
                else:
                    return_value.append(completion[1]["detail"] + " (variable)")
            except Exception as e:
                print(e)
                
        return return_value

    def get_class_info(self, class_or_object_name):
        im = self.get_member(class_or_object_name, static=False)
        default_list = [
            "equals(",
            "getClass(",
            "hashCode(",
            "notify(",
            "notifyAll(",
            "toString(",
            "wait(",
        ]
        instance_members = [
            member
            for member in im
            if all([v not in member for v in default_list])
        ]
        sm = self.get_member(class_or_object_name, static=True)
        static_members = [
            member
            for member in sm
            if all([v not in member for v in default_list])
        ]

        pm = self.get_member(class_or_object_name, protected=True)
        protected_members = [
            member
            for member in pm
            if all([v not in member for v in default_list]) and all([v not in member for v in instance_members])
        ]
        
        

        am = self.get_member(class_or_object_name, abstract=True)
        am_control = self.get_member(class_or_object_name, abstract_control=True)            
        abstract_members = [member
            for member in am
            if (all([v not in member for v in default_list]) and all([v not in member for v in instance_members]) and (member not in am_control) and all([v not in member for v in protected_members]))
        ]


        abstract_members=[member.replace("(method", " (abstract method - SUBCLASSES MUST DEFINE") for member in abstract_members]
        protected_members=[member.replace("(method", " (protected method - ONLY SUBCLASSES CAN USE").replace(
                "(variable", " (protected variable - ONLY SUBCLASSES CAN USE"
            ) for member in protected_members]
        static_members=[member.replace("(method", " (static method").replace(
                "(variable", " (static variable"
            ) for member in static_members]
        instance_members=[member.replace("(method", " (instance method").replace(
                "(variable", " (instance variable"
            ) for member in instance_members]
        instance_members=instance_members+protected_members+abstract_members
        default_methods=["clone()", "equals(Object obj)", "finalize()", "getClass()", "hashCode()", "notify()", "notifyAll()", "toString()", "wait()", "wait(long timeout)", "wait(long timeout, int nanos)","class : Class"]
        static_members=list(filter(lambda x: all([default_method not in x for default_method in default_methods]),static_members))
        instance_members=list(filter(lambda x: all([default_method not in x for default_method in default_methods]),instance_members))
        
        return static_members, list(reversed(instance_members))
 
 
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

    def get_constructor(self,class_name):
        self.language_server.replace_text_in_scratchpad("\n\n\npublic class Scratchpad{\npublic void m1(){\n\n\n\nnew " + class_name + "(")
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
        return [sig["detail"] for sig in signatures if (("detail" in sig) and (class_name.split(".")[-1]+"(" in sig["detail"]))]

    def get_class_info_formatted(self, class_name, ranking_query_string=None,embedding_model=None):
        fqdns=self.get_fqdns(class_name)
        class_infos=[]
        for fqdn in fqdns:
            res_const = self.get_constructor(fqdn)                            
            all_static_members, all_instance_members = self.get_class_info(fqdn)
            static_scores=[]
            instance_scores=[]
            if ranking_query_string!=None:
                if len(all_static_members)>0:
                    static_scores=embedding_model.get_score(ranking_query_string, all_static_members)
                    sort_idx=np.argsort(static_scores)[::-1]
                    all_static_members=[all_static_members[i] for i in sort_idx]
                if len(all_instance_members)>0:
                    instance_scores=embedding_model.get_score(ranking_query_string, all_instance_members)
                    sort_idx=np.argsort(instance_scores)[::-1]
                    all_instance_members=[all_instance_members[i] for i in sort_idx]
            else:
                static_scores=[1 for _ in all_static_members]
                instance_scores=[1 for _ in all_instance_members]
            
            if len(all_static_members)+len(all_instance_members)>0:
                natural_language_results=[]            
                if len(all_static_members) + len(all_instance_members) > 10:
                    i_size=0
                    s_size=0
                    for _ in range(10):
                        if len(static_scores)>0 and (len(instance_scores)==0 or static_scores[0]>instance_scores[0]):
                            static_scores=static_scores[1:]
                            s_size+=1
                        elif len(instance_scores)>0:
                            instance_scores=instance_scores[1:]
                            i_size+=1
                        else:
                            break
                    
                    static_members_batches=create_batches(all_static_members, s_size) if s_size>0 else [[]]
                    instance_members_batches=create_batches(all_instance_members, i_size) if i_size>0 else [[]]
                    if len(static_members_batches)>len(instance_members_batches):
                        instance_members_batches.extend([[] for _ in range((len(static_members_batches)-len(instance_members_batches)))])
                    if len(static_members_batches)<len(instance_members_batches):
                        static_members_batches.extend([[] for _ in range((len(instance_members_batches)-len(static_members_batches)))])
                
                    for static_members,instance_members in zip(static_members_batches,instance_members_batches):
                        natural_language_results.append(
                            f"For class {fqdn}:\n\n"+
                            ((f"Constructor signatures: \n"
                            + "\n".join(res_const)) if len(res_const)>0 else "")                            
                            +((f"\nThe class {fqdn} has the following static members: \n-"
                            + "\n-".join(static_members)) if len(static_members)>0 else "")
                            + "\n\n"+
                            ((f"Objects of the class {fqdn} have the following instance members: \n-"
                            + "\n-".join(instance_members)) if len(instance_members)>0 else "")
                        )
                    
                    class_infos.append(natural_language_results[0])
                else:
                    static_members=all_static_members
                    instance_members=all_instance_members
                    class_infos.append(f"For class {fqdn}:\n"+((f"Constructor of class {fqdn} has signature: \n"+ "\n".join(res_const)) if len(res_const)>0 else "")+((f"\nThe class {fqdn} has the following static members: \n-"+ "\n-".join(static_members)) if len(static_members)>0 else "")+ "\n\n"+((f"Objects of the class {fqdn} have the following instance members: \n-"+ "\n-".join(instance_members)) if len(instance_members)>0 else ""))
                                    
            else:
                class_infos.append(f"The specified class {fqdn} does not exist.")
        return "\n#########\n".join(class_infos)
