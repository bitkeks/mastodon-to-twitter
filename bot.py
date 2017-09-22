#!/usr/bin/env python3

from mastodon import Mastodon
from pprint import pprint
import os
import json
import re
import twitter as Twitter

EXTRA_TAGS = 2
mastodon_config = None
twitter_config = None

with open('config.json', 'r') as fh:
    config = json.loads(fh.read())
    mastodon_config = config['mastodon']
    twitter_config = config['twitter']
    EXTRA_TAGS = config["extra_tags"]

mastodon = Mastodon(
    client_id = mastodon_config['client_key'],
    client_secret = mastodon_config['client_secret'],
    access_token = mastodon_config['access_token'],
    api_base_url = mastodon_config['api_base_url']
)

creds = mastodon.account_verify_credentials()
account_id = creds["id"]
statuses = mastodon.account_statuses(account_id)

latest_toots = []

for status in statuses:
    if status['visibility'] != 'public' or \
            len(status['mentions']) > 0 or \
            status['reblog']:
        # Only mirror my own public statements
        continue

    # Strip all HTML tags from content
    content = re.sub('<[^<]+?>', '', status['content'])

    # Fetch the toot ID
    toot_id = str(status['id'])

    # Take first two tags of post to add to the post
    tag = ""
    for item in status['tags'][:EXTRA_TAGS]:
        new_tag = item['name']
        tag += " #{}".format(new_tag)

    # Build the tweet
    if len(content) + len(str(toot_id)) + 17 <= 140:
        tweet = "{content} [Mirrored Toot {id}]".format(content=content, id=toot_id)
    else:
        tweet = content[:140 - len(tag) - len(str(toot_id)) - 17]
        tweet += "{tag} [Mirrored Toot {id}]".format(tag=tag, id=toot_id)

    latest_toots.append((toot_id, tweet))


twitter = Twitter.Api(
    consumer_key=twitter_config['consumer_key'],
    consumer_secret=twitter_config['consumer_secret'],
    access_token_key=twitter_config['access_token'],
    access_token_secret=twitter_config['access_token_secret']
)

twitter_user = twitter.VerifyCredentials()
twitter_id = twitter_user.id
twitter_statuses = twitter.GetUserTimeline(user_id=twitter_id)

latest_tweet = twitter_statuses[0].text
latest_mirrored_toot_id = None
m = re.search('^.* \[Mirrored Toot (\d*)\]$', latest_tweet)
if m:
    latest_mirrored_toot_id = m.group(1)

not_mirrored = []
for toot_id, toot in latest_toots:
    print(toot_id, latest_mirrored_toot_id)
    if toot_id == latest_mirrored_toot_id:
        print("Found anchor at toot {}.".format(toot_id))
        break
    else:
        not_mirrored.append(toot)

if len(latest_toots) == len(not_mirrored):
    print("Did not find a toot-tweet-anchor.")
else:
    print("Going to tweet {} toots.".format(len(not_mirrored)))


for tweet in reversed(not_mirrored):
    print(twitter.PostUpdate(tweet))
    print("Tweeting: {}".format(tweet))
