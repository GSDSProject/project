import numpy as np
import requests
from flask import Flask, request, make_response, jsonify
from flask_restx import Resource, Api, Namespace, fields
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import uuid

# define namespace
ns = Namespace('word', description='Word operations')

# MongoDB 연결 설정
mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
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


def related_word(word, limit=100):
    word = word.lower()
    url = f"http://api.conceptnet.io/query?node=/c/en/{word}&rel=/r/RelatedTo&limit={limit}"
    response = requests.get(url)
    data = response.json()

    related_words = []
    for edge in data['edges']:
        if edge['end']['@id'] != f"/c/en/{word}":
            related_word_ = edge['end']['@id'].split('/')[-1]
            related_words.append(related_word_)

    return list(set(related_words))


def store_word(word, user_type):
    collection = get_collection(user_type)
    doc = collection.find_one({"word": word})
    if doc is None:
        params = {"successes": 1, "failures": 1}
        doc = {
            "word": word,
            "params": params
        }
        collection.insert_one(doc)


def store_related_words(word, user_type, limit=100):
    related_words = related_word(word, limit)
    collection = get_collection(user_type)
    for a_word in related_words:
        doc = collection.find_one({"word": a_word})
        if doc is None:
            params = {"successes": 1, "failures": 1}
            doc = {
                "word": a_word,
                "params": params
            }
            collection.insert_one(doc)


def add_user(word, user_id):
    collection = get_collection('recommended')
    collection.insert_one({"user_id": user_id, "words": [word]})


def recommend_words(user_id, user_type, num_recommendations=10):
    collection = get_collection(user_type)
    recommended_collection = get_collection('recommended')
    doc = recommended_collection.find_one({"user_id": user_id})
    previously_recommended = doc['words'] if doc else []

    words = collection.find({})
    word_samples = []

    for word_doc in words:
        word = word_doc["word"]
        if word not in previously_recommended:
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
    if doc:
        previously_recommended = doc['words']
        updated_words = previously_recommended + recommended_words
        recommended_collection.update_one({"user_id": user_id}, {"$set": {"words": updated_words}})
    else:
        recommended_collection.insert_one({"user_id": user_id, "words": recommended_words})


def get_word_params(word, user_type):
    """
    Get the parameters of a word for Thompson Sampling from the database.
    If the word does not exist in the database, initialize it with 1 success and 1 failure.
    """
    collection = get_collection(user_type)
    doc = collection.find_one({"word": word})
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
    success = (selected_word in recommended_words)
    update_word_params(selected_word, user_type, success)


@ns.route('/center/<user_type>/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True},
                        {'name': 'user_type', 'in': 'path', 'type': 'string', 'required': True}]})
class centerWord(Resource):
    def get(self, word, user_type):
        user_id = str(uuid.uuid4())
        response = make_response({'user_id': user_id})
        response.set_cookie('user_id', user_id)
        store_word(word, user_type)
        store_related_words(word, user_type)
        user_id = request.cookies.get('user_id')
        add_user(word, user_id)
        recommended_words = recommend_words(user_id, user_type, num_recommendations=10)
        store_recommend_words(user_id, recommended_words)
        return jsonify(recommended_words)


list_item_model = ns.model('ListItem', {
    'center_word': fields.String(required=True, description='Center word'),
    'user_type': fields.String(required=True, description='User type'),
})


@ns.route('/human/<choice_word>')
@ns.doc({'parameters': [{'name': 'choice_word', 'in': 'path', 'type': 'string', 'required': True}]})
class humanFeedback(Resource):
    @ns.expect(list_item_model)
    def post(self, choice_word):
        user_id = request.cookies.get('user_id')
        user_type = ns.payload['user_type']
        store_word(choice_word, user_type)
        store_related_words(choice_word, user_type)
        recommended_words = recommend_words(user_id, user_type, num_recommendations=10)
        store_recommend_words(user_id, recommended_words)
        process_feedback(recommended_words, user_type, choice_word)
        return jsonify(recommended_words)
