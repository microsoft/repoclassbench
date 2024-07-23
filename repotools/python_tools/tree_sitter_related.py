# Importing necessary modules from tree_sitter
import re
from tree_sitter import Language, Parser
import os  # Importing os module for interacting with the operating system
from typing import List  # Importing List from typing for type hinting
import project_utils.common_utils as utils  # TODO: remove dependency
from tree_sitter_languages import get_parser

# Fetching a logger with IST adjusted time
logger = utils.fetch_ist_adjusted_logger()

# # Defining the path to the shared object file for tree-sitter languages
# so_file_path = os.path.join(os.path.dirname(
#     __file__), "./python_tree_sitter_my-languages.so")


class SpanRelated:
    '''Class containing static methods for span-related operations'''

    @staticmethod
    def convert_to_tuple_format(original_span):
        '''Converts the span to a tuple format'''
        assert (len(original_span) == 2)  # Ensure the span has 2 elements
        assert (len(original_span[0]) == 2)
        assert (len(original_span[1]) == 2)
        return ((original_span[0][0], original_span[0][1]),
                (original_span[1][0], original_span[1][1]))  # Convert to tuple format

    @staticmethod
    def has_span_overlap(span1, span2):
        '''Returns True if the spans overlap, else False'''
        # When do 2 ranges not overlap? They don't overlap when one of them
        # starts after the other one ends
        span1, span2 = SpanRelated.convert_to_tuple_format(
            span1), SpanRelated.convert_to_tuple_format(span2)
        dont_overlap = (span1[1] < span2[0]) or (
            span1[0] > span2[1])  # Check for non-overlapping condition
        return not dont_overlap

    @staticmethod
    def does_span_contain(parent_span, child_span):
        '''Returns True if span1 contains span2, else False'''
        parent_span, child_span = SpanRelated.convert_to_tuple_format(
            parent_span), SpanRelated.convert_to_tuple_format(child_span)
        return (parent_span[0] <= child_span[0]) and (
            parent_span[1] >= child_span[1])  # Check if parent_span contains child_span


def fetch_python_parser():
    '''Fetches and returns a Python parser using tree-sitter'''
    # PY_LANGUAGE = Language(
    #     so_file_path, "python")  # Load the Python language from the shared object file
    parser = get_parser(
    "python"
    )

    # parser = Parser()
    # parser.set_language(PY_LANGUAGE)
    return parser


def fetch_tree(parser, code_use):
    '''Parses the given code and returns the syntax tree'''
    tree = parser.parse(bytes(code_use, "utf8"))
    return tree


def fetch_relevant_body(node, test_code_str):
    '''Fetches the relevant body of code for a given node'''
    lb, ub = node.start_point, node.end_point
    all_lines = test_code_str.split("\n")
    ans_str = ""
    if lb[0] == ub[0]:  # If the node is within a single line
        # Extract the relevant part of the line
        ans_str = all_lines[lb[0]][lb[1]:ub[1]]
    else:  # If the node spans multiple lines
        # Extract from the start point to the end of the line
        ans_str = all_lines[lb[0]][lb[1]:]
        for _line in range(lb[0] + 1, ub[0]):  # Loop through the lines in between
            ans_str += '\n'
            ans_str += all_lines[_line]  # Add each line to the result
        ans_str += '\n'
        # Add the part of the last line up to the end point
        ans_str += all_lines[ub[0]][:ub[1]]
    return ans_str


def fetch_type_nodes(s, desired_types_list: List[str]):
    '''Fetches nodes of the desired types from the syntax tree'''
    relevant_nodes = []

    if s.type in desired_types_list:
        relevant_nodes.append(s)

    for curr_child in s.children:  # Recursively fetch nodes of the desired types from the children
        relevant_nodes += fetch_type_nodes(curr_child, desired_types_list)

    return relevant_nodes  # Return the list of relevant nodes


def fetch_nodes_of_type(file_path, types_allowed, wanted_parent_span=None):
    '''Fetches the locations of type annotations in the file in the form [{"node_text", "span"}]'''
    parser = fetch_python_parser()  # Fetch the Python parser
    test_code_str = open(file_path).read()  # Read the code from the file

    generic_type_nodes = fetch_type_nodes(
        fetch_tree(parser, test_code_str).root_node, types_allowed)  # Fetch nodes of the desired types

    node_list = [
        {
            'node_obj': curr_node,
            "node_txt": fetch_relevant_body(
                curr_node,
                test_code_str),
            "start_point": curr_node.start_point,
            "end_point": curr_node.end_point} for curr_node in generic_type_nodes]  # Create a list of node details

    # tree sitter has 0-based indexing whereas jedi has 1-based indexing, adjust for this
    for curr_node in node_list:
        curr_node['start_point'] = (curr_node['start_point'][0] + 1,  # row
                                    curr_node['start_point'][1])  # column
        curr_node['end_point'] = (curr_node['end_point'][0] + 1,  # row
                                  curr_node['end_point'][1])  # column
        curr_node['span'] = SpanRelated.convert_to_tuple_format(
            (curr_node['start_point'], curr_node['end_point']))  # Convert start and end points to span
        # Remove the start point from the dictionary
        del curr_node['start_point']
        del curr_node['end_point']  # Remove the end point from the dictionary

    return node_list  # Return the list of nodes with their details


