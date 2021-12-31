#!/usr/bin/env bash
python main.py --headless --url "https://www.glassdoor.com/Overview/Working-at-Google-EI_IE9079.11,17.htm" --limit 50 -f google_reviews.csv
python main.py --headless --url "https://www.glassdoor.com/Overview/Working-at-Amazon-EI_IE6036.11,17.htm" --limit 50 -f amazon_reviews.csv
python main.py --headless --url "https://www.glassdoor.com/Overview/Working-at-Apple-EI_IE1138.11,16.htm" --limit 50 -f apple_reviews.csv
python main.py --headless --url "https://www.glassdoor.com/facebook" --limit 50 -f facebook_reviews.csv
