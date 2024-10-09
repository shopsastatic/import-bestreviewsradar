from flask import Flask, request, jsonify, render_template
from selectorlib import Extractor
import requests
import json
import time
import re
import unidecode
import random
from requests.auth import HTTPBasicAuth


WORDPRESS_URL = "http://temp5.local/wp-json/wp/v2/source-product"
WORDPRESS_USER = "adminheadless"
WORDPRESS_PASSWORD = "I3lZlae6lAL6hGeM30HM"


USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:45.0) Gecko/20100101 Firefox/45.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/604.3.5 (KHTML, like Gecko) Version/11.0.1 Safari/604.3.5',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15 Version/13.0.4'
]

def slugify(text):
    text = unidecode.unidecode(text)
    
    text = re.sub(r'[\s_]+', '-', text)
    
    text = re.sub(r'[^\w\-]', '', text)
    
    return text.lower()

def upload_image_from_url(image_url, new_filename=None):
    image_response = requests.get(image_url)
    
    if image_response.status_code == 200:
        original_filename = image_url.split("/")[-1]
        
        content_type = image_response.headers['Content-Type']
        
        filename = new_filename if new_filename else original_filename
        
        extension = original_filename.split('.')[-1]
        if '.' not in filename:
            filename = f"{filename}.{extension}"
        
        files = {
            'file': (filename, image_response.content, content_type)
        }

        media_response = requests.post(
            "http://temp5.local/wp-json/wp/v2/media",
            auth=HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_PASSWORD),
            files=files 
        )

        if media_response.status_code == 201:
            media_data = media_response.json()
            return media_data['id']
        else:
            print(f"Failed to upload image: {media_response.json()}")
            return None
    else:
        print(f"Failed to download image: {image_response.status_code}")
        return None


def post_to_wordpress(data):
    headers = {
        'Content-Type': 'application/json',
    }

    image_id = upload_image_from_url(data.get('images', ''), slugify(data.get('name', '')))
    
    post_data = {
        'title': data.get('name', 'Unnamed Product'),
        'featured_media': image_id,
        'content': '',
        'excerpt': data.get('short_description', ''),
        'status': 'publish',
        'categories': data.get('categoryID', []),
        'acf': {
            "general": {
                "global_id": "",
                "brand": data.get('brand', '')
            },
            'price': {
                "sale_price": data.get('price', ''),
                "origin_price": "",
                "discount": ""
            },
            "additionals": {
                "specifications": "",
                "features": ""
            },
            "description": data.get('short_description', ''),
            'actions': [
                {
                    'acf_fc_layout': 'item',
                    'stores': "Amazon",
                    'actions_link': data.get('url', ''),
                },
            ]
        }
    }

    response = requests.post(
        WORDPRESS_URL,
        auth=HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_PASSWORD),
        headers=headers,
        json=post_data
    )

    if response.status_code == 201:
        print(f"Post created successfully for {data.get('prodID', 'Unknown Product')}")
    else:
        print(f"Failed to create post. Status Code: {response.status_code}, Response: {response.text}")

current_user_agent_index = 0

def get_current_user_agent():
    global current_user_agent_index
    return USER_AGENTS[current_user_agent_index]

def switch_to_next_user_agent():
    global current_user_agent_index
    current_user_agent_index = (current_user_agent_index + 1) % len(USER_AGENTS)
    print(f"Switched to another User-Agent")

import re

def clean_price(price):
    price = re.sub(r'\s+', '', price)
    
    price = price.replace('$', '').replace(',', '')
    
    match = re.match(r'(\d+)(\d{2})$', price)
    if match:
        price_value = float(f"{match.group(1)}.{match.group(2)}")
    else:
        try:
            price_value = float(price)
        except ValueError:
            return "Invalid price format"
    
    return f"${price_value:,.2f}"


app = Flask(__name__)

first_extractor = Extractor.from_yaml_file('category_selectors.yml')
final_extractor = Extractor.from_yaml_file('selectors.yml')

def scrape(url, extractor, retries=3):  
    attempt = 0
    while attempt < retries:
        attempt += 1
        headers = {
            'dnt': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': get_current_user_agent(),
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'referer': 'https://www.amazon.com/',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        }

        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 503:
                time.sleep(1)
                switch_to_next_user_agent()
                continue
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL {url}: {e}")
            return None, f"Error fetching page: {e}"

        if "To discuss automated access to Amazon data" in r.text:
            print(f"Blocked by Amazon for URL: {url} on attempt {attempt}, switching to next user-agent...")
            switch_to_next_user_agent()
            continue

        data = extractor.extract(r.text)
        if data:
            return data, "OK"
        else:
            print(f"Extraction failed for {url}")
            return None, "Extraction failed or returned no data."

    return None, "Blocked by Amazon after all retries."

