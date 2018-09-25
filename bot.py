#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mas2bird - the Mastodon 2.0 to Twitter Mirrorbot

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
import re
from collections import namedtuple
from time import sleep

from bs4 import BeautifulSoup
from mastodon import Mastodon
import twitter as Twitter


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
mastodon_account_id = creds["id"]

twitter_user = twitter.VerifyCredentials()
twitter_id = twitter_user.id

if not os.path.exists('.sync_id'):
    print("There's no .sync_id file containing your latest synced Toot, creating one")
    with open('.sync_id', 'w') as fh:
        fh.write("0")

while 1:
    toots = mastodon.account_statuses(mastodon_account_id)

    latest_toots = []
    for toot in toots:
        if (toot['visibility'] not in ['public', 'unlisted'] or     # Skip private Toots
                len(toot['mentions']) > 0 or                        # Skip replies
                toot['reblog']):                                    # Skip reblogs/boosts
            continue

        # Unescape HTML entities in content
        # This means, that e.g. a Toot "Hi, I'm a bot" is escaped as
        # "Hi, I&apos;m a bot". Unescaping this text reconstructs the
        # original string "I'm"
        content = html.unescape(toot['content'])

        # Pass the resulting HTML to BeautifulSoup and extract all text
        content = BeautifulSoup(content, 'html.parser')
        content = content.get_text()

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
        if config.link_to_mastodon:
            # Append a link back to the Toot
            if len(content) + len(url) <= TWITTER_CHARS:
                # Content + URL are fitting in one Tweet
                tweet = "{content} {url}".format(content=content, url=url)
            else:
                # Calculate snipped of content plus all other text parts
                tweet = content[:TWITTER_CHARS - len(tag) - len(url) - 3]
                # Remove spaces between last word and "…"
                tweet = tweet.strip()
                tweet += "… {tag} {url}".format(tag=tag, url=url)
        else:
            # Don't link back to Mastodon
            banner = " (via Mas2Bird)"
            if len(content) + len(banner) > TWITTER_CHARS:
                content = content[:TWITTER_CHARS - len(banner) - 3]
                content = content.strip() + "…"
            tweet = "{content} {banner}".format(content=content, banner=banner)

        latest_toots.append((toot['id'], tweet))

    with open('.sync_id', 'r') as fh:
        latest_synced_toot = fh.read().strip()

    # Find the list slice of not-yet-synced latest Toots
    not_mirrored = []
    for toot_id, tweet in latest_toots:
        if str(toot_id) == latest_synced_toot:
            # Found the last synced Toot
            break
        else:
            # Append to list to be tweeted
            not_mirrored.append((toot_id, tweet))

    print("Going to tweet {} toots.".format(len(not_mirrored)))

    # Post actual tweets
    for tweet in reversed(not_mirrored):
        try:
            # Post single Tweet
            status = twitter.PostUpdate(tweet[1])

            # Update cache if no exception was thrown
            with open('.sync_id', 'w') as fh:
                fh.write("{toot_id}".format(toot_id=tweet[0]))

        except Twitter.error.TwitterError as ex:
            print("Error posting tweet: '{tweet}' (length {length}). {error}"\
                .format(tweet=tweet, length=len(tweet), error=ex))
            exit(1)
        print("Tweeting: {}".format(tweet).encode('utf-8'))

    # Sleep and show next update timer
    sleep_seconds = config.interval_minutes * 60
    for i in range(sleep_seconds):
        print("\rUpdate in {:4} seconds.".format(sleep_seconds - i), end="\r")
        sleep(1)

