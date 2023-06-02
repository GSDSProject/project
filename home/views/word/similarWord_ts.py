import numpy as np
import requests
from flask import Flask, request, make_response, jsonify
from flask_restx import Resource, Api, Namespace, fields
from pymongo import MongoClient
from random import sample
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
                related = item['start']['label'].lower() if item['start']['label'].lower() != word else item['end'][
                    'label'].lower()
                if related not in related_words:
                    related_words.append(related)
        return related_words


def store_word_and_related_words(word, user_type, limit=100):
    try:
        collection = get_collection(user_type)
        if collection is None:
            raise PyMongoError("Collection not found")
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
    except PyMongoError as e:
        print(f"An error occurred while storing word and related words in MongoDB: {e}")


def center_word(word, user_type, num_samples=10):
    store_word_and_related_words(word, user_type, limit=100)
    words = related_word(word, limit=100)
    return sample(words, num_samples)


def recommend_words(user_id, user_type, num_recommendations=10):
    """
    Recommend a list of words using Thompson Sampling.
    Exclude words that have already been recommended.
    """
    try:
        collection = get_collection(user_type)
        recommended_collection = get_collection('recommended')
        if collection is None or recommended_collection is None:
            raise PyMongoError("Collection not found")

        # Fetch previously recommended words for the user
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
        recommended_words = [word for word, sample_ in word_samples[:num_recommendations]]

        # Update the list of recommended words for the user
        if doc:
            recommended_collection.update_one({"user_id": user_id},
                                              {"$set": {"words": previously_recommended + recommended_words}})
        else:
            recommended_collection.insert_one({"user_id": user_id, "words": recommended_words})

        return recommended_words
    except PyMongoError as e:
        print(f"An error occurred while recommending words: {e}")
        return []


def get_word_params(word, user_type):
    """
    Get the parameters of a word for Thompson Sampling from the database.
    If the word does not exist in the database, initialize it with 1 success and 1 failure.
    """
    collection = get_collection(user_type)
    doc = collection.find_one({"word": word})
    if doc is None:
        params = {"successes": 2, "failures": 0}
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
    try:
        collection = get_collection(user_type)
        if collection is None:
            raise PyMongoError("Collection not found")
        params = get_word_params(word, user_type)
        if success:
            params["successes"] += 1
        else:
            params["failures"] += 1
        collection.update_one({"word": word}, {"$set": {"params": params}})
    except PyMongoError as e:
        print(f"An error occurred while updating word parameters in MongoDB: {e}")


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
        user_id = str(uuid.uuid4())
        response = make_response({'user_id': user_id})
        response.set_cookie('user_id', user_id)
        suggestions = center_word(word, user_type)
        return jsonify(suggestions)


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
        store_word_and_related_words(choice_word, user_type)
        recommended_words = recommend_words(user_id, user_type, num_recommendations=10)
        process_feedback(recommended_words, user_type, choice_word)
        return jsonify(recommended_words)
