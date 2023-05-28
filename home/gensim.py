import gensim.downloader as api
import numpy as np
import random
import networkx as nx
import matplotlib.pyplot as plt

# Load pre-trained Word2Vec model
model = api.load('word2vec-google-news-300')

def most_similar_bandit(word, num_options=5, epsilon=0.1):
    similar_words = model.most_similar(positive=[word], topn=num_options*10)
    options = random.sample(similar_words, num_options)
    rewards = [0] * num_options
    counts = [0] * num_options

    for i in range(num_options):
        if random.random() < epsilon:
            choice = random.choice(range(num_options))
        else:
            choice = np.argmax(rewards)

        option = options[choice]
        counts[choice] += 1
        rewards[choice] = model.similarity(word, option[0])

    return [options[i] for i in np.argsort(rewards)[::-1]]

def draw_mind_map(graph):
    plt.figure(figsize=(16, 10))
    pos = nx.spring_layout(graph, seed=42)
    nx.draw(graph, pos, with_labels=True, node_color="skyblue", font_size=14, font_weight="bold", node_size=3000, alpha=0.8)
    nx.draw_networkx_edge_labels(graph, pos, edge_labels={(n1, n2): f"{w:.2f}" for n1, n2, w in graph.edges(data="weight")}, font_size=12)
    plt.title("Mind Map", fontsize=24)
    plt.axis("off")
    plt.show()


def add_graph(graph, current_word, suggestions):
    for i, (word, _) in enumerate(suggestions):
        print(f"{i + 1}. {word}")
        if not graph.has_node(word):
            graph.add_node(word)
        if not graph.has_edge(current_word, word):
            graph.add_edge(current_word, word, weight=suggestions[i][1])
    return suggestions


def mind_mapping(center_word, exit_indicator=False):
    current_word = center_word
    graph = nx.Graph()
    graph.add_node(center_word)

    while not exit_indicator:
        suggestions = most_similar_bandit(current_word)
        suggestions = add_graph(graph, current_word, suggestions)
        yield graph, suggestions  # return the graph and the new suggestions at each step


def human_feedback(center_word, choice, exit_indicator=False):
    mind_map_generator = mind_mapping(center_word, exit_indicator)

    while True:
        graph, suggestions = next(mind_map_generator)

        try:
            index = int(choice) - 1
            current_word = suggestions[index][0]
        except (ValueError, IndexError):
            print("Invalid input. Please try again.")

        if exit_indicator:
            break
        else:
            choice = input("Enter the next choice: ")  # This line should be replaced with appropriate front-end logic

    return graph