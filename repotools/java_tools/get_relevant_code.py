import os
from repotools.java_tools.tree_sitter_utils import get_tree, get_classes_dict

class RelevantCodeTool:
    
    def __init__(self, parent_context, repo_root_dir: str, class_name: str = None):
        self.repo_root_dir = repo_root_dir
        self.parent_context = parent_context

  
    def get_relevant_snippets(self, search_string, return_scores=False):
        repo_dir=self.repo_root_dir
        snippets=[]
        window_size=20
        sliding_size=10
        num_snippets=5
        for root, _, files in os.walk(repo_dir):
            for file in files:
                file_path=os.path.join(root,file)
                if file_path[-5:] == ".java":
                    with open(file_path,"r") as f:
                        lines=f.read().split("\n")
                        l = len(lines)
                        snippets+=["\n".join(lines[ndx:min(ndx + window_size, l)]) for ndx in range(0, l, sliding_size)]

        snippets=[snippet for snippet in snippets if snippet!=""]
        top_snippets=[]        
        scores=self.parent_context.embedding_model.get_score(search_string, snippets, use_cache=True)
        
        top_scores = sorted(scores)[-1*num_snippets:]        
        for k, score in enumerate(reversed(top_scores)):
            i = scores.index(score)
            top_snippets.append(snippets[i])
        
        return_string=""
        
        for i,snippet in enumerate(top_snippets):
            return_string+=f"\n####SNIPPET {i+1}\n"+snippet+"```"
        if return_scores:
            return top_snippets, top_scores
        else:            
            return return_string



      
    def get_relevant_classes(self, search_string, return_scores=False):
        classes=get_classes_dict(self.repo_root_dir,[])
        score_list = []
        class_list = []
        for class_name in classes:
            non_private_sigs=list(filter(lambda x:("public" in x or "protected" in x) and "private" not in x,classes[class_name].split("\n")))
            definition = "\n".join([sig.replace("{",";") for sig in non_private_sigs])
            score_list.append(
                definition
            )
            class_list.append(class_name)
        score_list=self.parent_context.embedding_model.get_score(search_string, score_list, use_cache=True)
        

        top_scores = sorted(score_list)[-5:]
        class_infos = []
        for k, score in enumerate(reversed(top_scores)):
            try:
                i = score_list.index(score)
                class_name = class_list[i]
                class_infos.append(self.parent_context.get_class_info(class_name,search_string))
                score_list = score_list[:i] + score_list[i + 1 :]
                class_list = (
                    class_list[:i] + class_list[i + 1 :]
                )
            except Exception as e:
                print("Get relevant methods error",e)
                
        if return_scores:
            return class_infos, list(reversed(top_scores))
        else:
            return "\n".join(class_infos)+"\nNote that get_relevant_classes is limited to the repository and does not check external libraries. It is possible that the method you are looking for comes from an external library."



    def get_relevant_code(self, search_string):
        classes,classes_scores=self.get_relevant_classes(search_string, return_scores=True)
        
        snippets, snippets_scores=self.get_relevant_snippets(search_string, return_scores=True)
        
        
        c1,s1=0,0
        codes=[]
        for _ in range(3):
            if len(classes_scores)>c1 and classes_scores[c1]>snippets_scores[s1]:
                codes.append(classes[c1])
                c1+=1                
            elif len(snippets_scores)>s1:
                codes.append(snippets[s1])
                s1+=1
        return "\n".join([f"#### Code Piece {i+1}:\n{code}" for i,code in enumerate(codes)])