def write_to_jsonl(data, filename="output.jsonl"):
    with open(filename, 'a') as outfile:
        json.dump(data, outfile)
        outfile.write('\n')

def get_or_create_category(category_name, wp_url, auth, parent_id=None):
    response = requests.get(f"{wp_url}/wp-json/wp/v2/categories", params={'search': category_name}, auth=auth)
    
    if response.status_code == 200:
        categories = response.json()

        if len(categories) > 0:
            return categories[0]['id']
        
        else:
            create_response = requests.post(
                f"{wp_url}/wp-json/wp/v2/categories",
                json={'name': category_name, 'parent': parent_id} if parent_id else {'name': category_name},
                auth=auth
            )

            if create_response.status_code == 201:
                created_category = create_response.json()
                return created_category['id']
            elif create_response.status_code == 400 and create_response.json().get('code') == 'term_exists':
                return create_response.json()['data']['term_id']
            else:
                print(f"Failed to create category: {create_response.json()}")
                return None
    else:
        print(f"Failed to retrieve categories: {response.json()}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_urls():
    urls = request.form['url_input']
    url_list = urls.splitlines()
    results = []

    for url in url_list:
        if url.strip():
            initial_data, status = scrape(url.strip(), first_extractor)

            if initial_data:
                if 'links' in initial_data:
                    for partial_url in initial_data['links']:
                        full_url = f"https://www.amazon.com{partial_url}"
                        full_url = full_url.split('?')[0]
                        final_data, final_status = scrape(full_url, final_extractor)
                        category_ids = []
                        parent_id = None

                        if final_data:
                            final_data['prodID'] = full_url.split("/dp/")[1].split("/")[0]
                            final_data['url'] = full_url

                            if 'brand' in final_data and final_data['brand']:
                                pattern1 = r"Brand:\s*(.*)"
                                pattern2 = r"Visit the\s*(.*)\s*Store"
                                
                                match1 = re.match(pattern1, final_data['brand'])
                                match2 = re.match(pattern2, final_data['brand'])
                                
                                if match1:
                                    final_data['brand'] = match1.group(1).strip()
                                elif match2:
                                    final_data['brand'] = match2.group(1).strip()
                                else:
                                    final_data['brand'] = final_data['brand'].strip()

                            if 'category' in final_data and final_data['category']:
                                for category_name in final_data['category']:
                                    category_id = get_or_create_category(category_name, "http://temp5.local", HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_PASSWORD), parent_id)
                                    
                                    if category_id:
                                        category_ids.append(category_id)
                                        parent_id = category_id
                                        final_data['categoryID'] = category_ids
                            
                            if 'rating' in final_data and final_data['rating']:
                                final_data['rating'] = final_data['rating'].replace('out of 5 stars', '').strip()
                            
                            if 'price' in final_data and final_data['price']:
                                final_data['price'] = clean_price(final_data['price'])
                            
                            if 'images' in final_data and final_data['images']:
                                final_data['images'] = final_data['images'].split('\":')[0].split('{"')[1]

                            if 'number_of_reviews' in final_data and final_data['number_of_reviews']:
                                final_data['number_of_reviews'] = final_data['number_of_reviews'].replace('ratings', '').strip()
                                final_data['number_of_reviews'] = final_data['number_of_reviews'].replace('rating', '').strip()

                            if 'short_description' in final_data and final_data['short_description']:
                                short_desc = final_data['short_description']

                                if isinstance(short_desc, list):
                                    random.shuffle(short_desc)
                                    final_data['short_description'] = "\n".join(short_desc)
                                else:
                                    final_data['short_description'] = short_desc.strip()

                            write_to_jsonl(final_data)
                            results.append({
                                'url': full_url,
                                'status': final_status,
                                'success': final_status == "OK"
                            })
                        else:
                            results.append({
                                'url': full_url,
                                'status': final_status,
                                'success': False
                            })
                else:
                    print(f"Key 'links' not found in initial data for URL: {url}")
                    results.append({
                        'url': url,
                        'status': "Key 'links' not found",
                        'success': False
                    })
            else:
                print(f"Failed to scrape {url}, status: {status}")
                results.append({
                    'url': url,
                    'status': status,
                    'success': False
                })

    return jsonify(results=results)

if __name__ == '__main__':
    app.run(debug=True)
