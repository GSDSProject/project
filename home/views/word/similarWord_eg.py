from random import sample

import numpy as np
import requests
from flask import jsonify
from flask_restx import Resource, Namespace, fields
from pymongo import MongoClient

# define namespace
ns = Namespace('eg', description='epsilon greedy operations')


# MongoDB 연결 설정
mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
client = MongoClient(mongodb_uri)
db = client['mindmapDB']
collections = {
    'marketer': db['marketer_epsilon'],
    'developer': db['developer_epsilon'],
    'designer': db['designer_epsilon'],
}


def get_db():
    client = MongoClient(mongodb_uri)
    db = client['mindmapDB']
    return db


def get_collection(user_type):
    if user_type in collections:
        db = get_db()
        return db[user_type+'_epsilon']


def related_word(word, limit=100):
    try:
        word = word.lower()
        url = f'http://api.conceptnet.io/c/en/{word}?rel=/r/RelatedTo&limit={limit}'
        response = requests.get(url)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.
        data = response.json()
    except (requests.HTTPError, ValueError) as err:
        print(f'An error occurred: {err}')
        return []
    else:
        related_words = []
        for item in data['edges']:
            if item['rel']['label'] == 'RelatedTo':
                related = item['start']['label'].lower() if item['start']['label'].lower() != word else item['end']['label'].lower()
                if related not in related_words:
                    related_words.append(related)
        return related_words


def store_word_and_related_words(word, user_type, limit=100):
    collection = get_collection(user_type)
    doc = collection.find_one({"word": word})
    if doc is None:
        params = {"successes": 1, "failures": 1}
        doc = {
            "word": word,
            "params": params
        }
        collection.insert_one(doc)

    related_words = related_word(word, limit)
    for a_word in related_words:
        doc = collection.find_one({"word": a_word})
        if doc is None:
            params = {"successes": 1, "failures": 1}
            doc = {
                "word": word,
                "params": params
            }
            collection.insert_one(doc)


def center_word(word, user_type, num_samples=10):
    store_word_and_related_words(word, user_type, limit=100)
    words = related_word(word, limit=100)
    return sample(words, num_samples)


def recommend_words_epsilon_greedy(user_type, num_recommendations=10, epsilon=0.1):
    """
    Recommend a list of words using epsilon-greedy strategy.
    """
    collection = get_collection(user_type)
    words = collection.find({})

    # Creating a list of words and their successes
    word_list = []
    word_successes = []
    for word_doc in words:
        word = word_doc["word"]
        params = word_doc["params"]
        word_list.append(word)
        word_successes.append(params["successes"] / (params["successes"] + params["failures"]))

    recommended_words = []
    for _ in range(num_recommendations):
        # With probability epsilon, select a random word
        if np.random.random() < epsilon:
            recommended_words.append(np.random.choice(word_list))
        # Otherwise, select the word with the highest success rate
        else:
            idx = np.argmax(word_successes)
            recommended_words.append(word_list[idx])

    return recommended_words


def get_word_params(word, user_type):
    """
    Get the parameters of a word for Thompson Sampling from the database.
    If the word does not exist in the database, initialize it with 1 success and 1 failure.
    """
    collection = get_collection(user_type)
    doc = collection.find_one({"word": word})
    if doc is None:
        params = {"successes": 1, "failures": 1}
        doc = {
            "word": word,
            "params": params
        }
        collection.insert_one(doc)
    else:
        params = doc["params"]
    return params


def update_word_params(word, user_type, success):
    """
    Update the parameters of a word for Thompson Sampling in the database.
    If success is True, increment the successes of the word.
    If success is False, increment the failures of the word.
    """
    collection = get_collection(user_type)
    params = get_word_params(word, user_type)
    if success:
        params["successes"] += 1
    else:
        params["failures"] += 1
    collection.update_one({"word": word}, {"$set": {"params": params}})


def process_feedback(recommended_words, user_type, selected_word):
    """
    Process the feedback of a user.
    If the selected word is in the recommended words, consider it a success for that word.
    """
    success = (selected_word in recommended_words)
    update_word_params(selected_word, user_type, success)




@ns.route('/center/<user_type>/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True},
                        {'name': 'user_type', 'in': 'path', 'type': 'string', 'required': True}]})
class centerWord(Resource):
    def get(self, word, user_type):
        suggestions = center_word(word, user_type)
        return jsonify(suggestions)


list_item_model = ns.model('ListItem', {
    'center_word': fields.String(required=True, description='Center word'),
    'user_type': fields.String(required=True, description='User type')
})


@ns.route('/human/<choice_word>')
@ns.doc({'parameters': [{'name': 'choice_word', 'in': 'path', 'type': 'string', 'required': True}]})
class humanFeedback(Resource):
    @ns.expect(list_item_model)
    def post(self, choice_word, epsilon):
        recommended_words = recommend_words_epsilon_greedy(ns.payload['user_type'], 10, epsilon)
        process_feedback(recommended_words, ns.payload['user_type'], choice_word)
        return jsonify(recommended_words)