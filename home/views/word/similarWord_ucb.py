from random import sample

import math
import requests
from flask import jsonify
from flask_restx import Resource, Namespace, fields
from pymongo import MongoClient

# define namespace
ns = Namespace('ucb', description='ucb operations')


# MongoDB 연결 설정
mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
client = MongoClient(mongodb_uri)
db = client['mindmapDB']
collections = {
    'marketer': db['marketer_ucb'],
    'developer': db['developer_ucb'],
    'designer': db['designer_ucb'],
}


def get_db():
    client = MongoClient(mongodb_uri)
    db = client['mindmapDB']
    return db


def get_collection(user_type):
    if user_type in collections:
        db = get_db()
        return db[user_type+'_ucb']


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


def get_ucb(total, success, num_samples, c):
    """
    Calculate the Upper Confidence Bound (UCB)
    """
    if success == 0:
        return float('inf')
    average = success / total
    ucb = average + math.sqrt((c * math.log(num_samples)) / success)
    return ucb


def recommend_words_ucb(user_type, c, num_recommendations=10):
    """
    Recommend a list of words using Upper Confidence Bound (UCB)
    """
    collection = get_collection(user_type)
    words = collection.find({})
    word_samples = []
    total_samples = 0
    for word_doc in words:
        word = word_doc["word"]
        params = word_doc["params"]
        total_samples += params["successes"] + params["failures"]

    for word_doc in words:
        word = word_doc["word"]
        params = word_doc["params"]
        ucb = get_ucb(params["successes"] + params["failures"], params["successes"], total_samples, c)
        word_samples.append((word, ucb))

    word_samples.sort(key=lambda x: x[1], reverse=True)
    recommended_words = [word for word, ucb in word_samples[:num_recommendations]]
    return recommended_words


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
    def post(self, choice_word, c):
        recommended_words = recommend_words_ucb(ns.payload['user_type'], c, num_recommendations=10)
        process_feedback(recommended_words, ns.payload['user_type'], choice_word)
        return jsonify(recommended_words)