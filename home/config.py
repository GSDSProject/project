import requests
import numpy as np
from itertools import islice

# Define a function to get related words and weights
def get_related_words(word, num=10, limit=1000):
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

def select_word(word, selected_words):
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
    #z = dict(islice(y.items(), many))
    total = sum(y.values())
    result = {key: value / total for key, value in y.items()}
    transition_matrix[word] = result

    if len(selected_words) == 1:
        next_words = list(y.keys())
    else:
        current_word = word
        next_words = recommend_next_words(current_word, transition_matrix, 5)

    return next_words

def step(word, selected_words):
    next_words = select_word(word, selected_words)
    print(f"\nRelated words for '{word}':")
    print(next_words, '\n')
    input('Press Enter')


def main():
    selected_words = []

    word = input("Enter the central word for your mind map: ")
    #many = int(input("How many related words?: "))
    selected_words.append(word)
    step(word, selected_words)

    while True:
        word = input("Choose the Word (if there is no word you think, say 'none' or 'others')  ")
        #number_of_words = int(input("\n How many related words?: "))
        selected_words.append(word)

        if word == 'none':
            break
        elif word == 'others':
            word = input("Write the word: ")
            selected_words[-1] = word
        step(word, selected_words)