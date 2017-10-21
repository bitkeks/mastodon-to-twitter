#!/usr/bin/env python3

import os
import html
import json
import re
from collections import namedtuple
from pprint import pprint
from time import sleep

from mastodon import Mastodon
import twitter as Twitter


config = None
with open('config.json', 'r') as fh:
    config = json.loads(fh.read(),
        object_hook=lambda d: namedtuple('config', d.keys())(*d.values()))


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
        if toot['visibility'] != 'public' or \
                len(toot['mentions']) > 0 or \
                toot['reblog']:
            # Only mirror my own public statements
            continue

        # Strip all HTML tags from content
        content = re.sub('<[^<]+?>', '', toot['content'])

        # Fetch the toot URL
        url = "{}".format(toot['url'][8:])

        # Take first two tags of post to add to the post
        tag = ""
        for item in toot['tags'][:2]:
            new_tag = item['name']
            tag += " #{}".format(new_tag)

        # Build the tweet
        if len(content) + len(url) <= 140:
            tweet = "{content} {url}".format(content=content, url=url)
        else:
            tweet = content[:140 - len(tag) - len(url) - 3]
            tweet += "… {tag} {url}".format(tag=tag, url=url)

        latest_toots.append((toot['id'], tweet))


    tweets = twitter.GetUserTimeline(user_id=twitter_id)

    latest_tweeted_toot = 0
    mstdn_url = config.mastodon.user_base_url
    latest_tweeted_toot = None
    for tweet in tweets:
        for url in tweet.urls:
            expanded = url.expanded_url

            prefix_len = 8  # https://
            if mstdn_url in expanded:
                if expanded.startswith("http://"):
                    prefix_len = 7

                # int in Mstdn < 2, str in Mstdn => 2
                latest_tweeted_toot = expanded[prefix_len + len(mstdn_url):]

        if latest_tweeted_toot:
            break


    not_mirrored = []
    for toot_id, toot in latest_toots:
        if toot_id == latest_tweeted_toot:
            print("Found anchor at toot {}.".format(toot_id))
            break
        else:
            not_mirrored.append(toot)

    if len(latest_toots) == len(not_mirrored):
        print("Did not find a toot-tweet-anchor.")
    else:
        print("Going to tweet {} toots.".format(len(not_mirrored)))


    for tweet in reversed(not_mirrored):
        tweet = html.unescape(tweet)
        twitter.PostUpdate(tweet)
        print("Tweeting: {}".format(tweet))

    sleep(config.interval_minutes * 60)
