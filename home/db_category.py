from pymongo import MongoClient
import requests
import numpy as np
from itertools import islice

# MongoDB 연결 설정
mongodb_uri = "mongodb+srv://p4dsteam6:team6@cluster0.yvkcbg6.mongodb.net/"
client = MongoClient(mongodb_uri)
db = client['mindmapDB']
marketer_collection = db['marketer']
developer_collection = db['developer_transition']
designer_collection = db['designer_transition']
collection = db['transition']

def get_related_words(word, limit=1000):
    word = word.lower()
    url = f'http://api.conceptnet.io/c/en/{word}?rel=/r/RelatedTo&limit={limit}'
    response = requests.get(url)
    data = response.json()

    related_words = {}
    for item in data['edges']:
        if item['rel']['label'] == 'RelatedTo':
            related_word = item['start']['label'].lower() if item['start']['label'].lower() != word else item['end']['label'].lower()
            if related_word not in related_words:
                weight = item['weight']
                related_words[related_word] = weight

    return related_words

def thompson_sampling(probs, N, alpha=1, beta=1):
    samples = [np.random.beta(alpha + prob, beta + 1 - prob) for prob in probs]
    top_N_indices = np.argpartition(samples, -N)[-N:]
    return top_N_indices

def recommend_next_words(current_word):
    recommended = []
    possible_words = collection.find_one({'word': current_word})

    if not possible_words:
        return None

    words = list(possible_words['related_words'].keys())
    probabilities = list(possible_words['related_words'].values())
    next_word_indices = thompson_sampling(probabilities, len(words))
    for i in next_word_indices:
        recommended.append(words[i])

    return recommended


def select_word(word, selected_words, user_type):
    x = {}
    cnt = 0
    x_temp = get_related_words(word)
    for i in range(len(x_temp)):
        if list(x_temp)[i] in selected_words:
            continue
        else:
            x[list(x_temp)[i]] = list(x_temp.values())[i]
            cnt += 1
            if cnt == 5:
                break

    y = dict(sorted(x.items(), key=lambda item: item[1], reverse=True))
    total = sum(y.values())
    result = {key: value / total for key, value in y.items()}

    if user_type == 'marketer':
        marketer_collection.insert_one({'word': word, 'related_words': result})
    elif user_type == 'developer':
        developer_collection.insert_one({'word': word, 'related_words': result})
    elif user_type == 'designer':
        designer_collection.insert_one({'word': word, 'related_words': result})

    if len(selected_words) == 1:
        next_words = list(y.keys())
    else:
        current_word = word
        next_words = recommend_next_words(current_word)

    return next_words

def mind_map_step(word, selected_words, user_type):
    next_words = select_word(word, selected_words, user_type)
    return next_words

def center_word(word, user_type):
    selected_words = [word]
    related_words = mind_map_step(word, selected_words, user_type)
    return related_words

def human_feedback(center_word, choice_word, selected_words):
    if choice_word == 'none':
        return None
    elif choice_word == 'others':
        choice_word = collection.find_one({'word': choice_word})
    selected_words.append(choice_word)
    return mind_map_step(choice_word, selected_words)