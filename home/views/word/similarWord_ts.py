import numpy as np
import requests
import uuid
from flask import make_response, jsonify
from flask_restx import Resource, Namespace, fields
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import re
import nltk
from nltk.corpus import words
nltk.download('words')


# define namespace
ns = Namespace('word', description='Word operations')

# MongoDB 연결 설정
mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
# mongodb_uri = "mongodb://localhost:27017"
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

    english_words = set(words.words())
    related_words = []
    for edge in data['edges']:
        end_word_path = edge['end']['@id']
        if end_word_path.startswith("/c/en/") and end_word_path != f"/c/en/{word}":
            related_word_ = end_word_path.split('/')[-1]
            if re.match("^[a-z]*$", related_word_) and related_word_ in english_words:
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
    previously_chosen = doc['choice']
    recommended_list = []
    for recommended in previously_recommended:
        for word in recommended:
            recommended_list.append(word)
    for word in previously_chosen:
        recommended_list.append(word)
    recommended_list = list(set(recommended_list))

    a_words = collection.find({"center_word": center_word})
    word_samples = []
    for word_doc in a_words:
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


def calculate_success_rate(user_type):
    collection = get_collection(user_type)
    successes, failures = 0, 0
    for doc in collection.find():
        successes += doc["params"]["successes"]
        failures += doc["params"]["failures"]
    if successes + failures == 0:
        return 0  # To avoid division by zero
    return successes / (successes + failures)


def get_average_reward(user_id, user_type, center_word):
    recommended_collection = get_collection('recommended')
    doc = recommended_collection.find_one({"user_id": user_id})
    a_words = doc['words']

    total_reward = 0
    total_recommendations = 0
    for word_list in a_words:
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
        a_words = doc['words']
        center_word = a_words[0][0]
        for word_list in a_words:
            for word in word_list:
                params = get_word_params(word, user_type, center_word)
                total_reward += params["reward"]
                total_recommendations += 1

    if total_recommendations == 0:
        return None
    else:
        return total_reward / total_recommendations


def calculate_ctr(user_type):
    recommended_collection = get_collection('recommended')

    clicks, impressions = 0, 0
    for doc in recommended_collection.find({"user_type": user_type}):
        clicks += len(doc["choice"])
        impressions += sum(len(a_words) for a_words in doc["words"])

    if impressions == 0:
        return 0  # Avoid division by zero
    return clicks / impressions


def calculate_expectation_of_regret(user_type):
    collection = get_collection(user_type)

    # Find the best action
    best_success_rate = 0
    for doc in collection.find():
        success_rate = doc["params"]["successes"] / (doc["params"]["successes"] + doc["params"]["failures"])
        if success_rate > best_success_rate:
            best_success_rate = success_rate

    # Calculate the expectation of regret
    total_regret = 0
    total_count = 0
    for doc in collection.find():
        success_rate = doc["params"]["successes"] / (doc["params"]["successes"] + doc["params"]["failures"])
        regret = best_success_rate - success_rate
        total_regret += regret
        total_count += 1

    if total_count == 0:
        return 0  # To avoid division by zero
    return total_regret / total_count


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


@ns.route('/performance/<user_type>')
@ns.doc({'parameters': [{'name': 'user_type', 'in': 'path', 'type': 'string', 'required': True}]})
class performanceMeasure(Resource):
    def post(self, user_type):
        # ctr = get_average_reward(user_id, user_type, center_word)
        success_rate = calculate_success_rate(user_type)
        ctr = calculate_ctr(user_type)
        expected_regret = calculate_expectation_of_regret(user_type)
        response_data = {'user_type': user_type,
                         'overall_success_rate': success_rate,
                         'CTR': ctr,
                         'expected_regret': expected_regret
                         }
        response = make_response(jsonify(response_data))
        return response
