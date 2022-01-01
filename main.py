'''
main.py
----------
Matthew Chatham, Miguel Ferreira
December, 2021

Given a company's landing page on Glassdoor and an output filename, scrape the
following information about each employee review:

Review date
Employee position
Employee location
Employee status (current/former)
Review title
Pros text
Cons text
Advice to mgmttext
Overall rating
'''

import time
import pandas as pd
from argparse import ArgumentParser
import argparse
import logging
import logging.config
from selenium import webdriver as wd
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
import selenium
import numpy as np
from schema import SCHEMA
import json
import urllib
from datetime import datetime as dt

start = time.time()

DEFAULT_URL = ('https://www.glassdoor.com/Overview/Working-at-Google-EI_IE9079.11,17.htm')

parser = ArgumentParser()
parser.add_argument('-u', '--url',
                    help='URL of the company\'s Glassdoor landing page.',
                    default=DEFAULT_URL)
parser.add_argument('-f', '--file', default='glassdoor_ratings.csv',
                    help='Output file.')
parser.add_argument('--headless', action='store_true',
                    help='Run Chrome in headless mode.')
parser.add_argument('--username', help='Email address used to sign in to GD.')
parser.add_argument('-p', '--password', help='Password to sign in to GD.')
parser.add_argument('-c', '--credentials', help='Credentials file')
parser.add_argument('-l', '--limit', default=25,
                    action='store', type=int, help='Max reviews to scrape')
parser.add_argument('--start_from_url', action='store_true',
                    help='Start scraping from the passed URL.')
