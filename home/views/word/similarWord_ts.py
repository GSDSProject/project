import uuid

import numpy as np
import requests
from flask import make_response, jsonify, Flask
from flask_restx import Resource, Namespace, fields, Api
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# define namespace
ns = Namespace('word', description='Word operations')

# MongoDB 연결 설정
# mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
mongodb_uri = "mongodb://localhost:27017"
client = MongoClient(mongodb_uri)
db = client['mindmapDB']
collections = {
    'Marketer': db['Marketer'],
    'Developer': db['Developer'],
    'Designer': db['Designer'],
    'recommended': db['recommended'],
}


def get_db():
    try:
        client_ = MongoClient(mongodb_uri)
        db_ = client_['mindmapDB']
    except PyMongoError as e:
        print(f"An error occurred while connecting to MongoDB: {e}")
        return None
    return db_


def get_collection(user_type):
    try:
        if user_type in collections:
            db_ = get_db()
            if db_ is None:
                raise PyMongoError("Database not found")
            return db_[user_type]
    except PyMongoError as e:
        print(f"An error occurred while accessing collection: {e}")
        return None


def related_word(word, limit=50):
    word = word.lower()
    url = f"http://api.conceptnet.io/query?node=/c/en/{word}&rel=/r/RelatedTo&limit={limit}"
    response = requests.get(url)
    data = response.json()

    related_words = []
    for edge in data['edges']:
        if edge['end']['@id'] != f"/c/en/{word}":
            related_word_ = edge['end']['@id'].split('/')[-1]
            if related_word_.isalpha():
                related_words.append(related_word_)
    return list(set(related_words))


def store_word(center_word, word, user_type):
    collection = get_collection(user_type)
    doc = collection.find_one({"center_word": center_word, "word": word})
    if doc is None:
        params = {"successes": 3, "failures": 1, "reward": 0}
        doc = {
            "center_word": center_word,
            "word": word,
            "params": params
        }
        collection.insert_one(doc)


def store_related_words(center_word, word, user_type, limit=100):
    related_words = related_word(word, limit)
    collection = get_collection(user_type)
    for a_word in related_words:
        doc = collection.find_one({"center_word": center_word, "word": a_word})
        if doc is None:
            params = {"successes": 1, "failures": 1, "reward": 0}
            doc = {
                "center_word": center_word,
                "word": a_word,
                "params": params
            }
            collection.insert_one(doc)


def add_user(word, user_id, user_type):
    collection = get_collection('recommended')
    collection.insert_one({"user_id": user_id, "user_type": user_type, "words": [[word]], "choice": []})


def get_users_recommended(user_id):
    collection = get_collection('recommended')
    doc = collection.find_one({"user_id": user_id})
    previously_recommended = doc['words'][-1]
    return previously_recommended


def add_user_chosen(choice_word, user_id):
    collection = get_collection('recommended')
    doc = collection.find_one({"user_id": user_id})
    chosen = doc['choice']
    chosen.append(choice_word)
    collection.update_one({"user_id": user_id}, {"$set": {"choice": chosen}})


def recommend_words(user_id, user_type, center_word, num_recommendations=10):
    collection = get_collection(user_type)
    recommended_collection = get_collection('recommended')
    doc = recommended_collection.find_one({"user_id": user_id})
    previously_recommended = doc['words']
    recommended_list = []
    for i in range(len(previously_recommended)):
        for j in previously_recommended[i]:
            recommended_list.append(j)

    words = collection.find({"center_word": center_word})
    word_samples = []

    for word_doc in words:
        word = word_doc["word"]
        if word not in recommended_list:
            params = word_doc["params"]
            samples = np.random.beta(params["successes"], params["failures"])
            word_samples.append((word, samples))

    word_samples.sort(key=lambda x: x[1], reverse=True)
    num_to_recommend = min(len(word_samples), num_recommendations)
    recommended_words = [word for word, sample_ in word_samples[:num_to_recommend]]
    return recommended_words


def store_recommend_words(user_id, recommended_words):
    recommended_collection = get_collection('recommended')
    doc = recommended_collection.find_one({"user_id": user_id})
    previously_recommended = doc['words']
    previously_recommended.append(recommended_words)
    recommended_collection.update_one({"user_id": user_id}, {"$set": {"words": previously_recommended}})