def format_node_list(nodes, file_body):
    '''Formats the list of nodes with their details'''
    formatted_identifier_nodes = []
    for node in nodes:
        formatted_identifier_nodes.append({'node_obj': node,
                                          'node_txt': fetch_relevant_body(node, file_body),
                                           'start_point': node.start_point,
                                           'end_point': node.end_point})  # Create a list of formatted nodes

    for node in formatted_identifier_nodes:
        node['start_point'] = (node['start_point'][0] + 1,  # row
                               node['start_point'][1])  # Adjust the start point for 1-based indexing
        node['end_point'] = (node['end_point'][0] + 1,  # row
                             node['end_point'][1])  # Adjust the end point for 1-based indexing
        node['span'] = SpanRelated.convert_to_tuple_format(
            (node['start_point'], node['end_point']))  # Convert to span
        del node['start_point']  # Remove the start point from the dictionary
        del node['end_point']  # Remove the end point from the dictionary
    formatted_identifier_nodes = sorted(
        formatted_identifier_nodes, key=lambda x: x['span'])  # Sort nodes by span
    return formatted_identifier_nodes  # Return the formatted list of nodes


def fetch_class_and_function_nodes_defn_identifiers(file_path):
    '''Fetches the class and function definition identifiers from the file'''
    wanted_definition_nodes = fetch_nodes_of_type(file_path, [
                                                  "function_definition", 'class_definition'])  # Fetch function and class definition nodes
    file_body = open(file_path).read()  # Read the code from the file

    # now, in the children of these nodes, find the identifier nodes
    identifier_nodes = []
    for node in wanted_definition_nodes:
        # Fetch identifier nodes from the children
        curr_identifier_nodes = [
            x for x in node['node_obj'].children if x.type == "identifier"]
        # Ensure there is exactly one identifier node
        assert (len(curr_identifier_nodes) == 1)
        # Add the identifier node to the list
        identifier_nodes.append(curr_identifier_nodes[0])
    formatted_identifier_nodes = format_node_list(
        identifier_nodes, file_body)  # Format the list of identifier nodes

    return formatted_identifier_nodes  # Return the formatted list of identifier nodes


def find_left_side_identifiers_of_assignments(file_path):
    '''Fetches the left side identifiers of assignments from the file'''
    wanted_definition_nodes = fetch_nodes_of_type(file_path, ["assignment"])
    file_body = open(file_path).read()

    identifier_nodes = []
    # now, in the children of these nodes, find the identifier nodes
    for node in wanted_definition_nodes:
        node_obj = node['node_obj']
        # first child should be the left side of the assignment and should be an identifier
        assert (len(node_obj.children) > 0)
        # assert(node_obj.children[0].type == "identifier") # this does not hold true in cases such as : `self.x  = 1`
        if node_obj.children[0].type == "identifier":
            identifier_nodes.append(node_obj.children[0])
    identifier_nodes = format_node_list(identifier_nodes, file_body)
    return identifier_nodes


def fetch_entity_artifacts(class_body, entity_type):
    assert (entity_type in ["class", "function"])
    parser = fetch_python_parser()
    tree = fetch_tree(parser, class_body)
    entity_node = tree.root_node
    # fetch all nodes of type `class_definition`
    entity_defn_nodes = fetch_type_nodes(
        entity_node, [f"{entity_type}_definition"])
    entity_defn_nodes = sorted(entity_defn_nodes, key=lambda x: x.start_point)
    assert (len(entity_defn_nodes) > 0)
    entity_root_node = entity_defn_nodes[0]

    block_nodes = fetch_type_nodes(entity_root_node, ["block"])
    assert (len(block_nodes) > 0)
    block_nodes = sorted(block_nodes, key=lambda x: x.start_point)
    entity_block_node = block_nodes[0]

    entity_root_node_txt = fetch_relevant_body(entity_root_node, class_body)
    entity_block_node_txt = fetch_relevant_body(entity_block_node, class_body)
    assert (entity_block_node_txt in entity_root_node_txt)
    entity_signature = entity_root_node_txt.split(entity_block_node_txt)[0]

    ans = dict()

    # remove extra spaces
    ans['signature'] = entity_signature.replace("\n", " ")
    ans['signature'] = re.sub(r'\s+', ' ', ans['signature']).strip()
    ans['block'] = entity_block_node_txt
    ans['docstring'] = ""
    if len(entity_block_node.children) > 0:
        first_child = entity_block_node.children[0]
        if first_child.type == "expression_statement":
            if len(first_child.children) > 0:
                first_child_child = first_child.children[0]
                if first_child_child.type == "string":
                    ans['docstring'] = fetch_relevant_body(
                        first_child_child, class_body)
    ans = {k: v.strip() for k, v in ans.items()}
    return ans
