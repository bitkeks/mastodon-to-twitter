#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mastodon 2.0 to Twitter Mirrorbot
Copyright 2017 by Dominik Pataky <dom@netdecorator.org>

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

from mastodon import Mastodon
import twitter as Twitter


config = None
with open('config.json', 'r') as fh:
    config = json.loads(fh.read(),
        object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))
TWITTER_CHARS = 140

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

while 1:
    toots = mastodon.account_statuses(mastodon_account_id)

    latest_toots = []
    for toot in toots:
        if (toot['visibility'] != 'public' or       # Skip non-public Toots
                len(toot['mentions']) > 0 or        # Skip replies
                toot['reblog']):                    # Skip reblogs/boosts
            continue

        content = toot['content']

        # Filter out all URLs in the Toot since they break the Twitter char
        # limit unpredictably
        collected_external_links = []
        m = re.finditer('href="(https?\:\/\/[^"]*)"', content)
        for match in m:
            link = match.group(1)
            if "/tags/" in link:
                continue
            collected_external_links.append(link)

        # Strip all HTML tags from content
        content = re.sub('<[^<]+?>', '', toot['content'])

        # Unescape HTML entities in content
        # This means, that e.g. a Toot "Hi, I'm a bot" is escaped as
        # "Hi, I&apos;m a bot". Unescaping this text reconstructs the
        # original string "I'm"
        content = html.unescape(content)
        for link in collected_external_links:
            content = content.replace(link, "")

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
        if len(content) + len(url) <= TWITTER_CHARS:
            # Content + URL are fitting in one Tweet
            tweet = "{content} {url}".format(content=content, url=url)
        else:
            # Calculate snipped of content plus all other text parts
            tweet = content[:TWITTER_CHARS - len(tag) - len(url) - 3]
            if tweet.endswith(" "):
                # Remove spaces between last word and "…"
                tweet = tweet.strip()
            tweet += "… {tag} {url}".format(tag=tag, url=url)

        latest_toots.append((toot['id'], tweet))

    tweets = twitter.GetUserTimeline(user_id=twitter_id)

    latest_tweeted_toot = None
    mstdn_url = config.mastodon.user_base_url

    # Iterate over the latest Tweets to find the latest tweeted Toot
    # Cannot be the latest only, since we want to skip e.g. Retweets
    for tweet in tweets:
        for url in tweet.urls:
            expanded = url.expanded_url

            prefix_len = 8  # https://
            if mstdn_url in expanded:
                # Mastodon URL found in Tweet
                if expanded.startswith("http://"):
                    prefix_len = 7

                # int in Mstdn < 2, str in Mstdn => 2
                latest_tweeted_toot = expanded[prefix_len + len(mstdn_url):]

        if latest_tweeted_toot:
            # Latest tweeted Toot was found
            break

    not_mirrored = []
    for toot_id, toot in latest_toots:
        if toot_id == latest_tweeted_toot:
            print("Found anchor at toot {}.".format(toot_id))
            break
        else:
            not_mirrored.append(toot)

    # Check if all public Toots are going to be mirrored
    if len(latest_toots) == len(not_mirrored):
        print("Did not find a toot-tweet-anchor.")
    else:
        # Only a part of the latest public Toots is going to be Tweeted
        print("Going to tweet {} toots.".format(len(not_mirrored)))

    # Post actual tweets
    for tweet in reversed(not_mirrored):
        try:
            twitter.PostUpdate(tweet)
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

