#!/usr/bin/env python3
"""
Helper script for TagFetcher Krita plugin
This script runs in a separate Python process with curl_cffi installed
"""

import sys
import json
import traceback
import os
from urllib.parse import unquote
from bs4 import BeautifulSoup
from curl_cffi import requests

def normalize_tag(tag):
    """Normalize tag by decoding URL encoding and converting underscores to spaces"""
    if not isinstance(tag, str):
        return ""
    # Decode URL-encoded characters (%28 -> '(', etc)
    tag = unquote(tag)
    # Convert underscores to spaces
    tag = tag.replace('_', ' ')
    return tag

def fetch_tags(site, solo_required=False, unwanted_tags=None):
    """
    Fetch random tags from specified site
    
    Args:
        site: The site to fetch from ('e621' or 'danbooru')
        solo_required: If True, only return posts with 'solo' tag
        unwanted_tags: List of tags to exclude (should already be normalized)
        
    Returns:
        JSON string with tags by category (with spaces instead of underscores)
    """
    if unwanted_tags is None:
        unwanted_tags = []
        
    # Make sure site is valid
    if site not in ["e621", "danbooru"]:
        return json.dumps({"error": f"Invalid site: {site}"})
        
    # Set URL based on site
    url = "https://danbooru.donmai.us/posts/random" if site == "danbooru" else "https://e621.net/posts/random"
        
    # Maximum number of attempts
    max_attempts = 10

    for attempt in range(max_attempts):
        try:
            # Use curl_cffi with browser impersonation and add the gw=seen cookie
            cookies = {"gw": "seen"} if site == "e621" else {}
            
            response = requests.get(
                url, 
                impersonate="chrome", 
                allow_redirects=True,
                cookies=cookies,
                timeout=10  # Add timeout to prevent hanging
            )
            
            if not response.ok:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Define selectors based on site
            if site == "danbooru":
                category_selectors = {
                    'artist': '.artist-tag-list li a.search-tag',
                    'copyright': '.copyright-tag-list li a.search-tag',
                    'character': '.character-tag-list li a.search-tag', 
                    'general': '.general-tag-list li a.search-tag'
                }
            else:  # e621
                category_selectors = {
                    'artist': '.tag-list.artist-tag-list .tag-list-item',
                    'copyright': '.tag-list.copyright-tag-list .tag-list-item',
                    'character': '.tag-list.character-tag-list .tag-list-item',
                    'species': '.tag-list.species-tag-list .tag-list-item',
                    'general': '.tag-list.general-tag-list .tag-list-item',
                    'meta': '.tag-list.meta-tag-list .tag-list-item'
                }
                
            # Extract all tags for solo check
            all_tags = []
            for category, selector in category_selectors.items():
                tag_elements = soup.select(selector)
                tags = []
                
                for tag_element in tag_elements:
                    try:
                        if site == "e621":
                            tag = tag_element.get('data-name', '').strip()
                            if not tag:
                                tag = tag_element.find(class_='tag-list-name')
                                if tag:
                                    tag = tag.get_text().strip()
                        else:  # Danbooru
                            tag = tag_element.text.strip()
                        
                        if tag:
                            tag = normalize_tag(tag)
                            if tag not in unwanted_tags:
                                tags.append(tag)
                                all_tags.append(tag)
                    except Exception:
                        continue
                
            # Check solo requirement if needed
            if solo_required:
                if 'solo' not in all_tags or any(x in all_tags for x in ['duo', 'group']):
                    continue
            
            # Collect tags by category
            tags_by_category = {}
            
            for category, selector in category_selectors.items():
                if site == "danbooru" and category == 'species':
                    continue
                    
                tag_elements = soup.select(selector)
                tags = []
                
                for tag_element in tag_elements:
                    try:
                        if site == "e621":
                            tag = tag_element.get('data-name', '').strip()
                            if not tag:
                                tag = tag_element.find(class_='tag-list-name')
                                if tag:
                                    tag = tag.get_text().strip()
                        else:  # Danbooru
                            tag = tag_element.text.strip()
                        
                        if tag:
                            tag = normalize_tag(tag)
                            if tag not in unwanted_tags:
                                tags.append(tag)
                    except Exception:
                        continue
                
                tags_by_category[category] = tags
            
            # Return tags in JSON format
            if any(tags for tags in tags_by_category.values()):
                return json.dumps({"tags": tags_by_category})
            
        except Exception:
            continue
    
    return json.dumps({"error": "Failed to get valid tags after all attempts"})

if __name__ == "__main__":
    try:
        # Handle Windows console encoding issues
        if sys.platform == "win32":
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
        if len(sys.argv) < 2:
            print(json.dumps({"error": "Missing site parameter"}))
            sys.exit(1)
            
        site = sys.argv[1]
        solo_required = len(sys.argv) > 2 and sys.argv[2].lower() == "true"
        unwanted_tags = [normalize_tag(tag) for tag in sys.argv[3].split(",")] if len(sys.argv) > 3 and sys.argv[3] else []
        
        result = fetch_tags(site, solo_required, unwanted_tags)
        print(result)
    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        print(json.dumps({"error": f"An unexpected error occurred: {error_msg}", "traceback": tb}))
        sys.exit(1)