def get_word_params(word, user_type, center_word):
    """
    Get the parameters of a word for Thompson Sampling from the database.
    If the word does not exist in the database, initialize it with 1 success and 1 failure.
    """
    collection = get_collection(user_type)
    doc = collection.find_one({"center_word": center_word, "word": word})
    params = doc["params"]
    return params


def update_word_params(word, user_type, center_word, success):
    """
    Update the parameters of a word for Thompson Sampling in the database.
    If success is True, increment the successes of the word.
    If success is False, increment the failures of the word.
    """
    params = get_word_params(word, user_type, center_word)
    if success:
        params["successes"] += 1
        params["reward"] += 1  # Increment the reward when the word is selected
    else:
        params["failures"] += 1
    collection = get_collection(user_type)
    collection.update_one({"center_word": center_word, "word": word}, {"$set": {"params": params}})


def process_feedback(recommended, user_type, center_word, choice_word):
    for i in range(len(recommended)):
        if recommended[i] == choice_word:
            update_word_params(choice_word, user_type, center_word, True)
        else:
            update_word_params(recommended[i], user_type, center_word, False)


def get_average_reward(user_id, user_type, center_word):
    recommended_collection = get_collection('recommended')
    doc = recommended_collection.find_one({"user_id": user_id})
    words = doc['words']

    total_reward = 0
    total_recommendations = 0
    for word_list in words:
        for word in word_list:
            params = get_word_params(word, user_type, center_word)
            total_reward += params["reward"]
            total_recommendations += 1

    if total_recommendations == 0:
        return None  # Avoid division by zero
    else:
        return total_reward / total_recommendations


def get_overall_ctr():
    recommended_collection = get_collection('recommended')
    total_reward = 0
    total_recommendations = 0
    for doc in recommended_collection.find():
        user_type = doc['user_type']
        words = doc['words']
        center_word = words[0][0]
        for word_list in words:
            for word in word_list:
                params = get_word_params(word, user_type, center_word)
                total_reward += params["reward"]
                total_recommendations += 1

    if total_recommendations == 0:
        return None
    else:
        return total_reward / total_recommendations


@ns.route('/center/<user_type>/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True},
                        {'name': 'user_type', 'in': 'path', 'type': 'string', 'required': True}]})
class centerWord(Resource):
    def get(self, word, user_type):
        user_id = str(uuid.uuid4())
        store_word(word, word, user_type)
        store_related_words(word, word, user_type)
        add_user(word, user_id, user_type)
        recommended_words = recommend_words(user_id, user_type, word, num_recommendations=10)
        store_recommend_words(user_id, recommended_words)
        resp = {
            'recommended_words': recommended_words,
            'user_id': user_id
        }
        response = make_response(jsonify(resp))
        return response


list_item_model = ns.model('ListItem', {
    'center_word': fields.String(required=True, description='Center word'),
    'user_type': fields.String(required=True, description='User type'),
    'user_id': fields.String(required=True, description='User id')
})


@ns.route('/human/<choice_word>')
@ns.doc({'parameters': [{'name': 'choice_word', 'in': 'path', 'type': 'string', 'required': True}]})
class humanFeedback(Resource):
    @ns.expect(list_item_model)
    def post(self, choice_word):
        user_id = ns.payload['user_id']
        user_type = ns.payload['user_type']
        center_word = ns.payload['center_word']
        add_user_chosen(choice_word, user_id)

        recommended = get_users_recommended(user_id)
        process_feedback(recommended, user_type, center_word, choice_word)

        store_word(center_word, choice_word, user_type)
        store_related_words(center_word, choice_word, user_type)
        recommended_words = recommend_words(user_id, user_type, center_word, num_recommendations=10)
        store_recommend_words(user_id, recommended_words)
        resp = {
            'recommended_words': recommended_words,
            'user_id': user_id
        }
        response = make_response(jsonify(resp))
        return response


@ns.route('/performance')
@ns.doc({'parameters': [{}]})
class performanceMeasure(Resource):
    @ns.expect(list_item_model)
    def post(self):
        user_id = ns.payload['user_id']
        user_type = ns.payload['user_type']
        center_word = ns.payload['center_word']
        ctr = get_average_reward(user_id, user_type, center_word)
        response_data = {'user_id': user_id, 'user_type': user_type,
                         'center_word': center_word, 'performance_measure': ctr}
        response = make_response(jsonify(response_data))
        return response
