import numpy as np
import requests
from flask import jsonify
from flask_restx import Resource, Namespace

# Load pre-trained Word2Vec model
# model = api.load('word2vec-google-news-300')

# define namespace
ns = Namespace('word', description='Word operations')


# def most_similar_bandit(word, num_options=5, epsilon=0.1):
#     similar_words = model.most_similar(positive=[word], topn=num_options * 10)
#     options = random.sample(similar_words, num_options)
#     rewards = [0] * num_options
#     counts = [0] * num_options
#
#     for i in range(num_options):
#         if random.random() < epsilon:
#             choice = random.choice(range(num_options))
#         else:
#             choice = np.argmax(rewards)
#
#         option = options[choice]
#         counts[choice] += 1
#         rewards[choice] = model.similarity(word, option[0])
#
#     return [options[i] for i in np.argsort(rewards)[::-1]]


def get_related_words(word, limit=1000):
    url = f'http://api.conceptnet.io/c/en/{word}?rel=/r/RelatedTo&limit={limit}'
    response = requests.get(url)
    data = response.json()

    related_words = {}
    for item in data['edges']:
        if item['rel']['label'] == 'RelatedTo':
            if item['start']['label'] != word:
                if item['start']['label'] not in related_words:
                    related_word = item['start']['label']
                    weight = item['weight']
            else:
                if item['end']['label'] not in related_words:
                    related_word = item['end']['label']
                    weight = item['weight']

            related_words[related_word] = weight

    return related_words


transition_matrix = {}

def thompson_sampling(probs, N, alpha=1, beta=1):
    samples = [np.random.beta(alpha + prob, beta + 1 - prob) for prob in probs]

    # Find the indices of the top N maximum values
    top_N_indices = np.argpartition(samples, -N)[-N:]

    return top_N_indices

def recommend_next_words(current_word, transition_matrix, N):
    recommended = []
    possible_words = transition_matrix.get(current_word, {})

    if not possible_words:
        return None

    words = list(possible_words.keys())
    probabilities = list(possible_words.values())

    next_word_indices = thompson_sampling(probabilities, N)
    for i in next_word_indices:
        recommended.append(words[i])

    return recommended


@ns.route('/gensim/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True}]})
class GensimWord(Resource):
    def get(self, word):
        suggestions = most_similar_bandit(word)
        return jsonify(suggestions)


@ns.route('/conceptnet/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True}]})
class ConceptNetWord(Resource):
    def get(self, word):
        suggestions = get_related_words(word)
        return jsonify(suggestions)
