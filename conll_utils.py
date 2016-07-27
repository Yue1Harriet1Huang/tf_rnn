import os
import sys
import codecs
from collections import defaultdict

import numpy as np

sys.path.append("../CONLL2012-intern")
from load_conll import load_data

class Node(object):
    def __init__(self):
        self.parent = None
        self.child_list = []
        
    def add_child(self, child):
        self.child_list.append(child)
        child.parent = self

def log(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()
    return
    
def get_sorted_dict(d):
    return sorted(zip(*reversed(zip(*d.iteritems()))), reverse=True)
    
def extract_conll_vocabulary(raw_data_path = "../CONLL2012-intern/conll-2012/v4/data",
                             vocabulary_file = "vocabulary.txt"):
    log("extract_conll_vocabulary()...")
    
    vocabulary_set = set()
    for split in ["train", "development", "test"]:
        full_path = os.path.join(raw_data_path, split, "data/english/annotations")
        config = {"file_suffix": "gold_conll", "dir_prefix": full_path}
        raw_data = load_data(config)
        for document in raw_data:
            for part in raw_data[document]:
                for sentence in raw_data[document][part]["text"]:
                    vocabulary_set |= set(sentence)
    
    with codecs.open(vocabulary_file, "w", encoding="utf8") as f:
        for word in sorted(vocabulary_set):
            f.write(word + '\n')
        
    log(" done\n")
    return
    
def read_vocabulary(vocabulary_file):
    log("read_vocabulary()...")
    
    word_list = []
    word_to_index = {}
    with codecs.open(vocabulary_file, "r", encoding="utf8") as f:
        for line in f.readlines():
            word = line.strip()
            word_to_index[word] = len(word_list)
            word_list.append(word)
    
    log(" %d words\n" % len(word_to_index))
    return word_list, word_to_index

def read_pos(pos_file):
    log("read_pos()...")
    
    pos_list = []
    pos_to_index = {}
    with open(pos_file, "r") as f:
        for line in f.readlines():
            pos = line.strip()
            pos_to_index[pos] = len(pos_list)
            pos_list.append(pos)
    
    log(" %d pos\n" % len(pos_to_index))
    return pos_list, pos_to_index
    
def read_ne(ne_file):
    log("read_ne()...")
    
    ne_list = []
    ne_to_index = {}
    with open(ne_file, "r") as f:
        for line in f.readlines():
            ne = line.strip()
            ne_to_index[ne] = len(ne_list)
            ne_list.append(ne)
    
    log(" %d ne\n" % len(ne_to_index))
    return ne_list, ne_to_index

def construct_node(tree, ner_raw_data, head_raw_data,
                    word_to_index, pos_to_index,
                    pos_count, ne_count, pos_ne_count,
                    sentence_index, offset):
    if len(tree.subtrees) == 1:
        return construct_node(tree.subtrees[0], ner_raw_data, head_raw_data,
                word_to_index, pos_to_index,
                pos_count, ne_count, pos_ne_count,
                sentence_index, offset)
    node = Node()
    start_offset = offset
    word = tree.word
    pos = tree.label
    
    # Process word info
    if word:
        node.word_index = word_to_index[word]
        offset += 1
    else:
        node.word_index = -1
    
    # Process pos info
    node.pos = pos
    node.pos_index = pos_to_index[pos]
    pos_count[pos] += 1
    
    # Process children and get ne info
    degree = len(tree.subtrees)
    for subtree in tree.subtrees:
        child, child_degree, offset = construct_node(subtree, ner_raw_data, head_raw_data,
                                        word_to_index, pos_to_index,
                                        pos_count, ne_count, pos_ne_count,
                                        sentence_index, offset)
        node.add_child(child)
        degree = max(degree, child_degree)
    
    # Process ne info
    span = (sentence_index, start_offset, offset)
    ne = ner_raw_data[span] if span in ner_raw_data else "NONE"
    node.ne = ne
    ne_count[ne] += 1
    if ne != "NONE": pos_ne_count[pos] += 1
    
    # Process head info
    head = head_raw_data[((start_offset,offset), pos)][1]
    node.word_index = word_to_index[head]
    node.parent_head_index = -1
    for child in node.child_list:
        child.parent_head_index = node.word_index
    
    return node, degree, offset

def get_tree_data(raw_data, word_to_index, pos_to_index):
    log("get_tree_data()...")
    """ Get tree structured data from CoNLL 2012
    
    Stores into Node data structure
    """
    root_list = []
    max_degree = 0
    pos_count = defaultdict(lambda: 0)
    ne_count = defaultdict(lambda: 0)
    pos_ne_count = defaultdict(lambda: 0)
    
    for document in raw_data:
        for part in raw_data[document]:
            ner_raw_data = raw_data[document][part]["ner"]
            for sentence_index, parse in enumerate(raw_data[document][part]["parses"]):
                head_raw_data = raw_data[document][part]["heads"][sentence_index]
                root_node, degree, _ = construct_node(
                                        parse, ner_raw_data, head_raw_data,
                                        word_to_index, pos_to_index,
                                        pos_count, ne_count, pos_ne_count,
                                        sentence_index, 0)
                root_list.append(root_node)
                max_degree = max(max_degree, degree)
            
    log(" %d sentences\n" % len(root_list))
    return root_list, max_degree, pos_count, ne_count, pos_ne_count

def label_tree_data(node, pos_ne_to_label):
    node.label = pos_ne_to_label[(node.pos, node.ne)]
        
    for child in node.child_list:
        label_tree_data(child, pos_ne_to_label)
    return
    
def read_conll_dataset(raw_data_path = "../CONLL2012-intern/conll-2012/v4/data",
                       vocabulary_file = "vocabulary.txt",
                       pos_file = "pos.txt",
                       ne_file = "ne.txt"):
    data_split_list = ["train", "development", "test"]
    
    # Read all raw data
    raw_data = {}
    for split in data_split_list:
        full_path = os.path.join(raw_data_path, split, "data/english/annotations")
        config = {"file_suffix": "gold_conll", "dir_prefix": full_path}
        raw_data[split] = load_data(config)
    
    # Read word list
    word_list, word_to_index = read_vocabulary(vocabulary_file)
    
    # Read POS list
    pos_list, pos_to_index = read_pos(pos_file)
    
    # Read named entity list
    ne_list, ne_to_index = read_ne(ne_file)
    
    # Build a tree structure for each sentence
    data = {}
    max_degree = 0
    pos_count = {}
    ne_count = {}
    pos_ne_count = {}
    for split in data_split_list:
        tree_data, degree, pos_count[split], ne_count[split], pos_ne_count[split] = (
            get_tree_data(raw_data[split], word_to_index, pos_to_index))
        sentences = len(tree_data)
        nodes = sum(pos_count[split].itervalues())
        nes = sum(pos_ne_count[split].itervalues())
        max_degree = max(max_degree, degree)
        data[split] = [tree_data, nodes, nes]
        log("<%s>\n  %d sentences; %d nodes; %d named entities\n"
            % (split, sentences, nodes, nes))
    log("degree %d\n" % max_degree)
    
    # Show POS distribution
    total_pos_count = defaultdict(lambda: 0)
    for split in data_split_list:
        for pos in pos_count[split]:
            total_pos_count[pos] += pos_count[split][pos]
    nodes = sum(total_pos_count.itervalues())
    print "\nTotal %d nodes" % nodes
    print "-"*50 + "\n   POS   count  ratio\n" + "-"*50
    for count, pos in get_sorted_dict(total_pos_count):
        print "%6s %7d %5.1f%%" % (pos, count, count*100./nodes)
    
    # Show NE distribution
    total_ne_count = defaultdict(lambda: 0)
    for split in data_split_list:
        for ne in ne_count[split]:
            if ne == "NONE": continue
            total_ne_count[ne] += ne_count[split][ne]
    nes = sum(total_ne_count.itervalues())
    print "\nTotal %d named entities" % nes
    print "-"*50 + "\n          NE  count  ratio\n" + "-"*50
    for count, ne in get_sorted_dict(total_ne_count):
        print "%12s %6d %5.1f%%" % (ne, count, count*100./nes)
    
    # Show POS-NE distribution
    total_pos_ne_count = defaultdict(lambda: 0)
    for split in data_split_list:
        if split == "test": continue
        for pos in pos_ne_count[split]:
            total_pos_ne_count[pos] += pos_ne_count[split][pos]
    print "-"*50 + "\n   POS     NE   total  ratio\n" + "-"*50
    for count, pos in get_sorted_dict(total_pos_ne_count):
        total = total_pos_count[pos]
        print "%6s %6d %7d %5.1f%%" % (pos, count, total, count*100./total)
    
    # Compute the mapping to label
    label = 0
    pos_ne_to_label = {}
    for ne in ne_list + ["NONE"]:
        for pos in pos_list:
            pos_ne_to_label[(pos, ne)] = label
            label += 1
    
    # Add label to nodes
    for split in data_split_list:
        for root_node in data[split][0]:
            label_tree_data(root_node, pos_ne_to_label)
    
    return data, max_degree, word_to_index, label, len(pos_to_index), ne_list
    
def get_formatted_input(root_node, degree):
    """ Get inputs with RNN required format
    
    x: vector; word indices of nodes
    T: matrix; the tree structure
    y: vector; labels of nodes
    p: vector; pos indices of nodes
    a: vector; word indices of node parents
    """
    # Get BFS layers
    layer_list = []
    layer = [root_node]
    while layer:
        layer_list.append(layer)
        child_layer = []
        for node in layer:
            child_layer.extend(node.child_list)
        layer = child_layer
    
    # Extract data from layers bottom-up
    x = []
    T = []
    y = []
    p = []
    a = []
    
    index = -1
    for layer in reversed(layer_list):
        for node in layer:
            index += 1
            node.index = index
            
            x.append(node.word_index)
            
            child_index_list = [child.index for child in node.child_list]
            T.append(child_index_list + [-1]*(degree-len(node.child_list)) + [node.index])
            
            y.append(node.label)
            
            p.append(node.pos_index)
            
            a.append(node.parent_head_index)
            
    x = np.array(x, dtype=np.int32)
    T = np.array(T, dtype=np.int32)
    y = np.array(y, dtype=np.int32)
    p = np.array(p, dtype=np.int32)
    a = np.array(a, dtype=np.int32)
    return x, T, y, p, a

def extract_glove_embeddings(glove_file = "glove.840B.300d.txt",
                             vocabulary_file = "vocabulary.txt"):
    
    word_list, word_to_index = read_vocabulary(vocabulary_file)
    
    word_list = []
    embedding_list = []
    with open(glove_file, "r") as f:
        for line in f:
            line = line.strip().split()
            word = line[0]
            if word not in word_to_index: continue
            embedding = np.array([float(i) for i in line[1:]])
            word_list.append(word)
            embedding_list.append(embedding)
    
    np.save("glove_word.npy", word_list)
    np.save("glove_embedding.npy", embedding_list)
    return
    
if __name__ == "__main__":
    # extract_glove_embeddings()
    # extract_conll_vocabulary()
    read_conll_dataset()
    exit()