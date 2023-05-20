import requests
import numpy as np
from itertools import islice

# Set up the ConceptNet API endpoint
base_url = 'http://api.conceptnet.io/'


# Define a function to get related words and weights
def get_related_words_and_weights(word):
    # Build the API query URL
    query_url = base_url + 'c/en/' + word + '?limit=100'

    # Send the GET request to the API
    response = requests.get(query_url)

    # Parse the JSON response
    json_response = response.json()

    # Extract the related words and their weights from the JSON response
    related_words_and_weights = {}
    for edge in json_response['edges']:
        if edge['start']['language'] == 'en' and strip_article(edge['start']['label'].lower()) != word:
            related_word = strip_article(edge['start']['label'].lower())
            weight = edge['weight']
            if related_word not in related_words_and_weights.keys():
                related_words_and_weights[related_word] = weight

        elif edge['end']['language'] == 'en' and strip_article(edge['end']['label'].lower()) != word:
            related_word = strip_article(edge['end']['label'].lower())
            weight = edge['weight']
            if related_word not in related_words_and_weights.keys():
                related_words_and_weights[related_word] = weight

    # Return the list of related words and their weights
    return related_words_and_weights


def strip_article(string):
    if string.startswith('a '):
        return string[2:]
    elif string.startswith('an '):
        return string[3:]
    if string.startswith('the '):
        return string[4:]
    else:
        return string


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

