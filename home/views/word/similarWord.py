import random

import gensim.downloader as api
import numpy as np
from flask import jsonify
from flask_restx import Resource, Namespace

# Load pre-trained Word2Vec model
model = api.load('word2vec-google-news-300')

# define namespace
ns = Namespace('word', description='Word operations')


def most_similar_bandit(word, num_options=5, epsilon=0.1):
    similar_words = model.most_similar(positive=[word], topn=num_options * 10)
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


@ns.route('/similar/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True}]})
class SimilarWord(Resource):
    def get(self, word):
        suggestions = most_similar_bandit(word)
        return jsonify(suggestions)
