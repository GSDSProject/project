from flask import jsonify
from flask_restx import Resource, Api, Namespace

ns = Namespace('word', description='Word operations')


@ns.route('/<word>')
@ns.doc({'parameters': [{'name': 'word', 'in': 'path', 'type': 'string', 'required': True}]})
class FindWord(Resource):
    def strip_article(self, string):
        if string.startswith('a '):
            return string[2:]
        elif string.startswith('an '):
            return string[3:]
        if string.startswith('the '):
            return string[4:]
        else:
            return string

    def get(self, word):
        import requests

        # Set up the ConceptNet API endpoint
        base_url = 'http://api.conceptnet.io/'

        # Build the API query URL
        query_url = base_url + 'c/en/' + word + '?rel=/r/RelatedTo&filter=/c/en'

        # Send the GET request to the API
        response = requests.get(query_url)

        # Parse the JSON response
        json_response = response.json()

        # Extract the related words and their weights from the JSON response
        related_words_and_weights = {}
        for edge in json_response['edges']:
            if edge['start']['language'] == 'en' and self.strip_article(edge['start']['label'].lower()) != word:
                related_word = self.strip_article(edge['start']['label'].lower())
                weight = edge['weight']
                if related_word not in related_words_and_weights.keys():
                    related_words_and_weights[related_word] = weight
            elif edge['end']['language'] == 'en' and self.strip_article(edge['end']['label'].lower()) != word:
                related_word = self.strip_article(edge['end']['label'].lower())
                weight = edge['weight']
                if related_word not in related_words_and_weights.keys():
                    related_words_and_weights[related_word] = weight

        return jsonify(related_words_and_weights)