parser.add_argument(
    '--max_date', help='Latest review date to scrape.\
    Only use this option with --start_from_url.\
    You also must have sorted Glassdoor reviews ASCENDING by date.',
    type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"))
parser.add_argument(
    '--min_date', help='Earliest review date to scrape.\
    Only use this option with --start_from_url.\
    You also must have sorted Glassdoor reviews DESCENDING by date.',
    type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"))
args = parser.parse_args()

if not args.start_from_url and (args.max_date or args.min_date):
    raise Exception(
        'Invalid argument combination:\
        No starting url passed, but max/min date specified.'
    )
elif args.max_date and args.min_date:
    raise Exception(
        'Invalid argument combination:\
        Both min_date and max_date specified.'
    )

if args.credentials:
    with open(args.credentials) as f:
        d = json.loads(f.read())
        args.username = d['username']
        args.password = d['password']
else:
    try:
        with open('secret.json') as f:
            d = json.loads(f.read())
            args.username = d['username']
            args.password = d['password']
    except FileNotFoundError:
        msg = 'Please provide Glassdoor credentials.\
        Credentials can be provided as a secret.json file in the working\
        directory, or passed at the command line using the --username and\
        --password flags.'
        raise Exception(msg)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(lineno)d\
    :%(filename)s(%(process)d) - %(message)s')
ch.setFormatter(formatter)

logging.getLogger('selenium').setLevel(logging.CRITICAL)
logging.getLogger('selenium').setLevel(logging.CRITICAL)


def scrape(field, review, author):

    def scrape_date(review):
        try:
            date_time_str = author.text.split('-')[0].strip()
            date_time_obj = dt.strptime(date_time_str, '%b %d, %Y')
            res = date_time_obj
        except Exception:
            logger.warning('Failed to scrape review date')
            res = "N/A"
        return res

    def scrape_emp_title(review):
        if 'Anonymous Employee' not in review.text:
            try:
                res = author.find_element(By.CLASS_NAME, 'authorJobTitle').text.split('-')[1].strip()
            except Exception:
                logger.warning('Failed to scrape employee_title')
                res = "N/A"
        else:
            res = "Anonymous"
        return res

    def scrape_location(author):
        try:
            res =  author.find_element(By.XPATH, './/span[@class="authorLocation"]').text.strip()
        except Exception:
            logger.warning('Failed to scrape employee_location')
            res = "N/A"
        return res

    def scrape_status(review):
        try:
            res = review.find_element(By.XPATH, './/div[@class="gdReview"]/div[1]/div[1]/span').text.strip().split(',')[0]
        except Exception:
            logger.warning('Failed to scrape employee_status')
            res = "N/A"
        return res

    def scrape_rev_title(review):
        return review.find_element(By.CLASS_NAME, 'reviewLink').text.strip('"')

    def expand_show_more(section):
        try:
            more_link = section.find_element(By.CLASS_NAME, 'v2__EIReviewDetailsV2__continueReading')
            more_link.click()
            time.sleep(2)
        except Exception:
            pass

    def scrape_pros(review):
        try:
            pros = review.find_element(By.CSS_SELECTOR, 'span[data-test="pros"]')
            res = pros.text.replace("\n", " ").strip()
        except Exception:
            res = np.nan
        return res

    def scrape_cons(review):
        try:
            cons = review.find_element(By.CSS_SELECTOR, 'span[data-test="cons"]')
            res = cons.text.replace("\n", " ").strip()
        except Exception:
            res = np.nan
        return res

    def scrape_advice(review):
        # skiping for now (not working)
        #try:
        #    advice_container = review.find_element(By.CLASS_NAME, 'gdReview')
        #    expand_show_more(advice_container)
        #    advice = advice_container.find_element(By.XPATH, './/span[@data-test="advice-management"]')
        #    res = advice.text.replace("\n", "")
        #except Exception:
        #    res = np.nan
        #return res
        return "N/A"

    def scrape_overall_rating(review):
        try:
            ratings = review.find_element(By.CLASS_NAME, 'ratingNumber')
            res = float(ratings.text[:3])
        except Exception:
            res = np.nan
        return res

    funcs = [
        scrape_date,
        scrape_emp_title,
        scrape_location,
        scrape_status,
        scrape_rev_title,
        scrape_pros,
        scrape_cons,
        scrape_advice,
        scrape_overall_rating
    ]

    fdict = dict((s, f) for (s, f) in zip(SCHEMA, funcs))

    return fdict[field](review)


def extract_from_page():

    def is_featured(review):
        try:
            review.find_element(By.CLASS_NAME, 'featuredFlag')
            return True
        except selenium.common.exceptions.NoSuchElementException:
            return False

    def extract_review(review):
        try:
            author = review.find_element(By.CLASS_NAME, 'authorInfo')
        except:
            return None # Account for reviews that have been blocked
        res = {}
        # import pdb;pdb.set_trace()
        for field in SCHEMA:
            res[field] = scrape(field, review, author)

        assert set(res.keys()) == set(SCHEMA)
        return res

    logger.info(f'Extracting reviews from page {page[0]}')

    res = pd.DataFrame([], columns=SCHEMA)

    reviews = browser.find_elements(By.CLASS_NAME, 'empReview')
    logger.info(f'Found {len(reviews)} reviews on page {page[0]}')
    
    # refresh page if failed to load properly, else terminate the search
    if len(reviews) < 1:
        browser.refresh()
        time.sleep(5)
        reviews = browser.find_elements(By.CLASS_NAME, 'empReview')
        logger.info(f'Found {len(reviews)} reviews on page {page[0]}')
        if len(reviews) < 1:
            valid_page[0] = False # make sure page is populated

    for review in reviews:
        if not is_featured(review):
            data = extract_review(review)
            if data != None:
                logger.info(f'Scraped data for "{data["review_title"]}"\
    ({data["date"]})')
                res.loc[idx[0]] = data
            else:
                logger.info('Discarding a blocked review')
        else:
            logger.info('Discarding a featured review')
        idx[0] = idx[0] + 1

    if args.max_date and \
        (pd.to_datetime(res['date']).max() > args.max_date) or \
            args.min_date and \
            (pd.to_datetime(res['date']).min() < args.min_date):
        logger.info('Date limit reached, ending process')
        date_limit_reached[0] = True

    return res


def more_pages():
    try:
        current = browser.find_element(By.CLASS_NAME, 'selected')
        pages = browser.find_element(By.CLASS_NAME, 'pageContainer').text.split()
        if int(pages[-1]) != int(current.text):
            return True
        else:
            return False
    except selenium.common.exceptions.NoSuchElementException:
        return False


def go_to_next_page():
    logger.info(f'Going to page {page[0] + 1}')
    next_ = browser.find_element(By.CLASS_NAME, 'nextButton')
    ActionChains(browser).click(next_).perform()
    time.sleep(5) # wait for ads to load
    page[0] = page[0] + 1


def no_reviews():
    return False
    # TODO: Find a company with no reviews to test on


def navigate_to_reviews():
    logger.info('Navigating to company reviews')

    browser.get(args.url)
    time.sleep(1)

    if no_reviews():
        logger.info('No reviews to scrape. Bailing!')
        return False

    reviews_cell =  browser.find_element(By.XPATH, '//a[@data-label="Reviews"]')
    reviews_path = reviews_cell.get_attribute('href')
    
    browser.get(reviews_path)
    time.sleep(1)
    return True


def sign_in():
    logger.info(f'Signing in to {args.username}')

    url = 'https://www.glassdoor.com/profile/login_input.htm'
    browser.get(url)

    email_field = browser.find_element(By.NAME,'username')
    password_field = browser.find_element(By.NAME, 'password')
    submit_btn = browser.find_element(By.XPATH, '//button[@type="submit"]')

    email_field.send_keys(args.username)
    password_field.send_keys(args.password)
    submit_btn.click()

    time.sleep(3)
    browser.get(args.url)

def accept_cookies():
    logger.info('Accepting cookies')
    accept_cookies_btn = browser.find_element(By.ID, 'onetrust-accept-btn-handler')
    accept_cookies_btn.click()
    time.sleep(2)

def get_browser():
    logger.info('Configuring browser')
    chrome_options = wd.ChromeOptions()
    if args.headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('window-size=1920x1080')
    chrome_options.add_argument('log-level=3')
    browser = wd.Chrome(options=chrome_options)
    return browser


def get_current_page():
    logger.info('Getting current page number')
    current = browser.find_element(By.CLASS_NAME, 'selected')
    return int(current.text)


def verify_date_sorting():
    logger.info('Date limit specified, verifying date sorting')
    ascending = urllib.parse.parse_qs(
        args.url)['sort.ascending'] == ['true']

    if args.min_date and ascending:
        raise Exception(
            'min_date required reviews to be sorted DESCENDING by date.')
    elif args.max_date and not ascending:
        raise Exception(
            'max_date requires reviews to be sorted ASCENDING by date.')


browser = get_browser()
page = [1]
idx = [0]
date_limit_reached = [False]
valid_page = [True]


def main():

    logger.info(f'Scraping up to {args.limit} reviews.')

    res = pd.DataFrame([], columns=SCHEMA)

    sign_in()

    if not args.start_from_url:
        reviews_exist = navigate_to_reviews()
        if not reviews_exist:
            return
    elif args.max_date or args.min_date:
        verify_date_sorting()
        browser.get(args.url)
        page[0] = get_current_page()
        logger.info(f'Starting from page {page[0]:,}.')
        time.sleep(1)
    else:
        browser.get(args.url)
        page[0] = get_current_page()
        logger.info(f'Starting from page {page[0]:,}.')
        time.sleep(1)

    accept_cookies()

    reviews_df = extract_from_page()
    res = res.append(reviews_df)

    while more_pages() and\
            len(res) < args.limit and\
            not date_limit_reached[0] and\
                valid_page[0]:
        go_to_next_page()
        try:
            reviews_df = extract_from_page()
            res = res.append(reviews_df)
        except:
            break

    logger.info(f'Writing {len(res)} reviews to file {args.file}')
    res.to_csv(args.file, index=False, encoding='utf-8')

    end = time.time()
    logger.info(f'Finished in {end - start} seconds')


if __name__ == '__main__':
    main()
