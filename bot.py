#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mas2tter - the Mastodon 2.0 to Twitter Mirrorbot

Copyright 2017, 2018 by Dominik Pataky <dev@bitkeks.eu>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import html
import json
import logging
import re
from collections import namedtuple
from time import sleep

from bs4 import BeautifulSoup
from mastodon import Mastodon, StreamListener, MastodonMalformedEventError
import twitter as Twitter

logger = logging.getLogger("Mas2tter")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

if not os.path.exists("config.json"):
    exit("config.json does not exist")
config = None
with open('config.json', 'r') as fh:
    config = json.loads(fh.read(),
        object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))
TWITTER_CHARS = 280

mastodon = Mastodon(
    client_id = config.mastodon.client_key,
    client_secret = config.mastodon.client_secret,
    access_token = config.mastodon.access_token,
    api_base_url = config.mastodon.api_base_url
)

twitter = Twitter.Api(
    consumer_key = config.twitter.consumer_key,
    consumer_secret = config.twitter.consumer_secret,
    access_token_key = config.twitter.access_token,
    access_token_secret = config.twitter.access_token_secret
)

creds = mastodon.account_verify_credentials()
mastodon_account_id = creds.id

twitter_user = twitter.VerifyCredentials()
twitter_id = twitter_user.id


class StatusReceiver(StreamListener):
    """StreamListener child class with handlers for received stream events.
    """

    def __init__(self, mastodon_account_id):
        super().__init__()
        self.mastodon_account_id = mastodon_account_id
        logger.info("Set mastodon_account_id to %s" % mastodon_account_id)
        logger.info("StatusReceiver started")

    def on_update(self, toot):
        # Filter out certain Toots

        # Don't handle Toots from other people
        if toot.account.id != self.mastodon_account_id:
            logger.info("Received Toot from other account, ignored")
            return

        # Skip private Toots
        if toot.visibility not in ['public', 'unlisted']:
            logger.info("Own Toot was filtered out due to visibility filter")
            return

        # Skip replies
        if toot.in_reply_to_id != None:
            logger.info("Own Toot was filtered out due to mention/in_reply_to_id filter")
            return

        # Skip reblogs/boosts
        if toot.reblog:
            logger.info("Own Toot was filtered out due to reblog filter")
            return

        # Unescape HTML entities in content
        # This means, that e.g. a Toot "Hi, I'm a bot" is escaped as
        # "Hi, I&apos;m a bot". Unescaping this text reconstructs the
        # original string "I'm"
        content = html.unescape(toot['content'])

        # Pass the resulting HTML to BeautifulSoup and extract all text
        content = BeautifulSoup(content, 'html.parser')
        content = content.get_text()

        # Filter @username@twitter.com mentions
        content = content.replace("@twitter.com", "")

        # Fetch the toot URL
        url = "{}".format(toot['url'][8:])

        # Take first x tags of post to add to the post
        # Uses tags_to_append form the config to count how many tags to use
        toot_tags = reversed(toot['tags'])  # Tags are sorted, but in reverse
        tag = ""
        for idx, item in enumerate(toot_tags):
            new_tag = item['name']
            tag += " #{}".format(new_tag)
            if idx+1 == config.tags_to_append:
                break

        # Build the tweet
        tweets = []
        if config.link_to_mastodon:
            # Append a link back to the Toot
            if len(content) + len(url) <= TWITTER_CHARS:
                # Content + URL are fitting in one Tweet
                tweet = "{content} {url}".format(content=content, url=url)
            else:
                # Calculate snipped of content plus all other text parts
                tweet = content[:TWITTER_CHARS - len(tag) - len(url) - 4]
                # Remove spaces between last word and "…"
                tweet = tweet.strip()
                tweet += "… {tag} {url}".format(tag=tag, url=url)
            tweets.append(tweet)
        else:
            # Don't link back to Mastodon
            if len(content) > TWITTER_CHARS:
                # The Toot has more characters than Twitter allows

                # Get the length, calculate the half and split the words
                length = len(content)
                middle = length/2
                tokens = content.split(" ")

                # Mastodon allows 500 characters, Twitter 280: two Tweets are enough
                first_tweet = ""
                second_tweet = ""
                for idx, token in enumerate(tokens):
                    # Test, if an additional word would exceed the first half
                    if len("{} {}".format(first_tweet, token)) > middle:
                        # Construct the second Tweet from the remaining words and stop
                        second_tweet = " ".join(tokens[idx:])
                        break
                    # If it still fits, append the word to the first Tweet
                    first_tweet = "{} {}".format(first_tweet, token)

                tweets = [first_tweet, second_tweet]
            else:
                tweet = "{content}".format(content=content)
                tweets.append(tweet)

        # Tweet
        logger.info("Tweeting: %s" % tweets)
        process_tweets(tweets)

    def on_notification(self, notification):
        logger.info("Received notification, ignored")

    def on_abort(self, err):
        logger.error("on_abort: %s" % err)

    def on_delete(self, status_id):
        logger.info("Received status deletion event for Toot %s, ignored" % status_id)

    def handle_heartbeat(self):
        logger.info("Received heartbeat")
        mastodon.account_verify_credentials()


def process_tweets(tweets):
    """Post one or multiple Tweets to twitter.com
    """
    # To be used for threads with two or more related Tweets
    latest_id = None

    for tweet in tweets:
        try:
            # Post single Tweet
            status = twitter.PostUpdate(
                tweet,
                in_reply_to_status_id=latest_id,
                auto_populate_reply_metadata=False
            )
            # and save the Tweet ID
            latest_id = status.id
        except Twitter.error.TwitterError as ex:
            logger.critical("Error posting tweet: '{tweet}' (length {length}). {error}"\
                .format(tweet=tweet, length=len(tweet), error=ex))
            exit(1)
        logger.debug(status)
        logger.info("Tweeted: {}".format(tweet.encode('utf-8')))


receiver = StatusReceiver(mastodon_account_id)

while 1:
    # Handle exceptions thrown by the StreamListener
    try:
        # Run listener
        mastodon.stream_user(receiver, run_async=False)
    except MastodonMalformedEventError as ex:
        logger.error("Catched MastodonMalformedEventError!")

